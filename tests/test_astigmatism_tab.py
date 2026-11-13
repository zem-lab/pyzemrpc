import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qtpy.QtWidgets import QApplication

from zemrpc.gui.widgets import astigmatism
from zemrpc.zem.conn.protocol import ProtocolBuilder, RespPacket, ReqPacket
from zemrpc.zem.zem_rpc_device import ZemRpcDevice
from zemrpc.tools.virtual_zem.virtual_zem import RemoteZem, VirtualZem, ZemRespBuilder


@pytest.fixture
def tab(monkeypatch):
    app = QApplication.instance() or QApplication([])
    work = []
    monkeypatch.setattr(astigmatism.ctx.async_executor, "run", work.append)
    widget = astigmatism.AstigmatismTab()
    widget.work = work
    yield widget
    assert app is not None


def virtual_device():
    """A ZemRpcDevice-like object whose UDP send is answered by VirtualZem in-process."""
    zem = VirtualZem()
    server = SimpleNamespace(zem_dev=zem, builder=ZemRespBuilder(), _send=Mock())
    for name in dir(RemoteZem):
        if name.startswith("resp_"):
            setattr(server, name, getattr(RemoteZem, name).__get__(server))

    def send(request):
        RemoteZem.process_packet(server, ReqPacket(("127.0.0.1", 61000), request.data))
        return RespPacket(server._send.call_args.args[1])

    device = SimpleNamespace(builder=ProtocolBuilder("127.0.0.1", 61000), send=send,
                             m=SimpleNamespace(optics=None, ast=None, stig_x=None, stig_y=None))
    for name in dir(ZemRpcDevice):
        if name in {"get_ast", "set_ast"} or "stig" in name or "optics_percentage" in name:
            setattr(device, name, getattr(ZemRpcDevice, name).__get__(device))
    return device, zem


def test_tab_opens_and_edits_without_device_traffic(tab):
    assert tab.work == []
    tab.raw["A"].setValue(5)
    tab.pct["x"].setValue(1.5)
    assert tab.work == []
    assert tab.raw["A"].maximum() == 4095


def test_busy_state_and_readback_display(tab):
    tab.apply_raw()
    assert len(tab.work) == 1 and tab.busy and not tab.read.isEnabled()
    tab.apply_raw()
    assert len(tab.work) == 1
    tab.complete("设置", True, {"ast": (5, -6), "x": 0.12, "y": -0.15})
    assert not tab.busy and tab.read.isEnabled()
    assert (tab.raw["B"].value(), tab.pct["y"].value()) == (-6, -0.15)
    tab.complete("设置", False, ValueError("boom"))
    assert "失败" in tab.status.text() and "boom" in tab.output.toPlainText()


def test_operations_against_virtual_zem(tab, monkeypatch):
    device, zem = virtual_device()
    operations = []
    monkeypatch.setattr(tab, "run", lambda description, operation: operations.append(operation))

    tab.pct["x"].setValue(50)
    tab.pct["y"].setValue(-12.5)
    tab.apply_pct()
    result = operations.pop()(device)
    assert result["ast"] == (2047, -511)
    assert result["x"] == pytest.approx(2047 * 100 / 4095)

    tab.pct_step.setValue(1)
    tab.step("y", 1)
    assert operations.pop()(device)["ast"][1] == int((-511 * 100 / 4095 + 1) / 100 * 4095)

    tab.raw["A"].setValue(100)
    tab.raw["B"].setValue(-200)
    tab.apply_raw()
    assert operations.pop()(device)["ast"] == (100, -200)

    rejected = SimpleNamespace(set_stig_x=lambda value: None)
    with pytest.raises(ValueError):
        astigmatism.set_stig(rejected, "x", 1)
