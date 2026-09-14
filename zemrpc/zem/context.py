#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from jgb.util.dds_util import BaseAppContext

from zemrpc import app_cfg


class ZemApiContext(BaseAppContext):
    """
    ZemApiContext is a singleton context for managing ZemApi instances.
    """

    def __init__(self):
        super().__init__(max_workers=2)

    @property
    def logdir(self):
        return app_cfg.log_dir


ctx = ZemApiContext()
