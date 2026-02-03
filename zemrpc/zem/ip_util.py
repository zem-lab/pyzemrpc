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
    1. Gets all local IP addresses
    2. Filters out Clash Fake-IP range (198.18.0.0/15)
    3. Filters out loopback addresses (127.0.0.1)
    4. Prioritizes private IP addresses (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    5. If target_ip is provided, prioritizes IPs in the same subnet
    6. Falls back to os_util.get_default_ip() if no suitable IP found
    
    Args:
        target_ip: Optional target device IP address. If provided, prioritize
                   IPs in the same subnet.
        
    Returns:
        Real local IP address string
    """
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
    
    # If target IP is provided, prioritize IPs in the same subnet
    if target_ip:
        try:
            target_net = ipaddress.ip_network(f"{target_ip}/24", strict=False)
            for ip in real_ips:
                try:
                    ip_obj = ipaddress.ip_address(ip)
                    if ip_obj in target_net:
                        logger.debug(f"Selected IP {ip} (same subnet as {target_ip})")
                        return ip
                except ValueError:
                    continue
        except Exception as e:
            logger.debug(f"Failed to match subnet for {target_ip}: {e}")
    
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

