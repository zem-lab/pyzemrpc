#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

"""
IP utility functions for filtering virtual IP addresses.

This module provides functions to get real local IP addresses, filtering out
virtual IPs created by proxy tools like Clash (Fake-IP mode).
"""

import socket
import ipaddress
from typing import Optional, List
from loguru import logger

from jgb.util import os_util


def _is_clash_fake_ip(ip: str) -> bool:
    """
    Check if an IP address is in Clash Fake-IP range (198.18.0.0/15).
    
    Args:
        ip: IP address string
        
    Returns:
        True if IP is in Clash Fake-IP range, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        # Clash Fake-IP range: 198.18.0.0/15 (198.18.0.0 - 198.19.255.255)
        fake_ip_network = ipaddress.ip_network("198.18.0.0/15")
        return ip_obj in fake_ip_network
    except ValueError:
        return False


def _is_private_ip(ip: str) -> bool:
    """
    Check if an IP address is a private (RFC 1918) address.
    
    Args:
        ip: IP address string
        
    Returns:
        True if IP is private, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_private
    except ValueError:
        return False


def _is_loopback_ip(ip: str) -> bool:
    """
    Check if an IP address is a loopback address.
    
    Args:
        ip: IP address string
        
    Returns:
        True if IP is loopback, False otherwise
    """
    try:
        ip_obj = ipaddress.ip_address(ip)
        return ip_obj.is_loopback
    except ValueError:
        return False


def _get_interface_subnets() -> List[tuple[str, str]]:
    """
    Get (local_ip, netmask) pairs from network interfaces.

    Returns:
        List of (ip, netmask) tuples for non-loopback, non-fake IPv4 addresses
    """
    subnets: List[tuple[str, str]] = []
    try:
        import netifaces

        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET not in addrs:
                continue
            for addr_info in addrs[netifaces.AF_INET]:
                ip = addr_info.get("addr")
                netmask = addr_info.get("netmask")
                if not ip or not netmask:
                    continue
                if _is_loopback_ip(ip) or _is_clash_fake_ip(ip):
                    continue
                subnets.append((ip, netmask))
    except ImportError:
        logger.debug("netifaces not available for subnet lookup")
    except Exception as e:
        logger.debug(f"Failed to get interface subnets: {e}")
    return subnets


def _ip_in_same_subnet(ip: str, target_ip: str, netmask: str) -> bool:
    try:
        ip_int = int(ipaddress.ip_address(ip))
        target_int = int(ipaddress.ip_address(target_ip))
        mask_int = int(ipaddress.ip_address(netmask))
        return (ip_int & mask_int) == (target_int & mask_int)
    except ValueError:
        return False


def get_route_local_ip(target_ip: str, target_port: int = 61557, candidates: Optional[List[str]] = None) -> Optional[str]:
    """
    Pick the local IP the OS would use to reach target_ip by probing UDP connect().
    """
    if candidates is None:
        candidates = [
            ip
            for ip in _get_all_local_ips()
            if not _is_clash_fake_ip(ip) and not _is_loopback_ip(ip)
        ]
    for ip in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.bind((ip, 0))
                s.connect((target_ip, target_port))
                logger.debug(f"Route to {target_ip}:{target_port} via local {ip}")
                return ip
        except OSError:
            continue
    return None


def _find_local_ip_for_target(target_ip: str, candidates: List[str]) -> Optional[str]:
    """
    Pick the local IP that can reach target_ip on the same L2/L3 subnet.

    Uses interface netmasks when available, otherwise tries common prefix lengths.
    """
    for ip, netmask in _get_interface_subnets():
        if ip in candidates and _ip_in_same_subnet(ip, target_ip, netmask):
            logger.debug(f"Selected IP {ip} (same subnet as {target_ip}, mask {netmask})")
            return ip

    try:
        target = ipaddress.ip_address(target_ip)
    except ValueError:
        return None

    for prefix_len in (32, 24, 22, 16):
        try:
            net = ipaddress.ip_network(f"{target_ip}/{prefix_len}", strict=False)
        except ValueError:
            continue
        if target not in net:
            continue
        for ip in candidates:
            try:
                if ipaddress.ip_address(ip) in net:
                    logger.debug(f"Selected IP {ip} (prefix /{prefix_len} with {target_ip})")
                    return ip
            except ValueError:
                continue
    return None


def _get_all_local_ips() -> List[str]:
    """
    Get all local IP addresses from network interfaces.
    
    Returns:
        List of IP address strings
    """
    ips = []
    
    # Method 1: Try using socket.getaddrinfo
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips:
                ips.append(ip)
    except Exception as e:
        logger.debug(f"Failed to get IPs via getaddrinfo: {e}")
    
    # Method 2: Try connecting to external address to get default route IP
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            if ip not in ips:
                ips.append(ip)
    except Exception as e:
        logger.debug(f"Failed to get IP via connect method: {e}")
    
    # Method 3: Try using netifaces if available
    try:
        import netifaces
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr_info in addrs[netifaces.AF_INET]:
                    ip = addr_info.get("addr")
                    if ip and ip not in ips:
                        ips.append(ip)
    except ImportError:
        logger.debug("netifaces not available, skipping")
    except Exception as e:
        logger.debug(f"Failed to get IPs via netifaces: {e}")
    
    return ips


def get_real_local_ip(target_ip: Optional[str] = None) -> str:
    """
    Get real local IP address, filtering out virtual IPs like Clash Fake-IP.
    
    This function:
    1. If target_ip is loopback, returns 127.0.0.1
    2. Gets all local IP addresses
    3. Filters out Clash Fake-IP range (198.18.0.0/15)
    4. Filters out loopback addresses (127.0.0.1) for LAN targets
    5. Prioritizes private IP addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    6. If target_ip is provided, prioritizes IPs in the same subnet
    7. Falls back to os_util.get_default_ip() if no suitable IP found
    
    Args:
        target_ip: Optional target device IP address. Loopback targets use
                   127.0.0.1; otherwise prioritize IPs in the same subnet.
        
    Returns:
        Real local IP address string
    """
    # 本机回环目标必须走 127.0.0.1，不能选局域网网卡，否则 Windows 会 WinError 10049
    if target_ip and _is_loopback_ip(target_ip):
        logger.debug(f"Selected loopback IP for target {target_ip}")
        return "127.0.0.1"

    # Get all local IPs
    all_ips = _get_all_local_ips()
    
    if not all_ips:
        logger.warning("No local IPs found, falling back to os_util.get_default_ip()")
        return os_util.get_default_ip()
    
    # Filter out virtual IPs
    real_ips = []
    for ip in all_ips:
        if _is_clash_fake_ip(ip):
            logger.debug(f"Filtered out Clash Fake-IP: {ip}")
            continue
        if _is_loopback_ip(ip):
            logger.debug(f"Filtered out loopback IP: {ip}")
            continue
        real_ips.append(ip)
    
    if not real_ips:
        logger.warning("All IPs were filtered out, falling back to os_util.get_default_ip()")
        return os_util.get_default_ip()
    
    # If target IP is provided, prioritize IPs on the same subnet/interface
    if target_ip:
        if matched := _find_local_ip_for_target(target_ip, real_ips):
            return matched
        if matched := get_route_local_ip(target_ip, candidates=real_ips):
            return matched
    
    # Prioritize private IPs
    private_ips = [ip for ip in real_ips if _is_private_ip(ip)]
    if private_ips:
        selected = private_ips[0]
        logger.debug(f"Selected private IP: {selected}")
        return selected
    
    # Fallback to first real IP
    selected = real_ips[0]
    logger.debug(f"Selected IP: {selected}")
    return selected

