#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多网卡 UDP 通信诊断脚本 — 配合 Wireshark 抓包使用。

Wireshark 过滤器建议:
  udp.port == 61557

用法:
  python tests/demo/wireshark_udp_test.py
  python tests/demo/wireshark_udp_test.py 192.168.109.9:61557
"""

import sys
import time

from loguru import logger

from zemrpc.zem import ip_util
from zemrpc.zem.conn.protocol import EnumCmd
from zemrpc.zem.zem_api import zem_api


def _print_network_info():
    logger.info("=== 本机网卡 IP ===")
    for ip in ip_util._get_all_local_ips():
        flags = []
        if ip_util._is_loopback_ip(ip):
            flags.append("loopback")
        if ip_util._is_clash_fake_ip(ip):
            flags.append("clash-fake")
        if ip_util._is_private_ip(ip):
            flags.append("private")
        logger.info(f"  {ip}  [{', '.join(flags) or 'other'}]")

    for ip, mask in ip_util._get_interface_subnets():
        logger.info(f"  subnet {ip} / {mask}")


def _parse_target(argv: list[str]):
    if not argv:
        return None
    host, _, port = argv[0].partition(":")
    return host, int(port or 61557)


def main():
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    _print_network_info()

    logger.info("=== Handshake (全网卡广播) ===")
    servers = zem_api.handshake()
    logger.info(f"发现 {len(servers)} 台设备: {servers}")

    iface_map = zem_api.device._iface_by_device
    for addr in servers:
        local = iface_map.get(addr, "(unknown)")
        logger.info(f"  设备 {addr[0]}:{addr[1]}  <- handshake 网卡 {local}")

    target = _parse_target(sys.argv[1:])
    if target is None:
        if not servers:
            logger.error("未发现设备，可指定地址: wireshark_udp_test.py 192.168.x.x:61557")
            return 1
        target = servers[0]
        logger.info(f"未指定目标，使用第一台: {target}")
    else:
        logger.info(f"使用指定目标: {target}")

    logger.info("=== update_remote_addr + sync ===")
    zem_api.update_remote_addr(target, sync=True)

    sock_ip, sock_port = zem_api.device.socket.sock.getsockname()
    logger.info(f"持久 socket: {sock_ip}:{sock_port}")
    logger.info(f"远程设备: {zem_api.device.m.addr}")

    logger.info("=== 手动发送 GetModel ===")
    resp = zem_api.send_cmd(EnumCmd.GetModel)
    logger.info(f"GetModel 响应: {resp.data_str if resp else None}")

    time.sleep(0.3)

    logger.info("=== 手动发送 StatusCheck ===")
    resp = zem_api.send_cmd(EnumCmd.StatusCheck)
    logger.info(f"StatusCheck 响应: {resp.data_str if resp else None}")

    logger.success("=== 测试完成，请在 Wireshark 中检查 udp.port==61557 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
