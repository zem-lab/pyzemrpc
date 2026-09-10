#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import cv2
import time
import socket
import threading
from concurrent.futures import CancelledError
import numpy as np
from loguru import logger

from .protocol import ImageResp, EnumImgDepth, EnumCmd


class ImageTransferError(RuntimeError):
    """An image response cannot be decoded according to its advertised format."""


class ImgReceiver:
    def __init__(self, resp: ImageResp, img_received_callback, is_newbee: bool, *, deadline=None):
        self.resp = resp
        self.img_received_callback = img_received_callback
        self.is_newbee = is_newbee
        if resp.width <= 0 or resp.height <= 0:
            raise ImageTransferError(f"Invalid image dimensions: {resp.width}x{resp.height}")

        self.total = resp.width * resp.height
        self.dtype = np.uint8
        self.channel = 1

        if resp.req == EnumCmd.Snap.name:
            if resp.depth not in (EnumImgDepth.U8.value, EnumImgDepth.U16.value):
                raise ImageTransferError(f"Invalid Snap image depth: {resp.depth}")
            if resp.depth == EnumImgDepth.U16.value:
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
        self.deadline = deadline
        self.error = None
        self.received_bytes = 0
        self.phase = "pending"
        self._cancelled = threading.Event()
        self._socket_lock = threading.Lock()
        self._socket = None

    def transfer_details(self):
        return {"phase": self.phase, "endpoint": f"{self.resp.ip}:{self.resp.port}", "received_bytes": self.received_bytes, "expected_bytes": self.total}

    def cancel(self):
        """Interrupt local reception only; never send a device command."""
        self._cancelled.set()
        with self._socket_lock:
            client = self._socket
            self._socket = None
        if client is not None:
            try:
                client.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            client.close()

    def _remaining(self):
        if self._cancelled.is_set():
            raise CancelledError(f"{self.resp.req} image reception cancelled")
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"{self.resp.req} image reception timed out: {self.received_bytes}/{self.total} bytes ({self.phase})")
        return remaining

    def __call__(self):
        try:
            self._receive()
        except Exception as error:
            if self._cancelled.is_set():
                error = CancelledError(f"{self.resp.req} image reception cancelled")
            self.error = error
            error.image_transfer_details = self.transfer_details()
            logger.warning(f"Image reception failed: {error}; {error.image_transfer_details}")

        if self.img_received_callback:
            self.img_received_callback(self)

    def _receive(self):
        started = time.monotonic()
        own_deadline = started + self.timeout
        self.deadline = min(self.deadline, own_deadline) if self.deadline is not None else own_deadline
        buffer = bytearray()
        # The context manager also closes sockets when connect/recv/decode fails.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            with self._socket_lock:
                self._remaining()
                self._socket = client
            try:
                self.phase = "connect"
                logger.debug(f"Image connection starting: {self.transfer_details()}")
                client.settimeout(min(1.0, self._remaining()))
                client.connect((self.resp.ip, self.resp.port))
                self.phase = "receive"
                logger.debug(f"Image connection established: {self.transfer_details()}")
                while True:
                    client.settimeout(min(0.1, self._remaining()))
                    try:
                        recv_bytes = client.recv(4096)
                    except socket.timeout:
                        # The deadline is checked on every iteration, including
                        # silence; it never depends on the last byte's timestamp.
                        continue
                    buffer += recv_bytes
                    self.received_bytes = len(buffer)
                    self._remaining()
                    if not recv_bytes:
                        break
                    if self.received_bytes >= self.total:
                        break

                if not buffer:
                    raise ConnectionError(f"{self.resp.req} image connection closed: 0/{self.total} bytes")
                self.phase = "decode"
                if len(buffer) == self.total:
                    img = self.img_from_buffer(buffer)
                else:
                    # Retain the SDK's encoded-image fallback for legacy peers;
                    # a partial raw frame must not quietly become img=None.
                    try:
                        img = cv2.imdecode(np.frombuffer(buffer, dtype=np.uint8), flags=cv2.IMREAD_UNCHANGED)
                    except cv2.error as error:
                        raise ImageTransferError(f"{self.resp.req} image decode failed: {len(buffer)}/{self.total} bytes") from error
                    expected_shape = (self.resp.height, self.resp.width) if self.channel == 1 else (self.resp.height, self.resp.width, self.channel)
                    if img is None or img.shape != expected_shape or img.dtype != self.dtype:
                        raise ImageTransferError(f"{self.resp.req} invalid encoded image: {len(buffer)}/{self.total} bytes")
                self._remaining()
                self.img = img
                self.phase = "complete"
                logger.debug(f"Image reception completed in {time.monotonic() - started:.3f}s: {self.transfer_details()}")
            finally:
                with self._socket_lock:
                    if self._socket is client:
                        self._socket = None

    def img_from_buffer(self, buffer):
        img = np.frombuffer(buffer, dtype=self.dtype)
        if self.channel == 1:
            img = img.reshape((self.resp.height, self.resp.width))
            if self.is_newbee and self.dtype == np.uint16:
                img.byteswap(True)
        else:
            img = img.reshape((self.resp.height, self.resp.width, self.channel))
        return img
