#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import re
import json
import base64
import collections

from typing import Tuple
from loguru import logger
from enum import Enum
from dataclasses import dataclass

from jgb.util import math_util, json_util
from jgb.util.enum_util import EnumWithCode
from jgb.conn.pubsub import BaseRequest, BaseResponse

from zemrpc.zem.models import NavParam, StagePos, ScanInfo, HvInfo, EnumImageSize, EnumBeamSize, BseInfo, BseQuadrant, EnumBsePhase, EnumCmdLevel


# fmt: off
hi_lut = [  0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
            0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
            0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
            0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
            0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41,
            0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
            0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
            0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
            0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
            0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
            0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
            0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
            0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40,
            0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
            0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
            0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40, 0x00, 0xC1, 0x81, 0x40,
            0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0, 0x80, 0x41, 0x00, 0xC1,
            0x81, 0x40, 0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41,
            0x00, 0xC1, 0x81, 0x40, 0x01, 0xC0, 0x80, 0x41, 0x01, 0xC0,
            0x80, 0x41, 0x00, 0xC1, 0x81, 0x40]

lo_lut = [  0x00, 0xC0, 0xC1, 0x01, 0xC3, 0x03, 0x02, 0xC2, 0xC6, 0x06,
            0x07, 0xC7, 0x05, 0xC5, 0xC4, 0x04, 0xCC, 0x0C, 0x0D, 0xCD,
            0x0F, 0xCF, 0xCE, 0x0E, 0x0A, 0xCA, 0xCB, 0x0B, 0xC9, 0x09,
            0x08, 0xC8, 0xD8, 0x18, 0x19, 0xD9, 0x1B, 0xDB, 0xDA, 0x1A,
            0x1E, 0xDE, 0xDF, 0x1F, 0xDD, 0x1D, 0x1C, 0xDC, 0x14, 0xD4,
            0xD5, 0x15, 0xD7, 0x17, 0x16, 0xD6, 0xD2, 0x12, 0x13, 0xD3,
            0x11, 0xD1, 0xD0, 0x10, 0xF0, 0x30, 0x31, 0xF1, 0x33, 0xF3,
            0xF2, 0x32, 0x36, 0xF6, 0xF7, 0x37, 0xF5, 0x35, 0x34, 0xF4,
            0x3C, 0xFC, 0xFD, 0x3D, 0xFF, 0x3F, 0x3E, 0xFE, 0xFA, 0x3A,
            0x3B, 0xFB, 0x39, 0xF9, 0xF8, 0x38, 0x28, 0xE8, 0xE9, 0x29,
            0xEB, 0x2B, 0x2A, 0xEA, 0xEE, 0x2E, 0x2F, 0xEF, 0x2D, 0xED,
            0xEC, 0x2C, 0xE4, 0x24, 0x25, 0xE5, 0x27, 0xE7, 0xE6, 0x26,
            0x22, 0xE2, 0xE3, 0x23, 0xE1, 0x21, 0x20, 0xE0, 0xA0, 0x60,
            0x61, 0xA1, 0x63, 0xA3, 0xA2, 0x62, 0x66, 0xA6, 0xA7, 0x67,
            0xA5, 0x65, 0x64, 0xA4, 0x6C, 0xAC, 0xAD, 0x6D, 0xAF, 0x6F,
            0x6E, 0xAE, 0xAA, 0x6A, 0x6B, 0xAB, 0x69, 0xA9, 0xA8, 0x68,
            0x78, 0xB8, 0xB9, 0x79, 0xBB, 0x7B, 0x7A, 0xBA, 0xBE, 0x7E,
            0x7F, 0xBF, 0x7D, 0xBD, 0xBC, 0x7C, 0xB4, 0x74, 0x75, 0xB5,
            0x77, 0xB7, 0xB6, 0x76, 0x72, 0xB2, 0xB3, 0x73, 0xB1, 0x71,
            0x70, 0xB0, 0x50, 0x90, 0x91, 0x51, 0x93, 0x53, 0x52, 0x92,
            0x96, 0x56, 0x57, 0x97, 0x55, 0x95, 0x94, 0x54, 0x9C, 0x5C,
            0x5D, 0x9D, 0x5F, 0x9F, 0x9E, 0x5E, 0x5A, 0x9A, 0x9B, 0x5B,
            0x99, 0x59, 0x58, 0x98, 0x88, 0x48, 0x49, 0x89, 0x4B, 0x8B,
            0x8A, 0x4A, 0x4E, 0x8E, 0x8F, 0x4F, 0x8D, 0x4D, 0x4C, 0x8C,
            0x44, 0x84, 0x85, 0x45, 0x87, 0x47, 0x46, 0x86, 0x82, 0x42,
            0x43, 0x83, 0x41, 0x81, 0x80, 0x40]
# fmt: on


def calc_crc(data, st: int = 0, ed: int = -1):
    if ed == -1:
        ed = len(data)

    hi = 0xFF
    lo = 0xFF
    curr = 0x0000
    for i in range(st, ed):
        curr = hi ^ data[i]
        hi = lo ^ hi_lut[curr]
        lo = lo_lut[curr]
    return lo << 8 | hi


def append_crc(data):
    if type(data) == str:
        data = data.encode()

    crc = calc_crc(data)
    crc = f"{crc & 0xff:02X}{crc >>8:02X}"
    # crc = crc.to_bytes(2, byteorder="big", signed=False)
    # crc = f"{chr(crc >> 8)}{chr(crc & 0xFF)}"
    data += crc.encode()
    data += "%".encode()
    return data


class EnumErrorCode(EnumWithCode):
    NO_ERROR = 0, "无错误"
    ILLEGAL_PARAMETER = 1, "非法参数"
    EXEC_FAILURE = 2, "执行失败"
    SERVER_BUSY = 3, "服务器忙"
    CRC_FAILURE = 4, "校验失败"
    IMG_SVR_DOWN = 5, "图像传输服务未建立"
    Unk = -1


# fmt: off
class EnumCmd(Enum):
    InvalidCmd        = "InvalidCmd",                   False, 1_000,    EnumCmdLevel.BASIC,        "无效命令"
    Handshake         = "ZepTools handshake request",   False, 1_000,    EnumCmdLevel.BASIC,        "握手请求"
    HandshakeResp     = "ZepTools Handshake",           False, 1_000,    EnumCmdLevel.BASIC,        "握手请求回包"
    StatusCheck       = "StatusCheck",                  False, 100,      EnumCmdLevel.BASIC,        "获取服务端状态"
    ServerName        = "ServerName",                   False, 100,      EnumCmdLevel.BASIC,        "获取服务主机名称"
    GetImg            = "GetImg",                       False, 100,      EnumCmdLevel.BASIC,        "请求发送当前内存中的图片"
    VideoPlay         = "VideoPlay",                    False, 500,      EnumCmdLevel.BASIC,        "播放视频"
    IsVideoAlive      = "IsVideoAlive",                 False, 100,      EnumCmdLevel.BASIC,        "获取视频状态"
    Snap              = "Snap",                         True,  60_000,   EnumCmdLevel.BASIC,        "拍摄一张图片"
    SnapCancel        = "SnapCancel",                   False, 500,      EnumCmdLevel.BASIC,        "取消拍摄"
    GetWD             = "GetWD",                        False, 100,      EnumCmdLevel.BASIC,        "获取工作距离"
    SetWD             = "SetWD",                        True,  100,      EnumCmdLevel.BASIC,        "设置工作距离"
    GetCofPS          = "GetCofPS",                     False, 100,      EnumCmdLevel.BASIC,        "获取像素脉冲系数"
    GetEDChanel       = "GetEDChanel",                  False, 100,      EnumCmdLevel.BASIC,        "获取电子信号通道"
    SetEDChanel       = "SetEDChanel",                  True,  100,      EnumCmdLevel.ADVANCED,     "设置电子信号通道"
    SetRotation       = "SetRotation",                  True,  100,      EnumCmdLevel.BASIC,        "设置扫描场旋转"
    GetRotation       = "GetRotation",                  False, 100,      EnumCmdLevel.BASIC,        "获取扫描场旋转"
    GetOB             = "GetOB",                        False, 100,      EnumCmdLevel.BASIC,        "获取物镜值"
    SetOB             = "SetOB",                        True,  100,      EnumCmdLevel.BASIC,        "设置物镜值"
    GetAST            = "GetAST",                       False, 100,      EnumCmdLevel.BASIC,        "获取像散"
    SetAST            = "SetAST",                       True,  100,      EnumCmdLevel.ADVANCED,     "设置像散"
    GetImgSz          = "GetImgSz",                     False, 100,      EnumCmdLevel.BASIC,        "获取图片尺寸"
    SetImgSz          = "SetImgSz",                     True,  100,      EnumCmdLevel.BASIC,        "设置图片尺寸"
    GetWindowPos      = "GetWindowPos",                 False, 100,      EnumCmdLevel.BASIC,        "获取小窗位置"
    SetWindowPos      = "SetWindowPos",                 True,  100,      EnumCmdLevel.ADVANCED,     "设置小窗位置"
    SetContrast       = "SetContrast",                  True,  100,      EnumCmdLevel.ADVANCED,     "设置对比度"
    SetBrightness     = "SetBrightness",                True,  100,      EnumCmdLevel.ADVANCED,     "设置亮度"
    GetSECV           = "GetSECV",                      False, 100,      EnumCmdLevel.BASIC,        "获取SE收集电压"
    SetSECV           = "SetSECV",                      True,  10_000,   EnumCmdLevel.ADVANCED,     "设置SE收集电压"
    GetSEGain         = "GetSEGain",                    False, 100,      EnumCmdLevel.BASIC,        "获取SE增益"
    SetSEGain         = "SetSEGain",                    True,  100,      EnumCmdLevel.ADVANCED,     "设置SE增益"
    GetVAC            = "GetVAC",                       False, 100,      EnumCmdLevel.BASIC,        "获取真空度"
    GetMag            = "GetMag",                       False, 100,      EnumCmdLevel.BASIC,        "获取放大倍数"
    SetMag            = "SetMag",                       True,  100,      EnumCmdLevel.BASIC,        "设置放大倍数"
    GetBeamSz         = "GetBeamSz",                    False, 100,      EnumCmdLevel.BASIC,        "获取束斑大小"
    SetBeamSz         = "SetBeamSz",                    True,  100,      EnumCmdLevel.ADVANCED,     "设置束斑大小"
    SetIe             = "SetIe",                        True,  100,      EnumCmdLevel.ADVANCED,     "设置束流大小"
    GetHV             = "GetHV",                        False, 1_000,    EnumCmdLevel.BASIC,        "获取加速电压"
    SetHV             = "SetHV",                        True,  20_000,   EnumCmdLevel.ADVANCED,     "设置加速电压"
    SetHV_ON          = "SetHV_ON",                     False, 3_000,    EnumCmdLevel.ADVANCED,     "启动高压"
    SetHV_OFF         = "SetHV_OFF",                    False, 1_000,    EnumCmdLevel.ADVANCED,     "关闭高压"
    GetHvStatus       = "GetHvStatus",                  False, 300,      EnumCmdLevel.BASIC,        "获取高压状态"
    GetStagePos       = "GetStagePos",                  False, 100,      EnumCmdLevel.BASIC,        "获取视场坐标"
    SetStagePos       = "SetStagePos",                  True,  100,      EnumCmdLevel.BASIC,        "设置视场坐标"
    GetNavImg         = "GetNavImg",                    False, 30_000,   EnumCmdLevel.BASIC,        "获取导航图片"
    GetNavPara        = "GetNavPara",                   False, 100,      EnumCmdLevel.BASIC,        "获取光导系数"
    GetStgStatus      = "GetStgStatus",                 False, 200,      EnumCmdLevel.BASIC,        "获取样品台状态"
    GetScanInfo       = "GetScanInfo",                  False, 100,      EnumCmdLevel.BASIC,        "获取扫描场信息"
    GetPixelSz        = "GetPixelSz",                   False, 100,      EnumCmdLevel.BASIC,        "获取像素尺寸um"
    RequestOpenVac    = "RequestOpenVac",               False, 100,      EnumCmdLevel.ADVANCED,     "请求结束换样" 
    RequestCloseVac   = "RequestCloseVac",              False, 100,      EnumCmdLevel.ADVANCED,     "请求开始换样"
    SetStigX          = "SetStigX",                     True,  100,      EnumCmdLevel.ADVANCED,     "设置像散X"
    GetStigX          = "GetStigX",                     False, 100,      EnumCmdLevel.BASIC,        "获取像散X"
    SetStigY          = "SetStigY",                     True,  100,      EnumCmdLevel.ADVANCED,     "设置像散Y"
    GetStigY          = "GetStigY",                     False, 100,      EnumCmdLevel.BASIC,        "获取像散Y"
    GetGunVac         = "GetGunVac",                    False, 100,      EnumCmdLevel.BASIC,        "获取枪头真空"
    GetSamVac         = "GetSamVac",                    False, 100,      EnumCmdLevel.BASIC,        "获取样品仓真空"
    AutoFocus         = "AutoFocus",                    False, 100,      EnumCmdLevel.ADVANCED,     "自动对焦"
    CheckAutoFocus    = "CheckAutoFocus",               False, 100,      EnumCmdLevel.BASIC,        "自动对焦是否结束"
    SetStageXPos      = "SetStageXPos",                 True,  100,      EnumCmdLevel.ADVANCED,     "设置X坐标"
    GetStageXStatus   = "GetStageXStatus",              False, 100,      EnumCmdLevel.BASIC,        "获取X坐标"
    SetStageYPos      = "SetStageYPos",                 True,  100,      EnumCmdLevel.ADVANCED,     "设置Y坐标"
    GetStageYStatus   = "GetStageYStatus",              False, 100,      EnumCmdLevel.BASIC,        "获取Y坐标"
    SetStageZPos      = "SetStageZPos",                 True,  100,      EnumCmdLevel.ADVANCED,     "设置Z坐标"
    GetStageZStatus   = "GetStageZStatus",              False, 100,      EnumCmdLevel.BASIC,        "获取Z坐标"
    SetStageRPos      = "SetStageRPos",                 True,  100,      EnumCmdLevel.ADVANCED,     "设置R坐标"
    GetStageRStatus   = "GetStageRStatus",              False, 100,      EnumCmdLevel.BASIC,        "获取R坐标"
    SetStageTPos      = "SetStageTPos",                 False, 100,      EnumCmdLevel.ADVANCED,     "设置T坐标"
    GetStageTStatus   = "GetStageTStatus",              False, 100,      EnumCmdLevel.BASIC,        "获取T坐标"
    SetAutoSnapTask   = "SetAutoSnapTask",              True,  100,      EnumCmdLevel.ADVANCED,     "设置自动拍图任务"
    GetModel          = "GetModel",                     False, 100,      EnumCmdLevel.BASIC,        "获取型号"
    GetBseCfg         = "GetBseCfg",                    False, 1000,     EnumCmdLevel.BASIC,        "获取BSE探测器设置"
    SetBseCfg         = "SetBseCfg",                    True,  1000,     EnumCmdLevel.ADVANCED,     "设置BSE探测器设置"
    ZemRpc            = "ZemRpc",                       True,  100,      EnumCmdLevel.BASIC,        "ZemRpc"
    AllowOpenGun      = "AllowOpenGun",                 False, 100,      EnumCmdLevel.ADVANCED,     "允许打开枪头"
    IsOpenGun         = "IsOpenGun",                    False, 100,      EnumCmdLevel.BASIC,        "是否打开枪头"
    IsChangingSamp    = "IsChangingSamp",               False, 100,      EnumCmdLevel.BASIC,        "是否正在换样"
    GetSetHV          = "GetSetHV",                     False, 100,      EnumCmdLevel.BASIC,        "获取设置高压"
    GetCompressA      = "GetCompressA",                 False, 100,      EnumCmdLevel.BASIC,        "获取压缩A值"
    GetCompressB      = "GetCompressB",                 False, 100,      EnumCmdLevel.BASIC,        "获取压缩B值"
    OpenVAC           = "OpenVAC",                      False, 100,      EnumCmdLevel.ADVANCED,     "启动真空"
    ReleaseVAC        = "ReleaseVAC",                   False, 100,      EnumCmdLevel.ADVANCED,     "卸载真空"

    @property
    def cmd(self):
        return self.value[0]

    @property
    def need_args(self):
        return self.value[1]

    @property
    def timeout(self):
        return self.value[2]

    @property
    def cmd_level(self):
        return self.value[3]
    
    @property
    def name_cn(self):
        return self.value[-1]

# fmt: on


class EnumStatus(Enum):
    Idle = "Idle"
    Busy = "Busy"
    Other = "Other"  # 其他当前正在执行的命令


class EnumStageStatus(Enum):
    Idle = 1  # 1: 脱机, 已到达指定位置
    Running = 0  # 0: 激活，运行中
    Unknown = 999


class EnumHvStatus(Enum):
    Close = 0  # 0: 高压关闭
    Open = 1  # 1: 高压开启
    Changing = 2  # 2: 高压正在开启或关闭


class EnumAutofocusStatus(Enum):
    Idle = 0
    Running = 1
    Unknown = 999


class EnumVideoStatus(Enum):
    Idle = 0
    Running = 1
    Unknown = 999


class EnumEDChannel(Enum):
    BSE = 0
    SE = 1


class EnumImgDepth(Enum):
    U8 = 0
    U16 = 7


class Request(BaseRequest):
    def __init__(self, cmd: EnumCmd, data: bytes):
        super().__init__()

        self.cmd = cmd
        self.data = data

    @property
    def timeout_ms(self):
        return self.cmd.timeout

    def get_pubsub_key(self) -> str:
        return self.cmd.name

    def __repr__(self) -> str:
        if self.cmd == EnumCmd.ZemRpc:
            parts = self.data.decode().split(",")
            payload = base64.b64decode(parts[0][8:]).decode()
            return f"{parts[0][:8]}:{payload},{','.join(parts[1:])}"
        else:
            return self.data.decode()


class ProtocolBuilder:
    def __init__(self, ip="", port=-1):
        self.ip = ip
        self.port = port

    def build_handshake_request(self) -> Request:
        return Request(EnumCmd.Handshake, self._build(f"{EnumCmd.Handshake.cmd}"))

    def build_set_stage_pos(self, x: float, y: float):
        return self.build_set(EnumCmd.SetStagePos, f"{x},{y}")

    def build_get_stage_pos(self):
        return self.build_get(EnumCmd.GetStagePos)

    def build_get_stage_status(self):
        return self.build_get(EnumCmd.GetStgStatus)

    def build_get_hv_status(self):
        return self.build_get(EnumCmd.GetHvStatus)

    def build_set_hv(self, value: int):
        # value in Voltage
        return self.build_set(EnumCmd.SetHV, f"{value}")

    def build_get_bse_cfg(self):
        return self.build_get(EnumCmd.GetBseCfg)

    def build_set_bse_cfg(self, cfg: BseInfo):
        v = [f"{q.phase.value},{q.bias}" for q in cfg.quadrants]
        return self.build_set(EnumCmd.SetBseCfg, ",".join(v))

    def build_gun_on(self):
        return self.build_get(EnumCmd.SetHV_ON)

    def build_gun_off(self):
        return self.build_get(EnumCmd.SetHV_OFF)

    def build_get_hv(self):
        return self.build_get(EnumCmd.GetHV)

    def build_set_ie(self, value: int):
        # value in uA
        return self.build_set(EnumCmd.SetIe, f"{value}")

    def build_set_beam_size(self, sz: EnumBeamSize):
        return self.build_set(EnumCmd.SetBeamSz, f"{sz.bs()}")

    def build_get_beam_size(self):
        return self.build_get(EnumCmd.GetBeamSz)

    def build_set_mag(self, value: int):
        # value in 500~150000
        return self.build_set(EnumCmd.SetMag, f"{value}")

    def build_get_mag(self):
        return self.build_get(EnumCmd.GetMag)

    def build_get_vac(self):
        return self.build_get(EnumCmd.GetVAC)

    def build_set_se_gain(self, value: float):
        # value in 0~100
        return self.build_set(EnumCmd.SetSEGain, f"{value}")

    def build_get_se_gain(self):
        return self.build_get(EnumCmd.GetSEGain)

    def build_set_se_cv(self, value: int):
        # value in voltage, 0, 3000~7000
        # 0-3000不响应
        return self.build_set(EnumCmd.SetSECV, f"{value}")

    def build_get_se_cv(self):
        return self.build_get(EnumCmd.GetSECV)

    def build_set_brightness(self, value: float):
        # value in 0 ~ 100
        return self.build_set(EnumCmd.SetBrightness, f"{value}")

    def build_set_contrast(self, value: float):
        # value in 0 ~ 100
        return self.build_set(EnumCmd.SetContrast, f"{value}")

    def build_get_ob(self):
        return self.build_get(EnumCmd.GetOB)

    def build_set_ob(self, value: int):
        value = math_util.clamp(value, 2, 65535)
        return self.build_set(EnumCmd.SetOB, f"{value}")

    def build_set_ob_pct(self, value):
        value = math_util.clamp(value, 2 / 65535 * 100, 100)
        return self.build_set(EnumCmd.SetOB, f"{value:.6f}")

    def build_set_wd(self, value: float):
        value = math_util.clamp(value, 3, 50)
        return self.build_set(EnumCmd.SetWD, f"{value:.6f}")

    def build_set_rotation(self, degree: int):
        # value in degree
        return self.build_set(EnumCmd.SetRotation, f"{degree}")

    def build_set_ed_channel(self, c: EnumEDChannel):
        return self.build_set(EnumCmd.SetEDChanel, f"{c.value}")

    def build_get_ed_channel(self):
        return self.build_get(EnumCmd.GetEDChanel)

    def build_get_wd(self):
        return self.build_get(EnumCmd.GetWD)

    def build_snap(self, avg, use_frame_avg, avg_frame_num, img_size: EnumImageSize):
        # avg 1-7, 使用帧平均时建议使用2，不使用帧平均时建议使用7
        return self.build_set(EnumCmd.Snap, f"{use_frame_avg},{avg},{avg_frame_num},{img_size.sz}")

    def build_snap_simple(self, pavg=2, sz=EnumImageSize.S512x512):
        return self.build_snap(pavg, 0, 0, sz)

    def build_snap_cancel(self):
        return self.build_get(EnumCmd.SnapCancel)

    def build_set_auto_snap_task(self, csv_file):
        return self.build_set(EnumCmd.SetAutoSnapTask, str(csv_file))

    def build_autofocus(self):
        return self.build_get(EnumCmd.AutoFocus)

    def build_check_autofocus(self):
        return self.build_get(EnumCmd.CheckAutoFocus)

    def build_is_video_alive(self):
        return self.build_get(EnumCmd.IsVideoAlive)

    def build_video_play(self):
        return self.build_get(EnumCmd.VideoPlay)

    def build_get_img(self):
        return self.build_get(EnumCmd.GetImg)

    def build_status_check(self):
        return self.build_get(EnumCmd.StatusCheck)

    def build_server_name(self):
        return self.build_get(EnumCmd.ServerName)

    def build_get_model(self):
        return self.build_get(EnumCmd.GetModel)

    def build_get_nav_img(self):
        return self.build_get(EnumCmd.GetNavImg)

    def build_get_nav_para(self):
        return self.build_get(EnumCmd.GetNavPara)

    def build_get_scan_info(self):
        return self.build_get(EnumCmd.GetScanInfo)

    def build_get_stg_status(self):
        return self.build_get(EnumCmd.GetStgStatus)

    def build_json_rpc(self, req: dict):
        data = base64.b64encode(json_util.dumps(req).encode()).decode()
        return self.build_set(EnumCmd.ZemRpc, data)

    def build_get_allow_open_gun(self):
        return self.build_get(EnumCmd.AllowOpenGun)

    def build_get_is_open_gun(self):
        return self.build_get(EnumCmd.IsOpenGun)

    def build_get_is_changing_samp(self):
        return self.build_get(EnumCmd.IsChangingSamp)

    def build_get_set_hv(self):
        return self.build_get(EnumCmd.GetSetHV)

    def build_set_compress_a(self, value: float):
        # value: 0-100 百分比
        value = math_util.clamp(value, 0, 100)
        return self.build_set(EnumCmd.SetCompressA, f"{value:.2f}")

    def build_get_compress_a(self):
        return self.build_get(EnumCmd.GetCompressA)

    def build_set_compress_b(self, value: float):
        # value: 0-100 百分比
        value = math_util.clamp(value, 0, 100)
        return self.build_set(EnumCmd.SetCompressB, f"{value:.2f}")

    def build_get_compress_b(self):
        return self.build_get(EnumCmd.GetCompressB)

    def build_open_vac(self):
        return self.build_get(EnumCmd.OpenVAC)

    def build_release_vac(self):
        return self.build_get(EnumCmd.ReleaseVAC)

    def append_ip_port(self, message):
        message = "$" + message
        message += f",{self.ip}:{self.port},"
        return message

    def _build(self, message):
        return append_crc(self.append_ip_port(message))

    def build_get(self, cmd: EnumCmd):
        return self.build_set(cmd, "")

    def build_set(self, cmd: EnumCmd, args: str) -> Request:
        if cmd == EnumCmd.SetAutoSnapTask:
            args = base64.b64encode(args.encode())
        return Request(cmd, self._build(f"{cmd.cmd}:{args}"))


@dataclass
class ImageResp:
    req: str
    svr_name: str
    ip: str
    port: int
    depth: int
    width: int
    height: int


@dataclass
class NavImgResp:
    ip: str
    port: int
    depth: int
    width: int
    height: int


@dataclass
class ImageReq:
    use_frame_avg: int
    avg: int
    avg_frame_num: int
    img_size: EnumImageSize


class ReqPacket:
    _re_snap = re.compile(r"\$(.*):(.*),(.*),(.*),(.*),(.*):(.*),(.*)%")
    _re_1 = re.compile(r"\$(.*):(.*),(.*):(.*),(.*)%")
    _re_2 = re.compile(r"\$(.*):(.*),(.*),(.*):(.*),(.*)%")

    def __init__(self, addr, data):
        self.addr = addr
        self.data = data
        self.data_str = data.decode()

    def __repr__(self) -> str:
        return f"{self.addr} -> [{self.data_str}]"

    def parse_cmd(self) -> EnumCmd:
        if self.data_str[1:].startswith(EnumCmd.Handshake.cmd):
            return EnumCmd.Handshake
        cmd_str = self.data_str.split(":")[0][1:]
        return EnumCmd[cmd_str]

    def _parse_1(self):
        req, val, ip, port, crc = self._re_1.findall(self.data_str)[0]
        return val

    def _parse_2(self):
        req, val1, val2, ip, port, crc = self._re_2.findall(self.data_str)[0]
        return val1, val2

    def parse_mag(self) -> int:
        return int(self._parse_1())

    def parse_ob(self) -> int:
        return int(self._parse_1())

    def parse_hv(self) -> int:
        return int(self._parse_1())

    def parse_bse_cfg(self) -> BseInfo:
        data = list(map(int, self._parse_1().split(",")))
        quadrants = [BseQuadrant() for _ in range(4)]
        for i in range(4):
            quadrants[i].phase = EnumBsePhase(data[i * 2])
            quadrants[i].bias = data[i * 2 + 1]
        q1, q2, q3, q4 = quadrants
        return BseInfo(q1=q1, q2=q2, q3=q3, q4=q4)

    def parse_rotation(self) -> int:
        return int(self._parse_1())

    def parse_snap(self) -> ImageReq:
        req, use_frame_avg, avg, avg_frame_num, img_size, ip, port, crc = self._re_snap.findall(self.data_str)[0]
        return ImageReq(int(use_frame_avg), int(avg), int(avg_frame_num), EnumImageSize.from_code(int(img_size)))

    def parse_stage_pos(self):
        x, y = self._parse_2()
        return float(x), float(y)

    def parse_json_rpc(self):
        s = base64.b64decode(self._parse_1()).decode()
        logger.debug(f"ZemRpc: {s}")
        return json.loads(s)


class RespPacket(BaseResponse):
    _re_img = re.compile(r"\$(.*):(.*):(.*):(\d+),(\d+),(\d+),(\d+),(.*)%")
    _re_1 = re.compile(r"\$(.*):(.*),(.*)%")
    _re_2 = re.compile(r"\$(.*):(.*),(.*),(.*)%")
    _re_nav_para = re.compile(r"\$GetNavPara:(.*),(.*),(.*),(.*),(.*)%")
    _re_scan_info = re.compile(r"\$GetScanInfo:(.*),(.*),(.*)%")

    def __init__(self, data: bytes):
        super().__init__()

        self.data = data
        self.data_str = data.decode()

        self.cmd = self.parse_cmd()

        self.extra = {}

    def __repr__(self) -> str:
        if self.cmd == EnumCmd.ZemRpc and not self.is_error():
            parts = self.data_str.split(",")
            payload = base64.b64decode(parts[0][8:]).decode()
            return f"{parts[0][:8]}:{payload},{','.join(parts[1:])}"
        else:
            return self.data_str

    def get_pubsub_key(self) -> str:
        return self.cmd.name

    def parse_cmd(self) -> EnumCmd:
        if self.data_str[1:].lower().startswith(EnumCmd.HandshakeResp.cmd.lower()):
            return EnumCmd.HandshakeResp
        cmd_str = self.data_str.split(":")[0][1:]
        return EnumCmd[cmd_str]

    def parse_status(self) -> str:
        return self.data_str.split(":")[1].split(",")[0]

    def parse_model(self):
        if self.is_invalid_cmd():
            return "ZEM18"
        return self._parse_1()

    def is_idle_status(self):
        return self.parse_status() == EnumStatus.Idle.value

    def is_ack(self):
        return "Acknowledge" in self.data_str

    def is_ack_ok(self):
        return self.is_ack() and "Error Code:0" in self.data_str

    def is_invalid_cmd(self):
        return "invalidcommand" in self.data_str.lower().replace(" ", "")

    def is_error(self):
        s = "Error Code:"
        i = self.data_str.find(s)
        if 0 <= i:
            ec = EnumErrorCode.from_code(int(self.data_str[i + len(s) :].split(",")[0]))
            if ec == EnumErrorCode.NO_ERROR:
                return False
            return ec
        else:
            return False

    def parse_ip_port(self) -> Tuple[str, int]:
        ipport = self.data_str.split(",")[-2]
        ip, port = ipport.split(":")
        if "addr" in self.extra:
            ip = self.extra["addr"][0]
        return ip, int(port)

    def parse_stage_pos(self) -> StagePos:
        x, y = self._parse_2()
        return StagePos(x=float(x), y=float(y))

    def parse_stage_status(self) -> EnumStageStatus:
        return EnumStageStatus(int(self._parse_1()))

    def parse_autofocus_status(self) -> EnumAutofocusStatus:
        return EnumAutofocusStatus(int(self._parse_1()))

    def parse_video_status(self) -> EnumVideoStatus:
        return EnumVideoStatus(int(self._parse_1()))

    def parse_hv(self):
        v, i = self._parse_2()
        return HvInfo(acc_v=float(v), beam_i=float(i))

    def parse_hv_status(self) -> EnumHvStatus:
        return EnumHvStatus(int(self._parse_1()))

    def parse_bse_cfg(self) -> BseInfo:
        data = list(map(int, self._parse_1().split(",")))
        quadrants = [BseQuadrant() for _ in range(4)]
        for i in range(4):
            quadrants[i].phase = EnumBsePhase(data[i * 2])
            quadrants[i].bias = data[i * 2 + 1]
        q1, q2, q3, q4 = quadrants
        return BseInfo(q1=q1, q2=q2, q3=q3, q4=q4)

    def parse_wd(self) -> float:
        return float(self._parse_1())

    def parse_ob(self) -> int:
        return int(self._parse_1())

    def parse_mag(self) -> float:
        return float(self._parse_1())

    def parse_beam_size(self) -> EnumBeamSize:
        return EnumBeamSize.from_code(int(self._parse_1()))

    def parse_img_resp(self) -> ImageResp:
        try:
            req, svr_name, ip, port, depth, width, height, crc = self._re_img.findall(self.data_str)[0]
            if "addr" in self.extra:
                ip = self.extra["addr"][0]
            return ImageResp(req, svr_name, ip, int(port), int(depth), int(width), int(height))
        except Exception:
            logger.error(f"解析ImageResp失败: {self.data_str}")
            return None

    def parse_nav_para(self) -> NavParam:
        p0x, p0y, cx, cy, crc = self._re_nav_para.findall(self.data_str)[0]
        return NavParam(p0x=float(p0x), p0y=float(p0y), cx=float(cx), cy=float(cy))

    def parse_scan_info(self) -> ScanInfo:
        try:
            scan_um, rot_degree, crc = self._re_scan_info.findall(self.data_str)[0]
            return ScanInfo(scan_um=float(scan_um), rot_degree=float(rot_degree))
        except Exception:
            logger.debug(f"解析失败: {self.data_str}")
            return None

    def parse_json_rpc(self):
        if self.is_invalid_cmd() or self.is_error():
            return {"jsonrpc": "2.0", "error": "invalid command", "id": -1}
        s = base64.b64decode(self._parse_1()).decode()
        logger.debug(f"ZemRpc: {s}")
        return json.loads(s)

    def parse_allow_open_gun(self) -> bool:
        return self._parse_1().lower() == "true"

    def parse_is_open_gun(self) -> bool:
        return self._parse_1().lower() == "true"

    def parse_is_changing_samp(self) -> bool:
        return self._parse_1().lower() == "true"

    def parse_set_hv(self) -> float:
        return float(self._parse_1())

    def parse_compress_a(self) -> float:
        return float(self._parse_1())

    def parse_compress_b(self) -> float:
        return float(self._parse_1())

    def _parse_1(self):
        req, val, crc = self._re_1.findall(self.data_str)[0]
        return val

    def _parse_2(self):
        req, val1, val2, crc = self._re_2.findall(self.data_str)[0]
        return val1, val2


def find_packets(data):
    packets = []
    consumed = 0
    while len(data) > 0:
        st, ed = -1, -1
        for i, c in enumerate(data):
            if c == ord("$"):
                st = i
            elif st != -1 and c == ord("%"):
                ed = i
                packets.append(data[st : ed + 1])
                data = data[ed + 1 :]
                consumed += ed
                break
        if ed == -1:
            break
    return packets, consumed


class ProtocolParser:
    def __init__(self):
        self.buffer = collections.defaultdict(lambda: bytes())

    def append(self, addr, data):
        self.buffer[addr] += data
        packets, consumed = find_packets(self.buffer[addr])
        if packets:
            self.buffer[addr] = self.buffer[addr][consumed + 1 :]
        return packets
