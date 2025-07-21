#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import cv2
import functools
import numpy as np
import collections
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple
from pydantic import Field, computed_field

from jgb.util import cv_util
from jgb.util.pydantic_util import DefaultModel, NumpyNDArray
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


class ImageMetaItem(Enum):
    Model = "Model"
    AccVoltage = "ACC Voltage"
    AvgLenth = "AvLenth"
    Date = "Date"
    Detector = "Detector"
    FieldSize = "Field Size(um)"
    FieldRotation = "Field Rotation(°)"
    FirmwareVersion = "FirmwareVersion"
    Pressure = "Pressure"
    OB = "OB"
    Zoom = "Zoom"
    Position = "Position"
    PyZemRpc = "PYZEMRPC"


class ImageMeta(DefaultModel):
    model: str
    ob: int
    mag: int
    avg_length: int
    date: str
    detector: str
    hv_info: HvInfo
    scan_info: ScanInfo
    stage_pos: StagePos
    zemrpc_version: str

    def to_png_meta(self):
        meta = {
            ImageMetaItem.Model: self.model,
            ImageMetaItem.AccVoltage: self.hv_info.kv(),
            ImageMetaItem.AvgLenth: self.avg_length,
            ImageMetaItem.Date: self.date,
            ImageMetaItem.Detector: self.detector,
            ImageMetaItem.FieldSize: self.scan_info.scan_um,
            ImageMetaItem.FieldRotation: self.scan_info.rot_degree,
            ImageMetaItem.FirmwareVersion: "UNK",
            ImageMetaItem.Pressure: "***",
            ImageMetaItem.OB: self.ob,
            ImageMetaItem.Zoom: self.mag,
            ImageMetaItem.Position: self.stage_pos,
            ImageMetaItem.PyZemRpc: self.zemrpc_version,
        }
        return meta


class ZemImage(DefaultModel):
    img: NumpyNDArray = Field(default=None)
    bounds: Bounds
    meta: ImageMeta

    def dump(self, png: Path, **kwargs):
        meta = self.meta.to_png_meta()
        if png.is_dir() or png.suffix == "":
            ts = zu.cvt_image_time_str(meta[ImageMetaItem.Date])
            png = png / f"{ts}.png"
        meta = {k.value: str(v) for k, v in meta.items()}
        meta.update(kwargs.get("meta", {}))
        zu.write_zem_img_with_meta(png, self.img, meta)

        img = normalize_with_drop(self.img)
        cv_util.imwrite(png.parent / f"{png.stem}.u8.png", img)


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


class IdxGen:
    def __init__(self, init: int = 0):
        self._idx = init

    @property
    def vpp(self):
        idx = self._idx
        self._idx += 1
        return idx

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, info) -> "IdxGen":
        if isinstance(v, int):
            return cls(v)
        return v

    @staticmethod
    def idx_gen_encode(obj: "IdxGen"):
        return obj._idx


class ZemState(Enum):
    Disable = "Disable"
    Idel = "Idel"
    RunningTask = "RunningTask"


class ZemException(Exception):
    class Code(Enum):
        ConnTimeout = 10001
        SvrError = 10002
        ReqError = 10003
        ApiNotReady = 10004

        UiOpError = 20001

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
