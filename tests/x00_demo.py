

from jgb.util import json_util, loguru_util

from zemrpc import app_cfg
from zemrpc.zem.models import EnumImageSize, SnapArgs
from zemrpc.zem.zem_api import zem_api

def main():
    addr = "192.168.109.58", 61557
    loguru_util.init_log(app_cfg.log_dir)
    
    zem_api.update_remote_addr(addr)
    zem_api.sync()

    zem_api.stage_xy_goto_closed((0,0))
    print(zem_api.get_stage_pos())
    

if __name__ == "__main__":
    main()