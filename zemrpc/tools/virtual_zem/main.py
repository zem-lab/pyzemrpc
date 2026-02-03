#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import argparse
import random
import uvicorn

from zemrpc.tools.virtual_zem.virtual_zem import zem
from zemrpc.tools.virtual_zem.jsonrpc_server import app


def main():
    parser = argparse.ArgumentParser(description="Virtual ZEM JSON-RPC Server")
    parser.add_argument("--port", "-p", type=int, default=61600, help="服务器端口号 (默认: 61600)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="服务器主机地址 (默认: 0.0.0.0)")
    args = parser.parse_args()

    random.seed(3366)
    try:
        zem.start()
        uvicorn.run("zemrpc.tools.virtual_zem.main:app", host=args.host, port=args.port, access_log=True)
    except KeyboardInterrupt:
        print("stop zem")
        zem.close()
        zem.join()


if __name__ == "__main__":
    main()
