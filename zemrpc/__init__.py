#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import addict
from pathlib import Path
from jgb.util import app_util, file_util, db_util, addict_util

from zemrpc.__commit__ import GIT_INFO
from zemrpc.__version__ import __title__, __version__


class CfgDb:
    def __init__(self, app_name, cfg: addict.Dict):
        self.cfg = cfg
        db_file = app_util.resolve_app_home_prod_ng(app_name, None, None) / "cfg.db"
        file_util.ensure_dir(db_file.parent)
        self.kv_db = db_util.KvDataBase(db_file)
        self.update()

    def update(self):
        for k in self.kv_db.db.keys():
            if not k.startswith("cfg."):
                continue
            addict_util.update_addict(self.cfg, k[4:], self.kv_db.get_pkl(k))


class AppConfig(app_util.BaseAppConfig):
    def __init__(self):
        self.src_home = Path(__file__).resolve().parents[1]

        app_name = __title__
        app_home = app_util.resolve_app_home(__file__)
        super().__init__(app_home, app_name, author="Zeptools", version=__version__)

        self.outdir = self.app_home / self.cfg.output_dir  # type: Path
        self.log_dir = self.outdir / "logs"  # type: Path

        self.cfg_db = CfgDb(app_name, self.cfg)

    @property
    def about(self):
        s = [
            f"<p>版本: {self.version}</p>",
            f"<p>哈希: {GIT_INFO}</p>",
        ]
        return "".join(s)


app_cfg = AppConfig()
