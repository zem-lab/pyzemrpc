#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import cv2
import addict
import functools
import numpy as np
import collections
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple
from functools import cached_property
from pydantic import Field, computed_field

from jgb.util import cv_util, pkl_util
from jgb.util.pydantic_util import DefaultModel, NumpyNDArray, AddictDict
from jgb.util.enum_util import EnumWithCode

from zemrpc.zem import zem_util as zu
from zemrpc.zem.zem_image_processor import normalize_with_drop

XY = collections.namedtuple("XY", ["x", "y"])
Bounds = collections.namedtuple("Bounds", ["xmin", "ymin", "xmax", "ymax"])


class NavParam(DefaultModel):
    p0x: float
    p0y: float
    cx: float
    cy: float


class StagePos(DefaultModel):
    x: float = Field(default=0)
    y: float = Field(default=0)
    z: float = Field(default=0)
    r: float = Field(default=0)
    t: float = Field(default=0)

    def __str__(self):
        return ",".join(map(str, [self.x, self.y]))

    def xy(self):
        return np.array([self.x, self.y])


class StageMoveDirection(Enum):
    Up = "up"
    Down = "down"
    Left = "left"
    Right = "right"


class ScanInfo(DefaultModel):
    scan_um: float
    rot_degree: float


class EnumBsePhase(Enum):
    OFF = 0  # 关闭
    ANTI = 1  # 反相
    IN = 2  # 同相
    INOUT = 3  # 同反相


class BseQuadrant(DefaultModel):
    bias: int = Field(default=0x7FF)
    phase: EnumBsePhase = Field(default=EnumBsePhase.ANTI)


class BseInfo(DefaultModel):
    q1: BseQuadrant = Field(default_factory=BseQuadrant)
    q2: BseQuadrant = Field(default_factory=BseQuadrant)
    q3: BseQuadrant = Field(default_factory=BseQuadrant)
    q4: BseQuadrant = Field(default_factory=BseQuadrant)

    @property
    def quadrants(self):
        return [self.q1, self.q2, self.q3, self.q4]


class FieldWithLoc(DefaultModel):
    scan_info: ScanInfo
    pos: StagePos

    def img_bounds(self) -> Bounds:
        sz = self.scan_info.scan_um / 2
        xmin = self.pos.x - sz
        xmax = self.pos.x + sz
        ymin = self.pos.y - sz
        ymax = self.pos.y + sz
        return Bounds(xmin, ymin, xmax, ymax)


class HvInfo(DefaultModel):
    acc_v: float
    beam_i: float

    @property
    def kv(self):
        return round(self.acc_v / 1000)


class EnumImageSize(EnumWithCode):
    S512x512 = "S512x512", 512, 512, 0, "512x512"
    S2048x2048 = "S2048x2048", 2048, 2048, 1, "2048x2048"
    S1024x1024 = "S1024x1024", 1024, 1024, 2, "1024x1024"
    S128xS128 = "S128x128", 128, 128, 3, "128x128"
    S1920x1440 = "S1920x1440", 1920, 1440, 4, "1920x1440"
    S3840x2880 = "S3840x2880", 3840, 2880, 5, "3840x2880"
    Unk = "Unk", -1, -1, -1, "Unk"

    @property
    def width(self):
        return self.value[1]

    @property
    def height(self):
        return self.value[2]

    @property
    def sz(self):
        return self.value[3]

    @property
    def name_cn(self):
        return self.value[-1]


class SnapArgs(DefaultModel):
    pixel_avg: int = Field(default=7)
    frame_avg: int = Field(default=1)
    size: EnumImageSize = Field(default=EnumImageSize.S512x512)
    save: bool = Field(default=False)


class MetaItem(EnumWithCode):
    Model = "Model", "型号"
    Date = "Date", "日期"
    KV = "KV", "加速电压(KV)"
    AccVoltage = "AccVoltage", "加速电压(V)"
    AvgLenth = "AvLenth", "点平均数"
    Detector = "Detector", "探测器"
    PixelSize = "PixelSize", "像素尺寸(nm)"
    FieldSize = "FieldSize", "场大小(um)"
    FieldRotation = "FieldRotation", "场旋转(°)"
    DigitalRotation = "DigitalRotation", "数字旋转(°)"
    AnalogRotation = "AnalogRotation", "模拟旋转(°)"
    ScanK = "ScanK", "扫描档位"
    ScanDA = "ScanDA", "扫描DA"
    AnalogBias = "AnalogBias", "模拟偏置"
    FirmwareVersion = "FirmwareVersion", "固件版本"
    Pressure = "Pressure", "真空"
    OB = "OB", "物镜值"
    WD = "WD", "工作距离(mm)"
    Magnification = "Magnification", "放大倍数"
    Position = "Position", "样品台位置(xyzrt)"
    PyZemRpc = "PyZemRpc", "PyZemRpc版本"

    @property
    def name(self):
        return self.value[0]


class ImageMeta:
    def __init__(self, meta=None):
        self.meta = {}
        self.update(meta)

    @property
    def m(self):
        return addict.Dict(self.meta)

    def set_kv(self, k: MetaItem, v):
        self.meta[k] = v
        return self

    def update(self, d):
        if d is None:
            return

        self.meta.update(d)
        return self

    def get_prop(self, key: str):
        if isinstance(key, str) and hasattr(self, key):
            return getattr(self, key)
        key = MetaItem.from_code(key) if isinstance(key, str) else key
        return self.meta.get(key, None)


class ZemImage(DefaultModel):
    pkl: Path = Field(default=None)
    img: NumpyNDArray = Field(default=None, exclude=True)
    meta: AddictDict = Field(default=None, exclude=True)

    def dump(self, png: Path, raw=True, u8=True, pkl=True, **kwargs):
        if png.is_dir() or png.suffix == "":
            ts = zu.cvt_image_time_str(self.meta[MetaItem.Date])
            png = png / f"{ts}.png"

        if raw:
            meta = self.meta2dict()
            meta.update(kwargs.get("meta", {}))
            zu.write_zem_img_with_meta(png, self.img, meta)

        if u8:
            cv_util.imwrite(png.parent / f"{png.stem}.u8.png", self.u8, debug=False)

        if pkl:
            self.pkl = png.with_suffix(".pkl")
            pkl_util.dump(self.pkl, self)

    def meta2dict(self):
        d = {}
        for k, v in self.meta.items():
            if isinstance(k, MetaItem):
                d[k.name] = str(v)
            elif isinstance(k, str):
                d[k] = str(v)
            else:
                d[str(k)] = str(v)
        return d

    @property
    def pixel_size(self):
        return self.meta.get(MetaItem.PixelSize, None)

    @property
    def bounds(self):
        return self.meta.get("bounds", None)

    @cached_property
    def u8(self):
        return normalize_with_drop(self.img)

    def calc_stage_xy(self, px, py):
        pixel_size = self.pixel_size
        if pixel_size is None:
            return None

        pos = self.meta.get(MetaItem.Position, None)
        if pos is None:
            return None

        h, w = self.img.shape[:2]
        dx, dy = -1 * (px - w / 2) * pixel_size, (py - h / 2) * pixel_size
        xy0 = pos.xy()
        return np.array([xy0[0] + dx, xy0[1] + dy])


class NavImage(DefaultModel):
    ctime: float = Field(default=None)
    shape: Tuple[int, int] = Field(default=None)
    nav_param: NavParam = Field(default=None)
    img: Optional[np.ndarray] = Field(default=None, exclude=True)

    @computed_field(return_type=Tuple[float, float, float, float])
    @functools.cached_property
    def bounds(self):
        h, w = self.shape
        xmin, xmax = np.array([-(w - self.nav_param.p0x), self.nav_param.p0x]) * abs(self.nav_param.cx)
        ymin, ymax = np.array([-self.nav_param.p0y, (h - self.nav_param.p0y)]) * abs(self.nav_param.cy)
        return xmin, ymin, xmax, ymax

    def dump_img(self, nav_img_path: Path):
        h, w, c = cv_util.cv2_hwc(self.img)
        if c == 4:
            bgr = cv2.cvtColor(self.img, cv2.COLOR_RGBA2BGRA)
        elif c == 3:
            bgr = cv2.cvtColor(self.img, cv2.COLOR_RGB2BGR)
        else:
            bgr = self.img
        cv_util.imwrite(nav_img_path, bgr, debug=False)

    def load_img(self, nav_img_path: Path):
        if not nav_img_path.exists():
            return

        img = cv_util.imread(nav_img_path)
        h, w, c = cv_util.cv2_hwc(img)
        if c == 4:
            self.img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        elif c == 3:
            self.img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        else:
            self.img = img

    def get_coord_px(self, xy):
        xmin, ymin, xmax, ymax = self.bounds
        px = abs((xy[0] - xmax) / self.nav_param.cx)
        py = abs((xy[1] - ymin) / self.nav_param.cy)
        return px, py

    def get_length_px(self, dist):
        r = (abs(self.nav_param.cx) + abs(self.nav_param.cy)) / 2
        return dist / r


class EnumBeamSize(EnumWithCode):
    Coarse = "Coarse", 0, "粗"
    Medium = "Medium", 1, "中"
    Fine = "Fine", 2, "细"
    SuperFine = "SuperFine", 3, "极细"
    Unk = "Unk", -1, "未知"

    @property
    def bs(self):
        return self.value[1]

    @property
    def name_cn(self):
        return self.value[-1]

    @classmethod
    def from_name_cn(cls, code):
        for e in cls:
            if e.value[-1] == code:
                return e
        return cls.Unk


class EnumCmdLevel(Enum):
    """命令访问级别"""
    BASIC = 0       # 基础命令，可以任意调用
    ADVANCED = 1    # 高级命令，需要设置工作模式


class ZemException(Exception):
    class Code(Enum):
        ConnTimeout = 10001
        SvrError = 10002
        ReqError = 10003
        ApiNotReady = 10004

        UiOpError = 20001
        PermissionDenied = 20002  # 命令权限被拒绝

    def __init__(self, msg, code):
        super().__init__(msg, code)
        self.msg = msg
        self.code = code

    @classmethod
    def conn_timeout(cls, msg):
        return cls(msg, ZemException.Code.ConnTimeout)

    @classmethod
    def request_error(cls, msg):
        return cls(msg, ZemException.Code.ReqError)

    @classmethod
    def zem_api_not_ready(cls, msg):
        return cls(msg, ZemException.Code.ApiNotReady)

    @classmethod
    def snap_ng_failed(cls, msg):
        return cls(msg, ZemException.Code.SvrError)

    @classmethod
    def permission_denied(cls, msg):
        return cls(msg, ZemException.Code.PermissionDenied)
