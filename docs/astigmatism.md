# 像散接口

对应海思上位机（Zeptools.Instrument `ExternModel`）的 UDP 外部接口。像散线圈 A/B 即图像 X/Y，有两种刻度，写入的是同一对线圈，后写覆盖先写。JSON-RPC 没有像散方法，也没有远程自动消像散命令。

| Python API | UDP 命令 | 等级 | 参数 / 读回 |
| --- | --- | --- | --- |
| `get_ast()` | `GetAst` | BASIC | `(A, B)` 带符号 DAC 整数 |
| `set_ast(a, b)` | `SetAst` | ADVANCED | 两个整数；成功后返回 `get_ast()` 读回 |
| `get_stig_x()` / `get_stig_y()` | `GetStigX` / `GetStigY` | BASIC | 相对 `MaxAstigBiasA/B` 的百分比 |
| `set_stig_x(v)` / `set_stig_y(v)` | `SetStigX` / `SetStigY` | ADVANCED | −100～100 %；成功后返回同轴读回 |

`get_stig(axis)` / `set_stig(axis, value)` 以 `"x"` / `"y"` 选轴。`zem_api` 提供 `get_ast`、`set_ast`、`get_stig`、`set_stig` 高层封装，设置接口可加 `wait_stable_ms`。

```python
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.models import EnumCmdLevel

device = zem_api.device  # 按原流程连接电镜后使用
print(device.get_ast(), device.get_stig_x(), device.get_stig_y())
device.set_work_mode(EnumCmdLevel.ADVANCED)
x = device.set_stig_x(50)        # 默认 Max=4095 时写入 2047，读回 49.988
if x is None:
    raise RuntimeError("电镜拒绝修改像散")
device.set_ast(100, -200)         # 直接写 DAC 原值
```

## 换算与限幅

- 百分比写入：`AstigBias = int(百分比 / 100 × MaxAstigBias)`，向零截断；读回 `AstigBias × 100 / MaxAstigBias`。正负两侧都以最大值为分母，所以读回可能与请求值略有差异。
- 电镜对 `SetStigX/Y` 静默钳位到 ±100。SDK 先校验，超出 −100～100、NaN、无穷、bool、字符串在发送前就抛出 `ValueError`。
- `SetAst` 由电镜原样写入，不按配置的 Min/MaxAstigBias 限幅。协议不报告这组配置上限，SDK 只拒绝非整数和 |值| > 65535（线圈通道写入 16 位绝对值），其余物理范围由调用方负责。DAC 原值超过最大值时，百分比读回会大于 100。
- 设置失败沿用 SDK 现有语义：协议错误码抛 `ZemException`，ACK 非 0 返回 `None`，缓存 `device.m.ast / stig_x / stig_y` 只记录实际读回。

旧版 SDK 把原值命令写成 `GetAST` / `SetAST`。上位机按区分大小写的命令表注册 `GetAst` / `SetAst`，旧名称会回无效命令；本版已改为正确名称，`EnumCmd.GetAST` / `EnumCmd.SetAST` 改名为 `EnumCmd.GetAst` / `EnumCmd.SetAst`。

`SetUpCenterX/Y`（`AstigBiasC/D`）在上位机中用于枪对中的下线圈，不是图像像散，本 SDK 未封装。

## Qt 上位机“像散”页

1. 在“连接”页选中电镜并同步；如需设置，把工作模式切到“高级模式”。
2. 打开“像散”页不发送命令。点击“读取当前像散”同时读回 X/Y 百分比和 A/B 原值。
3. 编辑 X/Y 后点击“设置 X/Y”，或设置步长后点击 `−` / `+`；步进以设备刚读回的值为基准，在 ±100 % 处钳位。
4. 编辑 A/B 后点击“设置 A/B”直接写入 DAC 原值。
5. 每次操作完成后再次读回两种刻度并刷新输入框，结果和失败原因按时间记录在页面下方。请求期间仅暂停本页按钮；失败不自动重发。

虚拟电镜按上位机的换算实现了这 6 条命令（最大偏置 4095），可离线联调；虚拟图像不随像散变化。回归测试：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_astigmatism.py -q
```
