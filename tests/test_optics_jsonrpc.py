import copy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from jsonrpcserver import dispatch

from zemrpc.tools.virtual_zem import jsonrpc_server
from zemrpc.tools.virtual_zem.virtual_zem import VirtualZem, RemoteZem, ZemRespBuilder
from zemrpc.zem.conn.protocol import ProtocolBuilder, ReqPacket
from zemrpc.zem.conn.rpc_protocol import JsonRpcBuilder, RpcStatusResp
from zemrpc.zem.context import ctx
from zemrpc.zem.models import EnumCmdLevel, ZemException
from zemrpc.zem.zem_rpc_device import ZemModel, ZemRpcDevice


@pytest.fixture
def rpc(monkeypatch):
    virtual = VirtualZem()
    monkeypatch.setattr(jsonrpc_server, "zem", SimpleNamespace(zem_dev=virtual))
    device = object.__new__(ZemRpcDevice)
    device.m = ZemModel(ctx=ctx)
    device.rpc_builder = JsonRpcBuilder()
    device._work_mode = EnumCmdLevel.ADVANCED
    device.send = Mock(side_effect=AssertionError("JSON-RPC must not send UDP"))
    device.zem_rpc = Mock(side_effect=lambda req: json.loads(dispatch(json.dumps(req))))
    return device, virtual


def test_status_and_partial_writes_roundtrip_through_jsonrpc_dispatch(rpc):
    device, virtual = rpc
    status = device.status_rpc()
    assert status.optics.astigmatism.x == 0
    assert status.result["optics"]["unit"] == "percent"
    assert status.software == virtual.software
    assert device.set_ast_rpc(123, -456).astigmatism.y_dac == -456
    result = device.set_astigmatism_rpc(y=25)
    assert result.astigmatism.x_dac == 123
    assert result.astigmatism.y_dac == 1023
    assert result.astigmatism.y == pytest.approx(1023 * 100 / 4095)
    assert device.zem_rpc.call_args.args[0]["params"] == [None, 25]
    result = device.set_alignment_rpc(up_x=-50, down_y=100)
    assert result.alignment.up.x_dac == -2047
    assert result.alignment.up.y_dac == result.alignment.down.x_dac == 0
    assert result.alignment.down.y_dac == 4095
    assert device.status_rpc().optics == result == device.m.optics
    assert device.m.ast == (123, 1023)
    assert device.m.stig_x == result.astigmatism.x
    assert device.m.up_center_x == result.alignment.up.x
    assert device.m.down_center_y == 100
    device.send.assert_not_called()


def test_udp_or_local_changes_are_visible_in_status(rpc):
    device, virtual = rpc
    server = SimpleNamespace(zem_dev=virtual, builder=ZemRespBuilder(), _send=Mock())
    builder = ProtocolBuilder("127.0.0.1", 61000)
    RemoteZem.process_packet(server, ReqPacket(None, builder.build_set_ast(-100, 200).data))
    assert device.status_rpc().optics.astigmatism.x_dac == -100
    virtual.optics_dac["astig_c"] = 1234  # Local UI/model update, independent of RPC cache.
    assert device.status_rpc().optics.alignment.up.x_dac == 1234


@pytest.mark.parametrize("method,params", [
    ("SemSetAstigmatism", [10, 101]), ("SemSetAlignment", [10, None, None, -101]),
    ("SemSetAstigmatismDac", [10, 4096]), ("SemSetAstigmatismDac", [1.5, 2]),
    ("SemSetAstigmatism", []), ("SemSetAlignment", [None, None, None, None]),
    ("SemSetAstigmatism", [True, 0]), ("SemSetAlignment", ["10", None, None, None]),
])
def test_invalid_remote_request_rejected_before_any_axis_changes(rpc, method, params):
    device, virtual = rpc
    before = virtual.get_optics_state()
    response = device.zem_rpc({"jsonrpc": "2.0", "id": 90, "method": method, "params": params})
    assert response["error"]["code"] == -32602
    assert virtual.get_optics_state() == before


@pytest.mark.parametrize("value", [True, "5", float("nan"), float("inf"), -101, 101])
def test_invalid_client_input_never_reaches_network(rpc, value):
    device, _ = rpc
    with pytest.raises(ValueError):
        device.set_alignment_rpc(up_x=1, down_y=value)
    with pytest.raises(ValueError):
        device.set_astigmatism_rpc(x=value)
    device.zem_rpc.assert_not_called()


def test_basic_permission_blocks_all_jsonrpc_optics_writes(rpc):
    device, _ = rpc
    device._work_mode = EnumCmdLevel.BASIC
    for call in (lambda: device.set_astigmatism_rpc(x=1), lambda: device.set_ast_rpc(1, 2),
                 lambda: device.set_alignment_rpc(down_x=1)):
        with pytest.raises(ZemException):
            call()
    device.zem_rpc.assert_not_called()
    assert device.status_rpc().optics.astigmatism.x == 0


@pytest.mark.parametrize("reply", [
    {"error": {"code": -32601, "message": "Method not found"}},
    {"error": {"code": -32000, "message": "Busy"}}, {}, {"result": {}},
    {"result": {"optics": {}}},
])
def test_error_or_invalid_set_response_is_not_success_and_does_not_retry(rpc, reply):
    device, _ = rpc
    previous = device.status_rpc().optics
    device.zem_rpc = Mock(return_value=reply)
    with pytest.raises((ZemException, ValueError)):
        device.set_astigmatism_rpc(x=5)
    assert device.m.optics == previous
    device.zem_rpc.assert_called_once()
    device.send.assert_not_called()


def test_older_status_clears_optics_and_legacy_virtual_wrapper_is_supported(rpc):
    device, virtual = rpc
    state = virtual.get_zem_status()
    assert RpcStatusResp(result={"zem": state}).optics == RpcStatusResp(result=state).optics
    device.status_rpc()
    device.zem_rpc = Mock(return_value={"result": {"Model": "old"}})
    assert device.status_rpc().optics is None
    assert device.m.optics is device.m.ast is device.m.stig_x is device.m.up_center_x is None


def test_invalid_status_is_rejected_before_cache_update(rpc):
    device, virtual = rpc
    previous = device.status_rpc().optics
    reply = copy.deepcopy(virtual.get_zem_status())
    reply["scan_relay_mask"] = 7
    reply["optics"]["alignment"]["up"]["x"] = float("nan")
    device.zem_rpc = Mock(return_value={"result": reply})
    with pytest.raises(ValueError):
        device.status_rpc()
    assert device.m.optics == previous and device.m.scan_relay_mask == 15


def test_unavailable_percentages_are_null_not_zero(rpc):
    _, virtual = rpc
    state = virtual.get_zem_status()
    state["optics"]["astigmatism"]["x"] = None
    assert RpcStatusResp(result=state).optics.astigmatism.x is None
    assert RpcStatusResp(result=state).optics.astigmatism.x_dac == 0


def test_high_level_jsonrpc_does_not_trigger_udp_sync(monkeypatch, rpc):
    from zemrpc.zem.zem_api import ZemApi, zem_api

    device, _ = rpc
    monkeypatch.setattr(zem_api, "_init_sync_done", False)
    monkeypatch.setattr(zem_api, "sync", Mock(side_effect=AssertionError("Unexpected UDP sync")))
    api = SimpleNamespace(device=device)
    ZemApi.set_rpc_url(api, "http://127.0.0.1:54321/api/v1/jsonrpc")
    assert device.m.protocol_ng.url.endswith("/api/v1/jsonrpc")
    assert ZemApi.set_astigmatism_rpc(api, x=10).astigmatism.x_dac == 409
    assert ZemApi.set_alignment_rpc(api, down_x=20).alignment.down.x_dac == 819
    assert ZemApi.set_ast_rpc(api, -1, 2).astigmatism.x_dac == -1
    assert ZemApi.status_rpc(api).optics == device.m.optics
    zem_api.sync.assert_not_called()
