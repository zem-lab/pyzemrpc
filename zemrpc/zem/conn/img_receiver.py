#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import cv2
import time
import socket
import numpy as np
from loguru import logger

from .protocol import ImageResp, EnumImgDepth, EnumCmd


class ImgReceiver:
    def __init__(self, resp: ImageResp, img_received_callback, is_newbee: bool):
        self.resp = resp
        self.img_received_callback = img_received_callback
        self.is_newbee = is_newbee

        self.total = resp.width * resp.height
        self.dtype = np.uint8
        self.channel = 1

        if resp.req == EnumCmd.Snap.name:
            if EnumImgDepth(resp.depth) == EnumImgDepth.U16:
                self.total *= 2
                self.dtype = np.uint16
        else:
            if resp.depth == 24:
                self.total *= 3
                self.channel = 3
            elif resp.depth == 32:
                self.total *= 4
                self.channel = 4

        self.img = None
        self.timeout = 60  # seconds

    def __call__(self):
        try:
            self._receive()
        except Exception:
            logger.exception(f"error when receive image: {self.resp}")

        if self.img_received_callback:
            self.img_received_callback(self)

    def _receive(self):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(1)
        client.connect((self.resp.ip, self.resp.port))
        buffer = bytearray()
        ctime = time.time()
        mtime = time.time()
        while True:
            try:
                recv_bytes = client.recv(4096)
                if len(recv_bytes) == 0:
                    break
                buffer += recv_bytes
                mtime = time.time()
                if self.total <= len(buffer):
                    logger.debug(f"图像数据接收完成: {len(buffer)} bytes cost: {mtime-ctime:.3f}s")
                    break
            except socket.timeout:
                continue
            except Exception as e:
                logger.exception(f"图像接收失败: {repr(e)}")
                break
            if self.timeout < mtime - ctime:
                logger.warning(f"图像接收超时: {mtime}-{ctime}={mtime-ctime:.3f}s")
                break
        client.close()

        if len(buffer) == self.total:
            img = self.img_from_buffer(buffer)
        else:
            img = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), flags=cv2.IMREAD_UNCHANGED)

        self.img = img

    def img_from_buffer(self, buffer):
        img = np.frombuffer(buffer, dtype=self.dtype)
        if self.channel == 1:
            img = img.reshape((self.resp.height, self.resp.width))
            if self.is_newbee and self.dtype == np.uint16:
                img.byteswap(True)
        else:
            img = img.reshape((self.resp.height, self.resp.width, self.channel))
        return img
