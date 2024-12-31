#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import os
import io
import re
import sys
import setuptools
from pathlib import Path
from setuptools import setup


def read(filename):
    filename = os.path.join(os.path.dirname(__file__), filename)
    text_type = type("")
    with io.open(filename, mode="r", encoding="utf-8") as fd:
        return re.sub(text_type(r":[a-z]+:`~?(.*?)`"), text_type(r"``\1``"), fd.read())


base_dir = Path(__file__).resolve().parents[0]

about = {}
with open(base_dir / "zemrpc/__version__.py", "r", encoding="utf-8") as f:
    exec(f.read(), about)
app_name = about["__title__"]

with open("requirements.txt", "r", encoding="utf-8") as f:
    install_requires = [line.strip() for line in f.readlines() if line]

tools = {}
entry_points = []

data_files = [
    ("data/{}/conf".format(app_name), ["conf/config.yml"]),
]

# fmt: off

setup_args = dict(
    name=app_name,
    version=about["__version__"],
    license=about["__license__"],

    author=about["__author__"],
    author_email=about["__author_email__"],

    url=about["__url__"],
    description=about["__description__"],
    keywords=about["__keywords__"],

    long_description=read("readme.md"),
    long_description_content_type="text/markdown",

    packages=setuptools.find_packages(exclude=("tests",)),
    include_package_data=True,
    exclude_package_data={
        '': ['*.ui']
    },
    data_files=data_files,
    install_requires=install_requires,

    command_options={
        "nuitka": {
            "--show-scons": True,
            "--clang": None,
            "--enable-plugin": ("pyside6"),
            "--nofollow-import-to": ["*.tests", "*.distutils", "tests"],
        },
    },

    zip_safe=True,

    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3 :: Only",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX",
        "Operating System :: Unix",
        "Operating System :: MacOS",
    ],

    python_requires=">=3.11",

    entry_points={
        "console_scripts": [
            "pyzemrpc_info=zemrpc.tools.zemrpc_info:main",
            *entry_points,
        ],
        "gui_scripts": [
            "pyzemrpc=zemrpc.gui.zemrpc_main:main"
        ]
    },
)

# fmt: on

setup(**setup_args)
