#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import random
import uvicorn

from zemrpc.tools.virtual_zem.virtual_zem import zem
from zemrpc.tools.virtual_zem.jsonrpc_server import app


def main():
    random.seed(3366)
    try:
        zem.start()
        uvicorn.run("zemrpc.tools.virtual_zem.main:app", host="0.0.0.0", port=61600, access_log=True)
    except KeyboardInterrupt:
        print("stop zem")
        zem.close()
        zem.join()


if __name__ == "__main__":
    main()
