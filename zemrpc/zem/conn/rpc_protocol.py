#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import copy
import math
from pydantic import Field

from jgb.util import cv_util, idx_util
from jgb.util.pydantic_util import DefaultModel

from zemrpc.zem.models import Bounds, MetaItem, StagePos, valid_image_bounds
from zemrpc.zem.scan_relay import validate_scan_relay_mask
from zemrpc.zem.software_info import SoftwareInfo
from zemrpc.zem.optics import OpticsState
from zemrpc.zem.conn.protocol import validate_ast_dac, validate_optics_percentage


def _finite_number(value):
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


class Req(DefaultModel):
    jsonrpc: str = "2.0"
    idx: int = Field(default=-1, alias="id")
    method: str = Field(default="foo")
    params: list = Field(default=[])


class RpcResp(DefaultModel):
    jsonrpc: str = "2.0"
    idx: int = Field(default=-1, alias="id")
    result: dict = Field(default={})
    error: dict = Field(default={})


class Snap(Req):
    method: str = "Snap"


class RpcSnapResp(RpcResp):

    def success(self):
        return "img" in self.result

    def parse_image(self):
        img = cv_util.base64_to_cv2(self.result["img"])
        return img

    def parse_img_bounds(self):
        zem = self.result.get("meta", {}).get("zem", {})
        stage, imaging = zem.get("Stage", {}), zem.get("imaging", {})
        x, y = (_finite_number(stage.get(axis)) for axis in ("x", "y"))
        scan_um_width = _finite_number(imaging.get("ScanWidth"))
        scan_um_height = _finite_number(imaging.get("ScanHeight"))
        if None in (x, y, scan_um_width, scan_um_height) or scan_um_width <= 0 or scan_um_height <= 0:
            return None

        xmin = x - scan_um_width / 2
        xmax = x + scan_um_width / 2
        ymin = y - scan_um_height / 2
        ymax = y + scan_um_height / 2

        bounds = Bounds(xmin, ymin, xmax, ymax)
        return bounds if valid_image_bounds(bounds) else None

    def parse_img_meta(self, image_shape):
        """Use this capture's snapshot, including an explicitly unknown field."""
        snapshot = self.result.get("meta", {})
        zem = snapshot.get("zem", {})
        imaging, stage = zem.get("imaging", {}), zem.get("Stage", {})
        optics, hv = zem.get("ob", {}), zem.get("Hv", {})
        width, height = (_finite_number(imaging.get(k)) for k in ("ScanWidth", "ScanHeight"))
        calibrated = width is not None and height is not None and width > 0 and height > 0
        x, y = (_finite_number(stage.get(k)) for k in ("x", "y"))
        voltage = _finite_number(hv.get("RealAccVol"))
        return {
            MetaItem.Model: zem.get("Model"),
            MetaItem.Detector: imaging.get("Detector"),
            MetaItem.Magnification: _finite_number(imaging.get("Magnification")),
            MetaItem.AccVoltage: voltage,
            MetaItem.KV: None if voltage is None else voltage / 1000,
            MetaItem.OB: _finite_number(optics.get("ob")),
            MetaItem.WD: _finite_number(optics.get("wd")),
            MetaItem.Position: None if x is None or y is None else StagePos(x=x, y=y),
            MetaItem.FieldRotation: _finite_number(imaging.get("Rotation")),
            MetaItem.FieldSize: width if calibrated else 0.0,
            MetaItem.PixelSize: width / image_shape[1] if calibrated else 0.0,
            "pixel_size_y_um": height / image_shape[0] if calibrated else 0.0,
            "bounds": self.parse_img_bounds(),
            "field_size_available": calibrated,
            "metadata_source": "jsonrpc_capture",
            "rpc_meta": copy.deepcopy(snapshot),
        }


class Status(Req):
    method: str = "Status"


class RpcStatusResp(RpcResp):
    @property
    def state(self) -> dict:
        """Instrument returns fields directly; old VirtualZem wrapped them in zem."""
        return self.result.get("zem", self.result)

    @property
    def optics(self) -> OpticsState | None:
        value = self.state.get("optics")
        return None if value is None else OpticsState.model_validate(value)

    @property
    def scan_analog_zero(self) -> dict | None:
        from zemrpc.zem.scan_analog_zero import validate_state
        value = self.state.get("scan_analog_zero")
        return None if value is None else validate_state(value)

    @property
    def software(self) -> SoftwareInfo | None:
        """None means the remote server does not report software identity."""
        value = self.state.get("software")
        return None if value is None else SoftwareInfo.model_validate(value)

    @property
    def sn(self) -> str | None:
        """None means the remote server does not report the microscope SN."""
        value = self.state.get("sn")
        if value is not None and not isinstance(value, str):
            raise ValueError("Status sn must be a string")
        return value

    @property
    def scan_relay_mask(self) -> int | None:
        """None means an older server did not report the mask; never assume all enabled."""
        value = self.state.get("scan_relay_mask")
        return None if value is None else validate_scan_relay_mask(value)


class SnapParams(DefaultModel):
    width: int = Field(default=2048)
    height: int = Field(default=2048)
    pixel_avg: int = Field(default=7)
    frame_avg: int = Field(default=1)


class GetProtocolNg(Req):
    method: str = "get_protocol_ng"


class RespProtocolNg(DefaultModel):
    name: str = "ZEMRPC-NONE"
    url: str = ""

    def update_remote_host(self, host):
        import urllib.parse

        parsed = urllib.parse.urlparse(self.url)
        if ":" in parsed.netloc:
            netloc = ":".join([host, parsed.netloc.split(":")[-1]])
        else:
            netloc = host

        self.url = parsed._replace(netloc=netloc).geturl()
        return self

    def is_available(self):
        return self.name != "ZEMRPC-NONE"


class JsonRpcBuilder:
    def __init__(self):
        self.idx = idx_util.IdxGen()

    def _get_dict(self, req: Req):
        req.idx = self.idx.vpp
        return req.model_dump(by_alias=True)

    def snap(self, width: int = 2048, height: int = 2048, pixel_avg: int = 7, frame_avg: int = 1):
        req = Snap()
        req.params.append(SnapParams(width=width, height=height, pixel_avg=pixel_avg, frame_avg=frame_avg))
        return self._get_dict(req)

    def status(self):
        return self._get_dict(Status())

    def set_astigmatism(self, x: float | None = None, y: float | None = None):
        return self._optics_percent_request("SemSetAstigmatism", [x, y])

    def set_alignment(self, up_x=None, up_y=None, down_x=None, down_y=None):
        return self._optics_percent_request("SemSetAlignment", [up_x, up_y, down_x, down_y])

    def set_ast_dac(self, x: int, y: int):
        return self._get_dict(Req(method="SemSetAstigmatismDac", params=[validate_ast_dac(x), validate_ast_dac(y)]))

    def _optics_percent_request(self, method: str, values: list):
        if all(value is None for value in values):
            raise ValueError("Specify at least one optics axis")
        params = [None if value is None else validate_optics_percentage(value) for value in values]
        return self._get_dict(Req(method=method, params=params))

    def get_protocol_ng(self):
        return self._get_dict(GetProtocolNg())
