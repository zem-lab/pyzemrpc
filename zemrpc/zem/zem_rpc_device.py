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
import copy
import numpy as np
import threading
from loguru import logger
from pydantic import Field
from typing import List, Tuple
from tenacity import retry, stop_after_attempt, wait_fixed, wait_random, before_sleep_log

from jgb.util import cv_util, req_util, time_util, os_util
from jgb.util.dds_util import AppTreeNode, AppTreeNodeRequiredMixin
from jgb.conn.rw_service import ReadWriteService
from jgb.conn.pubsub import PubSub
from jgb.conn.udp_socket import UdpSocket, UdpPacket

from zemrpc import app_cfg
from zemrpc.zem.context import ctx
from zemrpc.zem.conn.img_receiver import ImgReceiver
from zemrpc.zem.models import EnumBeamSize, FieldWithLoc, HvInfo, ImageMeta, NavParam, ScanInfo, SnapArgs, StagePos, ZemException
from zemrpc.zem.conn.protocol import EnumAutofocusStatus, EnumCmd, EnumStageStatus, ProtocolBuilder, ProtocolParser, Request, RespPacket
from zemrpc.zem.conn.rpc_protocol import JsonRpcBuilder, RespProtocolNg, RpcSnapResp
from zemrpc.zem import zem_util as zu


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

        self.result = packet
        img_resp = packet.parse_img_resp()
        if img_resp is not None:
            # Start image reception in separate thread to avoid blocking
            threading.Thread(target=self._receive_img, args=(img_resp,), daemon=True).start()
        else:
            self.notify_done()

        return True

    def _receive_img(self, img_resp):
        """
        Handle image data reception in a separate thread.

        Args:
            img_resp: Image response containing reception parameters
        """
        receiver = ImgReceiver(img_resp, self.img_received_handler, self.is_newbee)
        receiver()
        self.notify_done()

    def img_received_handler(self, img_receiver: ImgReceiver):
        """
        Callback function called when image reception is complete.

        Args:
            img_receiver (ImgReceiver): The image receiver with completed image data
        """
        self.result.extra["img"] = img_receiver.img
        self.notify_done()


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

    mag: float = Field(default=0, on_setattr=True)
    beam_size: EnumBeamSize = Field(default=EnumBeamSize.Unk, on_setattr=True)
    ob: int = Field(default=0, on_setattr=True)
    wd: float = Field(default=0, on_setattr=True)

    hv_info: HvInfo = Field(default=None, on_setattr=True)
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

    def to_img_meta(self, avg_length):
        """
        Create image metadata from current device state.

        Args:
            avg_length: Number of frames averaged for this image

        Returns:
            ImageMeta: Complete metadata object for the acquired image
        """
        return ImageMeta(
            model=self.model,
            ob=self.ob,
            mag=self.mag,
            avg_length=avg_length,
            date=time_util.now_str(),
            detector=self.ed_chanel,
            hv_info=copy.deepcopy(self.hv_info),
            scan_info=copy.deepcopy(self.scan_info),
            stage_pos=copy.deepcopy(self.stage_pos),
            zemrpc_version=f"PYZEMRPC-{app_cfg.version}",
        )

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

    def __init__(self, name: str, **kwargs):
        """
        Initialize ZEM RPC device interface.

        Args:
            name (str): Device name identifier
            **kwargs: Additional configuration options including parent node
        """
        self.name = name
        self.m = ZemModel(ctx=ctx, node_name="zem_rpc_device")
        self.n = ctx.add_node(self, parent=kwargs.pop("parent", None))

        # Initialize UDP socket for device communication
        self.socket = UdpSocket(ctx, "zem_rpc_socket", parent=self.n, ip=os_util.get_default_ip(), port=0)

        # Set up read-write service for packet handling
        self.rws = ReadWriteService[RespPacket](f"RWS-{self.m.node_name}", ctx, self.socket, self._do_framing, self._do_write)

        # Initialize protocol builders
        self.builder = ProtocolBuilder()
        self.parser = ProtocolParser()
        self.rpc_builder = JsonRpcBuilder()

    def update_remote_addr(self, addr: Tuple[str, int]):
        """
        Update the remote device address.

        Args:
            addr (Tuple[str, int]): New device address (IP, port)
        """
        self.m.addr = addr
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()

    def build_handshake_request(self):
        """
        Build a handshake request packet for device discovery.

        Returns:
            Request: Handshake request packet ready to send
        """
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()
        return self.builder.build_handshake_request()

    def handshake(self):
        """
        Perform handshake with devices on the network.

        Returns:
            List: List of discovered device addresses
        """
        resp = self.send(self.build_handshake_request())  # type: List[RespPacket]
        return [packet.parse_ip_port() for packet in resp if not packet.is_error()]

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
            StagePos: New position if successful, None if failed
        """
        # Convert micrometers to pulses for older devices
        if self.m.is_stage_pos_unit_pulse():
            pos.x, pos.y = round(pos.x * zu.zem15_um2pulse), round(pos.y * zu.zem15_um2pulse)

        resp = self.send(self.builder.build_set_stage_pos(pos.x, pos.y))
        if resp.is_ack_ok():
            self.m.stage_pos = pos
            return pos
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

    def ensure_stage_idle(self, timeout=30):
        """
        Wait for stage to stop moving and become idle.

        Args:
            timeout (int): Maximum wait time in seconds

        Raises:
            ZemException: If timeout is reached before stage becomes idle
        """
        time.sleep(0.5)  # Initial delay to allow movement to start
        st = time.time()
        status = self.get_stage_status()
        while status != EnumStageStatus.Idle:
            time.sleep(1)
            status = self.get_stage_status()
            if timeout < time.time() - st:
                raise ZemException("等待样品台脱机超时", ZemException.Code.SvrError)

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
        if resp.is_ack_ok():
            self.m.hv_info.kv = kv
            return self.m.hv_info
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

    def set_autofocus(self):
        """
        Start autofocus operation.

        Ensures any previous autofocus is complete before starting new one.
        """
        self.ensure_af_done()
        resp = self.send(self.builder.build_autofocus())
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

    def ensure_af_done(self, timeout=60):
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

    def set_ob(self, ob: int):
        """
        Set objective lens value.

        Args:
            ob (int): Target objective lens setting (0-65535 range)

        Returns:
            int: New objective value if successful, None if failed
        """
        if ob <= 0:
            return None

        # Convert to percentage for device command
        resp = self.send(self.builder.build_set_ob_pct(ob / 65535 * 100))
        if resp.is_ack_ok():
            self.m.ob = ob
            return ob
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

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(1) + wait_random(0, 1), before_sleep=before_sleep_log(logger, log_level="DEBUG"))
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
        # Choose appropriate PubSub handler based on request type
        if req.cmd == EnumCmd.Handshake:
            ps = HandshakePubSub(req, timeout=req.timeout_ms)
        elif req.cmd == EnumCmd.GetNavImg:
            ps = GetImagePubSub(req, self.m.is_newbee(), timeout=req.timeout_ms)
        elif req.cmd == EnumCmd.Snap:
            ps = GetImagePubSub(req, self.m.is_newbee(), timeout=req.timeout_ms)
        else:
            ps = PubSub(req, timeout=req.timeout_ms)

        resp = self.rws.pubsub_send(ps)

        # Check for errors in non-handshake, non-RPC responses
        if req.cmd != EnumCmd.Handshake and req.cmd != EnumCmd.ZemRpc:
            if e := resp.is_error():
                raise ZemException.request_error("")
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
        # Build request based on whether arguments are provided
        if args is None:
            req = self.builder.build_get(cmd)
        else:
            req = self.builder.build_set(cmd, args)

        # Choose appropriate PubSub handler
        if req.cmd == EnumCmd.Handshake:
            ps = HandshakePubSub(req)
        elif req.cmd == EnumCmd.GetNavImg:
            ps = GetImagePubSub(req, self.m.is_newbee())
        elif req.cmd == EnumCmd.Snap:
            ps = GetImagePubSub(req, self.m.is_newbee())
        else:
            ps = PubSub(req)
        return self.rws.pubsub_send(ps)

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
            self.m.cmd_rcv(resp.data_str)
            ret.append(resp)
        return ret

    def _do_write(self, req: Request):
        """
        Write request data to appropriate destination.

        Args:
            req (Request): Request to be sent
        """
        self.m.cmd_send(req.data.decode())
        if req.cmd == EnumCmd.Handshake:
            # Broadcast handshake requests for device discovery
            self.socket.broadcast(req.data, self.m.addr[1])
        else:
            # Send regular requests to specific device address
            self.socket.write(req.data, addr=self.m.addr)
