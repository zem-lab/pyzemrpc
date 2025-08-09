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
            "zem": {
                "Model": "Zem15C",
                "State": "VideoPlaying",
                "Hv": {
                    "RealAccVol": 45.9114,
                    "EmissCur": 0.3128,
                    "FilaR": 0.0625,
                    "GridVol": 31999.5117,
                },
                "BeamSz": {
                    "BeamType": "WideBeam",
                    "CompressA": 1650,
                    "CompressB": 1650,
                },
                "ob": {
                    "wd": 5.5,
                    "ob": 30000,
                },
                "Stage": {
                    "x": -zem.zem_dev.pos[0],
                    "y": -zem.zem_dev.pos[1],
                    "MotorIsStop": False,
                },
                "se": {
                    "CollectVol": 0.0,
                    "Gain": 0,
                    "Brightness": 51462,
                    "Contrast": 26535,
                },
                "bse": {
                    "ShiftRegisterData": 90,
                    "Brightness": 44862,
                    "Contrast": 21383,
                },
                "vac": {
                    "GunVacValue": 0.01,
                },
                "nav": {
                    "p0_x": 336.94,
                    "p0_y": 205.80,
                    "cx": 93.333,
                    "cy": 93.333,
                },
                "imaging": {
                    "Detector": "BSE",
                    "Magnification": zem.zem_dev.mag,
                    "SnapImageSize": "SizeOf2048",
                    "ScanWidth": zem.zem_dev.scan_um,
                    "ScanHeight": zem.zem_dev.scan_um,
                    "Rotation": zem.zem_dev.rot_degree,
                    "AverageMode": "AverageByPoints",
                    "SnapAvPointGear": "Gear7",
                    "AvFrameCount": 1,
                },
                "core": {"da_freq": 40_000_000},
            },
        },
    }
    return Success(result)


@app.post("/")
async def index(request: Request):
    return Response(dispatch(await request.body()))


@app.post("/api/v1/jsonrpc")
async def index(request: Request):
    return Response(dispatch(await request.body()))
