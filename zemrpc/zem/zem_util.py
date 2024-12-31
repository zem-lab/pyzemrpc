#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import shutil
from PIL import Image
from typing import Dict
from pathlib import Path
from loguru import logger
from PIL.PngImagePlugin import PngInfo

from jgb.util import time_util, cv_util

zem15_um2pulse = 8000 / 1000.0  # 脉冲与距离的比例关系, 8000个脉冲对应1000μm
zem15_pulse2um = 1 / zem15_um2pulse


def cvt_image_time_str(time_str):
    ts = time_util.cvt_str2ts(time_str)
    return time_util.cvt_ts2str(ts, time_util.FMT_DATETIME2)


def write_zem_img_with_meta(png: Path, img, meta: Dict[str, str]):
    cv_util.imwrite(png, img, debug=False)

    metadata = PngInfo()
    for k, v in meta.items():
        metadata.add_text(k, v)

    pil_obj = Image.open(png)
    pil_path = png.parent / f"{png.stem}_exif.png"
    pil_obj.save(pil_path, pnginfo=metadata)
    shutil.move(pil_path, png)
    logger.debug(f"write image: {png}")
