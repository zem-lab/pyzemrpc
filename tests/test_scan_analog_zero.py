import pytest

from zemrpc.zem.scan_analog_zero import ScanAnalogZeroJsonRpc, validate_state
from zemrpc.zem.conn.rpc_protocol import RpcStatusResp


def state(**changes):
    return dict(schema="normal-scan-analog-zero-v1", mode="normal", sin=31000, cos=32000,
                sin_range=[0, 65535], cos_range=[0, 65535], saved=None,
                beam_raw=dict(x=0, y=0), **changes)


def test_status_old_server_and_new_field():
    assert RpcStatusResp(result={}).scan_analog_zero is None
    assert RpcStatusResp(result={"scan_analog_zero": state()}).scan_analog_zero["sin"] == 31000


def test_read_uses_existing_status():
    client = ScanAnalogZeroJsonRpc("http://unused")
    calls = []
    client.call = lambda method, params: calls.append((method, params)) or {"scan_analog_zero": state()}
    assert client.read()["cos"] == 32000
    assert calls == [("Status", [])]


@pytest.mark.parametrize("value", [-1, 65536, 1.5, True, "31000", None])
def test_invalid_write_never_reaches_transport(value):
    client = ScanAnalogZeroJsonRpc("http://unused")
    client.call = lambda *args: pytest.fail("invalid write reached transport")
    with pytest.raises(ValueError):
        client.set(value, 32000)


def test_no_retry_on_ambiguous_write():
    client = ScanAnalogZeroJsonRpc("http://unused")
    calls = []
    def fail(method, params):
        calls.append(method)
        raise TimeoutError()
    client.call = fail
    with pytest.raises(TimeoutError):
        client.set(31000, 32000)
    assert calls == ["SemSetScanAnalogZero"]


def test_save_requires_matching_live_and_saved_pair():
    client = ScanAnalogZeroJsonRpc("http://unused")
    calls = []
    value = state()
    client.call = lambda method, params: calls.append((method, params)) or value
    with pytest.raises(ValueError):
        client.save(31000, 32000)
    value["saved"] = dict(sin=31000, cos=32000)
    assert client.save(31000, 32000)["saved"] == value["saved"]
    assert calls[-1] == ("SemSaveScanAnalogZero", [31000, 32000])
    value["sin"] = 31001
    with pytest.raises(ValueError):
        client.save(31000, 32000)


def test_live_channel_limits_are_required():
    value = state()
    value["sin_range"] = [31500, 65535]
    with pytest.raises(ValueError):
        validate_state(value)
