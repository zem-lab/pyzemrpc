#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import argparse
import random
import socket
import uvicorn

from zemrpc.tools.virtual_zem.virtual_zem import zem
from zemrpc.tools.virtual_zem.jsonrpc_server import app


def _resolve_port(requested_port: int) -> int:
    if requested_port == 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("", 0))
            return s.getsockname()[1]
    return requested_port


def main():
    parser = argparse.ArgumentParser(description="Virtual ZEM JSON-RPC Server")
    parser.add_argument("--port", "-p", type=int, default=0, help="服务器端口号 (默认: 0, 自动选择空闲端口)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务器主机地址 (默认: 0.0.0.0)")
    args = parser.parse_args()

    port = _resolve_port(args.port)
    zem.zem_dev.jsonrpc_port = port
    random.seed(3366)
    try:
        zem.start()
        print(f"JSONRPC_PORT={port}")
        uvicorn.run(app, host=args.host, port=port, access_log=True)
    except KeyboardInterrupt:
        print("stop zem")
        zem.close()
        zem.join()


if __name__ == "__main__":
    main()
