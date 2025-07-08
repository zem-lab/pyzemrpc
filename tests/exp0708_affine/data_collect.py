from pathlib import Path
from jgb.util import json_util, loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api


def main():
    addr = "192.168.110.83", 61557
    loguru_util.init_log(app_cfg.log_dir)

    zem_api.handshake()

    zem_api.update_remote_addr(addr)
    zem_api.sync()

    outdir = app_cfg.outdir / "exp0708_affine/9kv"
    for avg in [5, 7]:
        for sz in [EnumImageSize.S512x512, EnumImageSize.S1024x1024, EnumImageSize.S2048x2048]:
            snap_args = SnapArgs(pixel_avg=avg, size=sz)
            zimg = zem_api.snap(snap_args=snap_args)
            for i in range(3):
                zimg.dump(outdir / f"{sz.width}_{avg}_{i:02d}.png")


if __name__ == "__main__":
    main()


"""
1. 手动修改加速电压
2. 调整电镜对焦到清晰
3. 修改脚本输出目录
4. 运行脚本采集图片

"""
