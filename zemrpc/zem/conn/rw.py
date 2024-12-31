#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from loguru import logger
from typing import TypeVar, Generic

from jgb.util.thread_util import SingleConsumer

from zemrpc.zem.context import ctx
from .pubsub import PubSubMgr, PubSub

R = TypeVar("R")
T = TypeVar("T")


class ReadWriteService(Generic[R, T]):
    """
    将rw节点的基础读写事情(_data_rcv, _data_write)托管给ReadWriteService
    """

    def __init__(self, rw, data_rcv_handler, data_write_handler):
        super().__init__()
        self.name = f"RWS-{rw.name}"
        self.rw = rw
        self.data_rcv_handler = data_rcv_handler
        self.data_write_handler = ctx.async_wrapper(data_write_handler)

        self.pubsub_mgr = PubSubMgr()
        self.framer = SingleConsumer(self.name, data_rcv_handler)
        self.framer.start()

        self.rw.data_rcv_handler = self.framer.enqueue

    def pubsub_send(self, ps: PubSub) -> T:
        self.pubsub_mgr.sub(ps)
        self.rw.ensure_min_write_interval()
        self.data_write_handler(ps.request)
        resp = self.pubsub_mgr.wait(ps)
        return resp
