#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import functools
import numpy as np
from matplotlib.backend_bases import MouseButton, MouseEvent

from jgb.gui.qt import qt_util
from jgb.gui.qt.widgets.mpl_qpanel import QMplPanelWithToolbar

from zemrpc.zem.models import ZemImage
from zemrpc.zem.zem_api import zem_api


class ZemImgViewer:
    def __init__(self, panel):
        self.widget, self.layout = qt_util.init_panel_with_widget(panel, QMplPanelWithToolbar)
        self.canvas = self.widget.plot_canvas

        self.gid_zem_img = "zem_img"
        self.gid_zem_img_cmarker = "zem_img_cmarker"

        self.canvas.init_ss(self)

    def update_sem_image(self, zem_img: ZemImage):
        if zem_img is None:
            self.canvas.axes.cla()
        else:
            img = zem_img.img
            x_min, y_min, x_max, y_max = zem_img.bounds
            kwargs = dict(cmap="gray", vmin=0, vmax=255 if img.dtype == np.uint8 else 65535, extent=(x_max, x_min, y_max, y_min))
            self.canvas.update_ui(self.gid_zem_img, self.canvas.axes.imshow(img, **kwargs))
            self.canvas.set_lims((x_max, x_min), (y_max, y_min))

            # h, w, c = cv_util.cv2_hwc(img)
            # self.canvas.update_ui(self.gid_zem_img_cmarker, self.canvas.axes.scatter(w / 2, h / 2, s=5, marker="+", c="g"))
            x_min, y_min, x_max, y_max = zem_img.bounds
            self.canvas.update_ui(self.gid_zem_img_cmarker, self.canvas.axes.scatter((x_min + x_max) / 2, (y_min + y_max) / 2, c="green", marker="+", zorder=10))

        self.canvas.draw()
        self.widget.navi_toolbar.update()
        self.widget.navi_toolbar.push_current()

    def on_click(self, event: MouseEvent):
        if event.xdata is None or event.ydata is None:
            return

        if not self.canvas.has_ui(self.gid_zem_img):
            return

        if event.button == MouseButton.RIGHT:
            qt_util.popup_menu(self.canvas, ("移动至此", functools.partial(self._slot_goto, (event.xdata, event.ydata))))

    def _slot_goto(self, xy, checked: bool = False):
        zem_api.stage_xy_goto(xy)
