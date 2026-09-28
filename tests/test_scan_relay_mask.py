from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest

from zemrpc.zem.conn.protocol import EnumCmd, ProtocolBuilder, RespPacket, ReqPacket, append_crc
from zemrpc.zem.conn.rpc_protocol import RpcStatusResp
from zemrpc.zem.scan_relay import ScanRelayMask, validate_scan_relay_mask
from zemrpc.zem.zem_rpc_device import ZemRpcDevice, ZemModel
from zemrpc.tools.virtual_zem.virtual_zem import RemoteZem, VirtualZem, ZemRespBuilder


@pytest.mark.parametrize("mask", [1, 2, 4, 7, 8, 15, np.int64(7), ScanRelayMask.K1 | ScanRelayMask.K2 | ScanRelayMask.K3])
def test_mask_wire_roundtrip(mask):
    builder = ProtocolBuilder("127.0.0.1", 61000)
    request = builder.build_set_scan_relay_mask(mask)
    assert request.cmd == EnumCmd.SetScanRelayMask
    assert request.data.decode().startswith(f"$SetScanRelayMask:{int(mask)},127.0.0.1:61000,")
    assert builder.build_get_scan_relay_mask().cmd == EnumCmd.GetScanRelayMask
    response = RespPacket(append_crc(f"$GetScanRelayMask:{int(mask)},"))
    assert response.parse_scan_relay_mask() == int(mask)


@pytest.mark.parametrize("mask", [0, -1, 16, 255, True, False, 7.0, 7.5, "7", None, float("nan")])
def test_invalid_mask_rejected_before_network(mask):
    device = SimpleNamespace(builder=ProtocolBuilder(), send=Mock())
    with pytest.raises(ValueError):
        ZemRpcDevice.set_scan_relay_mask(device, mask)
    device.send.assert_not_called()


def test_device_ack_readback_and_error_do_not_fake_success():
    device = SimpleNamespace(builder=ProtocolBuilder(), m=SimpleNamespace(scan_relay_mask=None))
    device.send = Mock(side_effect=[RespPacket(append_crc("$SetScanRelayMask:Acknowledge,Error Code:0,")),
                                   RespPacket(append_crc("$GetScanRelayMask:7,"))])
    device.get_scan_relay_mask = lambda: ZemRpcDevice.get_scan_relay_mask(device)
    assert ZemRpcDevice.set_scan_relay_mask(device, 7) == 7
    assert device.m.scan_relay_mask == 7
    assert [c.args[0].cmd for c in device.send.call_args_list] == [EnumCmd.SetScanRelayMask, EnumCmd.GetScanRelayMask]
    device.send = Mock(return_value=RespPacket(append_crc("$SetScanRelayMask:Acknowledge,Error Code:1,")))
    assert ZemRpcDevice.set_scan_relay_mask(device, 15) is None
    assert device.send.call_count == 1
    assert device.m.scan_relay_mask == 7


def test_json_status_and_old_server_compatibility():
    assert "scan_relay_mask" in ZemModel.model_fields
    assert RpcStatusResp(result={"scan_relay_mask": 7}).scan_relay_mask == 7
    assert RpcStatusResp(result={"Model": "old"}).scan_relay_mask is None
    device = SimpleNamespace(m=SimpleNamespace(scan_relay_mask=7), rpc_builder=Mock(),
                             zem_rpc=Mock(return_value={"result": {"scan_relay_mask": 15}}))
    assert ZemRpcDevice.status_rpc(device).scan_relay_mask == 15
    assert device.m.scan_relay_mask == 15
    device.zem_rpc.return_value = {"result": {"Model": "old"}}
    assert ZemRpcDevice.status_rpc(device).scan_relay_mask is None
    assert device.m.scan_relay_mask is None


@pytest.mark.parametrize("value", [0, 16, True, "7", 7.0])
def test_invalid_status_mask_is_not_silently_accepted(value):
    with pytest.raises(ValueError):
        _ = RpcStatusResp(result={"scan_relay_mask": value}).scan_relay_mask


def test_virtual_server_udp_set_get_and_status_share_one_mask():
    zem = VirtualZem()
    server = SimpleNamespace(zem_dev=zem, builder=ZemRespBuilder(), _send=Mock())
    builder = ProtocolBuilder("127.0.0.1", 61000)

    def exchange(request):
        RemoteZem.process_packet(server, ReqPacket(("127.0.0.1", 61000), request.data))
        return RespPacket(server._send.call_args.args[1])

    assert exchange(builder.build_get_scan_relay_mask()).parse_scan_relay_mask() == 15
    assert exchange(builder.build_set_scan_relay_mask(7)).is_ack_ok()
    assert exchange(builder.build_get_scan_relay_mask()).parse_scan_relay_mask() == 7
    assert zem.get_zem_status()["scan_relay_mask"] == 7
    for invalid in ["0", "16", "7.5", "x", "7,15"]:
        response = exchange(builder.build_set(EnumCmd.SetScanRelayMask, invalid))
        assert response.is_error()
        assert zem.scan_relay_mask == 7
    assert exchange(builder.build_set_scan_relay_mask(15)).is_ack_ok()
    assert zem.get_zem_status()["scan_relay_mask"] == 15
