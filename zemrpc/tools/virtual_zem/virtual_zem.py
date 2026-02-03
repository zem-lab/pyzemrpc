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
from zemrpc.zem.conn.protocol import (
    EnumAutofocusStatus,
    EnumCmd,
    ProtocolParser,
    ReqPacket,
    append_crc,
    EnumStageStatus,
    EnumStatus,
    EnumImageSize,
    EnumImgDepth,
    ImageReq,
    NavParam,
    EnumBeamSize,
    BseInfo,
    BseQuadrant,
    EnumBsePhase,
)


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
        return self.build_set(EnumCmd.GetBeamSz, f"{bs.bs}")

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

    def build_get_bse_cfg(self, cfg: BseInfo):
        v = [f"{q.phase.value},{q.bias}" for q in cfg.quadrants]
        return self.build_set(EnumCmd.GetBseCfg, ",".join(v))

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
        self.bse_cfg = BseInfo()
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


# 尝试导入 Rust 实现的高性能噪声生成器
try:
    from perlin_zem_rs import PerlinZemGenerator

    _USE_RUST_PERLIN = True
    logger.info("使用 Rust 实现的 PerlinZem (高性能)")
except ImportError:
    _USE_RUST_PERLIN = False
    logger.warning("Rust 模块 perlin_zem_rs 未安装，使用 Python 实现（性能较低）")


class PerlinZem(VirtualZem):
    """
    基于柏林噪声的虚拟电镜 - 增强版

    特性：
    1. 使用柏林噪声 + Worley噪声 + Ridge噪声 组合生成类似电镜图像的纹理
    2. 支持无限放大，使用多尺度噪声叠加实现无限细节
    3. 同一区域多次生成的图案完全一致（确定性）
    4. 高倍率时边缘清晰锐利，有明显的颗粒和晶界结构

    技术细节：
    - Worley噪声: 产生类似晶粒/细胞的锐利边缘结构
    - Ridge噪声: 产生锐利的山脊状线性结构
    - 自适应细节层: 根据放大倍率动态调整噪声层数
    - 边缘锐化: 使用 Unsharp Mask 增强图像边缘

    性能优化：
    - 优先使用 Rust 实现 (perlin_zem_rs)，性能提升 10-50 倍
    - 如果 Rust 模块不可用，回退到 Python 实现
    """

    def __init__(self, seed=42):
        super().__init__()
        self.model = "VirtualZem/PerlinZem"
        self.seed = seed

        # 导航图参数 (640x480)
        self.nav_width = 640
        self.nav_height = 480

        # 导航图对应的物理范围 (um)
        self.nav_scale = 500  # um, 导航图覆盖的物理范围

        # 噪声参数
        self.base_frequency = 0.1  # 基础频率
        self.worley_scale = 0.08  # Worley噪声缩放
        self.ridge_scale = 0.06  # Ridge噪声缩放

        # 初始化 Rust 或 Python 实现
        self._use_rust = _USE_RUST_PERLIN
        if self._use_rust:
            self._rust_generator = PerlinZemGenerator(
                seed=seed,
                base_frequency=self.base_frequency,
                worley_scale=self.worley_scale,
                ridge_scale=self.ridge_scale,
            )
        else:
            self._init_permutation_table()
            self._init_worley_points()

    def _init_permutation_table(self):
        """初始化确定性的排列表，用于柏林噪声计算"""
        rng = np.random.default_rng(self.seed)
        p = np.arange(256, dtype=np.int32)
        rng.shuffle(p)
        # 复制一份以避免边界检查
        self.perm = np.concatenate([p, p])

        # 预计算梯度向量 (8个方向)
        self.gradients = np.array(
            [[1, 1], [-1, 1], [1, -1], [-1, -1], [1, 0], [-1, 0], [0, 1], [0, -1]],
            dtype=np.float64,
        )

    def _init_worley_points(self):
        """初始化 Worley 噪声的特征点缓存"""
        # 使用确定性随机数生成器
        self.worley_rng = np.random.default_rng(self.seed + 1000)
        # 预生成特征点偏移 (每个单元格一个点)
        self.worley_cache = {}

    def _get_worley_point(self, cell_x, cell_y):
        """获取指定单元格的特征点位置（确定性）"""
        key = (cell_x, cell_y)
        if key not in self.worley_cache:
            # 使用哈希函数生成确定性的随机位置
            h = (cell_x * 374761393 + cell_y * 668265263) & 0xFFFFFFFF
            h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
            px = (h & 0xFFFF) / 65536.0
            py = ((h >> 16) & 0xFFFF) / 65536.0
            self.worley_cache[key] = (cell_x + px, cell_y + py)
        return self.worley_cache[key]

    def _fade(self, t):
        """平滑插值函数: 6t^5 - 15t^4 + 10t^3"""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _perlin_2d_vectorized(self, x, y):
        """向量化的2D柏林噪声计算"""
        xi = np.floor(x).astype(np.int32) & 255
        yi = np.floor(y).astype(np.int32) & 255

        xf = x - np.floor(x)
        yf = y - np.floor(y)

        u = self._fade(xf)
        v = self._fade(yf)

        aa = self.perm[self.perm[xi] + yi]
        ab = self.perm[self.perm[xi] + yi + 1]
        ba = self.perm[self.perm[xi + 1] + yi]
        bb = self.perm[self.perm[xi + 1] + yi + 1]

        def grad_dot(hash_val, dx, dy):
            g = self.gradients[hash_val & 7]
            return g[..., 0] * dx + g[..., 1] * dy

        n00 = grad_dot(aa, xf, yf)
        n01 = grad_dot(ab, xf, yf - 1)
        n10 = grad_dot(ba, xf - 1, yf)
        n11 = grad_dot(bb, xf - 1, yf - 1)

        nx0 = n00 + u * (n10 - n00)
        nx1 = n01 + u * (n11 - n01)

        return nx0 + v * (nx1 - nx0)

    def _worley_2d_vectorized(self, x, y, n_closest=1):
        """
        向量化的 Worley 噪声（细胞噪声）
        产生锐利的边缘，类似晶粒边界

        Args:
            x, y: 坐标数组
            n_closest: 使用第n近的距离 (1=最近, 2=次近)

        Returns:
            距离值数组，范围 [0, ~1.4]
        """
        shape = x.shape
        x_flat = x.flatten()
        y_flat = y.flatten()
        n = len(x_flat)

        # 获取当前所在的单元格
        cell_x = np.floor(x_flat).astype(np.int64)
        cell_y = np.floor(y_flat).astype(np.int64)

        # 存储最近的距离
        min_dist = np.full(n, np.inf)
        second_dist = np.full(n, np.inf)

        # 搜索周围 3x3 的单元格
        for di in range(-1, 2):
            for dj in range(-1, 2):
                # 使用哈希生成确定性的特征点位置
                ni = cell_x + di
                nj = cell_y + dj

                # 确定性哈希函数生成特征点偏移
                h = (ni * 374761393 + nj * 668265263).astype(np.int64) & 0xFFFFFFFF
                h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
                px = ni + (h & 0xFFFF) / 65536.0
                py = nj + ((h >> 16) & 0xFFFF) / 65536.0

                # 计算距离
                dist = np.sqrt((x_flat - px) ** 2 + (y_flat - py) ** 2)

                # 更新最近和次近距离
                mask = dist < min_dist
                second_dist = np.where(mask, min_dist, second_dist)
                min_dist = np.where(mask, dist, min_dist)

                mask2 = (~mask) & (dist < second_dist)
                second_dist = np.where(mask2, dist, second_dist)

        if n_closest == 1:
            return min_dist.reshape(shape)
        else:
            return second_dist.reshape(shape)

    def _worley_edge(self, x, y):
        """
        Worley 边缘检测
        使用 F2 - F1 (次近距离 - 最近距离) 产生锐利的边界线

        Returns:
            边缘强度，边界处接近0，内部接近1
        """
        shape = x.shape
        x_flat = x.flatten()
        y_flat = y.flatten()
        n = len(x_flat)

        cell_x = np.floor(x_flat).astype(np.int64)
        cell_y = np.floor(y_flat).astype(np.int64)

        min_dist = np.full(n, np.inf)
        second_dist = np.full(n, np.inf)

        for di in range(-1, 2):
            for dj in range(-1, 2):
                ni = cell_x + di
                nj = cell_y + dj

                h = (ni * 374761393 + nj * 668265263).astype(np.int64) & 0xFFFFFFFF
                h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
                px = ni + (h & 0xFFFF) / 65536.0
                py = nj + ((h >> 16) & 0xFFFF) / 65536.0

                dist = np.sqrt((x_flat - px) ** 2 + (y_flat - py) ** 2)

                mask = dist < min_dist
                second_dist = np.where(mask, min_dist, second_dist)
                min_dist = np.where(mask, dist, min_dist)

                mask2 = (~mask) & (dist < second_dist)
                second_dist = np.where(mask2, dist, second_dist)

        # F2 - F1 产生边界
        edge = (second_dist - min_dist).reshape(shape)
        return edge

    def _ridge_noise(self, x, y, octaves=4, lacunarity=2.0, persistence=0.5):
        """
        Ridge 噪声（脊线噪声）
        通过对柏林噪声取绝对值并反转，产生锐利的山脊状结构

        Returns:
            噪声值数组，范围 [0, 1]
        """
        value = np.zeros_like(x, dtype=np.float64)
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0
        weight = 1.0

        for _ in range(octaves):
            # 取绝对值并反转
            noise = 1.0 - np.abs(self._perlin_2d_vectorized(x * frequency, y * frequency))
            # 平方使山脊更锐利
            noise = noise * noise
            # 权重衰减
            noise *= weight
            weight = np.clip(noise * 2, 0, 1)

            value += amplitude * noise
            max_value += amplitude
            amplitude *= persistence
            frequency *= lacunarity

        return value / max_value

    def _fbm(self, x, y, octaves=8, lacunarity=2.0, persistence=0.5):
        """分形布朗运动"""
        value = np.zeros_like(x, dtype=np.float64)
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0

        for _ in range(octaves):
            value += amplitude * self._perlin_2d_vectorized(x * frequency, y * frequency)
            max_value += amplitude
            amplitude *= persistence
            frequency *= lacunarity

        return value / max_value

    def _multiscale_worley(self, x, y, scales=[1.0, 2.0, 4.0], weights=[0.5, 0.3, 0.2]):
        """
        多尺度 Worley 噪声
        叠加不同尺度的 Worley 噪声，产生更丰富的细节
        """
        result = np.zeros_like(x, dtype=np.float64)
        total_weight = sum(weights)

        for scale, weight in zip(scales, weights):
            edge = self._worley_edge(x * scale, y * scale)
            result += weight * edge

        return result / total_weight

    def _generate_perlin_image(self, xmin, xmax, ymin, ymax, width, height, mag_factor=1.0):
        """
        生成指定区域的增强型噪声图像

        组合多种噪声类型产生类似电镜的图像：
        1. Worley噪声：晶粒结构，锐利边界
        2. Ridge噪声：脊线状结构
        3. Perlin FBM：平滑的背景变化
        """
        # 创建坐标网格
        x = np.linspace(xmin, xmax, width)
        y = np.linspace(ymin, ymax, height)
        xx, yy = np.meshgrid(x, y)

        # 根据放大倍率动态调整参数
        # 高倍率时增加细节层数
        base_octaves = 6
        extra_octaves = int(np.log2(max(1, mag_factor / 100))) if mag_factor > 100 else 0
        octaves = min(16, base_octaves + extra_octaves)

        # 1. Worley 噪声 - 主要的晶粒结构
        worley_freq = self.worley_scale * (1 + 0.1 * np.log2(max(1, mag_factor / 100)))
        worley_x = xx * worley_freq
        worley_y = yy * worley_freq

        # 多尺度 Worley 产生不同大小的颗粒
        scales = [1.0, 2.5, 6.0]
        weights = [0.5, 0.3, 0.2]
        worley_multi = self._multiscale_worley(worley_x, worley_y, scales, weights)

        # 基本 Worley 距离场
        worley_dist = self._worley_2d_vectorized(worley_x, worley_y)

        # 2. Ridge 噪声 - 锐利的线性结构
        ridge_freq = self.ridge_scale * (1 + 0.1 * np.log2(max(1, mag_factor / 100)))
        ridge_x = xx * ridge_freq
        ridge_y = yy * ridge_freq
        ridge = self._ridge_noise(ridge_x, ridge_y, octaves=min(8, octaves))

        # 3. Perlin FBM - 平滑的背景
        perlin_freq = self.base_frequency
        perlin_x = xx * perlin_freq
        perlin_y = yy * perlin_freq
        perlin = self._fbm(perlin_x, perlin_y, octaves=octaves)
        perlin = (perlin + 1) / 2  # 归一化到 [0, 1]

        # 4. 高频细节噪声 - 纳米级颗粒感
        if mag_factor > 1000:
            # 高倍率时添加更多细节
            detail_freq = perlin_freq * 20 * (1 + np.log10(mag_factor / 1000))
            detail_x = xx * detail_freq
            detail_y = yy * detail_freq
            detail = self._perlin_2d_vectorized(detail_x, detail_y) * 0.1
        else:
            detail = 0

        # 组合各种噪声
        # Worley 边缘产生晶界
        edge_strength = np.clip(worley_multi * 2, 0, 1)
        # 使用 sigmoid 函数使边缘更锐利
        edge_sharp = 1 / (1 + np.exp(-10 * (edge_strength - 0.3)))

        # 晶粒内部的灰度变化
        grain_interior = worley_dist * 0.5 + perlin * 0.3 + ridge * 0.2

        # 组合：边界暗，内部有纹理
        combined = grain_interior * edge_sharp + (1 - edge_sharp) * 0.1

        # 添加高频细节
        combined = combined + detail

        # 全局对比度调整
        combined = np.clip(combined, 0, 1)

        # 直方图拉伸增强对比度
        p2, p98 = np.percentile(combined, [2, 98])
        if p98 > p2:
            combined = (combined - p2) / (p98 - p2)
            combined = np.clip(combined, 0, 1)

        return combined

    def _sharpen_image(self, img, strength=1.0):
        """
        使用 Unsharp Mask 锐化图像

        Args:
            img: 输入图像 (uint8 或 uint16)
            strength: 锐化强度 (0-2)

        Returns:
            锐化后的图像
        """
        if strength <= 0:
            return img

        # 高斯模糊
        if img.dtype == np.uint16:
            img_float = img.astype(np.float32) / 65535
        else:
            img_float = img.astype(np.float32) / 255

        blurred = cv2.GaussianBlur(img_float, (0, 0), 1.5)

        # Unsharp Mask: 原图 + (原图 - 模糊图) * 强度
        sharpened = img_float + strength * (img_float - blurred)
        sharpened = np.clip(sharpened, 0, 1)

        if img.dtype == np.uint16:
            return (sharpened * 65535).astype(np.uint16)
        else:
            return (sharpened * 255).astype(np.uint8)

    @cached_property
    def nav_perlin_img(self):
        """缓存的导航图，只计算一次"""
        if self._use_rust:
            # 使用 Rust 实现
            noise = self._rust_generator.generate_nav_image(self.nav_width, self.nav_height, self.nav_scale)
        else:
            # 使用 Python 实现
            aspect = self.nav_width / self.nav_height
            half_scale = self.nav_scale / 2

            xmin = -half_scale * aspect
            xmax = half_scale * aspect
            ymin = -half_scale
            ymax = half_scale

            noise = self._generate_perlin_image(xmin, xmax, ymin, ymax, self.nav_width, self.nav_height, mag_factor=100)

        # 转换为 uint8 BGR 图像
        img = (noise * 255).astype(np.uint8)
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        return img

    def get_nav_img(self):
        """获取导航图"""
        return self.nav_perlin_img

    def snap_jsonrpc(self, width: int, height: int, pixel_avg: int, frame_avg: int):
        """JSON-RPC 方式的拍照"""
        _, img = self._snap_perlin(width, height)
        return img

    def snap(self, req: ImageReq):
        """响应拍照请求"""
        width, height = 512, 512
        if req.img_size == EnumImageSize.S1024x1024:
            width, height = 1024, 1024
        elif req.img_size == EnumImageSize.S2048x2048:
            width, height = 2048, 2048

        return self._snap_perlin(width, height)

    def _snap_perlin(self, width, height):
        """
        根据当前位置和倍率生成拍照图像

        关键点：
        1. 使用 self.pos 获取当前台架位置
        2. 使用 self.scan_um 获取当前扫描场大小
        3. 生成对应区域的增强型噪声图像
        4. 高倍率时自动增加细节和锐化
        """
        # 获取当前扫描场大小 (um)
        s = self.scan_um
        x, y = self.pos

        # 计算当前视野的物理范围
        xmin = x - s / 2
        xmax = x + s / 2
        ymin = y - s / 2
        ymax = y + s / 2

        # 计算放大倍率因子 (相对于100倍)
        mag_factor = self.mag

        # 生成图像
        if self._use_rust:
            # 使用 Rust 实现 (高性能)
            noise = self._rust_generator.generate_image(xmin, xmax, ymin, ymax, width, height, mag_factor)
        else:
            # 使用 Python 实现
            noise = self._generate_perlin_image(xmin, xmax, ymin, ymax, width, height, mag_factor=mag_factor)

        # 垂直翻转以匹配坐标系
        noise = np.flipud(noise)

        # 根据配置的数据类型转换
        if self.img_dtype == np.uint16:
            img = (noise * 65535).astype(np.uint16)
            # 高倍率时锐化
            if mag_factor > 1000:
                sharpen_strength = min(1.5, 0.5 + np.log10(mag_factor / 1000) * 0.5)
                img = self._sharpen_image(img, strength=sharpen_strength)
            return EnumImgDepth.U16, img
        else:
            img = (noise * 255).astype(np.uint8)
            # 高倍率时锐化
            if mag_factor > 1000:
                sharpen_strength = min(1.5, 0.5 + np.log10(mag_factor / 1000) * 0.5)
                img = self._sharpen_image(img, strength=sharpen_strength)
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
        self.zem_type = app_cfg.get_param("virtual_zem.type", "perlin")  # mandelbrot, perlin, replay

        if self.zem_type == "mandelbrot":
            self.zem_dev = MandelbrotZem()
        elif self.zem_type == "perlin":
            self.zem_dev = PerlinZem()
        elif self.zem_type == "replay":
            task_json = app_cfg.get_param("virtual_zem.replay_zem.cap_roi_task", None)
            self.zem_dev = ReplayZem(Path(task_json))

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
        elif cmd == EnumCmd.SetHV:
            self._send(packet.addr, self.resp_set_hv(packet))
        elif cmd == EnumCmd.GetBseCfg:
            self._send(packet.addr, self.builder.build_get_bse_cfg(self.zem_dev.bse_cfg))
        elif cmd == EnumCmd.SetBseCfg:
            self._send(packet.addr, self.resp_set_bse_cfg(packet))
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

    def resp_set_hv(self, packet: ReqPacket):
        self.zem_dev.acc_v = packet.parse_hv() * 1000
        return self.builder.build_ack(EnumCmd.SetHV)

    def resp_set_bse_cfg(self, packet: ReqPacket):
        self.zem_dev.bse_cfg = packet.parse_bse_cfg()
        return self.builder.build_ack(EnumCmd.SetBseCfg)

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
