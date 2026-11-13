import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from zemrpc.zem.conn.protocol import EnumCmd, EnumCmdLevel, ProtocolBuilder, RespPacket, ReqPacket, append_crc
from zemrpc.zem.zem_rpc_device import ZemModel, ZemRpcDevice
from zemrpc.tools.virtual_zem.virtual_zem import RemoteZem, VirtualZem, ZemRespBuilder


def test_wire_names_match_instrument_registration():
    # Instrument ExternModel registers these names; the command table is case-sensitive.
    assert [c.cmd for c in (EnumCmd.GetAst, EnumCmd.SetAst)] == ["GetAst", "SetAst"]
    assert [c.cmd for c in (EnumCmd.GetStigX, EnumCmd.SetStigX, EnumCmd.GetStigY, EnumCmd.SetStigY)] == ["GetStigX", "SetStigX", "GetStigY", "SetStigY"]
    assert "GetAST" not in EnumCmd.__members__
    assert {c.cmd_level for c in (EnumCmd.SetAst, EnumCmd.SetStigX, EnumCmd.SetStigY)} == {EnumCmdLevel.ADVANCED}
    assert {c.cmd_level for c in (EnumCmd.GetAst, EnumCmd.GetStigX, EnumCmd.GetStigY)} == {EnumCmdLevel.BASIC}


def test_builders_and_parsers():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert builder.build_set_ast(120, -80).data.decode().startswith("$SetAst:120,-80,127.0.0.1:61000,")
    assert builder.build_get_ast().data.decode().startswith("$GetAst:,127.0.0.1:61000,")
    assert builder.build_set_stig("x", -12.5).data.decode().startswith("$SetStigX:-12.500000,")
    assert builder.build_get_stig("y").cmd == EnumCmd.GetStigY
    assert RespPacket(append_crc("$GetAst:120,-80,")).parse_ast() == (120, -80)
    assert RespPacket(append_crc("$GetStigX:-49.98779,")).parse_stig() == pytest.approx(-49.98779)


@pytest.mark.parametrize("args", [(1.0, 0), (True, 0), (0, 65536), ("1", 0), (0, None)])
def test_invalid_raw_rejected_before_network(args):
    device = SimpleNamespace(builder=ProtocolBuilder(), send=Mock())
    with pytest.raises(ValueError):
        ZemRpcDevice.set_ast(device, *args)
    device.send.assert_not_called()


@pytest.mark.parametrize("value", [100.001, -101, float("nan"), float("inf"), True, "1", None])
def test_invalid_percentage_rejected_before_network(value):
    device = SimpleNamespace(builder=ProtocolBuilder(), send=Mock())
    with pytest.raises(ValueError):
        ZemRpcDevice.set_stig(device, "x", value)
    device.send.assert_not_called()


def test_invalid_axis_rejected():
    with pytest.raises(ValueError):
        ProtocolBuilder().build_get_stig("z")


def test_set_returns_device_readback_and_failure_is_not_faked():
    assert {"ast", "stig_x", "stig_y"} <= ZemModel.model_fields.keys()
    device = SimpleNamespace(builder=ProtocolBuilder(), m=SimpleNamespace(ast=None, stig_x=None))
    device.get_ast = lambda: ZemRpcDevice.get_ast(device)
    device.get_stig = lambda axis: ZemRpcDevice.get_stig(device, axis)
    device.send = Mock(side_effect=[RespPacket(append_crc("$SetStigX:Acknowledge,Error Code:0,")),
                                   RespPacket(append_crc("$GetStigX:49.98779,"))])
    assert ZemRpcDevice.set_stig(device, "x", 50) == pytest.approx(49.98779)
    assert device.m.stig_x == pytest.approx(49.98779)
    device.send = Mock(side_effect=[RespPacket(append_crc("$SetAst:Acknowledge,Error Code:0,")),
                                   RespPacket(append_crc("$GetAst:7,-3,"))])
    assert ZemRpcDevice.set_ast(device, 7, -3) == (7, -3)
    assert [c.args[0].cmd for c in device.send.call_args_list] == [EnumCmd.SetAst, EnumCmd.GetAst]
    device.send = Mock(return_value=RespPacket(append_crc("$SetAst:Acknowledge,Error Code:1,")))
    assert ZemRpcDevice.set_ast(device, 1, 1) is None
    assert device.send.call_count == 1
    assert device.m.ast == (7, -3)


def test_virtual_server_matches_instrument_conversion():
    zem = VirtualZem()
    server = SimpleNamespace(zem_dev=zem, builder=ZemRespBuilder(), _send=Mock())
    server.resp_astigmatism = lambda cmd, packet: RemoteZem.resp_astigmatism(server, cmd, packet)
    builder = ProtocolBuilder("127.0.0.1", 61000)

    def exchange(request):
        RemoteZem.process_packet(server, ReqPacket(("127.0.0.1", 61000), request.data))
        return RespPacket(server._send.call_args.args[1])

    assert exchange(builder.build_get_ast()).parse_ast() == (0, 0)
    assert exchange(builder.build_set_stig("x", 50)).is_ack_ok()
    assert exchange(builder.build_set_stig("y", -50)).is_ack_ok()
    assert exchange(builder.build_get_ast()).parse_ast() == (2047, -2047)
    assert exchange(builder.build_get_stig("x")).parse_stig() == pytest.approx(2047 * 100 / 4095)
    assert exchange(builder.build_set_ast(8000, 1)).is_ack_ok()
    assert exchange(builder.build_get_stig("x")).parse_stig() == pytest.approx(8000 * 100 / 4095)
    assert exchange(builder.build_set(EnumCmd.SetStigX, "250")).is_ack_ok()
    assert zem.ast[0] == 4095
    for invalid in ["1", "1,x", "1,2,3"]:
        assert exchange(builder.build_set(EnumCmd.SetAst, invalid)).is_error()
    assert exchange(builder.build_set(EnumCmd.SetStigY, "x")).is_error()
    assert zem.ast == [4095, 1]


def test_tab_opens_without_device_traffic_and_shows_readback(monkeypatch):
    from qtpy.QtWidgets import QApplication
    from zemrpc.gui.widgets import astigmatism

    app = QApplication.instance() or QApplication([])
    run = Mock()
    monkeypatch.setattr(astigmatism.ctx.async_executor, "run", run)
    tab = astigmatism.AstigmatismTab()
    run.assert_not_called()
    tab.raw["A"].setValue(5)
    run.assert_not_called()
    tab.apply_raw()
    assert run.call_count == 1 and tab.busy and not tab.read.isEnabled()
    tab.complete("设置", True, {"ast": (5, -6), "x": 0.12, "y": -0.15})
    assert not tab.busy and tab.read.isEnabled()
    assert (tab.raw["B"].value(), tab.pct["y"].value()) == (-6, -0.15)
    tab.complete("设置", False, ValueError("boom"))
    assert "失败" in tab.status.text()
    assert app is not None
