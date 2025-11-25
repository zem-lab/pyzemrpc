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

    st = np.array([-4074.750, -15634.750])
    ed = np.array([-3887.750, -4377.750])
    dist = np.linalg.norm(ed - st)
    n = 46
    step = dist / (n - 1)
    print(step)

    delta = step / dist * (ed - st)
    curr_pos, curr_dist = st, 0
    sa = SnapArgs(pixel_avg=6, size=EnumImageSize.S512x512)

    mag = 1000
    i = 0
    outdir = app_cfg.outdir / f"exp1024_hisi/20251024_{mag}"
    while curr_dist < dist:
        zem_api.set_mag(mag)
        zem_api.stage_xy_goto_closed((curr_pos[0], curr_pos[1]))
        zimg = zem_api.move_then_cap((curr_pos[0], curr_pos[1]), 500, snap_args=sa, raw=True)
        zimg.dump(outdir / f"{i:04d}.png")
        i += 1
        curr_pos = curr_pos + delta
        curr_dist = np.linalg.norm(curr_pos - st)


if __name__ == "__main__":
    # main()
    st = np.array([-3884.750, -4380.750])
    ed = np.array([-3885.250, -4354.250])
    ed1 = np.array([-3884.500, -4340.500])
    print(np.linalg.norm(st - ed))
    print(np.linalg.norm(ed1 - ed))
