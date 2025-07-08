
import tqdm
import time
import numpy as np

from jgb.util import json_util, loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api

s1_chc = 35000, 33500, 35900
s1_chd = 33500, 32000, 34500

np.arange(33500, 35900, 500) 
chc_lst = np.array([33500, 34000, 34500, 35000, 35500])

np.arange(32000, 34500, 500) 
chd_lst = np.array([32000, 32500, 33000, 33500, 34000])

obs = np.arange(26539, 26565, 2)

def main():
    ip = "192.168.110.231"
    
    loguru_util.init_log(app_cfg.log_dir)

    print(zem_api.handshake())
    zem_api.update_remote_addr((ip, 61557))
    zem_api.sync()

    i = 0
    j = 2
    chc = chc_lst[i]
    chd = chd_lst[j]

    outdir = app_cfg.outdir / f'spot_data_gold/20250123-9w-3050-2750/{chc}-{chd}'
    json_util.dump(outdir / 'zem_model.json', zem_api.device.m.model_dump())

    sa = SnapArgs(pixel_avg=7, size=EnumImageSize.S2048x2048)

    zem_api.set_ob(obs[0], wait_stable_ms=3000)

    for i, ob in tqdm.tqdm(enumerate(obs), total=len(obs)):
        zem_api.set_ob(ob, wait_stable_ms=1000)
        zimg = zem_api.snap(snap_args=sa)
        zimg.dump(outdir/f'images/{i:04d}_{ob}.png')

if __name__ == "__main__":
    main()
