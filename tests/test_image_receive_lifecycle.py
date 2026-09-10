"""Image transport regressions. Only ephemeral loopback peers; no microscope."""
from concurrent.futures import CancelledError
from contextlib import contextmanager
import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import cv2
import numpy as np
import pytest

from jgb.conn.pubsub import PubSubManager
from zemrpc.zem.conn.img_receiver import ImageTransferError, ImgReceiver
from zemrpc.zem.conn.protocol import EnumCmd, ImageResp, Request, RespPacket
from zemrpc.zem.models import ZemException
from zemrpc.zem.zem_rpc_device import GetImagePubSub, ZemRpcDevice


@contextmanager
def image_peer(payload=b"", *, eof=False):
    connected, disconnected, stop = (threading.Event() for _ in range(3))
    errors = []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(0.1)

        def serve():
            try:
                while not stop.is_set():
                    try:
                        client, _ = listener.accept()
                        break
                    except socket.timeout:
                        continue
                else:
                    return
                with client:
                    connected.set()
                    if payload:
                        # Fragment the image across several writes.
                        for offset in range(0, len(payload), 257):
                            client.sendall(payload[offset:offset + 257])
                    if eof:
                        client.shutdown(socket.SHUT_WR)
                    client.settimeout(0.1)
                    while not stop.is_set():
                        try:
                            if not client.recv(1):
                                disconnected.set()
                                break
                        except socket.timeout:
                            continue
                        except ConnectionResetError:
                            disconnected.set()
                            break
            except Exception as error:
                errors.append(error)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield SimpleNamespace(port=listener.getsockname()[1], connected=connected, disconnected=disconnected)
        finally:
            stop.set()
            worker.join(2)
            assert not worker.is_alive()
            assert not errors


def receiver_for(peer, callback=None, *, req="Snap", depth=7, size=64, newbee=False):
    receiver = ImgReceiver(ImageResp(req, "test", "127.0.0.1", peer.port, depth, size, size), callback, newbee)
    receiver.timeout = 0.25
    return receiver


def response_for(peer, *, size=64):
    return RespPacket(f"$Snap:ZEM20 Image service:127.0.0.1:{peer.port},7,{size},{size},97F8%".encode())


def request_with_budget(milliseconds=300):
    class TimedRequest(Request):
        @property
        def timeout_ms(self):
            return milliseconds
    return TimedRequest(EnumCmd.Snap, b"")


def fake_device(dispatch):
    return SimpleNamespace(_check_cmd_permission=Mock(), m=SimpleNamespace(is_newbee=lambda: False), rws=SimpleNamespace(pubsub_send=dispatch))


@pytest.mark.parametrize("payload", [b"", b"\x01\x00"])
def test_silent_or_partial_peer_obeys_deadline_and_closes_socket(payload):
    with image_peer(payload) as peer:
        callback = Mock()
        receiver = receiver_for(peer, callback)
        started = time.monotonic()
        worker = threading.Thread(target=receiver, daemon=True)
        worker.start()
        worker.join(1.5)
        # On the old implementation this assertion fails while the peer is
        # still open; fixture cleanup then closes it to release the old worker.
        assert not worker.is_alive(), "receive deadline did not terminate the thread"
        assert time.monotonic() - started < 1.5
        assert isinstance(receiver.error, TimeoutError)
        assert receiver.img is None
        assert receiver.error.image_transfer_details["received_bytes"] == len(payload)
        assert receiver.error.image_transfer_details["expected_bytes"] == 64 * 64 * 2
        callback.assert_called_once_with(receiver)
        assert peer.disconnected.wait(1)


@pytest.mark.parametrize("depth,dtype,newbee", [(0, np.uint8, False), (7, np.uint16, False), (7, np.uint16, True)])
def test_complete_raw_frame_preserves_pixels_and_byte_order(depth, dtype, newbee):
    pixels = np.arange(64 * 64, dtype=dtype).reshape(64, 64)
    payload = pixels.byteswap().tobytes() if newbee else pixels.tobytes()
    with image_peer(payload) as peer:
        receiver = receiver_for(peer, depth=depth, newbee=newbee)
        receiver.timeout = 2
        receiver()
        assert receiver.error is None
        np.testing.assert_array_equal(receiver.img, pixels)
        assert receiver.img.dtype == dtype
        assert peer.disconnected.wait(1)


@pytest.mark.parametrize("payload,error_type", [(b"", ConnectionError), (b"\x01\x00", ImageTransferError)])
def test_premature_eof_reports_error_instead_of_a_none_success(payload, error_type):
    with image_peer(payload, eof=True) as peer:
        receiver = receiver_for(peer)
        receiver()
        assert isinstance(receiver.error, error_type)
        assert receiver.received_bytes == len(payload)
        assert receiver.img is None
        assert peer.disconnected.wait(1)


@pytest.mark.parametrize("req,depth,dtype,channels", [("Snap", 7, np.uint16, 1), ("GetNavImg", 8, np.uint8, 1), ("GetNavImg", 24, np.uint8, 3)])
def test_legacy_encoded_fallback_preserves_shape_type_and_pixels(req, depth, dtype, channels):
    shape = (64, 64) if channels == 1 else (64, 64, channels)
    pixels = np.full(shape, 29, dtype=dtype)
    ok, encoded = cv2.imencode(".png", pixels)
    assert ok
    with image_peer(encoded.tobytes(), eof=True) as peer:
        receiver = receiver_for(peer, req=req, depth=depth)
        receiver()
        assert receiver.error is None
        np.testing.assert_array_equal(receiver.img, pixels)


def test_encoded_image_with_wrong_dimensions_is_rejected():
    _, encoded = cv2.imencode(".png", np.zeros((32, 32), dtype=np.uint8))
    with image_peer(encoded.tobytes(), eof=True) as peer:
        receiver = receiver_for(peer, req="GetNavImg", depth=8)
        receiver()
        assert isinstance(receiver.error, ImageTransferError)
        assert receiver.img is None


def test_unavailable_port_is_bounded_and_socket_is_closed():
    # Reserve a bound, non-listening local port so no other service can use it.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        receiver = receiver_for(SimpleNamespace(port=reserved.getsockname()[1]))
        receiver()
        # Windows may wait for the connect deadline instead of reporting RST.
        assert isinstance(receiver.error, (ConnectionError, TimeoutError))
        assert receiver.error.image_transfer_details["phase"] == "connect"
        assert receiver._socket is None


def test_connect_failure_preserves_the_error_and_closes_the_socket():
    receiver = receiver_for(SimpleNamespace(port=1))
    refused = ConnectionRefusedError("peer refused the image connection")
    with patch("zemrpc.zem.conn.img_receiver.socket.socket") as constructor:
        client = constructor.return_value.__enter__.return_value
        client.connect.side_effect = refused
        receiver()
        constructor.return_value.__exit__.assert_called_once()
    assert receiver.error is refused
    assert receiver._socket is None
    assert receiver.error.image_transfer_details["phase"] == "connect"


def test_cancel_before_connection_never_connects():
    receiver = receiver_for(SimpleNamespace(port=1))
    receiver.cancel()
    with patch("zemrpc.zem.conn.img_receiver.socket.socket") as constructor:
        receiver()
        constructor.return_value.__enter__.return_value.connect.assert_not_called()
    assert isinstance(receiver.error, CancelledError)


def test_cancel_during_receive_unblocks_reader_and_peer():
    with image_peer() as peer:
        callback = Mock()
        receiver = receiver_for(peer, callback)
        receiver.timeout = 10
        worker = threading.Thread(target=receiver, daemon=True)
        worker.start()
        assert peer.connected.wait(1)
        receiver.cancel()
        receiver.cancel()
        worker.join(1)
        assert not worker.is_alive()
        assert isinstance(receiver.error, CancelledError)
        callback.assert_called_once_with(receiver)
        assert peer.disconnected.wait(1)


@pytest.mark.parametrize("payload,eof,error_type", [(b"", False, TimeoutError), (b"\x01\x00", False, TimeoutError), (b"", True, ConnectionError), (b"\x01\x00", True, ImageTransferError)])
def test_sdk_propagates_transfer_error_and_sends_snap_only_once(payload, eof, error_type):
    with image_peer(payload, eof=eof) as peer:
        manager = PubSubManager()
        subscriptions = []

        def dispatch(subscription):
            subscriptions.append(subscription)
            manager.sub(subscription)
            assert manager.pub(response_for(peer))
            return manager.wait(subscription)

        with pytest.raises(error_type) as raised:
            ZemRpcDevice.pubsub_send(fake_device(dispatch), request_with_budget())
        assert len(subscriptions) == 1
        assert not manager._pubsubs
        assert not subscriptions[0]._receiver_thread.is_alive()
        assert raised.value.image_transfer_details["received_bytes"] == len(payload)
        assert peer.disconnected.wait(1)


def test_sdk_returns_complete_image_and_removes_subscription():
    with image_peer(b"\x34\x12" * (64 * 64)) as peer:
        manager = PubSubManager()
        subscriptions = []

        def dispatch(subscription):
            subscriptions.append(subscription)
            manager.sub(subscription)
            assert manager.pub(response_for(peer))
            return manager.wait(subscription)

        result = ZemRpcDevice.pubsub_send(fake_device(dispatch), request_with_budget(2000))
        assert result.extra["img"].shape == (64, 64)
        assert np.all(result.extra["img"] == 0x1234)
        assert not manager._pubsubs
        assert not subscriptions[0]._receiver_thread.is_alive()


def test_duplicate_service_response_only_starts_one_receiver_and_keeps_original_result():
    with image_peer() as peer:
        subscription = GetImagePubSub(request_with_budget(), False, timeout=200)
        response = response_for(peer)
        assert subscription.pub(response)
        assert peer.connected.wait(1)
        original_receiver = subscription._receiver
        assert subscription.pub(response_for(peer))
        assert subscription._receiver is original_receiver
        assert subscription.result is response
        subscription.wait()
        assert subscription.is_timeout
        assert not subscription._receiver_thread.is_alive()
        # A late completion after timeout cannot turn the failed result into success.
        subscription.img_received_handler(SimpleNamespace(img=np.zeros((64, 64)), error=None))
        assert "img" not in response.extra
        assert isinstance(subscription.error, TimeoutError)


def test_udp_delay_consumes_the_same_deadline_as_tcp_receive():
    with image_peer() as peer:
        subscription = GetImagePubSub(request_with_budget(), False, timeout=1000)
        started = time.monotonic()
        threading.Event().wait(0.65)
        subscription.pub(response_for(peer))
        subscription.wait()
        assert subscription.is_timeout
        assert time.monotonic() - started < 1.5, "TCP must not get a fresh one-second budget"
        assert peer.disconnected.wait(1)


def test_cancelled_subscription_cleans_up_and_ignores_late_udp_response():
    subscription = GetImagePubSub(request_with_budget(), False, timeout=1000)
    manager = PubSubManager()
    manager.sub(subscription)
    subscription.cancel()
    assert subscription.pub(response_for(SimpleNamespace(port=1)))
    manager.wait(subscription)
    assert isinstance(subscription.error, CancelledError)
    assert subscription._receiver is None
    assert not manager._pubsubs


def test_cancel_while_sdk_waits_propagates_after_cleanup():
    with image_peer() as peer:
        manager = PubSubManager()
        subscriptions = []

        def dispatch(subscription):
            subscriptions.append(subscription)
            manager.sub(subscription)
            manager.pub(response_for(peer))
            assert peer.connected.wait(1)
            subscription.cancel()
            return manager.wait(subscription)

        with pytest.raises(CancelledError):
            ZemRpcDevice.pubsub_send(fake_device(dispatch), request_with_budget(2000))
        assert not manager._pubsubs
        assert not subscriptions[0]._receiver_thread.is_alive()


@pytest.mark.parametrize("reply,error_type", [(b"$Snap:garbage,97F8%", ImageTransferError), (b"$Snap:Error Code:4,97F8%", ZemException)])
def test_bad_service_response_or_device_rejection_finishes_without_reception_or_retry(reply, error_type):
    manager = PubSubManager()
    subscriptions = []

    def dispatch(subscription):
        subscriptions.append(subscription)
        manager.sub(subscription)
        manager.pub(RespPacket(reply))
        return manager.wait(subscription)

    with pytest.raises(error_type):
        ZemRpcDevice.pubsub_send(fake_device(dispatch), request_with_budget())
    assert len(subscriptions) == 1
    assert subscriptions[0]._receiver_thread is None
    assert not manager._pubsubs


def test_no_udp_response_times_out_without_starting_a_receiver():
    manager = PubSubManager()
    subscription = GetImagePubSub(request_with_budget(), False, timeout=50)
    manager.sub(subscription)
    with pytest.raises(TimeoutError) as raised:
        manager.wait(subscription)
    assert raised.value.image_transfer_details["phase"] == "response"
    assert not manager._pubsubs
    assert subscription._receiver_thread is None


def test_cancelled_navigation_is_not_retried():
    calls = []
    manager = PubSubManager()

    def dispatch(subscription):
        calls.append(subscription)
        manager.sub(subscription)
        subscription.cancel()
        return manager.wait(subscription)

    with pytest.raises(CancelledError):
        ZemRpcDevice.pubsub_send(fake_device(dispatch), req=Request(EnumCmd.GetNavImg, b""))
    assert len(calls) == 1
    assert not manager._pubsubs


def test_unrelated_response_does_not_consume_the_image_subscription():
    subscription = GetImagePubSub(request_with_budget(), False, timeout=1000)
    assert not subscription.pub(RespPacket(b"$GetOB:15627,749E%"))
    assert subscription.result is None
    assert not subscription.event.is_set()
    subscription.cancel()


def test_receiver_start_failure_is_terminal_and_leaves_no_subscription():
    manager = PubSubManager()

    def dispatch(subscription):
        manager.sub(subscription)
        with patch("zemrpc.zem.zem_rpc_device.threading.Thread.start", side_effect=RuntimeError("cannot start thread")):
            manager.pub(response_for(SimpleNamespace(port=1)))
        return manager.wait(subscription)

    with pytest.raises(ImageTransferError, match="cannot start thread"):
        ZemRpcDevice.pubsub_send(fake_device(dispatch), request_with_budget())
    assert not manager._pubsubs
