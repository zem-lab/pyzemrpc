#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from qtpy.QtCore import QSignalBlocker
from qtpy.QtWidgets import QWidget, QListView, QComboBox

from jgb.gui.qt import qt_util

from zemrpc.gui import ui_utils
from zemrpc.zem.context import ctx
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.conn.protocol import EnumCmd

from .widgets.zem_img_viewer import ZemImgViewer
from .widgets.nav_img_viewer import NavImgViewer
from .zemrpc_win_ui import Ui_Form


class ZemRpcWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.zem_img_viewer = ZemImgViewer(self.ui.tab_sem_img)
        self.nav_img_viewer = NavImgViewer(self.ui.tab_nav_img)

        self.init_ss()
        self.init_ui()

    def init_ss(self):
        self.ui.btn_send.clicked.connect(self._slot_btn_send)
        self.ui.btn_handshake.clicked.connect(self._slot_btn_handshake)
        self.ui.cbox_sem_servers.currentTextChanged.connect(self._slot_cbox_sem_servers_txt_changed)

        self.ui.btn_zem_sync.clicked.connect(self._slot_btn_zem_sync)

        ctx.signals.cmd_send.connect(self.ui.lbl_cmd_send.setText)
        ctx.signals.cmd_rcv.connect(self.ui.lbl_cmd_rcv.setText)

    def init_ui(self):
        self._init_cbox_cmds()
        self._init_cbox_snap_args()
        self._init_cbox_mag()

    def _init_cbox_cmds(self):
        cbox = self.ui.cbox_cmds
        qt_util.init_cbox_with_userdata(cbox, ui_utils.get_api_cmds())
        cbox.setView(QListView())
        cbox.setStyleSheet(ui_utils.cbox_style)

    def _init_cbox_snap_args(self):
        cbox = self.ui.cbox_cap_avg
        with QSignalBlocker(cbox):
            for i in range(1, 8):
                cbox.addItem(str(i), i)
        cbox.setCurrentText(str(zem_api.m.snap_args.pixel_avg))

        cbox = self.ui.cbox_cap_size
        with QSignalBlocker(cbox):
            qt_util.init_cbox_with_userdata(cbox, ui_utils.get_snap_size())
        cbox.setCurrentText(zem_api.m.snap_args.size.name_cn)

    def _init_cbox_mag(self):
        cbox = self.ui.cbox_mag
        with QSignalBlocker(cbox):
            for mag in ["500x", "1k", "2k", "3k", "4k", "5k", "1w", "2w", "3w", "4w", "5w", "10w", "15w", "20w"]:
                cbox.addItem(mag)
        cbox.setCurrentText("500x")
        cbox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)

    def update_cbox_sem_servers(self, servers):
        for addr in servers:
            ip, port = addr
            key = f"{ip}:{port}"
            for i in range(self.ui.cbox_sem_servers.count()):
                if self.ui.cbox_sem_servers.itemText(i) == key:
                    continue
            self.ui.cbox_sem_servers.addItem(key, addr)

    def _slot_btn_handshake(self):
        servers = zem_api.handshake()
        self.update_cbox_sem_servers(servers)

    def _slot_btn_send(self):
        cmd = self.ui.cbox_cmds.currentData()  # type: EnumCmd
        if cmd.need_args:
            args = self.ui.input_cmd_args.text()
            if not args:
                return
            zem_api.send_cmd(cmd, args)
        else:
            zem_api.send_cmd(cmd)

    def _slot_cbox_sem_servers_txt_changed(self, v):
        addr = qt_util.get_cbox_metadata(self.ui.cbox_sem_servers)
        zem_api.update_remote_addr(addr)

    def _slot_btn_zem_sync(self):
        zem_api.ensure_api_state_idel()
        ctx.async_wrapper(zem_api.sync)()
