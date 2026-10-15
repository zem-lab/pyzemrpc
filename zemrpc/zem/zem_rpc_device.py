#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

"""
ZEM RPC Device Communication Module

This module provides the main interface for communicating with ZEM (Zeiss Electron Microscope)
devices through RPC protocols. It handles device discovery, configuration, imaging operations,
and stage control functionality.

Classes:
    HandshakePubSub: Handles handshake protocol communication
    GetImagePubSub: Manages image acquisition and reception
    ZemModel: Data model for ZEM device state and configuration
    ZemRpcDevice: Main device interface for ZEM operations
"""

import cv2
import json
import time
import socket
import numpy as np
import threading
import math
from concurrent.futures import CancelledError
from loguru import logger
from pydantic import Field
from typing import List, Tuple
from numbers import Real
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random, before_sleep_log

from jgb.util import cv_util, req_util, time_util, os_util
from jgb.util.dds_util import AppTreeNode, AppTreeNodeRequiredMixin
from jgb.conn.rw_service import ReadWriteService
from jgb.conn.pubsub import PubSub
from jgb.conn.udp_socket import UdpSocket, UdpPacket

from zemrpc import app_cfg
from zemrpc.zem.software_info import SoftwareInfo
from zemrpc.zem.context import ctx
from zemrpc.zem.conn.img_receiver import ImgReceiver, ImageTransferError
from zemrpc.zem.models import EnumBeamSize, FieldWithLoc, HvInfo, ImageMeta, MetaItem, NavParam, ScanInfo, SnapArgs, StagePos, ZemException, BseInfo, EnumCmdLevel
from zemrpc.zem.conn.protocol import EnumAutofocusStatus, EnumCmd, EnumHvStatus, EnumStageStatus, EnumVideoStatus, ProtocolBuilder, ProtocolParser, Request, RespPacket, patch_request_callback
from zemrpc.zem.conn.rpc_protocol import JsonRpcBuilder, RespProtocolNg, RpcSnapResp, RpcStatusResp
from zemrpc.zem import zem_util as zu
from zemrpc.zem import ip_util


def _retry_pubsub_request(retry_state):
    """Acquisition/navigation writes have no request ID; never replay an ambiguous result."""
    request = retry_state.args[1] if len(retry_state.args) > 1 else retry_state.kwargs["req"]
    return retry_state.outcome.failed and request.cmd not in {EnumCmd.Snap, EnumCmd.SetRoiNav, EnumCmd.SetStagePos, EnumCmd.SetStageMotionParameters, EnumCmd.GetStageMotionParameters} and not isinstance(retry_state.outcome.exception(), CancelledError)


class HandshakePubSub(PubSub):
    """
    Publisher-Subscriber for handling device handshake operations.

    This class manages the handshake protocol between the client and ZEM device
    to establish communication and discover available devices on the network.
    """

    def __init__(self, request, **kwargs):
        """
        Initialize handshake publisher-subscriber.

        Args:
            request: The handshake request to be sent
            **kwargs: Additional arguments passed to parent PubSub class
        """
        super().__init__(request, **kwargs)
        self.result = []

    def pub(self, resp: RespPacket):
        """
        Process incoming handshake response packets.

        Args:
            resp (RespPacket): Response packet from the device

        Returns:
            bool: True if packet was handled, False otherwise
        """
        if EnumCmd.HandshakeResp.name != resp.get_pubsub_key():
            return False

        self.result.append(resp)
        return True

    def timeout_handler(self):
        """Handle timeout events for handshake operations."""
        # 握手没有超时异常
        ...


class GetImagePubSub(PubSub):
    """
    Publisher-Subscriber for handling image acquisition operations.

    This class manages the complete image acquisition workflow including
    triggering image capture, receiving image data, and processing the
    received image through a separate thread.
    """

    def __init__(self, request, is_newbee, **kwargs):
        """
        Initialize image acquisition publisher-subscriber.

        Args:
            request: The image request to be sent
            is_newbee (bool): Flag indicating if device is a newer model
            **kwargs: Additional arguments passed to parent PubSub class
        """
        super().__init__(request, **kwargs)
        self.is_newbee = is_newbee
        self.error = None
        self._deadline = time.monotonic() + self.timeout
        self._state_lock = threading.Lock()
        self._terminal = False
        self._receiver = None
        self._receiver_thread = None

    def _finish(self, error=None):
        # Caller owns _state_lock. A late/duplicate callback cannot overwrite a
        # timed-out request or publish into a later subscription with this key.
        if self._terminal:
            return
        self.error = error
        self.is_timeout = isinstance(error, TimeoutError)
        if error is not None:
            error.image_transfer_details = self._receiver.transfer_details() if self._receiver is not None else {"phase": "response", "received_bytes": 0, "expected_bytes": None}
            logger.warning(f"Image request failed: {type(error).__name__}: {error}; {error.image_transfer_details}")
        self._terminal = True
        self.notify_done()

    def cancel(self):
        with self._state_lock:
            self._canceled = True
            self._finish(CancelledError(f"{self.key} image reception cancelled"))
        self.close()

    def close(self):
        """Release local transport without issuing SnapCancel or retrying Snap."""
        with self._state_lock:
            receiver, worker = self._receiver, self._receiver_thread
        if receiver is not None:
            receiver.cancel()
        if worker is not None and worker.ident is not None and worker is not threading.current_thread():
            worker.join(timeout=1.0)
            if worker.is_alive():
                logger.warning(f"Image worker has not exited after local transport cancellation: {receiver.transfer_details()}")

    def wait(self):
        # Do not raise here: jgb's PubSubManager must remove the subscription
        # before timeout_handler / pubsub_send propagates the terminal error.
        while not self.event.is_set():
            with self._state_lock:
                remaining = self._deadline - time.monotonic()
                if self._canceled:
                    self._finish(CancelledError(f"{self.key} image reception cancelled"))
                elif remaining <= 0:
                    self._finish(TimeoutError(f"{self.key}命令超时"))
            self.event.wait(max(0.0, min(0.1, remaining)))
        self.close()

    def timeout_handler(self):
        if self.error is not None:
            raise self.error
        super().timeout_handler()

    def pub(self, packet: RespPacket):
        """
        Process incoming image response packets.

        Args:
            packet (RespPacket): Response packet containing image data or metadata

        Returns:
            bool: True if packet was handled, False otherwise
        """
        if packet.get_pubsub_key() != self.request.get_pubsub_key():
            return False

        with self._state_lock:
            if self._terminal or self.result is not None:
                return True
            if time.monotonic() >= self._deadline:
                self._finish(TimeoutError(f"{self.key}命令超时"))
                return True
            self.result = packet
            try:
                if packet.is_error() or packet.is_invalid_cmd():
                    self._finish()
                    return True
                img_resp = packet.parse_img_resp()
                if img_resp is None:
                    raise ImageTransferError(f"{self.key} invalid image service response: {packet}")
                self._receiver = ImgReceiver(img_resp, self.img_received_handler, self.is_newbee, deadline=self._deadline)
                self._receiver_thread = threading.Thread(target=self._receiver, name=f"{self.key}-image-receiver", daemon=True)
                self._receiver_thread.start()
            except Exception as error:
                if not isinstance(error, ImageTransferError):
                    failure = ImageTransferError(f"{self.key} cannot start image reception: {error}")
                    failure.__cause__ = error
                    error = failure
                self._finish(error)
        return True

    def img_received_handler(self, img_receiver: ImgReceiver):
        """
        Callback function called when image reception is complete.

        Args:
            img_receiver (ImgReceiver): The image receiver with completed image data
        """
        with self._state_lock:
            if self._terminal:
                return
            error = img_receiver.error
            if error is None and time.monotonic() >= self._deadline:
                error = TimeoutError(f"{self.key}命令超时")
            if error is None and img_receiver.img is None:
                error = ImageTransferError(f"{self.key} image receiver completed without an image")
            if error is None:
                self.result.extra["img"] = img_receiver.img
            self._finish(error)


class ZemModel(AppTreeNode):
    """
    Data model representing the current state and configuration of a ZEM device.

    This class maintains all the device parameters including hardware settings,
    stage position, scan configuration, and imaging parameters. It provides
    reactive updates through the context system when values change.

    Attributes:
        model (str): Device model identifier
        protocol_ng (RespProtocolNg): New generation protocol handler
        addr (Tuple[str, int]): Device network address (IP, port)
        ed_chanel (str): Electron detector channel name
        mag (float): Current magnification value
        beam_size (EnumBeamSize): Current electron beam size setting
        ob (int): Objective lens setting
        wd (float): Working distance in micrometers
        hv_info (HvInfo): High voltage information
        scan_info (ScanInfo): Scan configuration parameters
        nav_param (NavParam): Navigation parameters
        stage_pos (StagePos): Current stage position
    """

    model: str = Field(default="Unk")
    protocol_ng: RespProtocolNg = Field(default=None)
    addr: Tuple[str, int] = Field(default=("UNK", 61557))

    ed_chanel: str = Field(default="BSE", init=False)
    bse_cfg: BseInfo = Field(default=None, on_setattr=True)

    mag: float = Field(default=0, on_setattr=True)
    scan_relay_mask: int | None = Field(default=None, on_setattr=True)
    software: SoftwareInfo | None = Field(default=None, on_setattr=True)
    sn: str | None = Field(default=None, on_setattr=True)
    beam_size: EnumBeamSize = Field(default=EnumBeamSize.Unk, on_setattr=True)
    ob: int = Field(default=0, on_setattr=True)
    wd: float = Field(default=0, on_setattr=True)
    compress_a: float = Field(default=0.0, on_setattr=True)
    compress_b: float = Field(default=0.0, on_setattr=True)

    hv_info: HvInfo = Field(default=None, on_setattr=True)
    is_open_gun: bool = Field(default=False, on_setattr=True)

    scan_info: ScanInfo = Field(default=None, on_setattr=True)
    nav_param: NavParam = Field(default=None)
    stage_pos: StagePos = Field(default=None, on_setattr=True)

    def cmd_rcv(self, cmd: str):
        """Publish received command to context subscribers."""
        ctx.pub_computed_attr(self, "cmd_rcv", cmd)

    def cmd_send(self, cmd: str):
        """Publish sent command to context subscribers."""
        ctx.pub_computed_attr(self, "cmd_send", cmd)

    def data_rcv(self, data: bytes):
        """Publish received data to context subscribers."""
        ctx.pub_computed_attr(self, "data_rcv", data)

    def is_stage_pos_unit_pulse(self):
        """
        Check if stage position units are in pulses instead of micrometers.

        Returns:
            bool: True if stage uses pulse units (older ZEM18OLD model)
        """
        return self.model == "ZEM18OLD"

    def is_newbee(self):
        """
        Check if device is a newer model with updated protocols.

        Returns:
            bool: True if device is a newer model
        """
        return self.model in {"ZEM18", "ZEM18OLD", "ZEM15"}

    def to_img_meta(self, snap_args: SnapArgs):
        """
        Create image metadata from current device state.

        Args:
            snap_args: Snap arguments containing image acquisition settings

        Returns:
            ImageMeta: Complete metadata object for the acquired image
        """

        im = ImageMeta()
        im.set_kv(MetaItem.Model, self.model)
        im.set_kv(MetaItem.Date, time_util.now_str())
        im.set_kv(MetaItem.KV, self.hv_info.kv)
        im.set_kv(MetaItem.AccVoltage, self.hv_info.acc_v)
        im.set_kv(MetaItem.WD, self.wd)
        im.set_kv(MetaItem.OB, self.ob)
        im.set_kv(MetaItem.Detector, self.ed_chanel)
        im.set_kv(MetaItem.AvgLenth, snap_args.pixel_avg)
        im.set_kv(MetaItem.Magnification, self.mag)
        im.set_kv(MetaItem.FieldSize, self.scan_info.scan_um)
        im.set_kv(MetaItem.FieldRotation, self.scan_info.rot_degree)
        im.set_kv(MetaItem.PixelSize, self.scan_info.scan_um / snap_args.size.width)
        im.set_kv(MetaItem.FirmwareVersion, "UNK")
        im.set_kv(MetaItem.Pressure, "***")
        im.set_kv(MetaItem.Position, self.stage_pos)
        im.set_kv(MetaItem.PyZemRpc, f"PYZEMRPC-{app_cfg.version}")

        return im.m

    def field_with_loc(self):
        """
        Create a field location object combining scan info and stage position.

        Returns:
            FieldWithLoc: Object containing current field location data
        """
        return FieldWithLoc(scan_info=self.scan_info, pos=self.stage_pos)


class ZemRpcDevice(AppTreeNodeRequiredMixin):
    """
    Main interface for controlling and communicating with ZEM devices.

    This class provides high-level methods for all ZEM device operations including:
    - Device discovery and connection management
    - Image acquisition (simple snap and RPC-based)
    - Stage positioning and control
    - Optical parameter adjustment (magnification, beam size, etc.)
    - Autofocus operations
    - Navigation and scanning control

    The class handles protocol differences between device models and provides
    unified interface regardless of the underlying device version.
    """

    DEFAULT_TIMEOUT_MULTIPLE = 3
    LONG_TIMEOUT_THRESHOLD_MS = 10_000

    def __init__(self, name: str, timeout_multiple: Real = DEFAULT_TIMEOUT_MULTIPLE, **kwargs):
        """
        Initialize ZEM RPC device interface.

        Args:
            name (str): Device name identifier
            timeout_multiple (Real): Multiplier applied to all protocol command
                timeouts. Defaults to 3 for slower network conditions.
            **kwargs: Additional configuration options including parent node
        """
        self.name = name
        self.set_timeout_multiple(timeout_multiple)
        self.m = ZemModel(ctx=ctx, node_name="zem_rpc_device")
        self.n = ctx.add_node(self, parent=kwargs.pop("parent", None))

        # Initialize UDP socket for device communication
        # Use get_real_local_ip() to filter out virtual IPs like Clash Fake-IP (198.18.0.1)
        self.socket = UdpSocket(ctx, "zem_rpc_socket", parent=self.n, ip=ip_util.get_real_local_ip(), port=0)

        # Set up read-write service for packet handling
        self.rws = ReadWriteService[RespPacket](f"RWS-{self.m.node_name}", ctx, self.socket, self._do_framing, self._do_write)

        # Initialize protocol builders
        self.builder = ProtocolBuilder()
        self.parser = ProtocolParser()
        self.rpc_builder = JsonRpcBuilder()

        # Initialize work mode - default to BASIC level
        self._work_mode = EnumCmdLevel.BASIC

        # device addr -> local IP that successfully reached it during handshake
        self._iface_by_device: dict[Tuple[str, int], str] = {}

    def set_timeout_multiple(self, timeout_multiple: Real):
        """Set the multiplier applied to protocol command timeouts.

        A value of 1 restores the command timeout declared by ``EnumCmd``.
        The value must be a finite positive number.
        """
        self.timeout_multiple = timeout_multiple
        return self.timeout_multiple

    def set_timeout_multiplier(self, timeout_multiplier: Real):
        """Alias for :meth:`set_timeout_multiple`."""
        return self.set_timeout_multiple(timeout_multiplier)

    @property
    def timeout_multiple(self):
        return getattr(self, "_timeout_multiple", ZemRpcDevice.DEFAULT_TIMEOUT_MULTIPLE)

    @timeout_multiple.setter
    def timeout_multiple(self, timeout_multiple):
        if isinstance(timeout_multiple, bool) or not isinstance(timeout_multiple, Real) or not math.isfinite(timeout_multiple) or timeout_multiple <= 0:
            raise ValueError("timeout_multiple must be a finite positive number")
        self._timeout_multiple = timeout_multiple

    @property
    def timeout_multiplier(self):
        """Alias for the configured protocol timeout multiplier."""
        return self.timeout_multiple

    @timeout_multiplier.setter
    def timeout_multiplier(self, timeout_multiplier):
        self.set_timeout_multiple(timeout_multiplier)

    def _scaled_timeout_ms(self, timeout_ms):
        if timeout_ms >= ZemRpcDevice.LONG_TIMEOUT_THRESHOLD_MS:
            return timeout_ms
        return timeout_ms * getattr(self, "timeout_multiple", ZemRpcDevice.DEFAULT_TIMEOUT_MULTIPLE)

    def _resolve_local_ip_for_device(self, addr: Tuple[str, int]) -> str:
        if ip_util._is_loopback_ip(addr[0]):
            logger.debug(f"Use loopback interface for device {addr[0]}:{addr[1]}")
            return "127.0.0.1"
        if local_ip := self._iface_by_device.get(addr):
            logger.debug(f"Use handshake interface {local_ip} for device {addr[0]}:{addr[1]}")
            return local_ip
        # Subnet match only; do not use UDP connect() route probe — on multi-homed
        # Windows it may pick the default-route NIC (e.g. wired) while the device
        # replies on another interface (e.g. WiFi).
        return ip_util.get_real_local_ip(target_ip=addr[0])

    def _ensure_socket_bind(self, local_ip: str):
        """
        Bind the persistent UDP socket to local_ip.

        Must set m.ip BEFORE the first sock access; otherwise jgb lazy-init binds
        the wrong interface.
        """
        if self.socket._socket is None:
            self.socket.m.ip = local_ip
            self.socket.m.port = 0
            self.socket.init_socket()
            self.parser.buffer.clear()
            self.builder.ip, self.builder.port = self.socket.sock.getsockname()
            logger.debug(f"UDP socket opened on {self.builder.ip}:{self.builder.port}")
            return

        current_ip, _ = self.socket.sock.getsockname()
        if current_ip == local_ip:
            self.builder.ip, self.builder.port = self.socket.sock.getsockname()
            return

        logger.info(f"Rebind UDP socket from {current_ip} to {local_ip}")
        self.socket.rcv_worker.stop()

        # jgb SingleWorker.start() is a no-op when thread is not None, even
        # if the thread is dead.  Clear it so init_socket() can restart.
        self.socket.rcv_worker.thread = None
        self.socket.rcv_worker.exit_evt.clear()

        with self.socket.mutex:
            if self.socket._socket is not None:
                try:
                    self.socket._socket.close()
                except OSError:
                    pass
                self.socket._socket = None

        self.socket.m.ip = local_ip
        self.socket.m.port = 0
        self.socket.init_socket()
        self.parser.buffer.clear()
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()

    def disconnect(self):
        """Release the local UDP channel while idle; sends no device command.

        Callers must serialize this with RPC requests. update_remote_addr can
        reopen the same device instance after disconnecting.
        """
        self.socket.rcv_worker.stop()
        self.socket.rcv_worker.thread = None
        with self.socket.mutex:
            if self.socket._socket is not None:
                self.socket._socket.close()
                self.socket._socket = None
        self.parser.buffer.clear()
        self.m.addr = ("UNK", 0)
        self.m.software = None
        self.m.sn = None

    def _prepare_comm(self):
        """Ensure socket and builder use the interface that can reach the selected device."""
        if self.m.addr[0] == "UNK":
            return
        local_ip = self._resolve_local_ip_for_device(self.m.addr)
        self._ensure_socket_bind(local_ip)
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()

    def update_remote_addr(self, addr: Tuple[str, int]):
        """
        Update the remote device address.

        Args:
            addr (Tuple[str, int]): New device address (IP, port)
        """
        if self.m.addr != addr:
            self.m.software = None
            self.m.sn = None
        self.m.addr = addr
        self._prepare_comm()
        logger.debug(f"Remote device {addr[0]}:{addr[1]} via local {self.builder.ip}:{self.builder.port}")

    def build_handshake_request(self):
        """
        Build a handshake request packet for device discovery.

        Returns:
            Request: Handshake request packet ready to send
        """
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()
        return self.builder.build_handshake_request()

    def _handshake_probe(self, bind_ip: str, dest: Tuple[str, int], deadline: float) -> List[RespPacket]:
        """Send a handshake from bind_ip and collect HandshakeResp until deadline."""
        packets: List[RespPacket] = []
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(0.3)
            sock.bind((bind_ip, 0))

            local_ip, local_port = sock.getsockname()
            self.builder.ip, self.builder.port = local_ip, local_port
            req = self.builder.build_handshake_request()
            sock.sendto(req.data, dest)
            logger.debug(f"Handshake probe {bind_ip} -> {dest[0]}:{dest[1]} ({local_ip}:{local_port})")

            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                sock.settimeout(min(remaining, 0.3))
                try:
                    data, addr = sock.recvfrom(4096)
                except socket.timeout:
                    break
                except Exception:
                    break
                for packet_data in self.parser.append(addr, data):
                    resp = RespPacket(packet_data)
                    resp.extra["addr"] = addr
                    resp.extra["local_ip"] = local_ip
                    if resp.cmd == EnumCmd.HandshakeResp and not resp.is_error():
                        packets.append(resp)
        except Exception as e:
            logger.debug(f"Handshake on {bind_ip} failed: {e}")
        finally:
            if sock:
                sock.close()
        return packets

    def handshake(self):
        """
        Perform handshake with devices on the network.

        Broadcast on ALL local network interfaces to discover ZEM devices,
        regardless of which subnet they are connected to.

        On Windows, a UDP socket bound to a specific IP only broadcasts on
        that IP's network interface. To reach devices on multiple subnets
        (e.g. wired + WiFi), we create a temporary socket per interface,
        broadcast from each, and merge the results.

        UDP broadcast cannot reach 127.0.0.1, so localhost is probed by unicast.
        Scanning must not rewrite the callback address of the current target;
        if the selected device is 127.0.0.1, subsequent packets still embed
        127.0.0.1:<ephemeral-port>.

        Returns:
            List[Tuple[str, int]]: List of discovered device addresses (ip, port)
        """
        dest_port = self.m.addr[1] or 61557
        all_packets: List[RespPacket] = []

        try:
            # 本机方案：广播到不了回环，单独单播探测 127.0.0.1
            loopback_deadline = time.time() + 0.4
            all_packets.extend(self._handshake_probe("127.0.0.1", ("127.0.0.1", dest_port), loopback_deadline))

            all_ips = ip_util._get_all_local_ips()
            local_ips = []
            for ip in all_ips:
                if ip_util._is_loopback_ip(ip) or ip_util._is_clash_fake_ip(ip):
                    continue
                if ip_util._is_private_ip(ip):
                    local_ips.append(ip)

            if not local_ips:
                if not all_packets:
                    resp = self.send(self.build_handshake_request())
                    all_packets.extend(packet for packet in resp if not packet.is_error())
            else:
                deadline = time.time() + EnumCmd.Handshake.timeout / 1000
                for ip in local_ips:
                    all_packets.extend(self._handshake_probe(ip, ("<broadcast>", dest_port), deadline))

            seen = set()
            unique = []
            for pkt in all_packets:
                ipport = pkt.parse_ip_port()
                if ipport not in seen:
                    seen.add(ipport)
                    unique.append(pkt)
                    if local_ip := pkt.extra.get("local_ip"):
                        self._iface_by_device[ipport] = local_ip

            logger.info(f"Handshake found {len(unique)} device(s)")
            return [packet.parse_ip_port() for packet in unique]
        finally:
            # 扫描只更新可选目标，不得改写当前本机/已选设备的回包地址
            if self.m.addr[0] != "UNK":
                try:
                    self._prepare_comm()
                except Exception as e:
                    logger.debug(f"Restore comm after handshake failed: {e}")

    def video_play_on(self):
        """
        Start video streaming from the device.

        Returns:
            RespPacket: Device response to video play command
        """
        return self.pubsub_send(self.builder.build_video_play())

    def check_video_play(self):
        """
        Check current video streaming status.

        Returns:
            Video status information from the device
        """
        resp = self.pubsub_send(self.builder.build_is_video_alive())
        status = resp.parse_video_status()
        return status

    def is_video_playing(self):
        return self.check_video_play() == EnumVideoStatus.Running

    def snap_simple(self, snap_args: SnapArgs):
        """
        Acquire a single image using simple snap protocol.

        Args:
            snap_args (SnapArgs): Image acquisition parameters

        Returns:
            np.ndarray: Acquired image data
        """
        resp = self.send(self.builder.build_snap_simple(snap_args.pixel_avg, snap_args.size))
        return resp.extra["img"]

    def snap_rpc(self, width: int = 2048, height: int = 2048, pixel_avg: int = 7, frame_avg: int = 1):
        """
        Acquire image using RPC protocol with advanced parameters.

        Args:
            width (int): Image width in pixels
            height (int): Image height in pixels
            pixel_avg (int): Number of pixels to average
            frame_avg (int): Number of frames to average

        Returns:
            RpcSnapResp: Complete image acquisition response with metadata
        """
        data = self.zem_rpc(self.rpc_builder.snap(width, height, pixel_avg, frame_avg))
        return RpcSnapResp(**data)

    def status_rpc(self):
        """
        Check device status using RPC protocol.

        Returns:
            dict: Status information from the device
        """
        data = self.zem_rpc(self.rpc_builder.status())
        response = RpcStatusResp(**data)
        self.m.scan_relay_mask = response.scan_relay_mask
        self.m.software = response.software
        self.m.sn = response.sn
        return response

    def get_stage_motion_parameters(self, *, transport="jsonrpc", url=None):
        from zemrpc.zem.stage_motion_parameters import StageMotionJsonRpc
        if transport == "jsonrpc":
            return StageMotionJsonRpc(url or self.m.protocol_ng.url).read()
        if transport != "udp":
            raise ValueError("transport 仅支持 jsonrpc/udp")
        return self.send(self.builder.build_get_stage_motion_parameters()).parse_stage_motion_parameters()

    def set_stage_motion_parameters(self, axes, *, transport="jsonrpc", url=None):
        from zemrpc.zem.stage_motion_parameters import StageMotionJsonRpc, validate_axes
        axes = validate_axes(axes)
        self._check_cmd_permission(EnumCmd.SetStageMotionParameters)
        if transport == "jsonrpc":
            return StageMotionJsonRpc(url or self.m.protocol_ng.url).configure(axes)
        if transport != "udp":
            raise ValueError("transport 仅支持 jsonrpc/udp")
        return self.send(self.builder.build_set_stage_motion_parameters(axes)).parse_stage_motion_parameters(axes)

    def get_nav_param(self) -> NavParam:
        """
        Retrieve navigation parameters from the device.

        Returns:
            NavParam: Current navigation parameters including center coordinates
        """
        resp = self.send(self.builder.build_get_nav_para())
        param = resp.parse_nav_para()
        # Convert pulse units to micrometers for older devices
        if self.m.is_stage_pos_unit_pulse():
            param.cx = param.cx * zu.zem15_pulse2um
            param.cy = param.cy * zu.zem15_pulse2um
        self.m.nav_param = param
        return self.m.nav_param

    def get_nav_img(self) -> np.ndarray:
        """
        Acquire navigation overview image.

        Returns:
            np.ndarray: Navigation image with proper color channel conversion
        """
        resp = self.send(self.builder.build_get_nav_img())
        img = resp.extra["img"]
        if img is not None:
            h, w, c = cv_util.cv2_hwc(img)
            # Convert color formats for proper display
            if c == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            elif c == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    def get_software_info(self) -> SoftwareInfo | None:
        """Query the remote host version and build commit over UDP.

        Older servers that reject this command return None. Network errors propagate.
        """
        resp = self.send(self.builder.build_get_software_info())
        self.m.software = resp.parse_software_info()
        return self.m.software

    def get_sn(self) -> str | None:
        """Query the SN configured in the remote microscope over UDP.

        Older servers that reject this command return None. Network errors propagate.
        """
        resp = self.send(self.builder.build_get_sn())
        self.m.sn = resp.parse_sn()
        return self.m.sn

    def get_model(self) -> str:
        """
        Get device model information.

        Returns:
            str: Device model identifier
        """
        resp = self.send(self.builder.build_get_model())
        self.m.model = resp.parse_model()
        return self.m.model

    def get_protocol_ng(self) -> str:
        """
        Get new generation protocol information.

        Returns:
            str: Protocol NG configuration status
        """
        resp = self.send(self.builder.build_json_rpc(self.rpc_builder.get_protocol_ng()))
        ret = resp.parse_json_rpc()
        if ret.get("error", None):
            self.m.protocol_ng = RespProtocolNg()
        else:
            self.m.protocol_ng = RespProtocolNg(**ret["result"]).update_remote_host(self.m.addr[0])

    def get_hv(self) -> HvInfo:
        """
        Get high voltage information from the device.

        Returns:
            HvInfo: Current high voltage settings and status
        """
        resp = self.send(self.builder.build_get_hv())
        self.m.hv_info = resp.parse_hv()
        return self.m.hv_info

    def get_stage_pos(self) -> StagePos:
        """
        Get current stage position.

        Returns:
            StagePos: Current X, Y coordinates of the sample stage
        """
        resp = self.send(self.builder.build_get_stage_pos())
        self.m.stage_pos = resp.parse_stage_pos()
        return self.m.stage_pos

    def set_stage_pos(self, pos: StagePos):
        """
        Move stage to specified position.

        Args:
            pos (StagePos): Target position coordinates

        Returns:
            StagePos: Accepted target in micrometers, None if rejected. Not readback.
        """
        if not all(math.isfinite(v) for v in (pos.x, pos.y)):
            raise ValueError("Stage target must be finite")
        # Keep command intent separate from measured position and caller-owned data.
        target = StagePos(x=pos.x, y=pos.y)
        x, y = target.x, target.y
        if self.m.is_stage_pos_unit_pulse():
            x, y = round(x * zu.zem15_um2pulse), round(y * zu.zem15_um2pulse)

        resp = self.send(self.builder.build_set_stage_pos(x, y))
        if resp.is_ack_ok():
            return target
        return None

    def check_status(self) -> RespPacket:
        """
        Check current device status.

        Returns:
            RespPacket: Device status response packet
        """
        return self.send(self.builder.build_status_check())

    def ensure_status_idle(self, timeout=60):
        """
        Wait for device to reach idle status.

        Args:
            timeout (int): Maximum wait time in seconds

        Raises:
            ZemException: If timeout is reached before device becomes idle
        """
        st = time.time()
        resp = self.check_status()
        while (resp is None) or (not resp.is_idle_status()):
            time.sleep(1)
            resp = self.check_status()
            if timeout < time.time() - st:
                raise ZemException("等待设备空闲超时", ZemException.Code.SvrError)

    def get_stage_status(self):
        """
        Get current stage movement status.

        Returns:
            EnumStageStatus: Current stage status (idle, moving, etc.)
        """
        resp = self.send(self.builder.build_get_stage_status())
        return resp.parse_stage_status()

    def ensure_stage_idle(self, timeout=30, *, target=None, tolerance_um=3.0, settle_s=1.0, poll_s=0.25):
        """Wait for idle and stable readback, optionally at a target in micrometers.

        The deadline includes polling and settling. Each RPC also has its own
        transport timeout. Old Shells expose cached samples without sequence IDs;
        stable readback is a fallback, not proof of hardware sample freshness.
        Returns the measured StagePos in the device's existing readback units.
        """
        if not all(math.isfinite(v) for v in (timeout, tolerance_um, settle_s, poll_s)) or timeout <= 0 or tolerance_um < 0 or settle_s <= 0 or poll_s <= 0:
            raise ValueError("Invalid stage wait bounds")
        scale = zu.zem15_um2pulse if self.m.is_stage_pos_unit_pulse() else 1.0
        target_xy = None if target is None else (float(target.x) * scale, float(target.y) * scale)
        if target_xy is not None and not all(math.isfinite(v) for v in target_xy):
            raise ValueError("Stage target must be finite")
        tolerance = tolerance_um * scale
        deadline = time.monotonic() + timeout
        stable_since, anchor = None, None
        observed, status = None, None
        while time.monotonic() < deadline:
            status = self.get_stage_status()
            observed = self.get_stage_pos()
            now = time.monotonic()
            if now >= deadline:
                break
            xy = None if observed is None else (observed.x, observed.y)
            valid = xy is not None and all(math.isfinite(v) for v in xy)
            arrived = valid and (target_xy is None or all(abs(a-b) <= tolerance for a, b in zip(xy, target_xy)))
            if status == EnumStageStatus.Idle and arrived:
                if anchor is None or any(abs(a-b) > tolerance for a, b in zip(xy, anchor)):
                    stable_since, anchor = now, xy
                elif now - stable_since >= settle_s:
                    return observed
            else:
                stable_since, anchor = None, None
            time.sleep(min(poll_s, max(0.0, deadline-time.monotonic())))
        error = ZemException(f"等待样品台到位超时：目标={target_xy}，读回={observed}，状态={status}，容差={tolerance_um} μm；未重发移台指令", ZemException.Code.SvrError)
        error.stage_wait_details = {"target_um": None if target is None else {"x_um": target.x, "y_um": target.y},
                                    "observed": None if observed is None else {"x": observed.x, "y": observed.y},
                                    "status": None if status is None else status.name, "timeout_s": timeout, "tolerance_um": tolerance_um}
        raise error

    def get_hv_status(self):
        """
        Get current high voltage status.

        Returns:
            EnumHvStatus: Current high voltage status (open, close, changing)
        """
        resp = self.send(self.builder.build_get_hv_status())
        return resp.parse_hv_status()

    def ensure_hv_ready(self, timeout=60):
        """
        Wait for high voltage to stabilize after setting.

        Args:
            timeout (int): Maximum wait time in seconds

        Raises:
            ZemException: If timeout is reached before HV is ready
        """
        time.sleep(5)

        st = time.time()
        status = self.get_hv_status()
        while status == EnumHvStatus.Changing:
            time.sleep(1)
            status = self.get_hv_status()
            if timeout < time.time() - st:
                raise ZemException("等待高压稳定超时", ZemException.Code.SvrError)

    def hv_on(self):
        """
        Turn on high voltage for the electron beam.

        Returns:
            HvInfo: Updated high voltage information if successful, None if failed
        """
        resp = self.send(self.builder.build_gun_on())
        return resp.is_ack_ok()

    def hv_off(self):
        """
        Turn off high voltage for the electron beam.

        Returns:
            HvInfo: Updated high voltage information if successful, None if failed
        """
        resp = self.send(self.builder.build_gun_off())
        return resp.is_ack_ok()

    def get_mag(self):
        """
        Get current magnification setting.

        Returns:
            float: Current magnification value
        """
        resp = self.send(self.builder.build_get_mag())
        self.m.mag = resp.parse_mag()
        return self.m.mag

    def set_mag(self, mag: int):
        """
        Set device magnification.

        Args:
            mag (int): Target magnification value

        Returns:
            int: New magnification if successful, None if failed
        """
        resp = self.send(self.builder.build_set_mag(mag))
        if resp.is_ack_ok():
            self.m.mag = mag
            return mag
        return None

    def set_hv(self, kv: int):
        """
        Set high voltage for the electron beam.

        Args:
            kv (int): Target high voltage in kilovolts

        Returns:
            HvInfo: Updated high voltage information if successful, None if failed
        """
        resp = self.send(self.builder.build_set_hv(kv))
        return resp.is_ack_ok()

    def get_bse_cfg(self) -> BseInfo:
        """
        Get current backscattered electron (BSE) detector configuration.
        Returns:
            BseInfo: Current BSE detector configuration
        """
        resp = self.send(self.builder.build_get_bse_cfg())
        self.m.bse_cfg = resp.parse_bse_cfg()
        return self.m.bse_cfg

    def set_bse_cfg(self, cfg: BseInfo):
        """
        Set backscattered electron (BSE) detector configuration.
        Args:
            cfg (BseInfo): Target BSE detector configuration
        Returns:
            BseInfo: New BSE configuration if successful, None if failed
        """
        resp = self.send(self.builder.build_set_bse_cfg(cfg))
        if resp.is_ack_ok():
            self.m.bse_cfg = cfg
            return cfg
        return None

    def gun_on(self):
        """
        Turn on the electron gun.

        Returns:
            HvInfo: Updated high voltage information if successful, None if failed
        """
        self.send(self.builder.build_gun_on())
        return None

    def gun_off(self):
        """
        Turn off the electron gun.

        Returns:
            HvInfo: Updated high voltage information if successful, None if failed
        """
        self.send(self.builder.build_gun_off())
        return None

    def get_beam_size(self):
        """
        Get current electron beam size setting.

        Returns:
            EnumBeamSize: Current beam size configuration
        """
        resp = self.send(self.builder.build_get_beam_size())
        self.m.beam_size = resp.parse_beam_size()
        return self.m.beam_size

    def set_beam_size(self, bs: EnumBeamSize):
        """
        Set electron beam size.

        Args:
            bs (EnumBeamSize): Target beam size setting
        """
        resp = self.send(self.builder.build_set_beam_size(bs))
        if resp.is_ack_ok():
            self.m.beam_size = bs

    def set_autofocus(self, seed_ob: float | None = None, search_range_ob: float | None = None):
        """
        Start autofocus operation.

        Ensures any previous autofocus is complete before starting new one.
        """
        self.ensure_af_done()
        resp = self.send(self.builder.build_autofocus(seed_ob, search_range_ob))
        if resp.is_ack_ok():
            ...

    def get_autofocus_status(self):
        """
        Get current autofocus operation status.

        Returns:
            EnumAutofocusStatus: Current autofocus status
        """
        resp = self.send(self.builder.build_check_autofocus())
        return resp.parse_autofocus_status()

    def ensure_af_done(self, timeout=600):
        """
        Wait for autofocus operation to complete.

        Args:
            timeout (int): Maximum wait time in seconds

        Raises:
            ZemException: If timeout is reached before autofocus completes
        """
        st = time.time()
        status = self.get_autofocus_status()
        while status != EnumAutofocusStatus.Idle:
            time.sleep(1)
            status = self.get_autofocus_status()
            if timeout < time.time() - st:
                raise ZemException("等待自动对焦结束超时", ZemException.Code.SvrError)

    def get_ob(self):
        """
        Get current objective lens setting.

        Returns:
            int: Current objective lens value
        """
        resp = self.send(self.builder.build_get_ob())
        self.m.ob = resp.parse_ob()
        return self.m.ob

    def get_imaging_mode(self):
        """Read Instrument's mode; never infer it from an objective value."""
        return self.send(self.builder.build_get_imaging_mode()).parse_imaging_mode()

    def get_scan_relay_mask(self) -> int:
        """Read normal-scan enabled relays: bit0=K1 .. bit3=K4."""
        value = self.send(self.builder.build_get_scan_relay_mask()).parse_scan_relay_mask()
        self.m.scan_relay_mask = value
        return value

    def set_scan_relay_mask(self, mask: int) -> int | None:
        """Set 1..15 and read back after ACK; 7 disables K4, 15 enables all.

        The server reselects immediately in idle/video normal mode and rejects
        an unsupported field or busy/fisheye mode without changing the mask.
        """
        response = self.send(self.builder.build_set_scan_relay_mask(mask))
        return self.get_scan_relay_mask() if response.is_ack_ok() else None

    def set_imaging_mode(self, mode):
        """Switch Normal (0) / Fisheye (2); Instrument owns optical restoration."""
        resp = self.send(self.builder.build_set_imaging_mode(mode))
        return self.get_imaging_mode() if resp.is_ack_ok() else None

    def get_fisheye_focus(self):
        """Read the 0..65535 focus handle; valid only in fisheye mode."""
        return self.send(self.builder.build_get_fisheye_focus()).parse_fisheye_focus()

    def set_fisheye_focus(self, value: int):
        """Set a focus handle, not OB DAC or compression percentage.

        Instrument maps it to its configured compression lens A/B and DAC range.
        A request in normal mode is rejected by the device.
        """
        resp = self.send(self.builder.build_set_fisheye_focus(value))
        return self.get_fisheye_focus() if resp.is_ack_ok() else None

    def set_ob(self, ob: int):
        """
        Set objective lens value.

        Args:
            ob (int): Target objective lens setting (0-65535 range)

        Returns:
            int: New objective value if successful, None if failed
        """
        resp = self.send(self.builder.build_set_ob_raw(ob))
        if resp.is_ack_ok():
            self.m.ob = ob
            return ob
        return None

    def set_ob_raw(self, ob: int):
        """Explicit alias for callers that want the wire unit in the method name."""
        return self.set_ob(ob)

    def get_wd(self):
        """Read working distance using the protocol-level GetWD command."""
        resp = self.send(self.builder.build_get_wd())
        parser = getattr(resp, "parse_wd", None)
        value = parser() if callable(parser) else resp.extra.get("wd")
        self.m.wd = value
        return value

    def set_wd(self, wd: float):
        """Set working distance and retain the value in the device model."""
        resp = self.send(self.builder.build_set_wd(float(wd)))
        if resp.is_ack_ok():
            self.m.wd = float(wd)
            return float(wd)
        return None

    def set_beam_shift(self, x_um: float, y_um: float):
        """Set absolute specimen-plane beam shift in micrometres."""
        resp = self.send(self.builder.build_set_beam_shift(x_um, y_um))
        if resp.is_ack_ok():
            return {"x_um": float(x_um), "y_um": float(y_um)}
        return None

    def set_field_rotation(self, degree: int):
        """
        Set field rotation angle.

        Args:
            degree (int): Rotation angle in degrees

        Returns:
            int: New rotation angle if successful, None if failed
        """
        resp = self.send(self.builder.build_set_rotation(degree))
        if resp.is_ack_ok():
            self.m.scan_info.rot_degree = degree
            return degree
        return None

    def set_roi_nav(self, width, height, bbox):
        """Center a point/box using Shell's current optics and stage/beam choice.

        Equal corners center a point without changing magnification. A box
        also zooms to its longer side. Never replay a timed-out navigation.
        """
        resp = self.send(self.builder.build_set_roi_nav(width, height, bbox))
        return {"accepted": True} if resp.is_ack_ok() else None

    def get_scan_info(self):
        """
        Get current scan configuration information.

        Returns:
            ScanInfo: Current scan parameters including field size and rotation
        """
        resp = self.send(self.builder.build_get_scan_info())
        si = resp.parse_scan_info()
        if si is None:
            # Fallback calculation for devices that don't support GetScanInfo
            mag = self.m.mag
            si = ScanInfo(scan_um=float(260000 / mag), rot_degree=float(0))
            logger.debug(f"cmd {EnumCmd.GetScanInfo} not supported, calc from mag: {si}")
        self.m.scan_info = si
        return self.m.scan_info

    def get_allow_open_gun(self) -> bool:
        """
        Get whether gun opening is allowed.

        Returns:
            bool: True if gun opening is allowed, False otherwise
        """
        resp = self.send(self.builder.build_get_allow_open_gun())
        self.m.allow_open_gun = resp.parse_allow_open_gun()
        return self.m.allow_open_gun

    def get_is_open_gun(self) -> bool:
        """
        Get whether gun is currently open.

        Returns:
            bool: True if gun is open, False otherwise
        """
        resp = self.send(self.builder.build_get_is_open_gun())
        self.m.is_open_gun = resp.parse_is_open_gun()
        return self.m.is_open_gun

    def get_is_changing_samp(self) -> int:
        """
        Get sample changing status.

        Returns:
            int: -1 for gun chamber changing, 0 for normal, 1 for sample chamber changing
        """
        resp = self.send(self.builder.build_get_is_changing_samp())
        self.m.is_changing_samp = resp.parse_is_changing_samp()
        return self.m.is_changing_samp

    def get_set_hv(self) -> float:
        """
        Get set high voltage value.

        Returns:
            float: Set acceleration voltage value
        """
        resp = self.send(self.builder.build_get_set_hv())
        self.m.set_hv = resp.parse_set_hv()
        return self.m.set_hv

    def set_compress_a(self, value: float) -> float:
        """
        Set compression lens A value.

        Args:
            value (float): Compression percentage (0-100)

        Returns:
            float: New compression value if successful, None if failed
        """
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("CompressA must be a finite percentage between 0 and 100")
        resp = self.send(self.builder.build_set_compress_a(value))
        if resp.is_ack_ok():
            self.m.compress_a = value
            return value
        return None

    def get_compress_a(self) -> float:
        """
        Get compression lens A value.

        Returns:
            float: Current compression A percentage (0-100)
        """
        resp = self.send(self.builder.build_get_compress_a())
        self.m.compress_a = resp.parse_compress_a()
        return self.m.compress_a

    def set_compress_b(self, value: float) -> float:
        """
        Set compression lens B value.

        Args:
            value (float): Compression percentage (0-100)

        Returns:
            float: New compression value if successful, None if failed
        """
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError("CompressB must be a finite percentage between 0 and 100")
        resp = self.send(self.builder.build_set_compress_b(value))
        if resp.is_ack_ok():
            self.m.compress_b = value
            return value
        return None

    def get_compress_b(self) -> float:
        """
        Get compression lens B value.

        Returns:
            float: Current compression B percentage (0-100)
        """
        resp = self.send(self.builder.build_get_compress_b())
        self.m.compress_b = resp.parse_compress_b()
        return self.m.compress_b

    def set_work_mode(self, mode: EnumCmdLevel):
        """
        设置设备工作模式

        Args:
            mode: 工作模式 (BASIC 或 ADVANCED)
        """
        self._work_mode = mode
        logger.info(f"工作模式已切换为: {mode.name}")

    def get_work_mode(self) -> EnumCmdLevel:
        """
        获取当前工作模式

        Returns:
            EnumCmdLevel: 当前工作模式
        """
        return self._work_mode

    def _check_cmd_permission(self, cmd: EnumCmd):
        """
        检查命令权限

        Args:
            cmd: 要执行的命令

        Raises:
            ZemException: 如果命令被拒绝
        """
        if cmd.cmd_level == EnumCmdLevel.BASIC:
            # 基础命令总是允许
            return

        if cmd.cmd_level == EnumCmdLevel.ADVANCED:
            if self._work_mode != EnumCmdLevel.ADVANCED:
                raise ZemException.permission_denied(f"命令 {cmd.name} ({cmd.name_cn}) 是高级命令，" f"需要先设置工作模式为 ADVANCED。当前模式: {self._work_mode.name}")

    def ensure_connected(self):
        """
        Verify device connection is established.

        Raises:
            ZemException: If no device is connected
        """
        if self.m.addr[0] == "UNK":
            raise ZemException("未选择远程设备", ZemException.Code.UiOpError)

    def zem_rpc(self, data):
        """
        Send RPC request to device using HTTP protocol.

        Args:
            data: JSON-RPC request data

        Returns:
            dict: Parsed JSON response from device
        """
        logger.debug(f"zem_rpc: {data}")
        content = req_util.req_post_json(self.m.protocol_ng.url, data)
        return json.loads(content)

    def send(self, req: Request):
        """
        Send request to device with appropriate validation.

        Args:
            req (Request): Request to send to device

        Returns:
            Response packet from device
        """
        # Skip connection check for handshake requests
        if req.cmd != EnumCmd.Handshake:
            self.ensure_connected()

        # Ensure device is idle for commands that require it
        if req.cmd.need_args:
            self.ensure_status_idle()

        return self.pubsub_send(req)

    @retry(retry=_retry_pubsub_request, reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(1) + wait_random(0, 1), before_sleep=before_sleep_log(logger, log_level="DEBUG"))
    def pubsub_send(self, req: Request):
        """
        Send request using publish-subscribe pattern with retry logic.

        Args:
            req (Request): Request to send

        Returns:
            Response from appropriate PubSub handler

        Raises:
            ZemException: If device returns an error response
        """
        # Check command permission before sending
        self._check_cmd_permission(req.cmd)
        timeout_ms = req.timeout_ms if req.cmd == EnumCmd.Handshake else ZemRpcDevice._scaled_timeout_ms(self, req.timeout_ms)

        # Choose appropriate PubSub handler based on request type
        if req.cmd == EnumCmd.Handshake:
            ps = HandshakePubSub(req, timeout=timeout_ms)
        elif req.cmd == EnumCmd.GetNavImg:
            ps = GetImagePubSub(req, self.m.is_newbee(), timeout=timeout_ms)
        elif req.cmd == EnumCmd.Snap:
            ps = GetImagePubSub(req, self.m.is_newbee(), timeout=timeout_ms)
        else:
            ps = PubSub(req, timeout=timeout_ms)

        try:
            resp = self.rws.pubsub_send(ps)
            if isinstance(ps, GetImagePubSub) and ps.error is not None:
                raise ps.error
        finally:
            if isinstance(ps, GetImagePubSub):
                ps.cancel()

        # Check for errors in non-handshake, non-RPC responses
        if req.cmd in (EnumCmd.GetSoftwareInfo, EnumCmd.GetSN) and resp.is_invalid_cmd():
            return resp
        if req.cmd != EnumCmd.Handshake and req.cmd != EnumCmd.ZemRpc:
            if resp.is_error() or resp.is_invalid_cmd():
                raise ZemException.request_error(f"{req.cmd.name}: {resp.data_str}")
        return resp

    def send_cmd(self, cmd: EnumCmd, args: str = None):
        """
        Send generic command to device.

        Args:
            cmd (EnumCmd): Command type to send
            args (str, optional): Command arguments if needed

        Returns:
            Response from appropriate PubSub handler
        """
        # Check command permission before building request
        self._check_cmd_permission(cmd)

        # Build request based on whether arguments are provided
        if args is None:
            req = self.builder.build_get(cmd)
        else:
            req = self.builder.build_set(cmd, args)

        return self.pubsub_send(req)

    def _do_framing(self, pkt: UdpPacket):
        """
        Process incoming UDP packets and frame them into response packets.

        Args:
            pkt (UdpPacket): Raw UDP packet received from device

        Returns:
            List[RespPacket]: List of parsed response packets
        """
        logger.debug(f'received udp data from {pkt.addr} "{pkt.data.decode()}"')
        ret = []
        for packet in self.parser.append(pkt.addr, pkt.data):
            resp = RespPacket(packet)
            resp.extra["addr"] = pkt.addr
            self.m.cmd_rcv(resp.data_str)
            ret.append(resp)
        return ret

    def _do_write(self, req: Request):
        """
        Write request data to appropriate destination.

        Args:
            req (Request): Request to be sent
        """
        if req.cmd != EnumCmd.Handshake:
            self._prepare_comm()
            local_ip, local_port = self.socket.sock.getsockname()
            data = patch_request_callback(req.data, local_ip, local_port)
        else:
            data = req.data

        _c = data.decode()
        logger.debug(f"send to {self.m.addr}: {_c}")
        self.m.cmd_send(_c)
        if req.cmd == EnumCmd.Handshake:
            # Broadcast handshake requests for device discovery
            self.socket.broadcast(data, self.m.addr[1])
        else:
            # Send regular requests to specific device address
            self.socket.write(data, addr=self.m.addr)
