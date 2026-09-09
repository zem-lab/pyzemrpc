#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from typing import Dict, Iterable, List, Optional, Sequence, Tuple

cbox_style = "QComboBox QAbstractItemView::item { min-height: 15px; min-width: 50px; }QListView::item:selected { color: black; background-color: lightgray}"

DEFAULT_SEM_SERVER_ADDR = ("127.0.0.1", 61557)
DEFAULT_SEM_SERVER_LABEL = "本机"


def merge_sem_server_items(
    existing_items: Sequence[Tuple[str, Optional[Tuple[str, int]]]],
    discovered: Optional[Iterable[Tuple[str, int]]] = None,
) -> List[Tuple[str, Tuple[str, int]]]:
    """Keep 本机 first; append discovered ip:port; skip the loopback duplicate."""
    items: Dict[str, Tuple[str, int]] = {DEFAULT_SEM_SERVER_LABEL: DEFAULT_SEM_SERVER_ADDR}
    for key, addr in existing_items:
        if addr is None or addr == DEFAULT_SEM_SERVER_ADDR:
            continue
        items[key] = addr
    for addr in discovered or []:
        if addr == DEFAULT_SEM_SERVER_ADDR:
            continue
        ip, port = addr
        items[f"{ip}:{port}"] = addr

    ordered: List[Tuple[str, Tuple[str, int]]] = [(DEFAULT_SEM_SERVER_LABEL, DEFAULT_SEM_SERVER_ADDR)]
    for key in sorted(k for k in items if k != DEFAULT_SEM_SERVER_LABEL):
        ordered.append((key, items[key]))
    return ordered


def get_api_cmds():
    from zemrpc.zem.conn.protocol import EnumCmd

    cbox_cmds = {}  # type: Dict[str, EnumCmd]
    for c in EnumCmd:
        if c in {EnumCmd.InvalidCmd, EnumCmd.Handshake, EnumCmd.HandshakeResp}:
            continue
        cbox_cmds[c.name_cn] = c
    return cbox_cmds


def parse_mag_str(mag_str):
    tbl = {"k": 1000, "w": 10000, "x": 1}
    return int(mag_str[:-1]) * tbl[mag_str[-1]]


def stage_pos_str(x: float, y: float):
    return f"{x:.3f},{y:.3f}"


def parse_stage_pos(pos_str: str):
    return list(map(float, pos_str.replace("，", ",").split(",")))


def get_snap_size():
    from zemrpc.zem.models import EnumImageSize

    sizes = {}
    for s in EnumImageSize:
        if s == EnumImageSize.Unk:
            continue
        sizes[s.name_cn] = s
    return sizes


def get_beam_size():
    from zemrpc.zem.models import EnumBeamSize

    sizes = []
    for s in EnumBeamSize:
        if s == EnumBeamSize.Unk:
            continue
        sizes.append(s)
    return sizes
