#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import cv2
import time
import socket
import random
import base64
import threading
import numpy as np
from queue import Queue
from pathlib import Path
from loguru import logger
from abc import abstractmethod
from dataclasses import dataclass
from functools import cached_property

from jgb.util import os_util, cv_util, file_util, json_util

from zemrpc import app_cfg
from zemrpc.zem.conn.protocol import EnumAutofocusStatus, EnumCmd, ProtocolParser, ReqPacket, append_crc, EnumStageStatus, EnumStatus, EnumImageSize, EnumImgDepth, ImageReq, NavParam, EnumBeamSize


class ZemRespBuilder:
    def __init__(self): ...

    def build_handshake(self, addr):
        return self._build(f"{EnumCmd.HandshakeResp.cmd},{addr[0]}:{addr[1]}")

    def build_status_check(self, status: EnumStatus):
        return self.build_set(EnumCmd.StatusCheck, status.value)

    def build_snap(self, addr, depth: EnumImgDepth, img_size: EnumImageSize):
        svr_name = "Virtual Zem Service"
        width, height = 512, 512
        if img_size == EnumImageSize.S1024x1024:
            width, height = 1024, 1024
        elif img_size == EnumImageSize.S2048x2048:
            width, height = 2048, 2048

        return self.build_set(EnumCmd.Snap, f"{svr_name}:{addr[0]}:{addr[1]},{depth.value},{width},{height}")

    def build_get_mag(self, mag):
        return self.build_set(EnumCmd.GetMag, f"{mag}")

    def build_get_beam_size(self, bs: EnumBeamSize):
        return self.build_set(EnumCmd.GetBeamSz, f"{bs.value[0]}")

    def build_get_nav_img(self, addr, depth):
        svr_name = "Virtual Zem Service"
        return self.build_set(EnumCmd.GetNavImg, f"{svr_name}:{addr[0]}:{addr[1]},{depth},640,480")

    def build_get_nav_para(self, p: NavParam):
        return self.build_set(EnumCmd.GetNavPara, f"{p.p0x:.6f},{p.p0y:.6f},{p.cx:.6f},{p.cy:.6f}")

    def build_get_ob(self, ob):
        return self.build_set(EnumCmd.GetOB, f"{ob}")

    def build_get_wd(self, wd):
        return self.build_set(EnumCmd.GetWD, f"{wd}")

    def build_get_stage_pos(self, pos):
        x, y = pos
        return self.build_set(EnumCmd.GetStagePos, f"{-x:.6f},{-y:.6f}")

    def build_get_stage_status(self, status: EnumStageStatus):
        return self.build_set(EnumCmd.GetStgStatus, f"{status.value}")

    def build_check_autofocus(self, status: EnumAutofocusStatus):
        return self.build_set(EnumCmd.CheckAutoFocus, f"{status.value}")

    def build_get_scan_info(self, data):
        scan_um, rot_degree = data
        return self.build_set(EnumCmd.GetScanInfo, f"{scan_um:.6f},{rot_degree:.6f}")

    def build_get_hv_info(self, data):
        acc_v, beam_i = data
        return self.build_set(EnumCmd.GetHV, f"{acc_v:.4f},{beam_i:.4f}")

    def build_get_model(self, model_str: str):
        return self.build_set(EnumCmd.GetModel, model_str)

    def build_is_video_alive(self, playing: bool):
        return self.build_set(EnumCmd.IsVideoAlive, "1" if playing else "0")

    def build_invalid_command(self, cmd: EnumCmd):
        return self.build_set(cmd, "Invalid command")

    def build_ack(self, cmd: EnumCmd):
        ec = 0
        return self.build_set(cmd, f"Acknowledge,Error Code:{ec}")

    def build_set(self, cmd: EnumCmd, args: str):
        return self._build(f"{cmd.cmd}:{args}")

    def _build(self, message):
        return append_crc(f"${message},")


class JsonRpcRespBuilder:
    def __init__(self, builder: ZemRespBuilder):
        self.pb = builder

    def build_resp(self, cmd: EnumCmd, resp):
        data = base64.b64encode(json_util.dumps(resp).encode()).decode()
        return self.pb.build_set(cmd, data)


class JsonRpcServer:
    def __init__(self, zem: "RemoteZem"):
        self.zem = zem
        self.rpc_builder = JsonRpcRespBuilder(self.zem.builder)

    def process_json_rpc(self, packet: ReqPacket):
        req = packet.parse_json_rpc()
        method = req["method"]
        if method == self.get_protocol_ng.__name__:
            # 从udp服务发现上来的请求原路返回
            result = self.get_protocol_ng()
            return self.rpc_builder.build_resp(packet.parse_cmd(), self.build_with_result(req, result))
        else:
            return self.rpc_builder.build_resp(packet.parse_cmd(), self.build_with_result(req, {"error": "UDP通道不支持该命令, 请调用JsonRPC服务"}))

    def get_protocol_ng(self):
        return {"name": self.zem.zem_dev.protocol_ng, "url": "http://127.0.0.1:61600/api/v1/jsonrpc"}

    def build_with_result(self, req, result):
        return {"jsonrpc": "2.0", "id": req["id"], "result": result}


class ImageSender(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._imgs = {}
        self._interrupted = False

    @property
    def addr(self):
        return self.server.getsockname()

    def set_image(self, img):
        self._imgs = img

    def run(self):
        self.server.bind((os_util.get_default_ip(), 0))
        self.server.listen(1)

        while not self._interrupted:
            client, address = self.server.accept()
            data = self._imgs.tobytes()
            client.send(data)
            client.close()

        self.server.close()


class UdpService(threading.Thread):
    def __init__(self):
        super().__init__()

        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ip = os_util.get_default_ip()
        port = 61557

        # Bind the socket to the port
        self.server_address = (ip, port)
        self.daemon = True

        self.data_received_callback = None
        self._interrupted = False
        self.last_send_time = 0
        self.min_send_interval = 0.05

    def send(self, data, ip, port):
        now = time.time()
        if (delta := now - self.last_send_time) < self.min_send_interval:
            time.sleep(self.min_send_interval - delta)
        self.server.sendto(data, (ip, port))
        self.last_send_time = time.time()
        logger.debug(f"send to {(ip, port)}: {data.decode()}")

    def close(self):
        self._interrupted = True

    def run(self):
        self.server.settimeout(0.1)
        logger.debug("starting up on %s port %s" % self.server_address)
        self.server.bind(self.server_address)

        while not self._interrupted:
            try:
                data, addr = self.server.recvfrom(4096)
                logger.debug(f"received udp data from {addr} {data.decode()}")
                if self.data_received_callback:
                    self.data_received_callback(addr, data)
            except socket.timeout:
                continue

            except Exception as e:
                logger.exception(f"recvfrom失败: {repr(e)}")


class VirtualZem:
    def __init__(self):
        self.nav_mag = 100
        # self.screen_size = 250  # mm
        self.screen_size = (2.54 * 5) * 10  # 5英寸底片倍率
        self.mag = 500
        self.ob = 30000
        self.wd = 11
        self.beam_size = EnumBeamSize.Coarse
        self.acc_v = 9846.5768
        self.beam_i = 26.8173
        self.is_video_alive = True
        self.pos = [0, 0]
        self.rot_degree = 0
        self.img_dtype = eval(app_cfg.get_param("virtual_zem.img_dtype", "np.uint8"))
        self.nav_para = NavParam(p0x=640 / 2, p0y=480 / 2, cx=200, cy=200)
        self.stage_status = EnumStageStatus.Idle
        self.autofocus_status = EnumAutofocusStatus.Idle
        self.model = "VirtualZem"
        self.protocol_ng = "ZEMRPC-202409"

    @property
    def scan_um(self):
        s = self.screen_size / self.mag * 1000  # 扫描场大小 um
        return s

    @property
    def scan_info(self):
        return self.scan_um, self.rot_degree

    @property
    def hv_info(self):
        return self.acc_v, self.beam_i

    @abstractmethod
    def get_nav_img(self):
        raise Exception("not implemented")

    @abstractmethod
    def snap(self, req: ImageReq):
        raise Exception("not implemented")


@dataclass
class NavMandelbrot:

    def __init__(self):
        self.width, self.height = 640, 480
        r = self.width / self.height

        s = 250 / 500 * 1000
        s /= 100  # 导航图生成mandelbrot时的系数

        self.xmin = -s * r
        self.xmax = s * r
        self.ymin = -s
        self.ymax = s


def mandelbrot(xmin, xmax, ymin, ymax, width, height, maxiter=100):
    x = np.linspace(xmin, xmax, width).reshape((1, width))
    y = np.linspace(ymin, ymax, height).reshape((height, 1))
    c = x + y * 1j
    z = c
    fractal = np.zeros(z.shape, dtype=int)
    for i in range(maxiter):
        z = z**2 + c
        mask = np.abs(z) > 2
        fractal += mask
        z[mask] = 2
    return fractal


class MandelbrotZem(VirtualZem):
    def __init__(self):
        super().__init__()
        self.nm = NavMandelbrot()
        self.model = "VirtualZem/MandelbrotZem"

    @cached_property
    def nav_nm_img(self):
        img = mandelbrot(self.nm.xmin, self.nm.xmax, self.nm.ymin, self.nm.ymax, self.nm.width, self.nm.height)
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        return img

    def get_nav_img(self):
        return self.nav_nm_img

    def snap_jsonrpc(self, width: int, height: int, pixel_avg: int, frame_avg: int):
        _, img = self._snap_from_mandelbrot(width, height)
        return img

    def snap(self, req: ImageReq):
        width, height = 512, 512
        if req.img_size == EnumImageSize.S1024x1024:
            width, height = 1024, 1024
        elif req.img_size == EnumImageSize.S2048x2048:
            width, height = 2048, 2048

        return self._snap_from_mandelbrot(width, height)

    def _snap_from_mandelbrot(self, width, height):
        s = self.scan_um
        x, y = self.pos
        xmin = x - s / 2
        xmax = x + s / 2
        ymin = y - s / 2
        ymax = y + s / 2

        r = (self.nav_para.cx * self.nm.width) / (self.nm.xmax - self.nm.xmin)
        xmin, xmax, ymin, ymax = list(map(lambda v: v / r, [xmin, xmax, ymin, ymax]))

        img = mandelbrot(xmin, xmax, ymin, ymax, width, height)
        img = cv2.flip(img, 0)
        if self.img_dtype == np.uint16:
            img = (img * 65535 / 100).astype(np.uint16)
            return EnumImgDepth.U16, img
        else:
            # img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
            img = cv2.convertScaleAbs(img, None, 255 / 100, 0).astype(np.uint8)
            return EnumImgDepth.U8, img


class ReplayZem(VirtualZem):
    def __init__(self, task_json: Path):
        super().__init__()
        self.model = "VirtualZem/ReplayZem"
        if task_json.is_dir():
            task_json = task_json / f"{task_json.name}.json"

        from zemcap.plugins.autocap.cap_roi.cap_roi_task import CapRoiTask

        self.task = CapRoiTask.load_from_file(task_json)
        self.img_list = self.get_img_list()
        self.curr_idx = 0

    def get_img_list(self):
        task_list = self.task.model.tasks
        img_list = []
        for task in task_list:
            png = self.task.get_dst_png(task.png)
            if png.exists():
                img_list.append(png)
        return img_list

    def get_nav_img(self):
        return self.task.model.nav_img.img

    def snap(self, req: ImageReq):
        width, height = 512, 512
        if req.img_size == EnumImageSize.S1024x1024:
            width, height = 1024, 1024
        elif req.img_size == EnumImageSize.S2048x2048:
            width, height = 2048, 2048

        img = self._snap(width, height)

        if self.img_dtype == np.uint16:
            return EnumImgDepth.U16, img
        else:
            return EnumImgDepth.U8, img

    def snap_jsonrpc(self, width: int, height: int, pixel_avg: int, frame_avg: int):
        img = self._snap(width, height)
        return img

    def _snap(self, width, height):
        png = self.img_list[self.curr_idx % len(self.img_list)]
        logger.debug(f"send: {png.name}")
        img = cv_util.imread(png)
        img = cv_util.resize(img, height, width)
        self.curr_idx += 1
        return img


class RemoteZem(threading.Thread):
    def __init__(self):
        super().__init__()
        self.daemon = True
        self.mq_event = Queue()
        self.use_replay_zem = app_cfg.get_param("virtual_zem.replay_zem.enable", False)

        if self.use_replay_zem:
            task_json = app_cfg.get_param("virtual_zem.replay_zem.cap_roi_task", None)
            self.zem_dev = ReplayZem(Path(task_json))
        else:
            self.zem_dev = MandelbrotZem()

        self.udp_service = UdpService()
        self.udp_service.data_received_callback = self.data_received_handler

        self.img_sender = ImageSender()

        self.parser = ProtocolParser()
        self.builder = ZemRespBuilder()

        self.rpc_server = JsonRpcServer(self)

        self._interrupted = False
        self._simu_timeout = app_cfg.get_param("virtual_zem.simu_timeout", 0)
        self._simu_busy = app_cfg.get_param("virtual_zem.simu_busy", 0)
        self._simu_stage_rng = app_cfg.get_param("virtual_zem.simu_stage_rng", 0)

    def run(self):
        self.udp_service.start()
        self.img_sender.start()

        while not self._interrupted:
            try:
                if self.mq_event.empty():
                    time.sleep(0.01)
                    continue

                event = self.mq_event.get(True, timeout=0.05)
                if event["type"] == "packet":
                    self.process_packet(event["data"])
            except Exception as e:
                logger.exception(f"VirtualZem Exception: {repr(e)}")

    def _send(self, addr, data):
        self.udp_service.send(data, addr[0], addr[1])

    def data_received_handler(self, addr, data):
        for packet in self.parser.append(addr, data):
            self.mq_event.put({"type": "packet", "data": ReqPacket(addr, packet)})

    def process_packet(self, packet: ReqPacket):
        cmd = packet.parse_cmd()
        if cmd == EnumCmd.Handshake:
            self._send(packet.addr, self.builder.build_handshake(self.udp_service.server_address))
        elif cmd == EnumCmd.StatusCheck:
            if random.random() < self._simu_timeout:  # 模拟超时
                time.sleep(EnumCmd.StatusCheck.timeout / 1000)
            if random.random() < self._simu_busy:
                self._send(packet.addr, self.builder.build_status_check(EnumStatus.Busy))
            else:
                self._send(packet.addr, self.builder.build_status_check(EnumStatus.Idle))
        elif cmd == EnumCmd.GetMag:
            self._send(packet.addr, self.builder.build_get_mag(self.zem_dev.mag))
        elif cmd == EnumCmd.SetMag:
            self._send(packet.addr, self.resp_set_mag(packet))
        elif cmd == EnumCmd.GetBeamSz:
            self._send(packet.addr, self.builder.build_get_beam_size(self.zem_dev.beam_size))
        elif cmd == EnumCmd.SetRotation:
            self._send(packet.addr, self.resq_set_rotation(packet))
        elif cmd == EnumCmd.Snap:
            self.zem_dev.is_video_alive = False
            self._send(packet.addr, self.resp_snap(packet))
        elif cmd == EnumCmd.VideoPlay:
            self.zem_dev.is_video_alive = True
            self._send(packet.addr, self.builder.build_ack(EnumCmd.VideoPlay))
        elif cmd == EnumCmd.GetOB:
            self._send(packet.addr, self.builder.build_get_ob(self.zem_dev.ob))
        elif cmd == EnumCmd.SetOB:
            self._send(packet.addr, self.resp_set_ob(packet))
        elif cmd == EnumCmd.GetWD:
            self._send(packet.addr, self.builder.build_get_wd(self.zem_dev.wd))
        elif cmd == EnumCmd.SetWD:
            self._send(packet.addr, self.builder.build_ack(EnumCmd.SetWD))
        elif cmd == EnumCmd.CheckAutoFocus:
            self._send(packet.addr, self.builder.build_check_autofocus(self.zem_dev.autofocus_status))
        elif cmd == EnumCmd.AutoFocus:
            self.zem_dev.ob += random.randint(-10, 10)  # 模拟自动对焦
            self._send(packet.addr, self.builder.build_ack(EnumCmd.AutoFocus))
        elif cmd == EnumCmd.GetNavImg:
            self._send(packet.addr, self.resp_nav_img())
        elif cmd == EnumCmd.GetNavPara:
            self._send(packet.addr, self.builder.build_get_nav_para(self.zem_dev.nav_para))
        elif cmd == EnumCmd.GetStagePos:
            self._send(packet.addr, self.builder.build_get_stage_pos(self.zem_dev.pos))
        elif cmd == EnumCmd.SetStagePos:
            self._send(packet.addr, self.resp_set_stage_pos(packet))
        elif cmd == EnumCmd.GetStgStatus:
            self._send(packet.addr, self.builder.build_get_stage_status(self.zem_dev.stage_status))
        elif cmd == EnumCmd.GetScanInfo:
            self._send(packet.addr, self.builder.build_get_scan_info(self.zem_dev.scan_info))
        elif cmd == EnumCmd.GetHV:
            self._send(packet.addr, self.builder.build_get_hv_info(self.zem_dev.hv_info))
        elif cmd == EnumCmd.GetModel:
            self._send(packet.addr, self.builder.build_get_model(self.zem_dev.model))
        elif cmd == EnumCmd.IsVideoAlive:
            self._send(packet.addr, self.builder.build_is_video_alive(self.zem_dev.is_video_alive))
        elif cmd == EnumCmd.VideoPlay:
            self.zem_dev.is_video_alive = True
            self._send(packet.addr, self.builder.build_ack(EnumCmd.VideoPlay))
        elif cmd == EnumCmd.ZemRpc:
            self._send(packet.addr, self.resp_json_rpc(packet))
        else:
            self._send(packet.addr, self.builder.build_invalid_command(cmd))

    def resp_set_mag(self, packet: ReqPacket):
        self.zem_dev.mag = packet.parse_mag()
        return self.builder.build_ack(EnumCmd.SetMag)

    def resp_set_ob(self, packet: ReqPacket):
        self.zem_dev.ob = packet.parse_ob()
        return self.builder.build_ack(EnumCmd.SetOB)

    def resq_set_rotation(self, packet: ReqPacket):
        rot_degree = packet.parse_rotation()
        self.zem_dev.rot_degree = rot_degree
        return self.builder.build_ack(EnumCmd.SetRotation)

    def resp_snap(self, packet: ReqPacket):
        req = packet.parse_snap()
        depth, img = self.zem_dev.snap(req)
        self.img_sender.set_image(img)
        return self.builder.build_snap(self.img_sender.addr, depth, req.img_size)

    def resp_nav_img(self):
        img = self.zem_dev.get_nav_img()
        self.img_sender.set_image(img)
        h, w, c = cv_util.cv2_hwc(img)
        depth = 24
        if img.dtype == np.uint8:
            depth = 8 * c
        elif img.dtype == np.uint16:
            depth = 16 * c
        return self.builder.build_get_nav_img(self.img_sender.addr, depth)

    def resp_set_stage_pos(self, packet: ReqPacket):
        x, y = packet.parse_stage_pos()
        if self._simu_stage_rng:
            self.zem_dev.pos = [-x + random.random(), -y + random.random()]
        else:
            self.zem_dev.pos = [-x, -y]
        return self.builder.build_ack(EnumCmd.SetStagePos)

    def resp_json_rpc(self, packet: ReqPacket):
        return self.rpc_server.process_json_rpc(packet)

    def close(self):
        self._interrupted = True
        self.udp_service.close()
        self.udp_service.join()


zem = RemoteZem()
