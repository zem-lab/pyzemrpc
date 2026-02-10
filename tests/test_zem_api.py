#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

"""
ZemAPI 单元测试

测试前提：
1. 虚拟电镜服务已启动 (python -m zemrpc.tools.virtual_zem.main)
2. 虚拟电镜服务默认监听在 192.168.31.140:61557
"""

import time
import pytest
import numpy as np
from loguru import logger

from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.models import StagePos, StageMoveDirection, SnapArgs, EnumImageSize, EnumCmdLevel


# 在所有测试前设置连接
@pytest.fixture(scope="session", autouse=True)
def setup_connection():
    """为所有测试设置连接"""
    logger.info("Setting up connection to virtual ZEM...")
    addr = zem_api.device.socket.m.ip, 61557
    zem_api.update_remote_addr(addr, sync=False)
    zem_api.device.set_work_mode(EnumCmdLevel.ADVANCED)
    logger.info("Connection setup complete")
    yield
    logger.info("Test session finished")


class TestZemApiConnection:
    """测试连接和握手功能"""

    def test_handshake(self):
        """测试握手连接"""
        logger.info("Testing handshake...")
        servers = zem_api.handshake()
        assert servers is not None
        assert isinstance(servers, list)
        logger.success(f"✓ Handshake successful: {servers}")

    def test_update_remote_addr(self):
        """测试更新远程地址"""
        logger.info("Testing update_remote_addr...")
        addr = zem_api.device.socket.m.ip, 61557
        zem_api.update_remote_addr(addr, sync=False)
        logger.success("✓ Remote address updated")

    def test_sync(self):
        """测试状态同步"""
        logger.info("Testing sync...")
        zem_api.sync()

        # 验证同步后的状态
        assert zem_api._init_sync_done is True
        assert zem_api.device.m.stage_pos is not None
        assert zem_api.device.m.scan_info is not None

        logger.success(f"✓ Sync completed")
        logger.info(f"  - Stage position: {zem_api.device.m.stage_pos}")
        logger.info(f"  - HV: {zem_api.device.m.hv_info.kv} kV")
        logger.info(f"  - Magnification: {zem_api.device.m.mag}x")


class TestZemApiHighVoltage:
    """测试高压和电子枪控制"""

    def test_set_hv(self):
        """测试设置高压"""
        logger.info("Testing set_hv...")

        # 确保已同步
        if not zem_api._init_sync_done:
            zem_api.sync()

        # 测试设置不同的高压值
        test_voltages = [5, 10, 15, 20]
        for kv in test_voltages:
            zem_api.set_hv(kv, wait=True)
            current_hv = zem_api.device.m.hv_info.kv
            assert abs(current_hv - kv) < 0.1, f"Expected {kv} kV, got {current_hv} kV"
            logger.success(f"✓ Set HV to {kv} kV")
            time.sleep(0.2)

    def test_set_gun_on(self):
        """测试开启电子枪"""
        logger.info("Testing gun on...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.set_gun(True, wait=True)
        logger.success("✓ Gun turned ON")
        time.sleep(0.5)

    def test_set_gun_off(self):
        """测试关闭电子枪"""
        logger.info("Testing gun off...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.set_gun(False, wait=True)
        logger.success("✓ Gun turned OFF")
        time.sleep(0.5)


class TestZemApiMagnification:
    """测试倍率控制"""

    def test_set_mag(self):
        """测试设置放大倍率"""
        logger.info("Testing set_mag...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        # 测试不同的倍率
        test_mags = [100, 500, 1000, 5000]
        for mag in test_mags:
            zem_api.set_mag(mag)
            current_mag = zem_api.device.m.mag
            assert current_mag == mag, f"Expected {mag}x, got {current_mag}x"
            logger.success(f"✓ Set magnification to {mag}x")
            time.sleep(0.2)

    def test_set_ob(self):
        """测试设置物镜电流"""
        logger.info("Testing set_ob...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        # 测试设置物镜电流
        test_ob_values = [100, 200, 300]
        for ob_value in test_ob_values:
            result = zem_api.set_ob(ob_value, wait_stable_ms=200)
            assert result is True
            logger.success(f"✓ Set OB to {ob_value}")


class TestZemApiStageControl:
    """测试载物台控制"""

    def test_stage_xy_goto(self):
        """测试载物台移动到指定位置"""
        logger.info("Testing stage_xy_goto...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        # 记录初始位置
        initial_pos = zem_api.device.m.stage_pos
        logger.info(f"Initial position: ({initial_pos.x:.2f}, {initial_pos.y:.2f})")

        # 测试移动到不同位置
        test_positions = [
            (100.0, 200.0),
            (150.0, 250.0),
            (200.0, 300.0),
        ]

        for x, y in test_positions:
            pos = zem_api.stage_xy_goto((x, y))
            assert pos is not None
            assert isinstance(pos, StagePos)
            # 给虚拟电镜一点时间更新位置
            time.sleep(0.2)
            current_pos = zem_api.device.get_stage_pos()
            assert abs(current_pos.x - x) < 1.0, f"X position mismatch: expected {x}, got {current_pos.x}"
            assert abs(current_pos.y - y) < 1.0, f"Y position mismatch: expected {y}, got {current_pos.y}"
            logger.success(f"✓ Moved to ({x:.2f}, {y:.2f})")

        # 返回初始位置
        zem_api.stage_xy_goto((initial_pos.x, initial_pos.y))
        logger.info("Returned to initial position")

    def test_stage_xy_goto_closed(self):
        """测试闭环载物台移动"""
        logger.info("Testing stage_xy_goto_closed...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        target_pos = (300.0, 400.0)
        zem_api.stage_xy_goto_closed(target_pos, stable_after_idle_ms=100)

        current_pos = zem_api.device.m.stage_pos
        assert abs(current_pos.x - target_pos[0]) < 1.0
        assert abs(current_pos.y - target_pos[1]) < 1.0
        logger.success(f"✓ Closed-loop move to ({target_pos[0]:.2f}, {target_pos[1]:.2f})")

    def test_stage_xy_rmove(self):
        """测试载物台相对移动"""
        logger.info("Testing stage_xy_rmove...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        # 先移动到一个已知位置
        zem_api.stage_xy_goto((500.0, 500.0))
        time.sleep(0.2)
        initial_pos = zem_api.device.get_stage_pos()

        # 测试向上移动
        move_distance = 50.0
        zem_api.stage_xy_rmove(StageMoveDirection.Up, move_distance)
        time.sleep(0.2)
        pos_after_up = zem_api.device.get_stage_pos()
        assert abs(pos_after_up.y - (initial_pos.y + move_distance)) < 1.0
        logger.success(f"✓ Moved UP by {move_distance}")

        # 测试向右移动
        zem_api.stage_xy_rmove(StageMoveDirection.Right, move_distance)
        time.sleep(0.2)
        pos_after_right = zem_api.device.get_stage_pos()
        assert abs(pos_after_right.x - (pos_after_up.x + move_distance)) < 1.0
        logger.success(f"✓ Moved RIGHT by {move_distance}")

        # 测试向下移动
        zem_api.stage_xy_rmove(StageMoveDirection.Down, move_distance)
        time.sleep(0.2)
        pos_after_down = zem_api.device.get_stage_pos()
        assert abs(pos_after_down.y - pos_after_right.y + move_distance) < 1.0
        logger.success(f"✓ Moved DOWN by {move_distance}")

        # 测试向左移动
        zem_api.stage_xy_rmove(StageMoveDirection.Left, move_distance)
        time.sleep(0.2)
        pos_after_left = zem_api.device.get_stage_pos()
        assert abs(pos_after_left.x - pos_after_down.x + move_distance) < 1.0
        logger.success(f"✓ Moved LEFT by {move_distance}")


class TestZemApiImageCapture:
    """测试图像采集功能"""

    def test_snap_default(self):
        """测试默认参数拍摄图像"""
        logger.info("Testing snap with default parameters...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        # 确保枪开启
        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)

        zem_img = zem_api.snap(save=False)

        assert zem_img is not None
        assert zem_img.img is not None
        assert isinstance(zem_img.img, np.ndarray)
        assert zem_img.meta is not None

        logger.success(f"✓ Captured image: shape={zem_img.img.shape}")

    def test_snap_different_sizes(self):
        """测试不同尺寸的图像采集"""
        logger.info("Testing snap with different image sizes...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)

        # 测试不同的图像尺寸
        test_sizes = [
            (EnumImageSize.S512x512, (512, 512)),
            (EnumImageSize.S1024x1024, (1024, 1024)),
            (EnumImageSize.S2048x2048, (2048, 2048)),
        ]

        for size_enum, expected_shape in test_sizes:
            snap_args = SnapArgs(size=size_enum, pixel_avg=1, frame_avg=1)
            zem_img = zem_api.snap(snap_args=snap_args, save=False)

            assert zem_img is not None
            assert zem_img.img.shape[:2] == expected_shape, f"Expected shape {expected_shape}, got {zem_img.img.shape[:2]}"
            logger.success(f"✓ Captured {expected_shape[0]}x{expected_shape[1]} image")
            time.sleep(0.2)

    def test_snap_with_averaging(self):
        """测试带平均的图像采集"""
        logger.info("Testing snap with averaging...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)

        # 测试像素平均
        snap_args = SnapArgs(size=EnumImageSize.S1024x1024, pixel_avg=2, frame_avg=2)
        zem_img = zem_api.snap(snap_args=snap_args, save=False)

        assert zem_img is not None
        assert zem_img.img is not None
        logger.success(f"✓ Captured image with pixel_avg=2, frame_avg=2")

    def test_move_then_cap(self):
        """测试移动后采集图像"""
        logger.info("Testing move_then_cap...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)

        target_pos = (600.0, 600.0)
        zem_img = zem_api.move_then_cap(target_pos, stable_after_idle_ms=100)

        assert zem_img is not None
        assert zem_img.img is not None

        # 验证位置
        current_pos = zem_api.device.m.stage_pos
        assert abs(current_pos.x - target_pos[0]) < 1.0
        assert abs(current_pos.y - target_pos[1]) < 1.0

        logger.success(f"✓ Moved to ({target_pos[0]:.2f}, {target_pos[1]:.2f}) and captured image")


class TestZemApiNavigation:
    """测试导航图像功能"""

    def test_get_nav_img(self):
        """测试获取导航图像"""
        logger.info("Testing get_nav_img...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        nav_img = zem_api.get_nav_img()

        if nav_img is not None:
            assert nav_img.img is not None
            assert isinstance(nav_img.img, np.ndarray)
            assert nav_img.nav_param is not None
            logger.success(f"✓ Got navigation image: shape={nav_img.img.shape}")
        else:
            logger.warning("⚠ Navigation image not available (may not be supported by virtual ZEM)")

    def test_sync_scan_field(self):
        """测试同步扫描场"""
        logger.info("Testing sync_scan_field...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.sync_scan_field()

        assert zem_api.device.m.mag is not None
        assert zem_api.device.m.scan_info is not None
        logger.success("✓ Scan field synchronized")

    def test_sync_stage_and_scan_field(self):
        """测试同步载物台和扫描场"""
        logger.info("Testing sync_stage_and_scan_field...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.sync_stage_and_scan_field()

        assert zem_api.device.m.stage_pos is not None
        assert zem_api.device.m.scan_info is not None
        logger.success("✓ Stage and scan field synchronized")


class TestZemApiAutofocus:
    """测试自动对焦功能"""

    def test_run_autofocus(self):
        """测试运行自动对焦"""
        logger.info("Testing run_autofocus...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        # 确保枪开启
        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)

        initial_ob = zem_api.device.get_ob()
        final_ob = zem_api.run_autofocus()

        assert final_ob is not None
        logger.success(f"✓ Autofocus completed: OB {initial_ob} -> {final_ob}")

    def test_mov_then_focus(self):
        """测试移动后对焦"""
        logger.info("Testing mov_then_focus...")

        if not zem_api._init_sync_done:
            zem_api.sync()

        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)

        target_pos = (700.0, 700.0)
        zem_api.mov_then_focus(target_pos, stable_after_idle_ms=100)

        # 验证位置
        current_pos = zem_api.device.m.stage_pos
        assert abs(current_pos.x - target_pos[0]) < 1.0
        assert abs(current_pos.y - target_pos[1]) < 1.0

        logger.success(f"✓ Moved to ({target_pos[0]:.2f}, {target_pos[1]:.2f}) and focused")


class TestZemApiIntegration:
    """集成测试：测试完整工作流程"""

    def test_full_workflow(self):
        """测试完整的工作流程"""
        logger.info("=" * 60)
        logger.info("Running full workflow integration test...")
        logger.info("=" * 60)

        # 1. 握手和同步
        logger.info("Step 1: Handshake and sync")
        zem_api.handshake()
        addr = zem_api.device.socket.m.ip, 61557
        zem_api.update_remote_addr(addr, sync=True)
        assert zem_api._init_sync_done is True
        logger.success("✓ Connected and synchronized")

        # 2. 开启高压和电子枪
        logger.info("\nStep 2: Turn on HV and gun")
        zem_api.set_hv(15, wait=True)
        zem_api.set_gun(True, wait=True)
        time.sleep(0.5)
        logger.success("✓ HV=15kV, Gun ON")

        # 3. 设置倍率
        logger.info("\nStep 3: Set magnification")
        zem_api.set_mag(1000)
        logger.success("✓ Magnification set to 1000x")

        # 4. 移动到指定位置
        logger.info("\nStep 4: Move stage to target position")
        target_pos = (800.0, 800.0)
        zem_api.stage_xy_goto_closed(target_pos, stable_after_idle_ms=200)
        current_pos = zem_api.device.m.stage_pos
        assert abs(current_pos.x - target_pos[0]) < 1.0
        assert abs(current_pos.y - target_pos[1]) < 1.0
        logger.success(f"✓ Moved to ({target_pos[0]:.2f}, {target_pos[1]:.2f})")

        # 5. 自动对焦
        logger.info("\nStep 5: Run autofocus")
        ob = zem_api.run_autofocus()
        logger.success(f"✓ Autofocus completed, OB={ob}")

        # 6. 采集高质量图像
        logger.info("\nStep 6: Capture high-quality image")
        snap_args = SnapArgs(size=EnumImageSize.S2048x2048, pixel_avg=2, frame_avg=2)
        zem_img = zem_api.snap(snap_args=snap_args, save=False)
        assert zem_img is not None
        assert zem_img.img.shape[:2] == (2048, 2048)
        logger.success(f"✓ Captured 2048x2048 image")

        # 7. 关闭电子枪
        logger.info("\nStep 7: Turn off gun")
        zem_api.set_gun(False, wait=True)
        logger.success("✓ Gun turned OFF")

        logger.info("=" * 60)
        logger.success("✓✓✓ Full workflow test PASSED ✓✓✓")
        logger.info("=" * 60)


if __name__ == "__main__":
    # 配置日志
    logger.info("=" * 60)
    logger.info("Starting ZemAPI Unit Tests")
    logger.info("=" * 60)

    # 运行pytest
    exit_code = pytest.main(
        [
            __file__,
            "-v",  # verbose output
            "-s",  # show print/log output
            "--tb=short",  # shorter traceback format
            "--color=yes",  # colored output
        ]
    )

    if exit_code == 0:
        logger.info("=" * 60)
        logger.success("✓✓✓ ALL TESTS PASSED ✓✓✓")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("✗✗✗ SOME TESTS FAILED ✗✗✗")
        logger.error("=" * 60)

    exit(exit_code)
