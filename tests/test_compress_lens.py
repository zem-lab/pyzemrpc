from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from zemrpc.zem.zem_rpc_device import ZemModel, ZemRpcDevice
from zemrpc.zem.conn.protocol import ProtocolBuilder, EnumCmd


def test_compress_values_are_declared_observable_fields():
    assert {'compress_a', 'compress_b'} <= ZemModel.model_fields.keys()


def test_compress_builders_use_registered_command_and_preserve_precision():
    builder = ProtocolBuilder()
    for axis in ('a', 'b'):
        request = getattr(builder, f'build_set_compress_{axis}')(17.582418)
        assert request.cmd == EnumCmd[f'SetCompress{axis.upper()}']
        assert '17.582418' in str(request.data)


@pytest.mark.parametrize('axis', ['a', 'b'])
def test_compress_roundtrip_and_invalid_values(axis):
    state = SimpleNamespace()
    response = SimpleNamespace(is_ack_ok=lambda: True, **{f'parse_compress_{axis}':lambda:17.582418})
    device = SimpleNamespace(m=state, send=Mock(return_value=response), builder=Mock())
    setter = getattr(ZemRpcDevice, f'set_compress_{axis}')
    getter = getattr(ZemRpcDevice, f'get_compress_{axis}')
    assert setter(device, 17.582418) == 17.582418
    assert getter(device) == 17.582418
    assert getattr(state, f'compress_{axis}') == 17.582418
    calls = device.send.call_count
    for value in [-1, 101, float('nan'), float('inf'), True]:
        with pytest.raises(ValueError): setter(device, value)
    assert device.send.call_count == calls
