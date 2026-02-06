#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import json
import argparse
from pathlib import Path

from zemrpc.zem.zem_image_meta import read_zem_meta


def main():
    parser = argparse.ArgumentParser(prog="pyzemrpc_show_zimg_meta", description="Show ZEM image metadata.")
    parser.add_argument("-i", "--img", type=str, help="Path to image (png/tif).", required=True)
    parser.add_argument("-j", "--json", action="store_true", help="Output metadata as JSON.")
    args = parser.parse_args()

    img_path = Path(args.img)
    if not img_path.exists():
        parser.error(f"File not found: {img_path}")

    meta = read_zem_meta(img_path)
    if not meta.metainfo_valid:
        print(f"Warning: Metadata in file '{img_path}' is not valid.")
        return

    if args.json:
        print(json.dumps(meta.model_dump(), indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print("完整的元信息:")
        print("=" * 60)
        print(f"模型 (model): {meta.model}")
        print(f"固件版本 (firmware_version): {meta.firmware_version}")
        print(f"版本 (version): {meta.version}")
        print(f"日期 (date): {meta.date}")
        print(f"加速电压 (acc_voltage): {meta.acc_voltage}")
        print(f"平均长度 (avg_length): {meta.avg_length}")
        print(f"探测器 (detector): {meta.detector}")
        print(f"视野大小 (field_size): {meta.field_size} um")
        print(f"物镜 (objective_lens): {meta.objective_lens}")
        print(f"位置 (position): {meta.position}")
        print(f"压力 (pressure): {meta.pressure}")
        print(f"放大倍数 (zoom): {meta.zoom}")
        print(f"像素长度 (pixel_length): {meta.pixel_length} um")
        print(f"有效位 (significant_bit): {meta.significant_bit}")
        print(f"有效位高 (significant_high): {meta.significant_high}")
        print(f"有效位低 (significant_low): {meta.significant_low}")
        print(f"标题 (title): {meta.title}")
        print(f"备注 (note): {meta.note}")
        print(f"元信息有效 (metainfo_valid): {meta.metainfo_valid}")
        print("=" * 60)


if __name__ == "__main__":
    main()
