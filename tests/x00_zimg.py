#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from jgb.util import pkl_util

from zemrpc.zem.models import ZemImage


def main():
    zimg = pkl_util.load("D:/workspace/2023_tribf_at_zeptools/0x00_repos/zem_hisi/data/appout/logs/tasks/hisi-20251010_155619/locate_roi/Roi0/img0.pkl")  # type: ZemImage
    print(zimg.calc_stage_xy(152.27405963, 433.22587314))


if __name__ == "__main__":
    main()
