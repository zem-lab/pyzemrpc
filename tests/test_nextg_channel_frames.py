import pytest

from zemrpc.zem.conn.protocol import ProtocolBuilder


def payload(request):
    return request.data.decode("utf-8")


def test_wd_frames_are_available():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_get_wd()).startswith("$GetWD:")
    assert payload(builder.build_set_wd(12.5)).startswith("$SetWD:12.500000,")


def test_autofocus_zero_or_seed_range_frames():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_autofocus()).startswith("$AutoFocus:")
    assert payload(builder.build_autofocus(32000, 1500)).startswith("$AutoFocus:32000.000000,1500.000000,")
    with pytest.raises(ValueError):
        builder.build_autofocus(seed_ob=32000)


def test_absolute_beam_shift_frame_uses_specimen_micrometres():
    builder = ProtocolBuilder("127.0.0.1", 61000)
    assert payload(builder.build_set_beam_shift(1.25, -0.75)).startswith("$SetBeamShift:1.250000,-0.750000,")
