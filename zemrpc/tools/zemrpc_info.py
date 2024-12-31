#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import psutil
import platform
from importlib_metadata import version as get_package_version

from zemrpc import app_cfg
from zemrpc import __title__, __version__
from zemrpc.__commit__ import GIT_INFO


def collect_app_info():
    return {
        "App name": __title__,
        "App version": __version__,
        "Commit id": GIT_INFO,
        "App home": app_cfg.app_home,
        "Src home": app_cfg.src_home,
        "Run type": app_cfg.run_type,
        "Output directory": app_cfg.outdir,
        "Log directory": app_cfg.log_dir,
        "Configuration file": app_cfg.cfg_file,
    }


def collect_memory_info():
    mem = psutil.virtual_memory()
    total = mem.total / 2**30
    used = mem.used / 2**30
    free = mem.free / 2**30
    return f"{total:.3f}G - {used:.3f}G = {free:.3f}G"


def get_installed_package_version(package_name):
    try:
        return get_package_version(package_name)
    except Exception:
        return None


def collect_system_info():
    os_info = platform.platform()
    cpu_info = platform.processor()
    python_info = platform.python_version()
    mem_info = collect_memory_info()

    system_info = {
        "Operating System": os_info,
        "CPU": cpu_info,
        "MEM": mem_info,
        "Python Version": python_info,
    }

    pkgs = [
        "PySide6",
        "opencv-python",
    ]
    pkg_info = {p: get_installed_package_version(p) for p in pkgs}

    return system_info, pkg_info


def information():
    app_info = collect_app_info()
    app_info_str = "\n".join([f"{key}: {value}" for key, value in app_info.items()])

    system_info, pkg_info = collect_system_info()
    system_info_str = "\n".join([f"{key}: {value}" for key, value in system_info.items()])
    pkg_info_str = "\n".join([f"{key}: {value}" for key, value in pkg_info.items()])
    msg = f"{app_info_str}\n\n{system_info_str}\n\n{pkg_info_str}"
    return msg


def main():
    print(information())


if __name__ == "__main__":
    main()
