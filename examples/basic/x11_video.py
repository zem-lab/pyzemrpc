#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
import time
import cv2
import numpy as np
import tqdm
from loguru import logger

from jgb.util import loguru_util, file_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api


def _to_bgr_u8(img: np.ndarray) -> np.ndarray:
    if img.dtype != np.uint8:
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
        img = img.astype(np.uint8, copy=False)

    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return np.ascontiguousarray(img)


def main():
    interval_s = 5.0
    duration_s = 500.0
    playback_fps = 10.0
    # addr = zem_api.device.socket.m.ip, 61557
    addr = "192.168.109.9", 61557

    loguru_util.init_log(app_cfg.log_dir)
    logger.add(sys.stderr, level="DEBUG", colorize=True, backtrace=True, diagnose=True)

    zem_api.handshake()
    zem_api.update_remote_addr(addr)
    zem_api.sync()

    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S512x512)

    out_dir = app_cfg.outdir / "data/videos"
    file_util.ensure_dir(out_dir)
    out_path = out_dir / f"snap_{time.strftime('%Y%m%d_%H%M%S')}.mp4"

    frame_count = max(1, int(duration_s / interval_s))
    fps = max(1.0, float(playback_fps))

    writer = None
    next_capture = time.monotonic()

    try:
        for idx in tqdm.tqdm(range(frame_count), desc="Capturing frames"):
            sleep_s = next_capture - time.monotonic()
            if sleep_s > 0:
                time.sleep(sleep_s)

            t0 = time.monotonic()
            zimg = zem_api.snap(snap_args=sa)
            frame = _to_bgr_u8(zimg.u8)

            if writer is None:
                height, width = frame.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height), True)
                if not writer.isOpened():
                    raise RuntimeError(f"VideoWriter open failed: {out_path}")

            writer.write(frame)

            elapsed = time.monotonic() - t0
            if elapsed >= interval_s:
                logger.warning("capture time ({:.3f}s) >= interval ({:.3f}s); increase interval", elapsed, interval_s)

            next_capture += interval_s
            logger.info("captured frame {}/{} in {:.3f}s", idx + 1, frame_count, elapsed)
    finally:
        if writer is not None:
            writer.release()
            logger.info("video saved: {}", out_path)


if __name__ == "__main__":
    main()
