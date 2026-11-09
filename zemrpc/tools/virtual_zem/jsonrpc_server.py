#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com
import cv2
import base64
from pydantic import BaseModel
from fastapi import FastAPI, Request, Response
from jsonrpcserver import Result, Success, Error, dispatch, method

from zemrpc.tools.virtual_zem.virtual_zem import zem

app = FastAPI()


class ReqSnap(BaseModel):
    width: int
    height: int
    pixel_avg: int
    frame_avg: int


@method
def Ping() -> Result:
    return Success("Pong")


@method
def Snap(d: dict) -> Result:
    req = ReqSnap(**d)
    zem.zem_dev.is_video_alive = False
    img = zem.zem_dev.snap_jsonrpc(req.width, req.height, req.pixel_avg, req.frame_avg)
    retval, buffer = cv2.imencode(".png", img)

    result = {
        "img": base64.b64encode(buffer).decode(),
        "meta": {
            "imaging": {
                "type": "Raw",
                "width": req.width,
                "height": req.height,
                "dtype": {
                    "Value": 2,
                    "Depth": 2,
                    "IsInteger": True,
                    "Channels": 1,
                },
                "silk": {
                    "img": "",
                },
            },
            "zem": zem.zem_dev.get_zem_status(),
        },
    }
    return Success(result)


@method
def Status() -> Result:
    """返回系统状态信息，与Snap中的meta.zem内容相同"""
    return Success(zem.zem_dev.get_zem_status())


def _change_optics(change, *args):
    try:
        return Success(change(*args))
    except ValueError as exc:
        return Error(-32602, str(exc))
    except RuntimeError as exc:
        return Error(-32000, str(exc))


@method
def SemSetAstigmatism(x=None, y=None) -> Result:
    return _change_optics(zem.zem_dev.set_astigmatism, x, y)


@method
def SemSetAstigmatismDac(x, y) -> Result:
    return _change_optics(zem.zem_dev.set_ast_dac, x, y)


@method
def SemSetAlignment(up_x=None, up_y=None, down_x=None, down_y=None) -> Result:
    return _change_optics(zem.zem_dev.set_alignment, up_x, up_y, down_x, down_y)


@app.post("/")
async def index(request: Request):
    return Response(dispatch(await request.body()))


@app.post("/api/v1/jsonrpc")
async def index(request: Request):
    return Response(dispatch(await request.body()))
