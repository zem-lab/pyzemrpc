#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from typing import Callable
from concurrent.futures import ThreadPoolExecutor
from qtpy.QtCore import QObject, Signal

from jgb.util.thread_util import PyThreadPoolTask

from zemrpc import app_cfg


class SignalBus(QObject):
    cmd_send = Signal(object)
    cmd_rcv = Signal(object)


class Context:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.logdir = app_cfg.log_dir
        self.signals = SignalBus()

    def async_wrapper(self, handler: Callable, exception_handler=None):
        return PyThreadPoolTask(self.executor, handler, exception_handler)


ctx = Context()
