#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
import os
import re
import contextlib
import shutil
from datetime import datetime
from pathlib import Path
from invoke import task
from invoke.context import Context

from jgb.util import file_util

PROJ_HOME = Path(__file__).resolve().absolute().parent
PROJ_NAME = "zemrpc"


@contextlib.contextmanager
def chdir(dirname=None):
    curdir = os.getcwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


@task
def ui2py(c: Context):
    ui_files = []  # type: list[Path]
    for ui in (PROJ_HOME / PROJ_NAME).rglob("*.ui"):
        ui_files.append(ui.relative_to(PROJ_HOME))

    for ui_file in ui_files:
        py_file = ui_file.parent / f"{ui_file.stem}_ui.py"
        c.run(f"pyside6-uic.exe {ui_file} -o {py_file}")


@task
def git_info(c):
    r = c.run('git log --pretty=format:"%H" -n 1', hide=True)
    hash = r.stdout
    line = f'GIT_INFO = "{hash}"\n'
    with open(f"{PROJ_NAME}/__commit__.py", "w") as f:
        f.write(line)


@task
def clean_build(c):
    d = PROJ_HOME / "build"
    if d.exists():
        shutil.rmtree(d, True)


@task(pre=[git_info, ui2py, clean_build])
def build(c, docs=False):
    r = c.run(f"{sys.executable} setup.py bdist_wheel")
    file_util.write_text_lines(PROJ_HOME / "build/build.log", [r.stdout])
    if docs:
        c.run("sphinx-build docs docs/_build")


@task
def publish(c, password="zeptools2024", devpi_url="http://dc000.local:7104/zeptools/devpi"):
    """发布包到 devpi 服务器，发布前会自动更新版本号中的日期，只上传当前版本的 whl 文件"""
    version_file = PROJ_HOME / PROJ_NAME / "__version__.py"
    
    # 读取版本文件
    with open(version_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 提取当前版本号并更新日期
    # 版本格式: 1.0.0dev1+20251228
    pattern = r'(__version__\s*=\s*")([^"]+)(")'
    match = re.search(pattern, content)
    
    if not match:
        raise ValueError(f"无法在 {version_file} 中找到 __version__ 定义")
    
    version_prefix = match.group(1)
    version_str = match.group(2)
    version_suffix = match.group(3)
    
    # 替换日期部分（格式: +YYYYMMDD）
    current_date = datetime.now().strftime("%Y%m%d")
    # 使用正则表达式替换日期部分
    if re.search(r'\+\d{8}', version_str):
        new_version = re.sub(r'\+\d{8}', f'+{current_date}', version_str)
    else:
        # 如果没有日期部分，在末尾添加
        new_version = f"{version_str}+{current_date}"
    
    # 更新文件内容
    new_content = re.sub(pattern, f'{version_prefix}{new_version}{version_suffix}', content)
    
    # 写回文件
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(new_content)
    
    print(f"版本号已更新: {version_str} -> {new_version}")
    
    # 配置 devpi 服务器
    c.run(f"devpi use {devpi_url}")
    
    # 登录 devpi
    c.run(f"devpi login zeptools --password={password}")
    
    # 查找并上传与当前版本号匹配的 whl 文件
    dist_dir = PROJ_HOME / "dist"
    if not dist_dir.exists():
        raise FileNotFoundError(f"dist 目录不存在，请先运行 'inv build' 构建包")
    
    # whl 文件名格式: pyzemrpc-1.0.0.dev1+20251228-py3-none-any.whl
    # 查找包含当前版本号的文件
    all_whl_files = list(dist_dir.glob("*.whl"))
    if not all_whl_files:
        raise FileNotFoundError(f"dist 目录中没有找到 .whl 文件，请先运行 'inv build' 构建包")
    
    # 匹配包含当前版本号的 whl 文件
    whl_files = [f for f in all_whl_files if f"pyzemrpc-{new_version}-" in f.name]
    
    if not whl_files:
        # 如果没有找到匹配的文件，使用最新构建的文件
        whl_files = [sorted(all_whl_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]]
        print(f"警告: 未找到版本号为 {new_version} 的 whl 文件，将上传最新的文件: {whl_files[0].name}")
    
    # 只上传匹配当前版本的文件（通常只有一个）
    for whl_file in whl_files:
        print(f"上传 {whl_file.name}...")
        c.run(f"devpi upload {whl_file}")
    
    print(f"版本 {new_version} 已成功上传到 devpi!")
