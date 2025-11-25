#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import numpy as np

from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api


def main():
    addr = "192.168.110.231", 61557
    loguru_util.init_log(app_cfg.log_dir)

    zem_api.handshake()

    zem_api.update_remote_addr(addr)
    zem_api.sync()

    # st = np.array([-2847.250, 5455.273])
    # ed = np.array([-3674.250, -6479.273])
    # step = 250
    st = np.array([-2825.750,5712.727])
    ed = np.array([-3699.500,-6628.849])
    step = 500
    
    dist = np.linalg.norm(ed - st)
    delta = step / dist * (ed - st)
    curr_pos, curr_dist = st, 0
    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S512x512)

    i = 0
    outdir = app_cfg.outdir / "exp1009_hisi/20251009_500"
    while curr_dist < dist:
        print(curr_pos, curr_dist)
        zimg = zem_api.move_then_cap((curr_pos[0], curr_pos[1]), 1000, snap_args=sa, raw=True)
        zimg.dump(outdir / f"{i:04d}.png")
        i += 1
        curr_pos = curr_pos + delta
        curr_dist = np.linalg.norm(curr_pos - st)


if __name__ == "__main__":
    main()
