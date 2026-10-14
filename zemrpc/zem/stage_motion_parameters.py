"""Stage PID / closed-loop speed configuration. Speeds are pulses per second."""
from __future__ import annotations

import base64
import http.client
import json
import math
import uuid
from urllib.parse import urlsplit


PROFILES = {
    "normal": {"p": 2.0, "i": .1, "d": .1, "min_speed_pps": 320, "max_speed_pps": 9600},
    "high": {"p": 40.0, "i": .1, "d": .1, "min_speed_pps": 500, "max_speed_pps": 20000},
}


def validate_axes(axes):
    if not isinstance(axes, list) or not 1 <= len(axes) <= 2:
        raise ValueError("必须提供 1–2 个轴的完整运动参数")
    result, seen = [], set()
    required = {"axis", "p", "i", "d", "min_speed_pps", "max_speed_pps"}
    for item in axes:
        if not isinstance(item, dict) or set(item) != required or item["axis"] not in {"X", "Y"} or item["axis"] in seen:
            raise ValueError("轴仅允许 X/Y 且不能重复，必须包含完整 PID 与速度上下限")
        seen.add(item["axis"])
        for field in ("p", "i", "d"):
            v = item[field]
            if type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 3.402823466e38 or field == "p" and v == 0:
                raise ValueError("PID 必须为有限数值，P>0、I/D>=0")
        for field in ("min_speed_pps", "max_speed_pps"):
            if type(item[field]) is not int or not 1 <= item[field] <= 2147483647:
                raise ValueError("速度必须为 Int32 正整数，单位脉冲/s")
        if item["min_speed_pps"] > item["max_speed_pps"]:
            raise ValueError("最小脉冲速度不能大于最大脉冲速度")
        result.append(dict(item))
    return result


def validate_state(value, requested=None):
    if not isinstance(value, dict) or value.get("api_version") != 1 or value.get("speed_unit") != "pulse/s" or value.get("source") != "hardware_readback" or not value.get("observed_at"):
        raise ValueError("电镜未返回有效的运动参数硬件读回，请更新配套电镜软件")
    axes = validate_axes(value.get("axes"))
    if requested is not None:
        if value.get("applied") is not True or value.get("configuration_error"):
            raise ValueError("电镜未确认参数应用成功，请读取核对；不自动重发")
        by_axis = {a["axis"]: a for a in axes}
        for expected in validate_axes(requested):
            actual = by_axis.get(expected["axis"])
            if actual is None or any(not math.isclose(actual[k], expected[k], rel_tol=1e-6, abs_tol=1e-6) for k in ("p", "i", "d")) or any(actual[k] != expected[k] for k in ("min_speed_pps", "max_speed_pps")):
                raise ValueError(f"{expected['axis']} 轴读回与请求不一致")
    return value


def encode_request(axes):
    return base64.b64encode(json.dumps({"axes": validate_axes(axes)}, allow_nan=False, separators=(",", ":")).encode()).decode("ascii")


def decode_state(value, requested=None):
    return validate_state(json.loads(base64.b64decode(value, validate=True)), requested)


class StageMotionJsonRpc:
    """Direct HTTP JSON-RPC, bounded timeout and no retry or UDP fallback."""
    def __init__(self, url, timeout=20):
        self.url, self.timeout = url, timeout

    def call(self, method, params):
        url = urlsplit(self.url)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            raise ValueError("请填写有效的 HTTP(S) JSON-RPC 地址")
        request_id = uuid.uuid4().hex
        body = json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}, allow_nan=False).encode()
        cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
        connection = cls(url.hostname, url.port, timeout=self.timeout)
        try:
            connection.request("POST", (url.path or "/") + ("?" + url.query if url.query else ""), body, {"Content-Type": "application/json"})
            response = connection.getresponse()
            payload = response.read()
            if response.status != 200:
                raise RuntimeError(f"JSON-RPC HTTP {response.status}，请核对设备状态；未重发")
            envelope = json.loads(payload)
            if envelope.get("id") != request_id or envelope.get("jsonrpc") != "2.0":
                raise ValueError("JSON-RPC 响应身份不匹配")
            if envelope.get("error"):
                raise RuntimeError(str(envelope["error"].get("message", envelope["error"])))
            return envelope["result"]
        finally:
            connection.close()

    def read(self):
        return validate_state(self.call("SemStageMotionParameters", []))

    def configure(self, axes):
        axes = validate_axes(axes)
        return validate_state(self.call("SemConfigureStageMotion", [{"axes": axes}]), axes)
