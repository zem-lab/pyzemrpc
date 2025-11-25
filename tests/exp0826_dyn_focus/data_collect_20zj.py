import tqdm
from jgb.util import loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api


def main():
    addr = "192.168.110.106", 61557
    loguru_util.init_log(app_cfg.log_dir)

    zem_api.handshake()

    zem_api.update_remote_addr(addr)
    zem_api.sync()

    outdir = app_cfg.outdir / "exp0826_dyn_focus/bse_x500_wd6.3mm"
    ob = 39374
    ob0, ob1, step = ob-1500, ob+500, 25
    obs = list(range(ob0, ob1, step))

    zem_api.set_ob(obs[0], wait_stable_ms=3000)
    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S2048x2048)

    for i, ob in tqdm.tqdm(enumerate(obs), total=len(obs)):
        zem_api.set_ob(ob, wait_stable_ms=500)
        zimg = zem_api.snap(snap_args=sa)
        zimg.dump(outdir/f'images/{i:04d}_{ob}.png')



if __name__ == "__main__":
    main()
