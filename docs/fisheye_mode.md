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
