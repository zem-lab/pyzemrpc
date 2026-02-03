#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 临时测试脚本 - 测试获取高压协议 (GetHV)

from jgb.util import loguru_util
from zemrpc import app_cfg
from zemrpc.zem.zem_rpc_device import ZemRpcDevice
from zemrpc.zem.conn.protocol import ProtocolBuilder, RespPacket


def main():
    loguru_util.init_log(app_cfg.log_dir)
    
    # 直接连接虚拟ZEM
    addr = ("192.168.111.206", 61557)
    print(f"直接连接虚拟ZEM: {addr}")
    
    # 创建设备实例并连接
    device = ZemRpcDevice(name="test")
    device.update_remote_addr(addr)
    device.ensure_connected()
    print("连接成功!")
    
    # === 测试获取高压协议 (GetHV) ===
    print("\n" + "=" * 50)
    print("测试: 获取高压协议 (GetHV)")
    print("=" * 50)
    
    result = device.get_hv()
    print("[OK] GetHV 协议测试成功!")
    print(f"  加速电压: {result.acc_v:.2f} V")
    print(f"  束流: {result.beam_i:.2f} uA")
    
    print("\n" + "=" * 50)
    print("[PASS] GetHV 协议测试通过!")
    print("=" * 50)


if __name__ == "__main__":
    main()
