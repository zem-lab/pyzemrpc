#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from typing import Dict

cbox_style = "QComboBox QAbstractItemView::item { min-height: 15px; min-width: 50px; }QListView::item:selected { color: black; background-color: lightgray}"


def get_api_cmds():
    from zemrpc.zem.conn.protocol import EnumCmd

    cbox_cmds = {}  # type: Dict[str, EnumCmd]
    for c in EnumCmd:
        if c in {EnumCmd.InvalidCmd, EnumCmd.Handshake, EnumCmd.HandshakeResp}:
            continue
        cbox_cmds[c.name_cn] = c
    return cbox_cmds


def get_snap_size():
    from zemrpc.zem.models import EnumImageSize

    sizes = {}
    for s in EnumImageSize:
        if s == EnumImageSize.Unk:
            continue
        sizes[s.name_cn] = s
    return sizes
