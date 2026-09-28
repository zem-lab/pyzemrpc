"""Capture metadata and rendering regressions; no device connection or commands."""
import base64
import os
from types import SimpleNamespace
import warnings

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np
import pytest
from addict import Dict

from zemrpc.zem.conn.rpc_protocol import RpcSnapResp
from zemrpc.zem.models import Bounds, MetaItem, SnapArgs, StagePos, ZemImage


def metadata(values):
    meta = Dict()
    meta.update(values)
    return meta


def response(width=0, height=0, x=12000, y=3500):
    image = np.random.default_rng(6).integers(0, 256, (512, 512), dtype=np.uint8)
    encoded = base64.b64encode(cv2.imencode('.png', image)[1]).decode()
    return RpcSnapResp(result={"img": encoded, "meta": {"zem": {
        "Model": "TestSEM", "Stage": {"x": x, "y": y},
        "Hv": {"RealAccVol": 8000}, "ob": {"ob": 23000, "wd": 7.8},
        "imaging": {"ScanWidth": width, "ScanHeight": height, "Magnification": 50,
                    "Rotation": 0, "Detector": "BSE"},
    }}})


@pytest.mark.parametrize("width,height,x,y", [(0, 0, 12000, 3500), (-1, 200, 0, 0),
    (200, None, 0, 0), (float('nan'), 200, 0, 0), (200, 200, 'NaN', 0), (200, 200, 0, float('inf'))])
def test_unknown_geometry_does_not_create_physical_bounds(width, height, x, y):
    assert response(width, height, x, y).parse_img_bounds() is None


def test_normal_capture_bounds_and_pixel_sizes():
    capture = response(1000, 500)
    assert capture.parse_img_bounds() == Bounds(11500, 3250, 12500, 3750)
    meta = capture.parse_img_meta((256, 512))
    assert meta[MetaItem.PixelSize] == 1000 / 512
    assert meta['pixel_size_y_um'] == 500 / 256
    assert meta['field_size_available']


def test_snap_uses_its_response_instead_of_connection_cache(monkeypatch):
    from zemrpc.zem.zem_api import ZemApi, zem_api

    monkeypatch.setattr(zem_api, '_init_sync_done', True)
    capture = response()
    cached = Dict({MetaItem.Magnification: 500, MetaItem.FieldSize: 254,
                   MetaItem.PixelSize: 254 / 512, MetaItem.AccVoltage: 0,
                   MetaItem.Position: StagePos(x=-999, y=-999)})
    model = SimpleNamespace(to_img_meta=lambda args: cached.copy())
    device = SimpleNamespace(m=model, snap_rpc=lambda *args: capture)
    fake = SimpleNamespace(device=device, img_processor_mgr=lambda image: image)
    image = ZemApi.snap_ng(fake, SnapArgs())
    assert image.img.shape == (512, 512)
    assert image.meta[MetaItem.Magnification] == 50
    assert image.meta[MetaItem.AccVoltage] == 8000
    assert image.meta[MetaItem.Position].x == 12000
    assert image.meta[MetaItem.FieldSize] == image.pixel_size == 0
    assert image.bounds is None
    assert image.calc_stage_xy(256, 256) is None
    assert image.meta.rpc_meta == capture.result['meta']
    assert image.meta.rpc_meta is not capture.result['meta']


@pytest.fixture
def viewer():
    from qtpy.QtWidgets import QApplication, QWidget
    from zemrpc.gui.widgets.zem_img_viewer import ZemImgViewer

    app = QApplication.instance() or QApplication([])
    panel = QWidget()
    widget = ZemImgViewer(panel)
    widget.canvas.resize(800, 500)
    yield widget
    panel.close()
    app.processEvents()


def test_zero_field_renders_square_pixels_and_cannot_move_stage(viewer, monkeypatch):
    from zemrpc.gui.widgets.zem_img_viewer import zem_api

    moves = []
    monkeypatch.setattr(zem_api, 'stage_xy_goto', lambda xy: moves.append(xy))
    capture = response()
    # Already saved legacy images can carry a stale positive pixel size and
    # degenerate bounds, so the viewer must validate the extent itself too.
    image = ZemImage(img=capture.parse_image(), meta=metadata({
        'bounds': Bounds(12000, 3500, 12000, 3500),
        MetaItem.PixelSize: 254 / 512, MetaItem.Position: StagePos(x=12000, y=3500)}))
    with warnings.catch_warnings():
        warnings.simplefilter('error', UserWarning)
        viewer.update_sem_image(image)
    artist = viewer.canvas.ui_items[viewer.gid_zem_img]
    assert np.array_equal(np.asarray(artist.get_array()), image.img)
    assert tuple(artist.get_extent()) == (-.5, 511.5, 511.5, -.5)
    box = artist.get_window_extent()
    assert box.width == pytest.approx(box.height)
    assert box.width > 100
    assert 'px' in viewer.coordinate_label.text()
    viewer._slot_goto((100, 100))
    assert moves == []
    assert image.calc_stage_xy(256, 256) is None


def test_viewer_recovers_physical_coordinates_and_clear(viewer, monkeypatch):
    from zemrpc.gui.widgets.zem_img_viewer import zem_api

    unknown = response()
    normal = response(1000, 1000)
    for capture in (normal, unknown, normal):
        viewer.update_sem_image(ZemImage(img=capture.parse_image(), meta=metadata(capture.parse_img_meta((512, 512)))))
    assert viewer._stage_navigation_available
    artist = viewer.canvas.ui_items[viewer.gid_zem_img]
    assert tuple(artist.get_extent()) == (12500, 11500, 4000, 3000)
    assert 'μm' in viewer.coordinate_label.text()
    moves = []
    monkeypatch.setattr(zem_api, 'stage_xy_goto', lambda xy: moves.append(xy))
    viewer._slot_goto((12000, 3500))
    assert moves == [(12000, 3500)]
    viewer.update_sem_image(None)
    assert not viewer.canvas.has_ui(viewer.gid_zem_img)
    assert not viewer._stage_navigation_available
    viewer.update_sem_image(ZemImage(img=normal.parse_image(), meta=metadata(normal.parse_img_meta((512, 512)))))
    assert viewer.canvas.has_ui(viewer.gid_zem_img)
