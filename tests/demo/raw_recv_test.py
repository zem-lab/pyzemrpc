#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compare handshake-style temp socket vs persistent socket recv."""

import socket
import sys
from loguru import logger

from zemrpc.zem.conn.protocol import EnumCmd, ProtocolBuilder, patch_request_callback
from zemrpc.zem.zem_api import zem_api

TARGET = ("192.168.109.9", 61557)
LOCAL = "192.168.110.82"


def _send_recv(sock, label: str):
    lip, lport = sock.getsockname()
    b = ProtocolBuilder(lip, lport)
    data = patch_request_callback(b.build_get_model().data, lip, lport)
    logger.info(f"[{label}] send {sock.getsockname()} -> {TARGET}: {data.decode()}")
    sock.sendto(data, TARGET)
    sock.settimeout(3.0)
    try:
        raw, addr = sock.recvfrom(4096)
        logger.success(f"[{label}] RECV from {addr}: {raw.decode()}")
        return True
    except Exception as e:
        logger.error(f"[{label}] RECV failed: {e}")
        return False


def main():
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")

    zem_api.handshake()

    logger.info("=== temp socket (handshake style) ===")
    ts = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    ts.bind((LOCAL, 0))
    ok_temp = _send_recv(ts, "temp")
    ts.close()

    logger.info("=== persistent socket ===")
    zem_api.update_remote_addr(TARGET, sync=False)
    zem_api.device.socket.rcv_worker.stop()
    zem_api.device.socket.rcv_worker.thread = None
    ok_persist = _send_recv(zem_api.device.socket.sock, "persist")

    return 0 if ok_temp or ok_persist else 1


if __name__ == "__main__":
    raise SystemExit(main())
