#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import time
import socket
import threading
from typing import Tuple
from loguru import logger

from jgb.util import os_util
from jgb.util.thread_util import SingleWorker


class UdpSocket:
    def __init__(self, name, *args, **kwargs):
        self.name = name
        self.ip = os_util.get_default_ip()
        self.port = 44444

        self.mutex = threading.Lock()
        self.rcv_worker = SingleWorker(f"UDP[{self.name}]-RCV", self._do_recv)
        self.data_rcv_handler = None

        self._socket = None  # type: socket.socket
        self._init_socket_lock = threading.Lock()
        self._last_write_time = 0
        self._last_read_time = 0
        self._min_send_interval = 0.1

    @property
    def sock(self):
        if self._socket is None:
            with self._init_socket_lock:
                self.init_socket()  # need double check
        return self._socket

    def init_socket(self):
        if self._socket is not None:
            return

        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        server.settimeout(0.1)
        server.bind((self.ip, 0))
        self.port = server.getsockname()[1]
        logger.debug(f"bind udp server @ {self.ip}:{self.port}")
        self._socket = server
        self.rcv_worker.start()

    def ensure_min_write_interval(self):
        now = time.time()
        mtime = max(self._last_write_time, self._last_read_time)
        if (delta := now - mtime) < self._min_send_interval:
            time.sleep(self._min_send_interval - delta)

    def send(self, data: bytes, addr: Tuple[str, int]):
        logger.debug(f"send to {addr}: {data.decode()}")
        with self.mutex:
            self.sock.sendto(data, addr)
            self._last_write_time = time.time()

    def broadcast(self, data: bytes):
        logger.debug(f"broadcast: {data.decode()}")
        self.sock.sendto(data, ("<broadcast>", 61557))

    def close(self):
        self.rcv_worker.stop()

    def _do_recv(self):
        try:
            data, addr = self.sock.recvfrom(4096)
            self._last_read_time = time.time()
            if self.data_rcv_handler:
                self.data_rcv_handler((self._last_read_time, addr, data))
        except socket.timeout:
            return
        except ConnectionResetError:
            logger.exception(f"recvfrom失败: connection reset")
            return
        except KeyboardInterrupt as e:
            print("stop udp sock")
            self.sock.close()
            return True
        except Exception as e:
            logger.exception(f"recvfrom失败: {repr(e)}")
            self.sock.close()
            return True
