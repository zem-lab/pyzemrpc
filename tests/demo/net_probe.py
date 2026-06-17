#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
OS 层 UDP 收包探针 —— 用于区分「防火墙丢包」与「strong-host 路由丢包」。

背景:
  GUI / jgb 持久 socket 发 GetModel 超时, Wireshark 能看到设备回包
  (109.9:544xx -> 110.82:62520), 但应用层 recvfrom 收不到。
  raw_recv_test 已证明: 即使停掉 worker、用裸阻塞 recvfrom 也收不到。
  => 丢包在 OS socket 层及以下, 不在 Python 收包链里。

本脚本刻意做到最简: 一个普通 UDP socket + 阻塞 recvfrom, 不走 jgb/DDS/framer。
通过「改一个系统变量、重跑一次」来定位:

  Run 1 (基线)            : 直接跑, 预期失败(复现)
  Run 2 (防火墙放行/关闭) : 若变成功 => 根因是 Windows 防火墙
  Run 3 (weak host 接收)  : 若变成功 => 根因是 strong-host 路由

用法 (在 pyzemrpc 的 .venv 里跑, 连着真机):
  .\.venv\Scripts\python.exe tests\demo\net_probe.py 192.168.109.9:61557
  .\.venv\Scripts\python.exe tests\demo\net_probe.py 192.168.109.9:61557 --bind 192.168.110.82
  .\.venv\Scripts\python.exe tests\demo\net_probe.py 192.168.109.9:61557 --bind-any
  .\.venv\Scripts\python.exe tests\demo\net_probe.py 192.168.109.9:61557 --count 10 --timeout 3
"""

import sys
import time
import socket
import argparse

from loguru import logger

from zemrpc.zem import ip_util
from zemrpc.zem.conn.protocol import ProtocolBuilder, patch_request_callback

try:
    sys.stderr.reconfigure(encoding="utf-8")  # 避免中文在 UTF-8 终端外乱码
except Exception:
    pass


# Windows: 尝试关闭 UDP "connection reset" (WSAECONNRESET) 行为。
# 否则之前对某端口的 sendto 引发的 ICMP port-unreachable 会让下一次 recvfrom
# 抛 10054。注: Python 的 socket.ioctl 不支持该控制码(会 ValueError), 此处仅尽力而为;
# 本 bug 症状是 timeout 而非 10054, 该项非根因, 设不上也无妨。
SIO_UDP_CONNRESET = 0x9800000C


def _disable_udp_connreset(sock: socket.socket):
    try:
        sock.ioctl(SIO_UDP_CONNRESET, False)
        logger.debug("SIO_UDP_CONNRESET disabled")
    except (AttributeError, OSError, ValueError) as e:
        logger.debug(f"SIO_UDP_CONNRESET not applied (ignored): {e}")


def _parse_target(s: str):
    host, _, port = s.partition(":")
    return host, int(port or 61557)


def _pick_bind_ip(target_ip: str) -> str:
    """选与目标同子网的本机 IP (优先按 netmask, 回退前缀启发式)。"""
    reals = [ip for ip in ip_util._get_all_local_ips()
             if not ip_util._is_loopback_ip(ip) and not ip_util._is_clash_fake_ip(ip)]
    matched = ip_util._find_local_ip_for_target(target_ip, reals)
    return matched or (reals[0] if reals else "0.0.0.0")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", help="设备地址 ip:port, 如 192.168.109.9:61557")
    ap.add_argument("--bind", default=None, help="绑定的本机 IP (默认: 自动选同子网网卡)")
    ap.add_argument("--bind-any", action="store_true", help="绑定 0.0.0.0 接收(embed 仍填同子网网卡 IP)")
    ap.add_argument("--embed", default=None, help="写进报文的回调 IP(默认=绑定 IP; bind-any 时=同子网网卡)")
    ap.add_argument("--count", type=int, default=5, help="发送次数")
    ap.add_argument("--timeout", type=float, default=3.0, help="每次 recvfrom 超时(秒)")
    args = ap.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="DEBUG", format="<level>{message}</level>")

    target = _parse_target(args.target)

    # 本机网卡概览
    logger.info("=== 本机网卡 ===")
    for ip, mask in ip_util._get_interface_subnets():
        same = ip_util._ip_in_same_subnet(ip, target[0], mask)
        logger.info(f"  {ip} / {mask}{'   <= 与目标同子网' if same else ''}")

    # 决定 bind 地址与 embed 地址
    subnet_ip = _pick_bind_ip(target[0])
    if args.bind_any:
        bind_ip = "0.0.0.0"
        embed_ip = args.embed or subnet_ip
    else:
        bind_ip = args.bind or subnet_ip
        embed_ip = args.embed or bind_ip

    logger.info("=== 探针配置 ===")
    logger.info(f"  目标设备 : {target[0]}:{target[1]}")
    logger.info(f"  bind     : {bind_ip}")
    logger.info(f"  embed IP : {embed_ip}  (写进报文, 设备据此回包)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    _disable_udp_connreset(sock)
    sock.bind((bind_ip, 0))
    lip, lport = sock.getsockname()
    embed_port = lport
    logger.info(f"  实际绑定 : {lip}:{lport}")
    logger.info(f"  embed    : {embed_ip}:{embed_port}")
    logger.info("  >>> Wireshark 过滤器:  udp && ip.addr == %s && ip.addr == %s" % (target[0], embed_ip))

    ok = 0
    for i in range(1, args.count + 1):
        data = patch_request_callback(ProtocolBuilder(embed_ip, embed_port).build_get_model().data, embed_ip, embed_port)
        sock.settimeout(args.timeout)
        t0 = time.time()
        try:
            sock.sendto(data, target)
            logger.debug(f"[{i}/{args.count}] send -> {target}: {data.decode()}")
            raw, addr = sock.recvfrom(4096)
            dt = (time.time() - t0) * 1000
            logger.success(f"[{i}/{args.count}] RECV from {addr} in {dt:.0f}ms: {raw.decode()}")
            ok += 1
        except socket.timeout:
            logger.error(f"[{i}/{args.count}] TIMEOUT {args.timeout}s — 无回包到达 socket (Wireshark 是否仍有回包?)")
        except OSError as e:
            logger.error(f"[{i}/{args.count}] OSError: {e!r}")
        time.sleep(0.2)

    sock.close()
    logger.info("=" * 50)
    if ok == args.count:
        logger.success(f"结果: {ok}/{args.count} 全部收到 —— 当前配置下收包正常")
    elif ok == 0:
        logger.error(f"结果: 0/{args.count} 全部超时 —— 复现丢包")
    else:
        logger.warning(f"结果: {ok}/{args.count} 部分收到 —— 间歇性丢包")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
