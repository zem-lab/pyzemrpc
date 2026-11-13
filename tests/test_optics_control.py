from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from zemrpc.tools.virtual_zem.virtual_zem import RemoteZem, VirtualZem, ZemRespBuilder
from zemrpc.zem.conn.protocol import EnumCmd, ProtocolBuilder, ReqPacket, RespPacket, append_crc
from zemrpc.zem.models import EnumCmdLevel, ZemException
from zemrpc.zem.context import ctx
from zemrpc.zem.zem_rpc_device import ZemModel, ZemRpcDevice


AXES = [
    ("stig_x", "StigX"), ("stig_y", "StigY"),
    ("up_center_x", "UpCenterX"), ("up_center_y", "UpCenterY"),
    ("down_center_x", "DownCenterX"), ("down_center_y", "DownCenterY"),
]


@pytest.fixture
def optics():
    server = SimpleNamespace(zem_dev=VirtualZem(), builder=ZemRespBuilder(), _send=Mock())
    server.resp_set_ob_raw = lambda packet: RemoteZem.resp_set_ob_raw(server, packet)
    device = object.__new__(ZemRpcDevice)
    device.builder = ProtocolBuilder("127.0.0.1", 61000)
    device.m = ZemModel(ctx=ctx)

    def exchange(request):
        RemoteZem.process_packet(server, ReqPacket(("127.0.0.1", 61000), request.data))
        return RespPacket(server._send.call_args.args[1])

    device.send = Mock(side_effect=exchange)
    return device


def test_ast_wire_spelling_legacy_aliases_and_raw_roundtrip(optics):
    request = optics.builder.build_set_ast(np.int64(-1200), 2300)
    assert request.data.decode().startswith("$SetAst:-1200,2300,127.0.0.1:61000,")
    assert ReqPacket(None, request.data).parse_cmd() == EnumCmd.SetAST == EnumCmd.SetAst
    assert optics.set_ast(-1200, 2300) == (-1200, 2300)
    assert optics.m.ast == (-1200, 2300)
    assert optics.send.call_args.args[0].cmd == EnumCmd.GetAST
    assert RespPacket(append_crc("$GetAST:1,-2,")).parse_ast() == (1, -2)
    assert RespPacket(append_crc("$GetAst:1,-2,")).get_pubsub_key() == optics.builder.build_get_ast().get_pubsub_key()


@pytest.mark.parametrize("field,command", AXES)
def test_percentage_commands_read_quantized_device_values(optics, field, command):
    setter, getter = getattr(optics, f"set_{field}"), getattr(optics, f"get_{field}")
    assert getter() == 0
    for value in (-100, -12.345678, 0, np.float64(12.345678), 100):
        result = setter(value)
        assert result == pytest.approx(int(value / 100 * 4095) * 100 / 4095, abs=1e-6)
        assert getattr(optics.m, field) == result == getter()
        commands = [call.args[0].cmd for call in optics.send.call_args_list[-3:]]
        assert commands == [EnumCmd[f"Set{command}"], EnumCmd[f"Get{command}"], EnumCmd[f"Get{command}"]]
    assert field in ZemModel.model_fields


def test_raw_and_percentage_ast_share_state_but_alignment_is_independent(optics):
    optics.set_ast(4095, -4095)
    assert optics.get_stig_x() == 100
    assert optics.get_stig_y() == -100
    optics.set_stig_x(20)
    assert optics.m.ast is None
    assert optics.get_ast() == (819, -4095)
    optics.set_up_center_x(-40)
    optics.set_down_center_y(60)
    assert optics.get_ast() == (819, -4095)
    assert optics.get_up_center_y() == optics.get_down_center_x() == 0
    optics.set_ast(0, 0)
    assert optics.m.stig_x is None and optics.m.stig_y is None


@pytest.mark.parametrize("field,command", AXES)
@pytest.mark.parametrize("value", [-100.01, 100.01, float("nan"), float("inf"), True, "10", None])
def test_invalid_percentage_never_sends(optics, field, command, value):
    with pytest.raises(ValueError):
        getattr(optics, f"set_{field}")(value)
    optics.send.assert_not_called()


@pytest.mark.parametrize("x,y", [(-4096, 0), (0, 4096), (1.0, 2), (0, True), (0, float("nan"))])
def test_invalid_raw_ast_never_sends(optics, x, y):
    with pytest.raises(ValueError):
        optics.set_ast(x, y)
    optics.send.assert_not_called()


@pytest.mark.parametrize("field,command", AXES)
def test_failed_ack_preserves_cache_and_does_not_read_back(optics, field, command):
    setattr(optics.m, field, 1)
    optics.send = Mock(return_value=RespPacket(append_crc(f"$Set{command}:Acknowledge,Error Code:1,")))
    assert getattr(optics, f"set_{field}")(2) is None
    assert getattr(optics.m, field) == 1
    assert optics.send.call_count == 1


def test_failed_ast_ack_preserves_cache(optics):
    optics.m.ast = (10, 20)
    optics.send = Mock(return_value=RespPacket(append_crc("$SetAst:Acknowledge,Error Code:1,")))
    assert optics.set_ast(30, 40) is None
    assert optics.m.ast == (10, 20)
    assert optics.send.call_count == 1


@pytest.mark.parametrize("field,command", AXES + [("ast", "Ast")])
def test_optics_write_permissions_remain_advanced(optics, field, command):
    optics._work_mode = EnumCmdLevel.BASIC
    optics._check_cmd_permission(EnumCmd[f"Get{command}"])
    with pytest.raises(ZemException):
        optics._check_cmd_permission(EnumCmd[f"Set{command}"])
    optics._work_mode = EnumCmdLevel.ADVANCED
    optics._check_cmd_permission(EnumCmd[f"Set{command}"])


@pytest.mark.parametrize("raw", [0, 1, 15817, 32768, 65535])
def test_virtual_focus_preserves_raw_dac(optics, raw):
    assert optics.set_ob_raw(raw) == raw
    assert optics.get_ob() == raw


@pytest.mark.parametrize("command,args", [
    (EnumCmd.SetOBRaw, "65536"), (EnumCmd.SetOBRaw, "1.5"),
    (EnumCmd.SetAst, "1,4096"), (EnumCmd.SetAst, "1,2,3"),
    (EnumCmd.SetStigX, "nan"), (EnumCmd.SetUpCenterX, "101"),
    (EnumCmd.SetDownCenterY, "1,2"),
])
def test_virtual_rejects_bad_wire_values_without_changing_optics(optics, command, args):
    optics.set_ast(10, 20)
    original_ob = optics.get_ob()
    response = optics.send(optics.builder.build_set(command, args))
    assert response.is_error()
    assert optics.get_ast() == (10, 20)
    assert optics.get_ob() == original_ob
    assert optics.get_up_center_x() == optics.get_down_center_y() == 0


@pytest.mark.parametrize("value", ["nan", "inf", "101", "1,2", "Acknowledge,Error Code:1"])
def test_malformed_percentage_readback_is_not_cached(optics, value):
    optics.m.stig_x = 7
    optics.send = Mock(return_value=RespPacket(append_crc(f"$GetStigX:{value},")))
    with pytest.raises(ValueError):
        optics.get_stig_x()
    assert optics.m.stig_x == 7


def test_high_level_api_reaches_device_without_requiring_new_sync_queries(monkeypatch, optics):
    from zemrpc.zem.zem_api import ZemApi, zem_api

    monkeypatch.setattr(zem_api, "_init_sync_done", True)
    api = SimpleNamespace(device=optics)
    assert ZemApi.set_ast(api, 12, -34) == ZemApi.get_ast(api) == (12, -34)
    for field, _ in AXES:
        result = getattr(ZemApi, f"set_{field}")(api, 12.5)
        assert getattr(ZemApi, f"get_{field}")(api) == result
    assert ZemApi.get_ob(api) == optics.get_ob()
