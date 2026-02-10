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

    x0 = zem_api.device.m.stage_pos.x
    y0 = zem_api.device.m.stage_pos.y
    dist = zem_api.device.m.scan_info.scan_um * 0.5
    logger.debug(f"stage pos: ({x0}, {y0}), dist: {dist}")

    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S512x512)
    outdir = app_cfg.app_home / "data/snap_3x3"
    for r in range(3):
        y = y0 + (r - 1) * dist
        for c in range(3):
            x = x0 - c * dist
            png = outdir / f"snap_{r}_{c}.png"
            zimg = zem_api.move_then_cap([x, y], stable_after_idle_ms=1000, snap_args=sa)
            zimg.dump(png, raw=False, pkl=False)


if __name__ == "__main__":
    main()
