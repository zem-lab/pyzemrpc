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

需要同时更新电镜 Instrument/FisheyeMode 模块。旧服务不支持这些命令时直接报错，不退回直写镜头。此次仅做语法及构建检查，未执行自动化测试或真机操作。

## Qt 上位机手动联调

在上位机下方的“鱼眼”页操作，仍使用“连接”页选中的电镜：

1. 连接并同步设备，或点击“读取模式/焦点”。显示实际模式；鱼眼模式同时读取焦点。
2. 点击“进入鱼眼”。读回确认成功后启用焦点输入框，禁用“对焦”页的 OB 滑块和物镜自动对焦。
3. 输入 0–65535 整数，点击“设置焦点”；或者设置步长，点击 `−` / `+`。步进以设备刚读回的焦点为基准，在范围边界处钳位。
4. 在“拍照”页获取图像观察调焦效果；按需在电镜端选择压缩镜 A/B 和 DAC 区间后重新读回。
5. 点击“恢复正常”。电镜负责恢复正常光学参数，界面重新读取倍率、扫描信息和 OB，恢复正常调焦控件。

编辑数值和接收读回值都不会自动发送调焦指令。页面下方显示操作结果或失败原因，鼠标悬停可查看完整错误；请求期间锁定相关控件和设备选择，防止重复操作或切换目标。若在电镜本机切换了模式，点击“读取模式/焦点”刷新；实际调焦前也会校验模式。

源码运行前如尚未生成 UI，执行 `invoke ui2py`，然后 `python -m zemrpc.gui.zemrpc_main`。本次已重新生成 UI，完成 Python 语法及静态布局检查；没有执行自动化测试或真机调焦。
