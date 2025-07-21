#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
import addict
from pathlib import Path

from jgb.util import app_util, db_util, addict_util, file_util

from zemrpc.__commit__ import GIT_INFO
from zemrpc.__version__ import __title__, __version__


class CfgDb:
    def __init__(self, app_name, cfg: addict.Dict, **kwargs):
        self.cfg = cfg
        if (db_file := kwargs.get("db_file", None)) is None:
            db_file = app_util.resolve_app_home_prod_ng(app_name, None, None) / "cfg.db"
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

    def after_init(self):
        if cfg_db := self.cfg.get("cfg_db", None):
            db_file = self.app_home / cfg_db
        else:
            db_file = None

        self.cfg_db = CfgDb(self.app_name, self.cfg, db_file=db_file)

    def init_cfg(self):
        assert self.run_type != app_util.AppRunType.DEV
        in_dir = Path(sys.prefix) / f"data/{__title__}"
        files = [
            (in_dir / "conf/config.yml", self.app_home / "conf/config.yml"),
        ]

        for src, dst in files:
            if dst.exists():
                continue

            print(f"copy {src} -> {dst}")
            file_util.copy(src, dst)

    @property
    def outdir(self) -> Path:
        return self.app_home / self.cfg.output_dir

    @property
    def log_dir(self) -> Path:
        return self.outdir / "logs"

    @property
    def about(self):
        s = [
            f"<p>版本: {self.version}</p>",
            f"<p>哈希: {GIT_INFO}</p>",
        ]
        return "".join(s)


app_cfg = AppConfig()
