#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

import numpy as np
import matplotlib

matplotlib.use("Qt5Agg")

import pyqtgraph as pg
from qtpy.QtWidgets import QWidget, QSizePolicy, QVBoxLayout

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.text import Text
from matplotlib.collections import PatchCollection, LineCollection


plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False  # 解决保存图像是负号'-'显示为方块的问题

from .qt_mpl import format_coordinates, zoom_factory, mpl_hide_ticks


class ViewerMpl(FigureCanvas):
    def __init__(self, parent=None, width=5, height=5, dpi=100, **kwargs):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        FigureCanvas.updateGeometry(self)

        frameon = kwargs.get("frameon", True)
        self.axes = self.fig.add_subplot(111, frameon=frameon)
        self.axes.format_coord = format_coordinates

        if kwargs.get("equal_axes", True):
            self.axes.set_aspect("equal", adjustable="box")
        if kwargs.get("axis_off", False):
            self.axes.set_axis_off()

        self.disconnect_zoom = zoom_factory(self.axes)

        self.ui_items = {}

        if kwargs.get("hide_ticks", True):
            # mpl_hide_ticks(self.axes)
            self.axes.tick_params(left=False, right=False, labelleft=False, labelbottom=False, bottom=False)
            self.fig.subplots_adjust(bottom=0, top=1, left=0, right=1, wspace=0, hspace=0)

        self.fig.set_facecolor("none")
        self.setStyleSheet("background-color:white;")

    def showEvent(self, event):
        # Set up correct pixel ratio, and connect to any signal changes for it,
        # once the window is shown (and thus has these attributes).
        window = self.window().windowHandle()
        if pg.Qt.isQObjectAlive(window):
            window.screenChanged.connect(self._update_screen)
            self._update_screen(window.screen())

    def init_ss(self, viewer_mgr):
        ss_map = {
            "button_press_event": "on_click",
            "button_release_event": "on_release",
            "pick_event": "on_pick",
            "motion_notify_event": "on_move",
        }
        for k, handler in ss_map.items():
            if hasattr(viewer_mgr, handler):
                self.fig.canvas.mpl_connect(k, getattr(viewer_mgr, handler))

    def add_patch(self, key, patch):
        self.ui_items[key] = patch
        self.axes.add_patch(patch)
        self.draw()

    def update_ui(self, key, item):
        item.set_gid(key)
        if key in self.ui_items:
            self.ui_items[key].remove()

        if isinstance(item, Patch):
            self.axes.add_patch(item)
        elif isinstance(item, (PatchCollection, LineCollection)):
            self.axes.add_collection(item)
        elif isinstance(item, Text):
            item.set_clip_on(True)

        self.ui_items[key] = item

    def has_ui(self, key):
        return key in self.ui_items

    def has_ui_like(self, prefix):
        for k in self.ui_items.keys():
            if k.startswith(prefix):
                return True
        return False

    def clear_all(self):
        self.ui_items.clear()
        self.axes.clear()

    def clear_ui(self, k):
        if k in self.ui_items:
            self.ui_items[k].remove()
            del self.ui_items[k]

    def clear_uis(self, prefix):
        keys = []
        for k, v in self.ui_items.items():
            if k.startswith(prefix):
                v.remove()
                keys.append(k)
        for k in keys:
            del self.ui_items[k]
        return len(keys)

    def set_lims(self, xlims, ylims):
        self.axes.set_xlim(*xlims)
        self.axes.set_ylim(*ylims)

    def savefig(self, png, **kwargs):
        kwargs.update(bbox_inches="tight", pad_inches=0)
        self.fig.savefig(png, **kwargs)


class NavigationToolbar(NavigationToolbar2QT):

    def __init__(self, canvas, parent):
        # text, tooltip_text, image_file, callback
        self.toolitems = [t for t in NavigationToolbar2QT.toolitems if t[0] not in {"Back", "Forward", "Subplots", "Customize"}]
        super().__init__(canvas, parent)

    def select_tool(self):
        print("...")


class ViewerMplWithToolbar(QWidget):
    def __init__(self, parent, canvas_kwargs=None):
        super().__init__(parent)
        self.plot_layout = QVBoxLayout(self)

        if canvas_kwargs is None:
            canvas_kwargs = {}

        self.plot_canvas = self.create_fig_canvas(canvas_kwargs)

        self.navi_toolbar = NavigationToolbar(self.plot_canvas, self)

        self.plot_layout.addWidget(self.navi_toolbar)
        self.plot_layout.addWidget(self.plot_canvas)
        self.plot_layout.setContentsMargins(0, 0, 0, 0)
        self.plot_layout.setSpacing(2)

    def create_fig_canvas(self, canvas_kwargs):
        return ViewerMpl(self, **canvas_kwargs)


class PlainImageViewer:
    def __init__(self, widget: ViewerMplWithToolbar):
        self.widget = widget
        self.canvas = self.widget.plot_canvas

        self.gid_img = "img"

    def update_image(self, img):
        # if not self.widget.isVisible():
        #     return

        self.canvas.update_ui(self.gid_img, self.canvas.axes.imshow(img, cmap="gray"))
        self.canvas.axes.set_xlim(0, img.shape[1])
        self.canvas.axes.set_ylim(img.shape[0], 0)
        self.canvas.draw()

        self.widget.navi_toolbar.update()
        self.widget.navi_toolbar.push_current()

    def clear_all(self):
        self.canvas.clear_all()

    def save_fig(self, png, **kwargs):
        self.canvas.savefig(png, **kwargs)


class ImgCmpCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=5, dpi=100, **kwargs):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.fig)
        self.setParent(parent)

        FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)

        self.ax1 = self.fig.add_subplot(1, 2, 1)
        self.ax2 = self.fig.add_subplot(1, 2, 2, sharex=self.ax1, sharey=self.ax1)

        self.disconnect_zoom1 = zoom_factory(self.ax1)
        self.disconnect_zoom2 = zoom_factory(self.ax2)

        mpl_hide_ticks(self.ax1)
        mpl_hide_ticks(self.ax2)
        self.fig.subplots_adjust(bottom=0, top=1, left=0, right=1, wspace=0, hspace=0)


class ImgCmpMpl(ViewerMplWithToolbar):
    def __init__(self, parent, canvas_kwargs=None):
        super().__init__(parent, canvas_kwargs)

    def create_fig_canvas(self, canvas_kwargs: dict):
        return ImgCmpCanvas(self, **canvas_kwargs)

    def draw_img1(self, img: np.ndarray):
        kwargs = dict(cmap="gray", vmin=0, vmax=255 if img.dtype == np.uint8 else 65536)
        self.plot_canvas.ax1.imshow(img, **kwargs)
        self.plot_canvas.ax1.set_xlim(0, img.shape[1])
        self.plot_canvas.ax1.set_ylim(img.shape[0], 0)
        self.plot_canvas.draw()
        self.navi_toolbar.update()
        self.navi_toolbar.push_current()

    def draw_img2(self, img: np.ndarray):
        kwargs = dict(cmap="gray", vmin=0, vmax=255 if img.dtype == np.uint8 else 65536)
        self.plot_canvas.ax2.imshow(img, **kwargs)
        self.plot_canvas.ax2.set_xlim(0, img.shape[1])
        self.plot_canvas.ax2.set_ylim(img.shape[0], 0)
        self.plot_canvas.draw()
        self.navi_toolbar.update()
        self.navi_toolbar.push_current()
