#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com
"""
命令级别权限系统示例

演示 BASIC 和 ADVANCED 两种命令级别的权限控制：
- BASIC 级别：只读操作，可以随时调用
- ADVANCED 级别：写操作，需要先设置工作模式为 ADVANCED
"""

import sys
from loguru import logger

from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.conn.protocol import EnumCmd, EnumCmdLevel
from zemrpc.zem.models import ZemException


def main():
    addr = zem_api.device.socket.m.ip, 61557
    loguru_util.init_log(app_cfg.log_dir)
    logger.add(sys.stderr, level="DEBUG", colorize=True, backtrace=True, diagnose=True)
    zem_api.update_remote_addr(addr)

    # ========================================
    # 1. BASIC 模式下的默认行为
    # ========================================
    logger.info("=" * 60)
    logger.info("1. BASIC 模式下的默认行为")
    logger.info("=" * 60)

    # 获取当前工作模式（默认为 BASIC）
    current_mode = zem_api.device.get_work_mode()
    logger.info(f"当前工作模式: {current_mode.name}")

    # BASIC 命令 - 可以正常执行
    logger.info("执行 BASIC 命令 GetMag...")
    mag = zem_api.device.get_mag()
    logger.info(f"  ✓ 成功获取放大倍数: {mag}")

    logger.info("执行 BASIC 命令 GetHV...")
    hv = zem_api.device.get_hv()
    logger.info(f"  ✓ 成功获取加速电压: {hv} kV")

    # 尝试执行 ADVANCED 命令 - 会抛出异常
    logger.info("尝试执行 ADVANCED 命令 SetHV...")
    try:
        zem_api.device.set_hv(20)
        logger.info("  ✓ SetHV 成功（不应该到达这里）")
    except ZemException as e:
        logger.warning(f"  ✗ 预期的异常: {e}")

    # ========================================
    # 2. 切换到 ADVANCED 模式
    # ========================================
    logger.info("=" * 60)
    logger.info("2. 切换到 ADVANCED 模式")
    logger.info("=" * 60)

    logger.info("设置工作模式为 ADVANCED...")
    zem_api.device.set_work_mode(EnumCmdLevel.ADVANCED)
    current_mode = zem_api.device.get_work_mode()
    logger.info(f"当前工作模式: {current_mode.name}")

    # ADVANCED 模式下可以执行 ADVANCED 命令
    logger.info("执行 ADVANCED 命令 SetHV...")
    try:
        zem_api.device.set_hv(20)
        logger.info(f"  ✓ SetHV 成功")
        hv = zem_api.device.get_hv()
        logger.info(f"  当前加速电压: {hv} kV")
    except ZemException as e:
        logger.error(f"  ✗ 意外的异常: {e}")

    # ========================================
    # 3. 切换回 BASIC 模式
    # ========================================
    logger.info("=" * 60)
    logger.info("3. 切换回 BASIC 模式")
    logger.info("=" * 60)

    logger.info("设置工作模式为 BASIC...")
    zem_api.device.set_work_mode(EnumCmdLevel.BASIC)
    current_mode = zem_api.device.get_work_mode()
    logger.info(f"当前工作模式: {current_mode.name}")

    # BASIC 模式下 ADVANCED 命令再次失败
    logger.info("尝试执行 ADVANCED 命令 SetHV...")
    try:
        zem_api.device.set_hv(15)
        logger.info("  ✓ SetHV 成功（不应该到达这里）")
    except ZemException as e:
        logger.warning(f"  ✗ 预期的异常: {e}")

    logger.info("=" * 60)
    logger.info("示例结束")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
