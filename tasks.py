#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import sys
import os
import contextlib
import shutil
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


@task(pre=[build, build_rust])
def build_all(c, docs=False):
    """构建 pyzemrpc 纯 Python wheel + 两个 Rust 加速包 wheel"""
    print("\n=== 所有 wheel 构建完成 ===")
    print("wheel 文件位于各自目录的 target/wheels/ 下")
