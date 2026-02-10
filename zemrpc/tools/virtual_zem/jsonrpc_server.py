#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com
import cv2
import base64
from pydantic import BaseModel
from fastapi import FastAPI, Request, Response
from jsonrpcserver import Result, Success, dispatch, method

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
    result = {
        "zem": zem.zem_dev.get_zem_status(),
    }
    return Success(result)


@app.post("/")
async def index(request: Request):
    return Response(dispatch(await request.body()))


@app.post("/api/v1/jsonrpc")
async def index(request: Request):
    return Response(dispatch(await request.body()))
