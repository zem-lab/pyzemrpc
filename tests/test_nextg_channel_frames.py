import pytest

from zemrpc.zem.conn.protocol import ProtocolBuilder


def payload(request):
    return request.data.decode("utf-8")


def test_wd_frames_are_available():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_get_wd()).startswith("$GetWD:")
    assert payload(builder.build_set_wd(12.5)).startswith("$SetWD:12.500000,")


@pytest.mark.parametrize("ob", [0, 15817, 16000, 65535])
def test_raw_ob_frame_preserves_integer_dac(ob):
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_set_ob(ob)).startswith(f"$SetOBRaw:{ob},")
    assert payload(builder.build_set_ob_raw(ob)).startswith(f"$SetOBRaw:{ob},")


@pytest.mark.parametrize("ob", [-1, 65536, 16000.0, 16000.5, float("nan"), float("inf"), True])
def test_raw_ob_frame_rejects_invalid_dac(ob):
    builder = ProtocolBuilder("127.0.0.1", 61000)
    with pytest.raises(ValueError, match="integer"):
        builder.build_set_ob_raw(ob)


def test_autofocus_zero_or_seed_range_frames():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_autofocus()).startswith("$AutoFocus:")
    assert payload(builder.build_autofocus(32000, 1500)).startswith("$AutoFocus:32000.000000,1500.000000,")
    with pytest.raises(ValueError):
        builder.build_autofocus(seed_ob=32000)


def test_absolute_beam_shift_frame_uses_specimen_micrometres():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_set_beam_shift(1.25, -0.75)).startswith("$SetBeamShift:1.250000,-0.750000,")
