from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from zemrpc.zem.conn.protocol import EnumCmd, EnumCmdLevel, ProtocolBuilder, RespPacket, ReqPacket, append_crc
from zemrpc.zem.conn.rpc_protocol import RpcStatusResp
from zemrpc.zem.software_info import SoftwareInfo
from zemrpc.zem.zem_rpc_device import ZemRpcDevice, ZemModel
from zemrpc.tools.virtual_zem.virtual_zem import RemoteZem, VirtualZem, ZemRespBuilder

INFO = SoftwareInfo(version="1.5.6", commit_id="abcdef0123" * 4)


def response(payload):
    return RespPacket(append_crc(f"$GetSoftwareInfo:{payload},"))


def test_udp_wire_and_readonly_permission():
    request = ProtocolBuilder("127.0.0.1", 61000).build_get_software_info()
    assert request.data.decode().startswith("$GetSoftwareInfo:,127.0.0.1:61000,")
    assert request.cmd.cmd_level == EnumCmdLevel.BASIC
    assert not request.cmd.need_args
    assert response(f"{INFO.version},{INFO.commit_id}").parse_software_info() == INFO
    assert response("1.5.5,").parse_software_info().commit_id == ""


@pytest.mark.parametrize("payload", ["1.5.6", "1.5.6,hash,extra", "Acknowledge,Error Code:1", "Acknowledge,Error Code:0"])
def test_bad_response_is_not_software_identity(payload):
    with pytest.raises(ValueError):
        response(payload).parse_software_info()


def test_old_server_and_json_status_clear_cached_identity():
    assert response("Invalid command").parse_software_info() is None
    assert "software" in ZemModel.model_fields
    device = SimpleNamespace(m=SimpleNamespace(software=INFO), builder=ProtocolBuilder(),
                             send=Mock(return_value=response("Invalid command")))
    assert ZemRpcDevice.get_software_info(device) is None
    assert device.m.software is None
    device.send.return_value = response(f"{INFO.version},{INFO.commit_id}")
    assert ZemRpcDevice.get_software_info(device) == INFO
    device.rpc_builder = Mock()
    device.zem_rpc = Mock(return_value={"result": {"software": INFO.model_dump()}})
    assert ZemRpcDevice.status_rpc(device).software == INFO
    device.zem_rpc.return_value = {"result": {"Model": "old"}}
    assert ZemRpcDevice.status_rpc(device).software is None
    assert device.m.software is None


def test_real_send_allows_only_unsupported_version_query():
    device = SimpleNamespace(_check_cmd_permission=Mock(), _timeout_multiplier=1,
                             rws=SimpleNamespace(pubsub_send=Mock(return_value=response("Invalid command"))))
    # Use the underlying request path, so retries cannot hide protocol errors.
    result = ZemRpcDevice.pubsub_send.__wrapped__(device, ProtocolBuilder().build_get_software_info())
    assert result.parse_software_info() is None


@pytest.mark.parametrize("info", [{"version": 156, "commit_id": "x"}, {"version": "1.5.6"}, "1.5.6"])
def test_malformed_json_identity_rejected(info):
    with pytest.raises(ValueError):
        _ = RpcStatusResp(result={"software": info}).software


def test_virtual_udp_and_http_share_identity():
    zem = VirtualZem()
    server = SimpleNamespace(zem_dev=zem, builder=ZemRespBuilder(), _send=Mock())
    request = ProtocolBuilder("127.0.0.1", 61000).build_get_software_info()
    RemoteZem.process_packet(server, ReqPacket(("127.0.0.1", 61000), request.data))
    udp = RespPacket(server._send.call_args.args[1]).parse_software_info()
    assert udp == RpcStatusResp(result=zem.get_zem_status()).software == zem.software
