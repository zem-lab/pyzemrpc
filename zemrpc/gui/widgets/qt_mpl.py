#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com


from matplotlib.axes import Axes
from matplotlib.patches import Circle
from matplotlib.backend_bases import MouseEvent


def zoom_factory(ax: Axes, base_scale=2.0):
    def zoom(event: MouseEvent):
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()

        xdata = event.xdata  # get event x location
        ydata = event.ydata  # get event y location
        if xdata is None or ydata is None:
            return

        if event.button == "up":
            # deal with zoom in
            scale_factor = 1 / base_scale
        elif event.button == "down":
            # deal with zoom out
            scale_factor = base_scale
        else:
            # deal with something that should never happen
            scale_factor = 1

        new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor

        relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])

        ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * (relx)])
        ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * (rely)])
        ax.figure.canvas.draw_idle()

    fig = ax.get_figure()  # get the figure of interest
    fig.canvas.mpl_connect("scroll_event", zoom)

    return zoom


def mpl_hide_ticks(axes):
    axes.xaxis.set_tick_params(labelbottom=False)
    axes.yaxis.set_tick_params(labelleft=False)
    axes.set_xticks([])
    axes.set_yticks([])


def extent_from_bounds(bounds):
    x_min, y_min, x_max, y_max = bounds
    return x_min, x_max, y_min, y_max


def format_coordinates(x, y):
    return f"{x:.3f}, {y:.3f}"


def mpl_get_circle_point(x, y):
    return Circle((x, y), radius=100, facecolor="None", edgecolor="green", label="a circle", linestyle="--", linewidth=1)
