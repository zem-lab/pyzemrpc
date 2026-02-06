#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import math
import functools
import numpy as np
from qtpy.QtGui import QCursor, QIcon
from qtpy.QtWidgets import QMenu, QToolButton
from matplotlib.patches import Circle, Rectangle
from matplotlib.backend_bases import MouseButton, MouseEvent, PickEvent
from loguru import logger

from jgb.gui.qt import qt_util
from jgb.gui.qt.widgets.mpl_qpanel import QMplPanelWithToolbar

from zemrpc.zem.models import FieldWithLoc, NavImage
from zemrpc.zem.zem_api import zem_api


class NavCircleMarker:
    def __init__(self):
        self.gid_nav_circle_mark = "nav_circle_mark"
        self.gid_nav_circle_mark_c = "nav_circle_mark_c"
        self.gid_nav_circle_mark_r = "nav_circle_mark_r"
        self.center = (0, 0)
        self.radius = 500


class NavImgViewer:
    def __init__(self, panel):
        self.widget, self.layout = qt_util.init_panel_with_widget(panel, QMplPanelWithToolbar)
        self.canvas = self.widget.plot_canvas

        self.btn = QToolButton(self.widget.navi_toolbar)
        self.btn.setIcon(QIcon(":/pyzemrpc/images/clear.png"))
        self.btn.clicked.connect(self._slot_clear_mark)
        self.widget.navi_toolbar.addWidget(self.btn)

        self._picked_gid = None  # type: str
        self.gid_nav_img = "nav_img"
        self.gid_nav_cmarker = "nav_center_marker"

        self.gid_stage_pos_xy = "stage_pos_xy"
        self.gid_stage_rect = "stage_pos_scan_field"

        self.gid_nav_poit_mark = "nav_poit_mark-"
        self.nav_poit_marks = []

        self.nav_circle_marker = NavCircleMarker()

        self.canvas.init_ss(self)

    def update_nav_img(self, nav_img: NavImage):
        if nav_img is None or nav_img.img is None:
            self.canvas.clear_ui(self.gid_nav_img)
            self.canvas.clear_ui("stage_pos")
            self.canvas.draw()
            return

        x_min, y_min, x_max, y_max = nav_img.bounds
        self.canvas.update_ui(self.gid_nav_img, self.canvas.axes.imshow(nav_img.img, extent=(x_max, x_min, y_max, y_min)))
        self.canvas.set_lims((x_max, x_min), (y_max, y_min))
        self.canvas.update_ui(self.gid_nav_cmarker, self.canvas.axes.scatter(0, 0, c="green", marker="+", zorder=10))
        self.canvas.draw()

        self.widget.navi_toolbar.update()
        self.widget.navi_toolbar.push_current()

    def on_click(self, event: MouseEvent):
        if event.xdata is None or event.ydata is None:
            return

        if not self.canvas.has_ui(self.gid_nav_img):
            return

        if event.button == MouseButton.RIGHT:
            self._popup_menu(
                [
                    ("移动至此", functools.partial(self._slot_goto, (event.xdata, event.ydata))),
                    ("添加标记", functools.partial(self._slot_mark, (event.xdata, event.ydata))),
                ]
            )

    def _popup_menu(self, items):
        menu = QMenu(self.canvas)
        for label, callback in items:
            action = menu.addAction(label)
            action.triggered.connect(callback)
        menu.exec(QCursor.pos())

    def _slot_goto(self, xy, checked: bool = False):
        zem_api.stage_xy_goto(xy)

    def _slot_mark(self, xy, checked: bool = False):
        gid = f"{self.gid_nav_poit_mark}{len(self.nav_poit_marks)}"
        self.canvas.update_ui(gid, self.canvas.axes.scatter(xy[0], xy[1], s=20, marker="*", c="blue", picker=True, zorder=10))
        self.nav_poit_marks.append(xy)
        self.canvas.draw()

    def _update_nav_point_mark(self, gid: str, x, y):
        idx = int(gid.split("-")[-1])
        self.nav_poit_marks[idx] = (x, y)
        self.canvas.ui_items[gid].set_offsets(np.array((x, y), dtype=np.float32))
        self.canvas.draw()

    def _slot_clear_mark(self, checked: bool = False):
        self.canvas.clear_uis(self.gid_nav_poit_mark)
        self.nav_poit_marks.clear()

        self.canvas.clear_uis(self.nav_circle_marker.gid_nav_circle_mark)
        self.canvas.draw()

    def on_release(self, event: MouseEvent):
        self._picked_gid = None

    def on_pick(self, event: PickEvent):
        if event.mouseevent.button != 1:
            return
        gid = event.artist.get_gid()
        logger.debug("pick: index={} gid={}".format(event.ind, gid))
        self._picked_gid = gid

    def on_move(self, event: MouseEvent):
        if event.xdata is None or event.ydata is None or self._picked_gid is None:
            return

        x, y = event.xdata, event.ydata

        if self._picked_gid.startswith(self.gid_nav_poit_mark):
            self._update_nav_point_mark(self._picked_gid, x, y)

        match self._picked_gid:
            case self.nav_circle_marker.gid_nav_circle_mark_c:
                self._update_nav_circle_mark_c(x, y)
            case self.nav_circle_marker.gid_nav_circle_mark_r:
                self._update_nav_circle_mark_r(x, y)

    def update_field_and_loc(self, field_with_loc: FieldWithLoc):
        x, y = field_with_loc.pos.x, field_with_loc.pos.y
        scan_um = field_with_loc.scan_info.scan_um

        if self.canvas.has_ui(self.gid_stage_pos_xy):
            w_pos = self.canvas.ui_items[self.gid_stage_pos_xy]
            w_pos.set_offsets((x, y))

            w_rect = self.canvas.ui_items[self.gid_stage_rect]  # type: Rectangle
            w_rect.xy = (x - scan_um / 2, y - scan_um / 2)
            w_rect.set_width(scan_um)
            w_rect.set_height(scan_um)
        else:
            rect = Rectangle((x - scan_um / 2, y - scan_um / 2), scan_um, scan_um, facecolor="None", edgecolor="red", linewidth=1, zorder=10)
            self.canvas.update_ui(self.gid_stage_rect, rect)
            self.canvas.update_ui(self.gid_stage_pos_xy, self.canvas.axes.scatter(x, y, c="green", marker="+", zorder=10))
        self.canvas.draw()

    def add_circle_mark(self, center, radius):
        ncm = self.nav_circle_marker
        ncm.center = center
        ncm.radius = radius
        self.canvas.update_ui(ncm.gid_nav_circle_mark, Circle(center, radius=radius, facecolor="None", edgecolor="blue", label="circle roi", linestyle="--", linewidth=2, zorder=10))
        self.canvas.update_ui(ncm.gid_nav_circle_mark_c, self.canvas.axes.scatter(center[0], center[1], s=20, marker="+", c="blue", picker=True, zorder=10))
        self.canvas.update_ui(ncm.gid_nav_circle_mark_r, self.canvas.axes.scatter(center[0] + radius, center[1], s=20, marker="x", c="red", picker=True, zorder=10))
        self.canvas.draw()

    def _update_nav_circle_mark_c(self, x, y):
        self.nav_circle_marker.center = (x, y)
        self._update_nav_circle_mark()

    def _update_nav_circle_mark_r(self, x, y):
        self.nav_circle_marker.radius = math.sqrt((x - self.nav_circle_marker.center[0]) ** 2 + (y - self.nav_circle_marker.center[1]) ** 2)
        self._update_nav_circle_mark()

    def _update_nav_circle_mark(self):
        ncm = self.nav_circle_marker
        self.canvas.ui_items[ncm.gid_nav_circle_mark].center = ncm.center
        self.canvas.ui_items[ncm.gid_nav_circle_mark].radius = ncm.radius
        self.canvas.ui_items[ncm.gid_nav_circle_mark_c].set_offsets(ncm.center)
        self.canvas.ui_items[ncm.gid_nav_circle_mark_r].set_offsets((ncm.center[0] + ncm.radius, ncm.center[1]))
        self.canvas.draw()
