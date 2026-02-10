#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
from loguru import logger
from matplotlib import pyplot as plt

from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api


def main():
    addr = "192.168.108.90", 61557

    loguru_util.init_log(app_cfg.log_dir)
    logger.add(sys.stderr, level="DEBUG", colorize=True, backtrace=True, diagnose=True)

    zem_api.handshake()

    zem_api.update_remote_addr(addr)
    zem_api.sync()

    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S512x512)
    zimg = zem_api.snap(snap_args=sa)
    plt.imshow(zimg.img, cmap="gray")
    plt.show()


if __name__ == "__main__":
    main()
