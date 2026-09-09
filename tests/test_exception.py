#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from types import SimpleNamespace

from zemrpc.zem.models import ZemException, format_exception_for_ui
from zemrpc.zem.zem_api import ZemApi


def test_format_exception_for_ui_adds_timeout_hint():
    exc = ZemException.conn_timeout("命令超时: GetModel")

    message = format_exception_for_ui(exc)

    assert message == "命令超时，可能电镜服务未开启\n详细信息：命令超时: GetModel"


def test_format_exception_for_ui_timeout_error():
    message = format_exception_for_ui(TimeoutError("GetModel命令超时"))

    assert message == "命令超时，可能电镜服务未开启\n详细信息：GetModel命令超时"


def test_format_exception_for_ui_keeps_regular_zem_message():
    exc = ZemException.zem_api_not_ready("Zem API 忙")

    message = format_exception_for_ui(exc)

    assert message == "Zem API 忙"


def test_sync_reraises_timeout_and_clears_flags():
    api = object.__new__(ZemApi)
    api._init_sync_done = False
    api._init_sync_ing = False
    api.device = SimpleNamespace(
        ensure_connected=lambda: None,
        get_model=lambda: (_ for _ in ()).throw(ZemException.conn_timeout("命令超时: GetModel")),
    )

    try:
        ZemApi.sync(api)
    except ZemException as exc:
        assert exc.msg == "命令超时: GetModel"
    else:
        raise AssertionError("expected ZemException")

    assert api._init_sync_done is False
    assert api._init_sync_ing is False
