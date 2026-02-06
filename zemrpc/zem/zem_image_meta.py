#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import math
from PIL import Image
from pathlib import Path
from loguru import logger
from pydantic import BaseModel, Field
import xml.etree.ElementTree as ET

from jgb.util import file_util


class ZemPngMeta(BaseModel):
    model: str = Field(default="")
    firmware_version: str = Field(default="")
    version: str = Field(default="")
    date: str = Field(default="")
    acc_voltage: int = 0
    avg_length: int = 0
    detector: str = Field(default="")
    field_size: float = 0  # um
    objective_lens: float = math.nan
    position: list[float] = Field(default=[])
    pressure: float = math.nan
    zoom: int = 0
    pixel_length: float = math.nan  # um
    significant_bit: int = -1
    significant_high: int = -1
    significant_low: int = -1
    title: str = Field(default="")
    note: str = Field(default="")
    metainfo_valid: bool = Field(default=False)

    def model_post_init(self, ctx):
        if 0 < self.significant_bit:
            self.significant_high = (self.significant_bit & 0xF0) >> 4
            self.significant_low = self.significant_bit & 0x0F


def read_zem15_metadata(img_path):
    im = Image.open(img_path)
    width, height = im.size[0], im.size[1]

    lut = {
        "acc_voltage": "ACC Voltage",
        "avg_length": "AvLenth",
        "date": "Date",
        "detector": "Detector",
        "field_size": "Field Size(um)",
        "firmware_version": "FirmwareVersion",
        "model": "Model",
        "position": "Position",
        "pressure": "Pressure",
        "zoom": "Zoom",
        "significant_bit": "Significant bit",
    }
    lut_rev = {v: k for k, v in lut.items()}

    d = {
        "acc_voltage": im.text[lut["acc_voltage"]],
        "avg_length": im.text[lut["avg_length"]],
        "date": im.text[lut["date"]],
        "detector": im.text[lut["detector"]],
        "field_size": im.text[lut["field_size"]],
        "firmware_version": im.text.get(lut["firmware_version"], ""),
        "model": im.text[lut["model"]],
        "zoom": im.text[lut["zoom"]],
    }
    if (key := lut["position"]) in im.text:
        d["position"] = list(im.text[key].split(","))
    if (key := lut["pressure"]) in im.text and im.text[key] != "***":
        d["pressure"] = im.text[key]
    if (key := lut["significant_bit"]) in im.text and im.text[key] != "***":
        d["significant_bit"] = ord(im.text[key])

    meta = ZemPngMeta(**d)
    meta.pixel_length = meta.field_size / width
    meta.metainfo_valid = True
    return meta


def read_zem20_metadata(img_path: Path):
    if img_path.name.endswith("png"):
        with Image.open(img_path) as im:
            xml = im.text["comment"]
    else:
        from PIL.TiffTags import TAGS

        with Image.open(img_path) as im:
            meta_dict = {TAGS[key]: im.tag[key] for key in im.tag.tagdata.keys()}
            xml = bytes(map(ord, meta_dict["ImageDescription"][0])).decode("utf8")

    root = ET.fromstring(xml)
    xml_meta = {}
    for child in root:
        xml_meta[child.tag] = child.text

    d = {
        "model": bytes(map(ord, xml_meta.get("Name", ""))).decode("utf8"),
        "version": xml_meta.get("Version", ""),
        "date": xml_meta.get("Date", ""),
        "detector": xml_meta.get("Detecter", ""),
        "position": list(xml_meta.get("Position", "").split(",")),
        "avg_length": xml_meta.get("AveragePoints", ""),
        "objective_lens": xml_meta.get("OB", "").replace("mm", ""),
        "zoom": xml_meta.get("Mag", "").strip("X"),
        "acc_voltage": xml_meta.get("HighVol", "")[:-2],
        "title": xml_meta.get("Title", ""),
        "note": xml_meta.get("Note", ""),
    }

    if d["title"] is None:
        d["title"] = ""

    if d["note"] is None:
        d["note"] = ""

    lut = {
        "significant_bit": "DataFlag",
        "pixel_length": "PixelLength",
    }

    if (key := lut["significant_bit"]) in xml_meta and xml_meta[key] != "***":
        d["significant_bit"] = int(xml_meta[key])
    if (key := lut["pixel_length"]) in xml_meta and xml_meta[key] != "***":
        if xml_meta[key].encode()[-2:] == b"\xbcm":
            s = bytes([ord(c) for c in xml_meta[key]]).decode()
            pl = s.replace("μm", "")
        else:
            pl = xml_meta[key].replace("μm", "")
        d["pixel_length"] = float(pl)

    meta = ZemPngMeta(**d)
    meta.metainfo_valid = True
    return meta


def read_zem20_metadata_for_tiff(img_path: Path):
    """
    专门用于处理 TIFF 格式的 Zem20 元数据读取，避免 Unicode 编码错误
    """
    from PIL.TiffTags import TAGS

    with Image.open(img_path) as im:
        # 安全地获取 ImageDescription
        image_desc = None

        # 尝试从 tag_v2 获取（推荐方式）
        if hasattr(im, "tag_v2") and 270 in im.tag_v2:
            image_desc = im.tag_v2[270]
        # 回退到 tag 方式
        elif hasattr(im, "tag") and 270 in im.tag:
            image_desc = im.tag[270]

        if image_desc is None:
            raise ValueError("无法从 TIFF 中获取 ImageDescription")

        # 根据类型安全地转换为字符串
        if isinstance(image_desc, str):
            xml = image_desc
        elif isinstance(image_desc, bytes):
            xml = image_desc.decode("utf-8", errors="ignore")
        elif isinstance(image_desc, (list, tuple)):
            # 某些 TIFF 可能将其存储为列表
            first_elem = image_desc[0] if len(image_desc) > 0 else ""
            if isinstance(first_elem, str):
                xml = first_elem
            elif isinstance(first_elem, bytes):
                xml = first_elem.decode("utf-8", errors="ignore")
            else:
                # 尝试直接转字符串
                xml = str(first_elem)
        else:
            xml = str(image_desc)

    # 解析 XML
    root = ET.fromstring(xml)
    xml_meta = {}
    for child in root:
        xml_meta[child.tag] = child.text

    # 构建字典，使用安全的字符串处理
    d = {
        "model": xml_meta.get("Name", ""),
        "version": xml_meta.get("Version", ""),
        "date": xml_meta.get("Date", ""),
        "detector": xml_meta.get("Detecter", ""),
        "position": list(xml_meta.get("Position", "").split(",")),
        "avg_length": xml_meta.get("AveragePoints", ""),
        "objective_lens": xml_meta.get("OB", "").replace("mm", ""),
        "zoom": xml_meta.get("Mag", "").strip("X"),
        "acc_voltage": xml_meta.get("HighVol", "")[:-2],
        "title": xml_meta.get("Title", ""),
        "note": xml_meta.get("Note", ""),
    }

    if d["title"] is None:
        d["title"] = ""

    if d["note"] is None:
        d["note"] = ""

    lut = {
        "significant_bit": "DataFlag",
        "pixel_length": "PixelLength",
    }

    if (key := lut["significant_bit"]) in xml_meta and xml_meta[key] != "***":
        d["significant_bit"] = int(xml_meta[key])
    if (key := lut["pixel_length"]) in xml_meta and xml_meta[key] != "***":
        import re

        pl_raw = xml_meta[key]
        # 移除各种可能的微米符号和单位，包括各种编码的 μ 符号
        pl = pl_raw.replace("μm", "").replace("µm", "").replace("Î¼m", "").replace("um", "")
        # 移除可能的其他非数字字符（保留小数点和负号）
        pl = re.sub(r"[^\d.-]", "", pl)
        d["pixel_length"] = float(pl)

    meta = ZemPngMeta(**d)
    meta.metainfo_valid = True
    return meta


def read_zem_meta(img_path) -> ZemPngMeta:
    img_path = file_util.resolve_filepath(img_path)
    try:
        return read_zem15_metadata(img_path)
    except Exception as e:
        logger.debug(f"读取NewBee元信息失败: {img_path}, 错误信息: {e}")

    try:
        return read_zem20_metadata(img_path)
    except Exception as e:
        logger.debug(f"读取Zem20元信息失败: {img_path}, 错误信息: {e}")

    # 针对 TIFF 格式的兜底尝试
    try:
        return read_zem20_metadata_for_tiff(img_path)
    except Exception as e:
        logger.debug(f"读取Zem20 TIFF元信息失败: {img_path}, 错误信息: {e}")

    return ZemPngMeta()


if __name__ == "__main__":
    import sys
    import io

    # 设置标准输出为 UTF-8 编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    img_path = Path(r"C:\Users\workpc\Desktop\20251118-145805\13预烧_4.tiff")
    infos = read_zem_meta(img_path)

    print("\n" + "=" * 60)
    print("完整的元信息:")
    print("=" * 60)
    print(f"模型 (model): {infos.model}")
    print(f"固件版本 (firmware_version): {infos.firmware_version}")
    print(f"版本 (version): {infos.version}")
    print(f"日期 (date): {infos.date}")
    print(f"加速电压 (acc_voltage): {infos.acc_voltage}")
    print(f"平均长度 (avg_length): {infos.avg_length}")
    print(f"探测器 (detector): {infos.detector}")
    print(f"视野大小 (field_size): {infos.field_size} um")
    print(f"物镜 (objective_lens): {infos.objective_lens}")
    print(f"位置 (position): {infos.position}")
    print(f"压力 (pressure): {infos.pressure}")
    print(f"放大倍数 (zoom): {infos.zoom}")
    print(f"像素长度 (pixel_length): {infos.pixel_length} um")
    print(f"有效位 (significant_bit): {infos.significant_bit}")
    print(f"有效位高 (significant_high): {infos.significant_high}")
    print(f"有效位低 (significant_low): {infos.significant_low}")
    print(f"标题 (title): {infos.title}")
    print(f"备注 (note): {infos.note}")
    print(f"元信息有效 (metainfo_valid): {infos.metainfo_valid}")
    print("=" * 60)
