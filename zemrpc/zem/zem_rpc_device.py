#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

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
    def __init__(self, request):
        super().__init__(request)
        self.result = []

    def pub(self, resp: RespPacket):
        if EnumCmd.HandshakeResp.name != resp.get_pubsub_key():
            return False

        self.result.append(resp)
        return True

    def timeout_handler(self):
        # 握手没有超时异常
        ...


class GetImagePubSub(PubSub):
    def __init__(self, request, is_newbee):
        super().__init__(request)
        self.is_newbee = is_newbee

    def pub(self, packet: RespPacket):
        if packet.get_pubsub_key() != self.request.get_pubsub_key():
            return False

        self.result = packet
        img_resp = packet.parse_img_resp()
        if img_resp is not None:
            threading.Thread(target=self._receive_img, args=(img_resp,), daemon=True).start()
        else:
            self.notify_done()

        return True

    def _receive_img(self, img_resp):
        receiver = ImgReceiver(img_resp, self.img_received_handler, self.is_newbee)
        receiver()
        self.notify_done()

    def img_received_handler(self, img_receiver: ImgReceiver):
        self.result.extra["img"] = img_receiver.img
        self.notify_done()


class ZemModel(AppTreeNode):
    model: str = Field(default="Unk")
    protocol_ng: RespProtocolNg = Field(default=None)
    addr: Tuple[str, int] = Field(default=("127.0.0.1", 61557))

    ed_chanel: str = Field(default="BSE", init=False)

    mag: float = Field(default=0)
    beam_size: EnumBeamSize = Field(default=EnumBeamSize.Unk)
    ob: int = Field(default=0)

    hv_info: HvInfo = Field(default=None)
    scan_info: ScanInfo = Field(default=None)
    nav_param: NavParam = Field(default=None)
    stage_pos: StagePos = Field(default=None)

    def cmd_rcv(self, cmd: str):
        ctx.pub_computed_attr(self, "cmd_rcv", cmd)

    def cmd_send(self, cmd: str):
        ctx.pub_computed_attr(self, "cmd_send", cmd)

    def data_rcv(self, data: bytes):
        ctx.pub_computed_attr(self, "data_rcv", data)

    def is_stage_pos_unit_pulse(self):
        return self.model == "ZEM18OLD"

    def is_newbee(self):
        return self.model in {"ZEM18", "ZEM18OLD", "ZEM15"}

    def to_img_meta(self, avg_length):
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
        return FieldWithLoc(scan_info=self.scan_info, pos=self.stage_pos)


class ZemRpcDevice(AppTreeNodeRequiredMixin):
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.m = ZemModel(ctx=ctx, node_name="zem_rpc_device")
        self.n = ctx.add_node(self, parent=kwargs.pop("parent", None))

        self.socket = UdpSocket(ctx, "zem_rpc_socket", parent=self.n, ip=os_util.get_default_ip(), port=0)

        self.rws = ReadWriteService[RespPacket](f"RWS-{self.m.node_name}", ctx, self.socket, self._do_framing, self._do_write)

        self.builder = ProtocolBuilder()
        self.parser = ProtocolParser()
        self.rpc_builder = JsonRpcBuilder()

    def update_remote_addr(self, addr: Tuple[str, int]):
        self.m.addr = addr
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()

    def build_handshake_request(self):
        self.builder.ip, self.builder.port = self.socket.sock.getsockname()
        return self.builder.build_handshake_request()

    def handshake(self):
        resp = self.send(self.build_handshake_request())  # type: List[RespPacket]
        return [packet.parse_ip_port() for packet in resp if not packet.is_error()]

    def video_play_on(self):
        return self.pubsub_send(self.builder.build_video_play())

    def check_video_play(self):
        resp = self.pubsub_send(self.builder.build_is_video_alive())
        status = resp.parse_video_status()
        return status

    def snap_simple(self, snap_args: SnapArgs):
        resp = self.send(self.builder.build_snap_simple(snap_args.pixel_avg, snap_args.size))
        return resp.extra["img"]

    def snap_rpc(self, width: int = 2048, height: int = 2048, pixel_avg: int = 7, frame_avg: int = 1):
        data = self.zem_rpc(self.rpc_builder.snap(width, height, pixel_avg, frame_avg))
        return RpcSnapResp(**data)

    def get_nav_param(self) -> NavParam:
        resp = self.send(self.builder.build_get_nav_para())
        param = resp.parse_nav_para()
        if self.m.is_stage_pos_unit_pulse():
            param.cx = param.cx * zu.zem15_pulse2um
            param.cy = param.cy * zu.zem15_pulse2um
        self.m.nav_param = param
        return self.m.nav_param

    def get_nav_img(self) -> np.ndarray:
        resp = self.send(self.builder.build_get_nav_img())
        img = resp.extra["img"]
        if img is not None:
            h, w, c = cv_util.cv2_hwc(img)
            if c == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
            elif c == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    def get_model(self) -> str:
        resp = self.send(self.builder.build_get_model())
        self.m.model = resp.parse_model()
        return self.m.model

    def get_protocol_ng(self) -> str:
        resp = self.send(self.builder.build_json_rpc(self.rpc_builder.get_protocol_ng()))
        ret = resp.parse_json_rpc()
        if ret.get("error", None):
            self.m.protocol_ng = RespProtocolNg()
        else:
            self.m.protocol_ng = RespProtocolNg(**ret["result"]).update_remote_host(self.m.addr[0])

    def get_hv(self) -> HvInfo:
        resp = self.send(self.builder.build_get_hv())
        self.m.hv_info = resp.parse_hv()
        return self.m.hv_info

    def get_stage_pos(self) -> StagePos:
        resp = self.send(self.builder.build_get_stage_pos())
        self.m.stage_pos = resp.parse_stage_pos()
        return self.m.stage_pos

    def set_stage_pos(self, pos: StagePos):
        if self.m.is_stage_pos_unit_pulse():
            pos.x, pos.y = round(pos.x * zu.zem15_um2pulse), round(pos.y * zu.zem15_um2pulse)

        resp = self.send(self.builder.build_set_stage_pos(pos.x, pos.y))
        if resp.is_ack_ok():
            self.m.stage_pos = pos
            return pos
        return None

    def check_status(self) -> RespPacket:
        return self.send(self.builder.build_status_check())

    def ensure_status_idle(self, timeout=60):
        st = time.time()
        resp = self.check_status()
        while (resp is None) or (not resp.is_idle_status()):
            time.sleep(1)
            resp = self.check_status()
            if timeout < time.time() - st:
                raise ZemException("等待设备空闲超时", ZemException.Code.SvrError)

    def get_stage_status(self):
        resp = self.send(self.builder.build_get_stage_status())
        return resp.parse_stage_status()

    def ensure_stage_idle(self, timeout=30):
        time.sleep(0.5)
        st = time.time()
        status = self.get_stage_status()
        while status != EnumStageStatus.Idle:
            time.sleep(1)
            status = self.get_stage_status()
            if timeout < time.time() - st:
                raise ZemException("等待样品台脱机超时", ZemException.Code.SvrError)

    def get_mag(self):
        resp = self.send(self.builder.build_get_mag())
        self.m.mag = resp.parse_mag()
        return self.m.mag

    def set_mag(self, mag: int):
        resp = self.send(self.builder.build_set_mag(mag))
        if resp.is_ack_ok():
            self.m.mag = mag
            return mag
        return None

    def get_beam_size(self):
        resp = self.send(self.builder.build_get_beam_size())
        self.m.beam_size = resp.parse_beam_size()
        return self.m.beam_size

    def set_beam_size(self, bs: EnumBeamSize):
        resp = self.send(self.builder.build_set_beam_size(bs))
        if resp.is_ack_ok():
            self.m.beam_size = bs

    def set_autofocus(self):
        self.ensure_af_done()
        resp = self.send(self.builder.build_autofocus())
        if resp.is_ack_ok():
            ...

    def get_autofocus_status(self):
        resp = self.send(self.builder.build_check_autofocus())
        return resp.parse_autofocus_status()

    def ensure_af_done(self, timeout=60):
        st = time.time()
        status = self.get_autofocus_status()
        while status != EnumAutofocusStatus.Idle:
            time.sleep(1)
            status = self.get_autofocus_status()
            if timeout < time.time() - st:
                raise ZemException("等待自动对焦结束超时", ZemException.Code.SvrError)

    def get_ob(self):
        resp = self.send(self.builder.build_get_ob())
        self.m.ob = resp.parse_ob()
        return self.m.ob

    def set_ob(self, ob: int):
        if ob <= 0:
            return None

        resp = self.send(self.builder.build_set_ob_pct(ob / 65535 * 100))
        if resp.is_ack_ok():
            self.m.ob = ob
            return ob
        return None

    def set_field_rotation(self, degree: int):
        resp = self.send(self.builder.build_set_rotation(degree))
        if resp.is_ack_ok():
            self.m.scan_info.rot_degree = degree
            return degree
        return None

    def get_scan_info(self):
        resp = self.send(self.builder.build_get_scan_info())
        si = resp.parse_scan_info()
        if si is None:
            mag = self.m.mag
            si = ScanInfo(scan_um=float(260000 / mag), rot_degree=float(0))
            logger.debug(f"cmd {EnumCmd.GetScanInfo} not supported, calc from mag: {si}")
        self.m.scan_info = si
        return self.m.scan_info

    def ensure_connected(self):
        if self.m.addr is None:
            raise ZemException("未选择远程设备", ZemException.Code.UiOpError)

    def zem_rpc(self, data):
        logger.debug(f"zem_rpc: {data}")
        content = req_util.req_post_json(self.m.protocol_ng.url, data)
        return json.loads(content)

    def send(self, req: Request):
        if req.cmd != EnumCmd.Handshake:
            self.ensure_connected()

        if req.cmd.need_args:
            self.ensure_status_idle()

        return self.pubsub_send(req)

    @retry(reraise=True, stop=stop_after_attempt(3), wait=wait_fixed(1) + wait_random(0, 1), before_sleep=before_sleep_log(logger, log_level="DEBUG"))
    def pubsub_send(self, req: Request):
        if req.cmd == EnumCmd.Handshake:
            ps = HandshakePubSub(req)
        elif req.cmd == EnumCmd.GetNavImg:
            ps = GetImagePubSub(req, self.m.is_newbee())
        elif req.cmd == EnumCmd.Snap:
            ps = GetImagePubSub(req, self.m.is_newbee())
        else:
            ps = PubSub(req)

        resp = self.rws.pubsub_send(ps)
        if req.cmd != EnumCmd.Handshake and req.cmd != EnumCmd.ZemRpc:
            if e := resp.is_error():
                raise ZemException.request_error("")
        return resp

    def send_cmd(self, cmd: EnumCmd, args: str = None):
        if args is None:
            req = self.builder.build_get(cmd)
        else:
            req = self.builder.build_set(cmd, args)

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
        logger.debug(f'received udp data from {pkt.addr} "{pkt.data.decode()}"')
        ret = []
        for packet in self.parser.append(pkt.addr, pkt.data):
            resp = RespPacket(packet)
            self.m.cmd_rcv(resp.data_str)
            ret.append(resp)
        return ret

    def _do_write(self, req: Request):
        self.m.cmd_send(req.data.decode())
        if req.cmd == EnumCmd.Handshake:
            self.socket.broadcast(req.data, self.m.addr[1])
        else:
            self.socket.write(req.data, addr=self.m.addr)
