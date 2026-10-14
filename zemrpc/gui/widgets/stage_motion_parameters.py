"""Manual JSON-RPC integration panel; opening it never queries or writes hardware."""
import json

from qtpy.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QDoubleSpinBox, QSpinBox, QCheckBox, QPlainTextEdit, QHeaderView
from jgb.gui.qt.qt_model import QTrigger
from jgb.util.async_task import AsyncTask
from zemrpc.zem.context import ctx
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.models import format_exception_for_ui
from zemrpc.zem.stage_motion_parameters import PROFILES, validate_axes


class StageMotionParametersTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.trigger = QTrigger(True)
        self.busy = False
        self.last_read = None
        layout = QVBoxLayout(self)
        info = QLabel("JSON-RPC · PID 与闭环速度（脉冲/s）。读取不改草稿；应用后核验硬件读回。写入沿用 ADVANCED 工作模式。")
        info.setWordWrap(True)
        layout.addWidget(info)
        endpoint = QHBoxLayout()
        endpoint.addWidget(QLabel("JSON-RPC 地址"))
        self.url = QLineEdit()
        self.url.setPlaceholderText("留空使用当前连接的 JSON-RPC 地址，也可填写完整 HTTP 地址")
        endpoint.addWidget(self.url, 1)
        layout.addLayout(endpoint)
        toolbar = QHBoxLayout()
        self.profile = QComboBox()
        self.profile.addItem("正常：PID 2 / 0.1 / 0.1，速度 320–9600", "normal")
        self.profile.addItem("高速：PID 40 / 0.1 / 0.1，速度 500–20000", "high")
        toolbar.addWidget(self.profile)
        self.load_profile = QPushButton("载入预设为草稿")
        self.load_profile.clicked.connect(self.fill_profile)
        toolbar.addWidget(self.load_profile)
        self.copy_read = QPushButton("用读回值填入草稿")
        self.copy_read.clicked.connect(self.fill_read)
        self.copy_read.setEnabled(False)
        toolbar.addWidget(self.copy_read)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.editor = QTableWidget(2, 7)
        self.editor.setHorizontalHeaderLabels(["应用", "轴", "P", "I", "D", "最小速度 / 脉冲·s⁻¹", "最大速度 / 脉冲·s⁻¹"])
        self.editor.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.editor.setMaximumHeight(145)
        self.fields = {}
        for row, axis in enumerate(("X", "Y")):
            enabled = QCheckBox()
            enabled.setChecked(True)
            self.editor.setCellWidget(row, 0, enabled)
            self.editor.setCellWidget(row, 1, QLabel(axis))
            fields = {"enabled": enabled}
            for col, key in enumerate(("p", "i", "d", "min_speed_pps", "max_speed_pps"), 2):
                if col < 5:
                    widget = QDoubleSpinBox()
                    widget.setDecimals(6)
                    widget.setRange(.000001 if key == "p" else 0, 3.402823466e38)
                    widget.setSingleStep(.1)
                else:
                    widget = QSpinBox()
                    widget.setRange(1, 2147483647)
                self.editor.setCellWidget(row, col, widget)
                fields[key] = widget
            self.fields[axis] = fields
        layout.addWidget(QLabel("待提交参数（修改数值不发送命令）"))
        layout.addWidget(self.editor)
        buttons = QHBoxLayout()
        self.read = QPushButton("读取设备参数")
        self.apply = QPushButton("应用所选轴并核验")
        self.read.clicked.connect(lambda: self.run(False))
        self.apply.clicked.connect(lambda: self.run(True))
        buttons.addWidget(self.read)
        buttons.addWidget(self.apply)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.status = QLabel("尚未读取设备参数；打开此页不会执行设备动作。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("这里显示硬件实际读回与原始 JSON 结果；失败时不会自动重发。")
        layout.addWidget(self.output, 1)
        self.fill_profile()

    def fill_profile(self):
        self.fill([{**PROFILES[self.profile.currentData()], "axis": axis} for axis in self.fields])

    def fill(self, axes):
        for item in axes:
            for key in ("p", "i", "d", "min_speed_pps", "max_speed_pps"):
                self.fields[item["axis"]][key].setValue(item[key])

    def fill_read(self):
        if self.last_read:
            self.fill(self.last_read["axes"])

    def set_busy(self, value):
        self.busy = value
        for widget in (self.editor, self.read, self.apply, self.profile, self.load_profile, self.url):
            widget.setEnabled(not value)
        self.copy_read.setEnabled(not value and self.last_read is not None)

    def run(self, write):
        if self.busy:
            return
        try:
            axes = validate_axes([{"axis": axis, **{key: values[key].value() for key in ("p", "i", "d", "min_speed_pps", "max_speed_pps")}}
                                  for axis, values in self.fields.items() if values["enabled"].isChecked()]) if write else None
            url = self.url.text().strip() or zem_api.device.m.protocol_ng.url
            if not url:
                raise ValueError("请先连接支持 JSON-RPC 的电镜，或填写完整地址")
        except Exception as exc:
            self.status.setText(str(exc))
            return
        self.set_busy(True)
        self.status.setText(("正在应用并核验" if write else "正在读取") + " · " + url)
        def operation():
            if write:
                return zem_api.device.set_stage_motion_parameters(axes, transport="jsonrpc", url=url)
            return zem_api.device.get_stage_motion_parameters(transport="jsonrpc", url=url)
        def completed(success, result):
            self.trigger.run(self.complete, success, result, write)
        work = AsyncTask(task_func=operation, on_complete=completed)
        work.task_id = id(self)
        ctx.async_executor.run(work)

    def complete(self, success, result, write):
        if success:
            self.last_read = result
            self.output.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
            self.status.setText(("所有请求轴应用成功，已核验实际读回" if write else "已取得新鲜硬件读回") + ("；" + result["configuration_error"] if result.get("configuration_error") else ""))
        else:
            self.last_read = None
            message = format_exception_for_ui(result)
            self.status.setText("请求失败：" + message + "；未自动重发，请先读取核对。")
            self.output.setPlainText(message)
        self.set_busy(False)
