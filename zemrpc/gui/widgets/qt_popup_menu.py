#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from qtpy import QtGui
from qtpy import QtWidgets


def popup_menu(parent, actions):
    if isinstance(actions, tuple):
        actions = [actions]

    menu = QtWidgets.QMenu(parent)
    for action in actions:
        menu.addAction(QtGui.QAction(QtGui.QIcon(""), action[0], menu, triggered=action[1]))
    menu.popup(QtGui.QCursor().pos())
