#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# tr!bf tribf@tribf.com

from pathlib import Path
from typing import cast
from loguru import logger
from qtpy.QtCore import QUrl, Qt, QSignalBlocker
from qtpy.QtGui import QDesktopServices
from qtpy.QtWidgets import QWidget, QListView, QComboBox

from jgb.gui.qt import qt_util
from jgb.gui.qt.dds_util import Attrs2QtValue
from jgb.gui.qt.qt_model import QEmitter, QTrigger
from jgb.gui.qt.qt_slots import QPushButtonClicked

from zemrpc.zem.context import ctx
from zemrpc.gui import ui_utils
from zemrpc.zem.models import StageMoveDirection, EnumCmdLevel, format_exception_for_ui
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.conn.protocol import EnumCmd, EnumVideoStatus

from .widgets.zem_img_viewer import ZemImgViewer
from .widgets.nav_img_viewer import NavImgViewer
from .zemrpc_win_ui import Ui_Form


class RecursivelyHandler:
    def __init__(self, widget, handler):
        self.widget = widget
        self.handler = handler

    def __call__(self):
        import contextlib

        value = self.widget.value()
        with contextlib.nullcontext() if self.widget.signalsBlocked() else QSignalBlocker(self.widget):
            self.handler(value)

            cur_value = self.widget.value()
            if value != cur_value:
                self()


class ZemRpcWidget(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.trigger = QTrigger(True)

        self.ui = Ui_Form()
        self.ui.setupUi(self)

        self.emitter = QEmitter(True)
        self.zem_img_viewer = ZemImgViewer(self.ui.tab_sem_img)
        self.nav_img_viewer = NavImgViewer(self.ui.tab_nav_img)

        self.init_ui()
        self.init_ss()

    def init_ss(self):
        # 连接
        self.ui.btn_send.clicked.connect(self._slot_btn_send)
        self.ui.btn_handshake.clicked.connect(self._slot_btn_handshake)
        self.ui.btn_snap.clicked.connect(self._slot_btn_snap)
        # activated: 用户从下拉列表选择时触发，即使选中项与当前相同也会触发（便于同步失败后重试）
        self.ui.cbox_sem_servers.activated.connect(self._slot_cbox_sem_servers_activated)
        self.ui.btn_zem_sync.clicked.connect(self._slot_btn_zem_sync)
        self.ui.cbox_work_mode.currentIndexChanged.connect(self._slot_cbox_work_mode_changed)

        # 高压
        self.ui.btn_hv_get.clicked.connect(zem_api.device.get_hv)
        self.ui.btn_hv_set.clicked.connect(self._slot_btn_hv_set)
        self.ui.btn_gun_on.clicked.connect(self._slot_btn_gun_on)
        self.ui.btn_gun_off.clicked.connect(self._slot_btn_gun_off)

        # 拍照
        self.ui.cbox_mag.currentTextChanged.connect(self._slot_cbox_mag_txt_changed)
        self.ui.input_mag.returnPressed.connect(self._slot_input_mag_confirmed)
        self.ui.input_field_rotation.returnPressed.connect(self._slot_input_field_rotation_confirmed)
        self.ui.btn_play.clicked.connect(self._slot_btn_play)
        self.ui.btn_open_image_path.clicked.connect(self._slot_btn_open_image_path)
        self.ui.cbox_cap_avg.currentIndexChanged.connect(self._slot_cbox_cap_avg_txt_changed)
        self.ui.cbox_cap_size.currentIndexChanged.connect(self._slot_cbox_cap_size_txt_changed)
        self.ui.ckb_snap_save.stateChanged.connect(self._slot_ckb_snap_save_state_changed)
        self.ui.btn_remap.clicked.connect(self._slot_btn_remap)

        # 对焦
        self.ui.slider_ob.valueChanged.connect(self._on_slider_ob_value_changed)
        self.ui.btn_ob.clicked.connect(self._slot_btn_ob)
        self.ui.btn_af.clicked.connect(self._slot_btn_af)

        # 样品台
        self.ui.btn_stage_xy_pos.clicked.connect(self._slot_btn_stage_xy_pos)
        self.ui.btn_stage_xy_goto.clicked.connect(self._slot_btn_stage_xy_goto)
        self.ui.btn_stage_xy_move_up.clicked.connect(lambda _: self._slot_btn_stage_xy_move(StageMoveDirection.Up))
        self.ui.btn_stage_xy_move_down.clicked.connect(lambda _: self._slot_btn_stage_xy_move(StageMoveDirection.Down))
        self.ui.btn_stage_xy_move_left.clicked.connect(lambda _: self._slot_btn_stage_xy_move(StageMoveDirection.Left))
        self.ui.btn_stage_xy_move_right.clicked.connect(lambda _: self._slot_btn_stage_xy_move(StageMoveDirection.Right))

        # 导航图
        self.ui.btn_get_nav_info.clicked.connect(self._slot_btn_get_nav_info)

        ## 虚拟zem
        self.ui.btn_vzem_start.clicked.connect(self._slot_btn_vzem_start)

        ctx.sub_computed_attr(zem_api.device.m.cmd_rcv, Attrs2QtValue(self, self.ui.lbl_cmd_rcv.setText, emitter=self.emitter))
        ctx.sub_computed_attr(zem_api.device.m.cmd_send, Attrs2QtValue(self, self.ui.lbl_cmd_send.setText, emitter=self.emitter))
        ctx.sub_attr(zem_api.m, "zem_img", Attrs2QtValue(self, self.zem_img_viewer.update_sem_image, emitter=self.emitter))

        ctx.sub_attr(zem_api.m, "nav_img", Attrs2QtValue(self, self.nav_img_viewer.update_nav_img, emitter=self.emitter))
        ctx.sub_computed_attr(zem_api.m.field_with_loc, Attrs2QtValue(self, self.nav_img_viewer.update_field_and_loc, emitter=self.emitter))
        ctx.sub_attr(zem_api.device.m, "scan_info", Attrs2QtValue(self, self.update_scan_info, emitter=self.emitter))
        ctx.sub_attr(zem_api.device.m, "stage_pos", Attrs2QtValue(self, self.update_stage_pos, emitter=self.emitter))
        ctx.sub_attr(zem_api.device.m, "hv_info", Attrs2QtValue(self, self.update_hv_info, emitter=self.emitter))
        ctx.sub_attr(zem_api.device.m, "mag", Attrs2QtValue(self, self.update_mag, emitter=self.emitter))
        ctx.sub_attr(zem_api.device.m, "ob", Attrs2QtValue(self, self.ui.slider_ob.setValue, emitter=self.emitter))

    def init_ui(self):
        self.ui.tab_modules.setCurrentIndex(0)
        self.ui.ipt_hv.setRange(0, 30)
        self._init_cbox_cmds()
        self._init_cbox_snap_args()
        self._init_cbox_mag()
        self._init_cbox_vzem()
        self._init_cbox_work_mode()
        self._init_cbox_sem_servers()

        self.ui.slider_ob.setRange(0, 65535)
        self.ui.slider_ob.setMidValueLabel("32768")
        self.ui.slider_ob.setValue(30000)
        self.ui.slider_ob.setOrientation(Qt.Orientation.Horizontal)

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

    def _init_cbox_vzem(self):
        cbox = self.ui.cbox_vzem_type
        with QSignalBlocker(cbox):
            for t in ["Mandelbrot", "Replay"]:
                cbox.addItem(t)

    def _init_cbox_work_mode(self):
        cbox = self.ui.cbox_work_mode
        with QSignalBlocker(cbox):
            cbox.addItem("基础模式", EnumCmdLevel.BASIC)
            cbox.addItem("高级模式", EnumCmdLevel.ADVANCED)
        cbox.setCurrentIndex(0)

    def _init_cbox_sem_servers(self):
        cbox = self.ui.cbox_sem_servers
        # Windows style 下默认列表行高过小，长的 ip:port 文本会与相邻行重叠。
        server_view = QListView()
        server_view.setUniformItemSizes(True)
        server_view.setStyleSheet("QListView::item { min-height: 20px; }")
        cbox.setView(server_view)
        with QSignalBlocker(cbox):
            cbox.addItem(ui_utils.DEFAULT_SEM_SERVER_LABEL, ui_utils.DEFAULT_SEM_SERVER_ADDR)
            cbox.setCurrentIndex(0)
        zem_api.update_remote_addr(ui_utils.DEFAULT_SEM_SERVER_ADDR, sync=False)

    def _slot_cbox_work_mode_changed(self, index: int):
        mode = self.ui.cbox_work_mode.currentData()
        if mode is not None:
            zem_api.device.set_work_mode(mode)

    def update_cbox_sem_servers(self, servers):
        cbox = self.ui.cbox_sem_servers
        current_key = cbox.currentText()
        existing = [(cbox.itemText(i), cbox.itemData(i)) for i in range(cbox.count())]
        items = ui_utils.merge_sem_server_items(existing, servers)

        with QSignalBlocker(cbox):
            cbox.clear()
            for key, addr in items:
                cbox.addItem(key, addr)
            idx = cbox.findText(current_key)
            if idx >= 0:
                cbox.setCurrentIndex(idx)
            elif cbox.count() > 0:
                cbox.setCurrentIndex(0)

    def _slot_btn_handshake(self):
        def handshake_task():
            return zem_api.handshake()

        def on_complete(success, result):
            if success:
                self.update_cbox_sem_servers(result)

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_handshake, handshake_task, on_complete))

    def _slot_btn_snap(self):
        def snap_task():
            zem_api.snap()

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_snap, snap_task))

    def _slot_input_mag_confirmed(self):
        mag = int(self.ui.input_mag.text())
        zem_api.set_mag(mag)

    def _slot_input_field_rotation_confirmed(self):
        zem_api.device.set_field_rotation(int(self.ui.input_field_rotation.text()))

    def _slot_btn_play(self):
        if zem_api.device.is_video_playing():
            zem_api.video_play_off()
            self.ui.btn_play.setText("播放")
        else:
            zem_api.device.video_play_on()
            self.ui.btn_play.setText("暂停")

    def _slot_btn_open_image_path(self):
        zem_img = zem_api.m.zem_img
        image_dir = Path(ctx.logdir) / "images"
        if zem_img is not None and zem_img.pkl is not None:
            image_dir = Path(zem_img.pkl).parent

        image_dir.mkdir(parents=True, exist_ok=True)
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(image_dir.resolve()))):
            self.trigger.run(
                qt_util.show_message_box_warning,
                self,
                f"无法打开图像路径: {image_dir}",
                "打开图像路径失败",
            )

    def _slot_btn_send(self):
        cmd = self.ui.cbox_cmds.currentData()  # type: EnumCmd
        if cmd.need_args:
            args = self.ui.input_cmd_args.text()
            if not args:
                return
            zem_api.send_cmd(cmd, args)
        else:
            zem_api.send_cmd(cmd)

    def _apply_selected_sem_server(self) -> bool:
        """读取下拉框选中设备，更新内存 addr 并触发同步。"""
        addr = qt_util.get_cbox_metadata(self.ui.cbox_sem_servers)
        if addr is None:
            return False
        zem_api.update_remote_addr(addr)
        return True

    def _on_sync_complete(self, success, result):
        if success:
            return
        self.trigger.run(qt_util.show_message_box_warning, self, format_exception_for_ui(result), "同步状态失败")

    def _run_sync_selected_server(self):
        def sync_task():
            if not self._apply_selected_sem_server():
                zem_api._init_sync_done = False
                zem_api.sync()

        ctx.async_executor.run(
            QPushButtonClicked(self.ui.btn_zem_sync, sync_task, self._on_sync_complete, loading_text="同步中...")
        )

    def _slot_cbox_sem_servers_activated(self, index: int):
        if index < 0:
            return
        self._run_sync_selected_server()

    def _slot_cbox_mag_txt_changed(self, v: str):
        mag = ui_utils.parse_mag_str(v)
        zem_api.set_mag(mag)
        with QSignalBlocker(self.ui.input_mag):
            self.ui.input_mag.setText(str(mag))

    def _slot_cbox_cap_avg_txt_changed(self, v: str):
        zem_api.m.snap_args.pixel_avg = qt_util.get_cbox_metadata(self.sender())

    def _slot_cbox_cap_size_txt_changed(self, v: str):
        zem_api.m.snap_args.size = qt_util.get_cbox_metadata(self.sender())

    def _slot_ckb_snap_save_state_changed(self, state):
        zem_api.m.snap_args.save = state == Qt.CheckState.Checked.value

    def _on_slider_ob_value_changed(self, value: float):
        def handler(ob):
            with ctx.signal_blocker(zem_api.device.m, "ob"):
                zem_api.set_ob(int(ob))

        rh = RecursivelyHandler(self.ui.slider_ob, handler)
        ctx.async_wrapper(rh)()

    def _slot_btn_ob(self):
        def ob_task():
            zem_api.device.get_ob()

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_ob, ob_task))

    def _slot_btn_af(self):
        def af_task():
            zem_api.run_autofocus()

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_af, af_task))

    def _slot_btn_zem_sync(self):
        self._run_sync_selected_server()

    def _slot_btn_hv_set(self):
        if not qt_util.show_confirmed_box(self):
            return

        def hv_set_task():
            zem_api.set_hv(self.ui.ipt_hv.value())
            return True, None

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_hv_set, hv_set_task))

    def _slot_btn_gun_on(self):
        if not qt_util.show_confirmed_box(self):
            return

        def gun_task():
            zem_api.set_gun(True, wait=True)
            return True, None

        def on_complete(success, result):
            if success:
                self.trigger.run(qt_util.show_message_box_info, self, "开枪成功")
            else:
                self.trigger.run(qt_util.show_message_box_info, self, f"开枪失败: {result}")

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_gun_on, gun_task, on_complete))

    def _slot_btn_gun_off(self):
        if not qt_util.show_confirmed_box(self):
            return

        def gun_off_task():
            zem_api.set_gun(False, wait=True)
            return True, None

        def on_complete(success, result):
            if success:
                self.trigger.run(qt_util.show_message_box_info, self, "关枪成功")
            else:
                self.trigger.run(qt_util.show_message_box_info, self, f"关枪失败: {result}")

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_gun_off, gun_off_task, on_complete))

    def _slot_btn_stage_xy_pos(self):
        def stage_xy_pos_task():
            zem_api.device.get_stage_pos()
            zem_api.sync_scan_field()

        def on_complete(success, result):
            if success:
                self.update_stage_pos(result)

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_stage_xy_pos, stage_xy_pos_task, on_complete))

    def _slot_btn_stage_xy_goto(self):
        def stage_xy_goto_task():
            x, y = ui_utils.parse_stage_pos(self.ui.input_stage_xy_pos.text())
            zem_api.stage_xy_goto((x, y))
            return True, None

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_stage_xy_goto, stage_xy_goto_task))

    def _slot_btn_stage_xy_move(self, direction: StageMoveDirection):
        rval = float(self.ui.input_stage_xy_rval.text())
        zem_api.stage_xy_rmove(direction, rval)

    def _slot_btn_get_nav_info(self):
        def get_nav_info():
            zem_api.get_nav_img()
            return True, None

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_get_nav_info, get_nav_info))

    def _slot_btn_vzem_start(self):
        def vzem_start_task():
            vzem_type = qt_util.get_cbox_metadata(self.ui.cbox_vzem_type)
            zem_api.start_vzem(vzem_type)
            return True, None

        def on_complete(success, result):
            if success:
                self.trigger.run(qt_util.show_message_box_info, self, "虚拟ZEM启动成功")
            else:
                self.trigger.run(qt_util.show_message_box_info, self, f"虚拟ZEM启动失败: {result}")

        ctx.async_executor.run(QPushButtonClicked(self.ui.btn_vzem_start, vzem_start_task, on_complete))

    def _slot_btn_remap(self): ...

    def update_scan_info(self, si):
        from zemrpc.zem.models import ScanInfo

        si = cast(ScanInfo, si)
        self.ui.input_field_size.setText(f"{si.scan_um:.3f}")
        self.ui.input_field_rotation.setText(f"{si.rot_degree:.3f}")

    def update_hv_info(self, hv_info):
        from zemrpc.zem.models import HvInfo

        hv_info = cast(HvInfo, hv_info)
        with QSignalBlocker(self.ui.ipt_hv):
            self.ui.ipt_hv.setValue(hv_info.kv)

    def update_stage_pos(self, pos):
        from zemrpc.zem.models import StagePos

        pos = cast(StagePos, pos)
        self.ui.input_stage_xy_pos.setText(f"{ui_utils.stage_pos_str(pos.x, pos.y)}")

    def update_mag(self, mag):
        with QSignalBlocker(self.ui.input_mag):
            self.ui.input_mag.setText(str(int(mag)))

    def closeEvent(self, event):
        super().closeEvent(event)
        zem_api.vzem_mgr.stop_vzem()
        ctx.close()
