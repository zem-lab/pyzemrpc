#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import socket
import threading
import time
from types import SimpleNamespace
from unittest.mock import patch

from zemrpc.gui import ui_utils
from zemrpc.zem import ip_util
from zemrpc.zem.conn.protocol import EnumCmd, ProtocolBuilder, ProtocolParser, append_crc
from zemrpc.zem.zem_rpc_device import ZemRpcDevice


def test_resolve_loopback_ignores_polluted_iface_map():
    device = object.__new__(ZemRpcDevice)
    device._iface_by_device = {("127.0.0.1", 61557): "192.168.1.34"}

    assert device._resolve_local_ip_for_device(("127.0.0.1", 61557)) == "127.0.0.1"


def test_handshake_restores_current_target_after_scan():
    restored = []
    device = SimpleNamespace(
        m=SimpleNamespace(addr=("127.0.0.1", 61557)),
        _iface_by_device={},
        _handshake_probe=lambda *args, **kwargs: [],
        _prepare_comm=lambda: restored.append("restore"),
    )

    with patch.object(ip_util, "_get_all_local_ips", return_value=["192.168.1.10"]):
        found = ZemRpcDevice.handshake(device)

    assert found == []
    assert restored == ["restore"]


def test_handshake_probe_unicast_loopback():
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    port = server.getsockname()[1]
    resp = append_crc(f"${EnumCmd.HandshakeResp.cmd},127.0.0.1:{port},")

    def serve():
        server.settimeout(1.0)
        try:
            _data, addr = server.recvfrom(4096)
            server.sendto(resp, addr)
        except OSError:
            pass

    worker = threading.Thread(target=serve, daemon=True)
    worker.start()
    try:
        device = object.__new__(ZemRpcDevice)
        device.builder = ProtocolBuilder()
        device.parser = ProtocolParser()
        packets = ZemRpcDevice._handshake_probe(device, "127.0.0.1", ("127.0.0.1", port), time.time() + 0.5)
        assert len(packets) == 1
        assert packets[0].parse_ip_port() == ("127.0.0.1", port)
    finally:
        server.close()
        worker.join(timeout=1.0)


def test_merge_sem_server_items_keeps_local_first_and_skips_loopback_duplicate():
    existing = [(ui_utils.DEFAULT_SEM_SERVER_LABEL, ui_utils.DEFAULT_SEM_SERVER_ADDR)]
    discovered = [("127.0.0.1", 61557), ("192.168.110.74", 61557)]

    items = ui_utils.merge_sem_server_items(existing, discovered)

    assert items[0] == (ui_utils.DEFAULT_SEM_SERVER_LABEL, ui_utils.DEFAULT_SEM_SERVER_ADDR)
    assert ("127.0.0.1:61557", ("127.0.0.1", 61557)) not in items
    assert ("192.168.110.74:61557", ("192.168.110.74", 61557)) in items
