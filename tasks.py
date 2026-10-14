#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
import os
import contextlib
import shutil
import subprocess
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
    if d.resolve() != PROJ_HOME.resolve() / "build":
        raise RuntimeError("Refusing to clean a redirected build directory")
    if d.exists():
        shutil.rmtree(d, True)


@task(pre=[git_info, ui2py, clean_build])
def build(c, docs=False):
    r = c.run(f"{sys.executable} setup.py bdist_wheel")
    file_util.write_text_lines(PROJ_HOME / "build/build.log", [r.stdout])
    if docs:
        c.run("sphinx-build docs docs/_build")


@task
def build_rust(c):
    """构建 mandelbrot_zem_rs 和 perlin_zem_rs 的 wheel"""
    rust_pkgs = [
        "zemrpc/tools/virtual_zem/mandelbrot_zem_rs",
        "zemrpc/tools/virtual_zem/perlin_zem_rs",
    ]
    for pkg in rust_pkgs:
        pkg_path = PROJ_HOME / pkg
        print(f"\n=== 构建 {pkg} ===")
        c.run(f"maturin build --release --manifest-path {pkg_path / 'Cargo.toml'}")


@task(pre=[git_info, ui2py])
def build_exe(c: Context):
    """使用预编译 bootloader 和依赖打包 GUI，不运行 C/C++ 编译器。"""
    from zemrpc.__version__ import __version__
    from zemrpc.__commit__ import GIT_INFO
    out_dir = PROJ_HOME / "dist" / f"pyzemrpc_{__version__}_windows"
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir = PROJ_HOME / "build" / "pyinstaller"
    work_dir.mkdir(parents=True, exist_ok=True)
    version_file = work_dir / "version.txt"
    version_file.write_text(
        "VSVersionInfo(ffi=FixedFileInfo(filevers=(1,2,7,1),prodvers=(1,2,7,1),mask=0x3f,flags=0,OS=0x40004,fileType=1,subtype=0,date=(0,0)),"
        "kids=[StringFileInfo([StringTable('040904B0',[StringStruct('CompanyName','ZEPTOOLS'),StringStruct('FileDescription','ZEPTOOLS ZEM Remote Control'),"
        f"StringStruct('FileVersion',{__version__!r}),StringStruct('ProductVersion',{(__version__+'+'+GIT_INFO)!r}),StringStruct('ProductName','pyzemrpc')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])",
        encoding="utf-8",
    )
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller", "--noconfirm", "--clean", "--onedir", "--windowed", "--name=pyzemrpc",
        f"--distpath={out_dir}", f"--workpath={work_dir / 'work'}", f"--specpath={work_dir}", f"--version-file={version_file}",
        f"--add-data={PROJ_HOME / 'conf/config.yml'};data/pyzemrpc/conf", "--collect-data=jgb",
        "--exclude-module=PyQt5", "--exclude-module=PyQt6", "--exclude-module=PySide2",
        "--exclude-module=mandelbrot_zem_rs", "--exclude-module=perlin_zem_rs", "--exclude-module=pytest",
        "zemrpc/gui/zemrpc_main.py",
    ]
    c.run(subprocess.list2cmdline(cmd), env={"QT_API":"pyside6", "PYQTGRAPH_QT_LIB":"PySide6"})
    dist_dir = out_dir / "pyzemrpc"
    exe = dist_dir / "pyzemrpc.exe"
    if exe.exists():
        print(f"独立 exe: {exe}")
    else:
        raise RuntimeError(f"Missing packaged executable: {exe}")


@task(pre=[build, build_exe])
def build_all(c):
    """打包纯 Python wheel 和 PyInstaller GUI，不触发 C/C++ 或 Rust 编译。"""
    print("pyzemrpc wheel 和 GUI 打包完成")
