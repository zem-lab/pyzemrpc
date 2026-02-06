#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from loguru import logger

from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.zem.zem_api import zem_api


def main():
    addr = "192.168.31.140", 61557
    loguru_util.init_log(app_cfg.log_dir)

    zem_api.handshake()
    zem_api.update_remote_addr(addr)
    zem_api.sync()

    zem_api.stage_xy_goto_closed((0, 0))
    logger.info(f"样品台坐标: {zem_api.device.get_stage_pos()}")


if __name__ == "__main__":
    main()
