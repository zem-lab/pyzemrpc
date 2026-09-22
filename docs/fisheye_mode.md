# 鱼眼模式接口（1.2.6.dev2026092301）

适配 Zeptools.Instrument 的 FisheyeMode 插件，设备拥有镜头选择、倍率换算和正常参数快照。

```python
from zemrpc.zem.models import EnumImagingMode

# device 为已连接的 ZemRpcDevice；zem_api 也提供同名方法。
device.set_imaging_mode(EnumImagingMode.Fisheye)
mode = device.get_imaging_mode()
focus = device.get_fisheye_focus()
device.set_fisheye_focus(min(65535, focus + 100))
device.set_imaging_mode(EnumImagingMode.Normal)
```

| Python API | UDP 命令 | 参数/读回 |
| --- | --- | --- |
| `get_imaging_mode()` | `GetImagingMode` | `EnumImagingMode`：Normal=0、LargeField=1（保留）、Fisheye=2 |
| `set_imaging_mode(mode)` | `SetImagingMode` | 仅接受整数/枚举 0、2；成功后返回实际模式 |
| `get_fisheye_focus()` | `GetFisheyeFocus` | 0–65535 整数对焦手柄，仅鱼眼模式可读 |
| `set_fisheye_focus(value)` | `SetFisheyeFocus` | 0–65535 整数；成功后返回实际手柄值 |

调焦值既不是压缩镜百分比，也不是物镜 DAC。电镜按配置映射到压缩镜 A/B 的 DAC 区间；不得由客户端重复换算。退出鱼眼模式由电镜恢复正常参数。设置失败沿用 SDK 现有 `None` / 协议异常语义；正常模式值是 0，调用方应使用 `is None` 判断拒绝，不能用真假值判断。

使用鱼眼功能需要配套更新电镜 Instrument/FisheyeMode 模块。旧服务不支持鱼眼命令时，仅该操作报错，不影响原有物镜对焦、读回和自动对焦。

## Qt 上位机手动联调

“对焦”页始终独立用于物镜控制，直接调用原有 OB / AF 接口；连接、同步和物镜对焦均不查询鱼眼模式，也不因鱼眼操作失败而禁用。没有鱼眼功能的机器照常使用原有页面即可。

支持鱼眼功能的设备，在上位机下方的“鱼眼”页手动操作，仍使用“连接”页选中的电镜：

1. 连接并同步设备后，在“鱼眼”页主动点击“读取模式/焦点”。显示实际模式；鱼眼模式同时读取焦点。
2. 点击“进入鱼眼”，确认操作成功后在本页调焦。两页控件不做模式禁用联动，请勿同时操作“对焦”页。
3. 输入 0–65535 整数，点击“设置焦点”；或者设置步长，点击 `−` / `+`。步进以设备刚读回的焦点为基准，在范围边界处钳位。
4. 在“拍照”页获取图像观察调焦效果；按需在电镜端选择压缩镜 A/B 和 DAC 区间后重新读回。
5. 点击“恢复正常”。电镜负责恢复正常光学参数；确认成功后再使用“对焦”页的物镜控制，可点击“当前值”读取 OB。

编辑鱼眼焦点数值和接收读回值都不会自动发送调焦指令。页面下方显示操作结果或失败原因，鼠标悬停可查看完整错误；请求期间仅暂停本页按钮以避免重复点击，不锁定连接或物镜对焦页。请在操作完成后再切换设备；切换设备或在电镜本机更改模式后，主动点击“读取模式/焦点”刷新。操作顺序由使用者遵循上述说明，客户端不添加跨页面模式前置检查。

源码运行前如尚未生成 UI，执行 `invoke ui2py`，然后 `python -m zemrpc.gui.zemrpc_main`。本次修正已重新生成 UI 并完成 Python 语法检查，没有执行自动化测试或真机调焦。
