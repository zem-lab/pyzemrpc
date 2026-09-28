#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import functools
import numpy as np
from matplotlib.backend_bases import MouseButton, MouseEvent
from qtpy.QtGui import QCursor
from qtpy.QtWidgets import QLabel, QMenu

from jgb.gui.qt import qt_util
from jgb.gui.qt.widgets.mpl_qpanel import QMplPanelWithToolbar

from zemrpc.zem.models import ZemImage, valid_image_bounds
from zemrpc.zem.zem_api import zem_api


class ZemImgViewer:
    def __init__(self, panel):
        self.widget, self.layout = qt_util.init_panel_with_widget(panel, QMplPanelWithToolbar)
        self.canvas = self.widget.plot_canvas

        self.gid_zem_img = "zem_img"
        self.gid_zem_img_cmarker = "zem_img_cmarker"
        self._stage_navigation_available = False
        self.coordinate_label = QLabel(self.widget.navi_toolbar)
        self.widget.navi_toolbar.addWidget(self.coordinate_label)

        self.canvas.init_ss(self)

    def update_sem_image(self, zem_img: ZemImage):
        self._stage_navigation_available = False
        if zem_img is None:
            self.canvas.clear_all()
            self.coordinate_label.clear()
        else:
            img = zem_img.img
            if valid_image_bounds(zem_img.bounds):
                x_min, y_min, x_max, y_max = zem_img.bounds
                extent = (x_max, x_min, y_max, y_min)
                self._stage_navigation_available = True
                self.coordinate_label.setText("样品台坐标（μm）")
            else:
                h, w = img.shape[:2]
                extent = (-0.5, w - 0.5, h - 0.5, -0.5)
                self.coordinate_label.setText("无有效场宽或台位 · 像素坐标（px）")
            kwargs = dict(cmap="gray", vmin=0, vmax=255 if img.dtype == np.uint8 else 65535,
                          extent=extent, aspect="equal")
            self.canvas.update_ui(self.gid_zem_img, self.canvas.axes.imshow(img, **kwargs))
            self.canvas.axes.set_aspect("equal", adjustable="box")
            self.canvas.set_lims(extent[:2], extent[2:])

            self.canvas.update_ui(self.gid_zem_img_cmarker, self.canvas.axes.scatter(
                (extent[0] + extent[1]) / 2, (extent[2] + extent[3]) / 2, c="green", marker="+", zorder=10))

        self.canvas.draw()
        self.widget.navi_toolbar.update()
        self.widget.navi_toolbar.push_current()

    def on_click(self, event: MouseEvent):
        if event.xdata is None or event.ydata is None:
            return

        if not self.canvas.has_ui(self.gid_zem_img) or not self._stage_navigation_available:
            return

        if event.button == MouseButton.RIGHT:
            self._popup_menu(
                [
                    ("移动至此", functools.partial(self._slot_goto, (event.xdata, event.ydata))),
                ]
            )

    def _popup_menu(self, items):
        menu = QMenu(self.canvas)
        for label, callback in items:
            action = menu.addAction(label)
            action.triggered.connect(callback)
        menu.exec(QCursor.pos())

    def _slot_goto(self, xy, checked: bool = False):
        if self._stage_navigation_available:
            zem_api.stage_xy_goto(xy)
