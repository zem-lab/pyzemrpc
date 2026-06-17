#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from zemrpc.zem.conn.protocol import ProtocolBuilder, patch_request_callback


def test_patch_request_callback_rewrites_ip_port_and_crc():
    builder = ProtocolBuilder("192.168.1.34", 10000)
    req = builder.build_get_model()
    patched = patch_request_callback(req.data, "192.168.110.82", 52232)

    text = patched.decode()
    assert "192.168.110.82:52232" in text
    assert "192.168.1.34:10000" not in text
    assert text.endswith("%")
    assert text.startswith("$GetModel:")
