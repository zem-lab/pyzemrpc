"""Manual stigmator panel; opening it never queries or writes hardware."""
from qtpy.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QDoubleSpinBox, QSpinBox, QPlainTextEdit
from jgb.gui.qt.qt_model import QTrigger
from jgb.util.async_task import AsyncTask
from zemrpc.zem.astigmatism import AST_RAW_LIMIT, STIG_PCT_LIMIT
from zemrpc.zem.context import ctx
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.models import format_exception_for_ui


def read_astigmatism(device):
    return {"ast": device.get_ast(), "x": device.get_stig_x(), "y": device.get_stig_y()}


class AstigmatismTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.trigger = QTrigger(True)
        self.busy = False
        layout = QVBoxLayout(self)
        info = QLabel("UDP 外部接口 · 像散 A/B 即图像 X/Y。百分比相对电镜配置的 MaxAstigBiasA/B，DAC 原值直接写入线圈、电镜不限幅。"
                      "两种写法作用于同一对线圈，后写覆盖先写。设置需要高级工作模式；修改数值不发送命令。")
        info.setWordWrap(True)
        layout.addWidget(info)

        pct = QGroupBox("百分比（GetStigX/Y · SetStigX/Y，−100～100 %）")
        grid = QGridLayout(pct)
        self.pct = {}
        for row, axis in enumerate(("x", "y")):
            spin = QDoubleSpinBox()
            spin.setRange(-STIG_PCT_LIMIT, STIG_PCT_LIMIT)
            spin.setDecimals(3)
            spin.setSuffix(" %")
            spin.setKeyboardTracking(False)
            self.pct[axis] = spin
            minus, plus = QPushButton("−"), QPushButton("+")
            minus.setMaximumWidth(32)
            plus.setMaximumWidth(32)
            minus.clicked.connect(lambda _=False, a=axis: self.step(a, -1))
            plus.clicked.connect(lambda _=False, a=axis: self.step(a, 1))
            grid.addWidget(QLabel(axis.upper()), row, 0)
            grid.addWidget(spin, row, 1)
            grid.addWidget(minus, row, 2)
            grid.addWidget(plus, row, 3)
        self.pct_step = QDoubleSpinBox()
        self.pct_step.setRange(0.001, STIG_PCT_LIMIT)
        self.pct_step.setDecimals(3)
        self.pct_step.setValue(1.0)
        self.pct_step.setSuffix(" %")
        grid.addWidget(QLabel("步长"), 2, 0)
        grid.addWidget(self.pct_step, 2, 1)
        self.set_pct = QPushButton("设置 X/Y")
        self.set_pct.clicked.connect(self.apply_pct)
        grid.addWidget(self.set_pct, 2, 2, 1, 2)
        layout.addWidget(pct)

        raw = QGroupBox("DAC 原值（GetAst · SetAst，带符号整数）")
        raw_row = QHBoxLayout(raw)
        self.raw = {}
        for name in ("A", "B"):
            spin = QSpinBox()
            spin.setRange(-AST_RAW_LIMIT, AST_RAW_LIMIT)
            spin.setKeyboardTracking(False)
            self.raw[name] = spin
            raw_row.addWidget(QLabel(name))
            raw_row.addWidget(spin, 1)
        self.set_raw = QPushButton("设置 A/B")
        self.set_raw.clicked.connect(self.apply_raw)
        raw_row.addWidget(self.set_raw)
        layout.addWidget(raw)

        buttons = QHBoxLayout()
        self.read = QPushButton("读取当前像散")
        self.read.clicked.connect(lambda: self.run("读取", read_astigmatism))
        buttons.addWidget(self.read)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.status = QLabel("尚未读取；打开此页不会执行设备动作。")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText("这里按时间记录每次请求与读回；失败时不会自动重发。")
        layout.addWidget(self.output, 1)
        self.controls = [self.read, self.set_pct, self.set_raw, self.pct_step, *self.pct.values(), *self.raw.values(),
                         *pct.findChildren(QPushButton)]

    def set_busy(self, value):
        self.busy = value
        for widget in self.controls:
            widget.setEnabled(not value)

    def apply_pct(self):
        x, y = self.pct["x"].value(), self.pct["y"].value()

        def operation(device):
            for axis, value in (("x", x), ("y", y)):
                if device.set_stig(axis, value) is None:
                    raise ValueError(f"设备未确认 SetStig{axis.upper()}")
            return read_astigmatism(device)

        self.run(f"设置 X={x:g} %、Y={y:g} %", operation)

    def apply_raw(self):
        a, b = self.raw["A"].value(), self.raw["B"].value()

        def operation(device):
            if device.set_ast(a, b) is None:
                raise ValueError("设备未确认 SetAst")
            return read_astigmatism(device)

        self.run(f"设置 A={a}、B={b}", operation)

    def step(self, axis, sign):
        delta = sign * self.pct_step.value()

        def operation(device):
            target = max(-STIG_PCT_LIMIT, min(STIG_PCT_LIMIT, device.get_stig(axis) + delta))
            if device.set_stig(axis, target) is None:
                raise ValueError(f"设备未确认 SetStig{axis.upper()}")
            return read_astigmatism(device)

        self.run(f"{axis.upper()} 步进 {delta:+g} %", operation)

    def run(self, description, operation):
        if self.busy:
            return
        self.set_busy(True)
        self.status.setText(description + "…")
        device = zem_api.device

        def completed(success, result):
            self.trigger.run(self.complete, description, success, result)

        work = AsyncTask(task_func=lambda: operation(device), on_complete=completed)
        work.task_id = id(self)
        ctx.async_executor.run(work)

    def complete(self, description, success, result):
        if success:
            self.show_readback(result)
            a, b = result["ast"]
            message = f"{description}成功 · 读回 X={result['x']:g} %、Y={result['y']:g} % · A={a}、B={b}"
        else:
            message = f"{description}失败：{format_exception_for_ui(result)}；未自动重发，请先读取核对。"
        self.status.setText(message)
        self.output.appendPlainText(message)
        self.set_busy(False)

    def show_readback(self, result):
        for axis in ("x", "y"):
            self.pct[axis].setValue(result[axis])
        for name, value in zip(("A", "B"), result["ast"]):
            self.raw[name].setValue(value)
