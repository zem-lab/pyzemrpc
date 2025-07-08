
import tqdm
import time

from jgb.util import json_util, loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api



def main():
    loguru_util.init_log(app_cfg.log_dir)

    print(zem_api.handshake())
    zem_api.update_remote_addr(("192.168.110.79", 61557))
    zem_api.sync()

    ob_focus = 20483
    ob_half_width = 100
    ob_step = 3
    outdir = app_cfg.outdir / 'spot_data_15mm/20250107-3w-极细'
    json_util.dump(outdir / 'zem_model.json', zem_api.device.m.model_dump())

    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S512x512)

    obs = list(range(ob_focus-ob_half_width, ob_focus+ob_half_width, ob_step))
    
    zem_api.set_ob(obs[0], wait_stable_ms=3000)
    
    for i, ob in tqdm.tqdm(enumerate(obs), total=len(obs)):
        zem_api.set_ob(ob, wait_stable_ms=1000)
        zimg = zem_api.snap(snap_args=sa)
        zimg.dump(outdir/f'images/{i:04d}_{ob}.png')




if __name__ == "__main__":
    main()
