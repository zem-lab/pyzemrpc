#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import time
import numpy as np

from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api


def main():
    addr = "192.168.110.106", 61557
    loguru_util.init_log(app_cfg.log_dir)

    zem_api.handshake()

    zem_api.update_remote_addr(addr)
    zem_api.sync()

    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S512x512)

    outdir = app_cfg.outdir / "exp1009_hisi/20251014_end_03"
    # mag_lst = list(range(500, 10000, 500))
    # mag_lst.extend(range(10000,30000, 5000))
    mag_lst = list(range(400, 1000, 100))
    for mag in mag_lst:
        zem_api.set_mag(mag)
        time.sleep(0.5)
        zimg = zem_api.snap(snap_args=sa)
        zimg.dump(outdir / f"{mag:06d}.png")


if __name__ == "__main__":
    main()
