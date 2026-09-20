from types import SimpleNamespace
from unittest.mock import Mock
import inspect

import pytest

from zemrpc.zem.conn.protocol import EnumCmd, Request
from zemrpc.zem.zem_rpc_device import ZemRpcDevice


def test_device_defaults_to_three_times_protocol_timeout():
    default = inspect.signature(ZemRpcDevice.__init__).parameters["timeout_multiple"].default
    assert default == 3
    assert ZemRpcDevice._scaled_timeout_ms(object(), 100) == 300


def test_pubsub_timeout_uses_configured_multiplier():
    captured = []

    def dispatch(subscription):
        captured.append(subscription.timeout)
        subscription.result = object()
        subscription.notify_done()
        return subscription.result

    device = SimpleNamespace(
        timeout_multiple=3,
        _check_cmd_permission=Mock(),
        rws=SimpleNamespace(pubsub_send=dispatch),
    )
    request = Request(EnumCmd.ZemRpc, b"")

    ZemRpcDevice.pubsub_send(device, request)
    device.timeout_multiple = 1.5
    ZemRpcDevice.pubsub_send(device, request)

    assert captured == [0.3, 0.15]


def test_long_protocol_timeouts_are_not_multiplied():
    device = SimpleNamespace(timeout_multiple=3)

    assert ZemRpcDevice._scaled_timeout_ms(device, EnumCmd.StatusCheck.timeout) == 6000
    assert ZemRpcDevice._scaled_timeout_ms(device, EnumCmd.SetSECV.timeout) == EnumCmd.SetSECV.timeout
    assert ZemRpcDevice._scaled_timeout_ms(device, EnumCmd.SetHV.timeout) == EnumCmd.SetHV.timeout
    assert ZemRpcDevice._scaled_timeout_ms(device, EnumCmd.GetNavImg.timeout) == EnumCmd.GetNavImg.timeout
    assert ZemRpcDevice._scaled_timeout_ms(device, EnumCmd.Snap.timeout) == EnumCmd.Snap.timeout


@pytest.mark.parametrize("timeout_multiple", [0, -1, float("inf"), True])
def test_timeout_multiple_must_be_positive_and_finite(timeout_multiple):
    device = object.__new__(ZemRpcDevice)

    with pytest.raises(ValueError):
        device.set_timeout_multiple(timeout_multiple)


def test_handshake_timeout_does_not_follow_command_multiplier():
    from unittest.mock import patch
    from zemrpc.zem import ip_util
    deadlines = []
    device = SimpleNamespace(m=SimpleNamespace(addr=("127.0.0.1", 61557)), timeout_multiple=30, _iface_by_device={}, _prepare_comm=Mock(), _handshake_probe=lambda ip, addr, deadline: deadlines.append(deadline) or [])
    with patch.object(ip_util, "_get_all_local_ips", return_value=["192.168.1.2"]), patch("zemrpc.zem.zem_rpc_device.time.time", return_value=100):
        ZemRpcDevice.handshake(device)
    assert deadlines == [100.4, 100 + EnumCmd.Handshake.timeout / 1000]
