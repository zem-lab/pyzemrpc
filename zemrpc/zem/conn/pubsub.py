#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import time
import threading
from loguru import logger
from typing import Dict, TypeVar, Generic

from zemrpc.zem.models import ZemException


R = TypeVar("R")
T = TypeVar("T")


class PubSub(Generic[R, T]):
    def __init__(self, request: R):
        self.request = request
        self.key = request.name

        self.event = threading.Event()
        self.result = None
        self.after_rcv = None
        self.is_timeout = False
        self._canceled = False

    def wait(self):
        st = time.time()
        while True:
            flat = self.event.wait(0.5)
            if flat:
                break
            if self._canceled:
                break
            if self.request.timeout < (time.time() - st):
                self.is_timeout = True
                break

    def timeout_handler(self):
        if self.is_timeout:
            raise ZemException.conn_timeout(f"命令超时: {self.key}")

    def notify_done(self):
        self.event.set()

    def pub(self, response: T):
        if response.name != self.key:
            return False

        self.result = response
        self.notify_done()
        return True


class PubSubMgr:
    def __init__(self):
        self._pubsubs = {}  # type: Dict[str, PubSub]
        self.mutex = threading.Lock()
        self._curr_key = None

    def sub(self, ps: PubSub):
        with self.mutex:
            self._pubsubs[ps.key] = ps
            self._curr_key = ps.key

    def pub(self, response):
        found = False
        with self.mutex:
            for k, v in self._pubsubs.items():
                if v.pub(response):
                    found = True
                    break
        return found

    def wait(self, ps: PubSub):
        ps.wait()

        with self.mutex:
            del self._pubsubs[ps.key]

        ps.timeout_handler()

        resp = ps.result
        ps.result = None
        return resp
