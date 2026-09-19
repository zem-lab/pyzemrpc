#!/usr/bin/env python3

import argparse
import configparser
import email
from pathlib import Path
import zipfile


def inspect_wheel(wheel: Path, version: str, commit: str) -> None:
    dist_info = f"pyzemrpc-{version}.dist-info"
    config_path = f"pyzemrpc-{version}.data/data/data/pyzemrpc/conf/config.yml"

    with zipfile.ZipFile(wheel) as archive:
        metadata = email.message_from_bytes(archive.read(f"{dist_info}/METADATA"))
        embedded_version = archive.read("zemrpc/__version__.py").decode("utf-8")
        embedded_commit = archive.read("zemrpc/__commit__.py").decode("utf-8")
        names = archive.namelist()

    assert metadata["Name"] == "pyzemrpc", metadata["Name"]
    assert metadata["Version"] == version, metadata["Version"]
    assert version in embedded_version
    assert commit in embedded_commit
    assert config_path in names

    print("Wheel metadata:", metadata["Name"], metadata["Version"], metadata["Requires-Python"])
    print("Embedded commit:", commit)
    print("Packaged config:", config_path)


def check_pypirc(path: Path, repository: str) -> None:
    config = configparser.RawConfigParser()
    config.read(path, encoding="utf-8")
    assert config.has_section(repository), f"missing [{repository}] section"
    assert config.has_option(repository, "username"), "missing username"
    assert config.has_option(repository, "password"), "missing password/token"
    print(f"Twine credentials configured for [{repository}]")


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect-wheel")
    inspect_parser.add_argument("wheel", type=Path)
    inspect_parser.add_argument("version")
    inspect_parser.add_argument("commit")

    pypirc_parser = subparsers.add_parser("check-pypirc")
    pypirc_parser.add_argument("path", type=Path)
    pypirc_parser.add_argument("repository")

    args = parser.parse_args()
    if args.command == "inspect-wheel":
        inspect_wheel(args.wheel, args.version, args.commit)
    elif args.command == "check-pypirc":
        check_pypirc(args.path, args.repository)


if __name__ == "__main__":
    main()
