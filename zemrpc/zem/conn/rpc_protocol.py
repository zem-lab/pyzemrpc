#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from pydantic import Field

from jgb.util import cv_util
from jgb.util.pydantic_util import DefaultModel

from zemrpc.zem.models import Bounds, IdxGen


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
        x = self.result["meta"]["zem"]["Stage"]["x"]
        y = self.result["meta"]["zem"]["Stage"]["y"]
        scan_um_width = self.result["meta"]["zem"]["imaging"]["ScanWidth"]
        scan_um_height = self.result["meta"]["zem"]["imaging"]["ScanHeight"]
        rot_degree = self.result["meta"]["zem"]["imaging"]["Rotation"]

        if isinstance(x, str) and x.lower() == "nan":
            x = 0

        if isinstance(y, str) and y.lower() == "nan":
            y = 0

        xmin = x - scan_um_width / 2
        xmax = x + scan_um_width / 2
        ymin = y - scan_um_height / 2
        ymax = y + scan_um_height / 2

        return Bounds(xmin, ymin, xmax, ymax)


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
        self.idx = IdxGen()

    def _get_dict(self, req: Req):
        req.idx = self.idx.vpp
        return req.model_dump(by_alias=True)

    def snap(self, width: int = 2048, height: int = 2048, pixel_avg: int = 7, frame_avg: int = 1):
        req = Snap()
        req.params.append(SnapParams(width=width, height=height, pixel_avg=pixel_avg, frame_avg=frame_avg))
        return self._get_dict(req)

    def get_protocol_ng(self):
        return self._get_dict(GetProtocolNg())
