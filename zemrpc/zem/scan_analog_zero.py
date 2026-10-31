"""Normal scan CHC/CHD: Status readback and explicit JSON-RPC mutations."""

from .stage_motion_parameters import StageMotionJsonRpc


def validate_pair(sin, cos):
    if any(type(v) is not int or not 0 <= v <= 65535 for v in (sin, cos)):
        raise ValueError("扫描模拟偏置必须是 0–65535 的整数")


def validate_state(state, expected=None, saved=False):
    if not isinstance(state, dict) or state.get("schema") != "normal-scan-analog-zero-v1":
        raise ValueError("Status 缺少正常扫描模拟调零字段，请升级电镜软件")
    validate_pair(state.get("sin"), state.get("cos"))
    for key in ("sin", "cos"):
        limits = state.get(key + "_range")
        if (not isinstance(limits, list) or len(limits) != 2
                or any(type(v) is not int for v in limits)
                or not 0 <= limits[0] <= state[key] <= limits[1] <= 65535):
            raise ValueError("扫描模拟偏置范围或读回无效")
    if expected is not None:
        if state.get("mode") != "normal" or [state["sin"], state["cos"]] != list(expected):
            raise ValueError("模拟偏置读回与设置不一致；请读取状态，不自动重发")
        if state.get("beam_raw") != dict(x=0, y=0):
            raise ValueError("束偏转未归零")
        if saved and state.get("saved") != dict(zip(("sin", "cos"), expected)):
            raise ValueError("电镜未确认调零值已保存")
    return state


class ScanAnalogZeroJsonRpc(StageMotionJsonRpc):
    """No UDP fallback, automatic replay, or implicit save."""

    def read(self):
        return validate_state(self.call("Status", []).get("scan_analog_zero"))

    def set(self, sin, cos):
        validate_pair(sin, cos)
        return validate_state(self.call("SemSetScanAnalogZero", [sin, cos]), (sin, cos))

    def save(self, expected_sin, expected_cos):
        validate_pair(expected_sin, expected_cos)
        return validate_state(self.call("SemSaveScanAnalogZero", [expected_sin, expected_cos]),
                              (expected_sin, expected_cos), saved=True)
