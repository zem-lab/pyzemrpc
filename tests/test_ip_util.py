#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ipaddress
from unittest.mock import patch

from zemrpc.zem import ip_util


def test_ip_in_same_subnet():
    assert ip_util._ip_in_same_subnet("192.168.110.82", "192.168.111.207", "255.255.252.0")
    assert not ip_util._ip_in_same_subnet("192.168.1.34", "192.168.111.207", "255.255.252.0")
    assert ip_util._ip_in_same_subnet("192.168.1.34", "192.168.1.50", "255.255.255.0")


def test_find_local_ip_for_target_uses_netmask():
    candidates = ["192.168.1.34", "192.168.110.82"]
    subnets = [
        ("192.168.1.34", "255.255.255.0"),
        ("192.168.110.82", "255.255.252.0"),
    ]
    with patch.object(ip_util, "_get_interface_subnets", return_value=subnets):
        assert ip_util._find_local_ip_for_target("192.168.111.207", candidates) == "192.168.110.82"
        assert ip_util._find_local_ip_for_target("192.168.1.50", candidates) == "192.168.1.34"


def test_find_local_ip_for_target_fallback_prefix():
    candidates = ["192.168.1.34", "192.168.110.82"]
    with patch.object(ip_util, "_get_interface_subnets", return_value=[]):
        assert ip_util._find_local_ip_for_target("192.168.111.207", candidates) == "192.168.110.82"


def test_get_real_local_ip_prefers_target_subnet():
    all_ips = ["192.168.1.34", "192.168.110.82"]
    subnets = [
        ("192.168.1.34", "255.255.255.0"),
        ("192.168.110.82", "255.255.252.0"),
    ]
    with patch.object(ip_util, "_get_all_local_ips", return_value=all_ips):
        with patch.object(ip_util, "_get_interface_subnets", return_value=subnets):
            assert ip_util.get_real_local_ip(target_ip="192.168.111.207") == "192.168.110.82"


def test_prefix_fallback_covers_slash22():
    target = "192.168.111.207"
    net = ipaddress.ip_network(f"{target}/22", strict=False)
    assert ipaddress.ip_address("192.168.110.82") in net
    assert ipaddress.ip_address("192.168.1.34") not in net
