# 对焦、像散和对中

接口已经对照 `zeptools.instrument` 的 `ExternModel.cs`、`OpticalModel.cs` 核对。
像散和对中可以通过 JSON-RPC 控制，并从 `Status` 一次性获取当前值。
原有 UDP 接口保留。以下接口同时提供在 `zem_api` 和 `zem_api.device` 上。
`run_autofocus()` 是 `zem_api` 的等待完成封装；
设备层对应 `set_autofocus()`、`get_autofocus_status()`、`ensure_af_done()`。

## JSON-RPC 像散与对中

| Python 方法 | JSON-RPC method | params（按位置） |
| --- | --- | --- |
| `set_astigmatism_rpc(x=None, y=None)` | `SemSetAstigmatism` | `[x, y]`，−100～100 百分比 |
| `set_alignment_rpc(up_x=…, up_y=…, down_x=…, down_y=…)` | `SemSetAlignment` | `[up_x, up_y, down_x, down_y]`，−100～100 百分比 |
| `set_ast_rpc(x, y)` | `SemSetAstigmatismDac` | `[x, y]`，−4095～4095 整数 DAC |
| `status_rpc()` | `Status` | `[]` |

百分比接口只修改指定轴，省略参数或传 `None`（JSON 的 `null`）保持该轴不变，
至少指定一个轴。数值是绝对值；例如 `x=1` 表示设置到 1%，不是增加 1%。
像散 X/Y 按设备的 `MaxAstigBiasA/B` 换算，上下对中按正负方向分别使用 Max / |Min|。
所有参数和配置范围在第一轴写入前完成校验，避免后一轴参数非法导致前一轴已改变。
电镜端仅在 Idle/VideoPlaying 且电流源可用时接受写入。

三个写入方法都返回完整 `OpticsState`，与 `Status.result.optics` 结构相同：

```json
{
  "unit": "percent",
  "source": "instrument_model",
  "astigmatism": {"x": 0.0, "y": 0.0, "x_dac": 0, "y_dac": 0},
  "alignment": {
    "up": {"x": 0.0, "y": 0.0, "x_dac": 0, "y_dac": 0},
    "down": {"x": 0.0, "y": 0.0, "x_dac": 0, "y_dac": 0}
  }
}
```

`x/y` 为百分比，`x_dac/y_dac` 为有符号整数 DAC。
`source=instrument_model` 表示读取电镜当前模型，包括本机 UI 和 UDP 修改后的值，
不是独立的电流源硬件回读。比例范围无效时对应百分比为 `null`，DAC 值仍保留。
VirtualZem 返回 `source=virtual_model`，使用同一组 UDP/JSON-RPC 状态。
旧服务没有 `optics` 字段时，SDK 的 `response.optics` 和对应缓存为 `None`。

### Python 调用

```python
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.models import EnumCmdLevel

# 使用电镜实际提供的 JSON-RPC URL，端口不是固定值。
# 这组方法直接走 HTTP，不触发 UDP 同步、导航图读取或模式切换。
zem_api.set_rpc_url("http://192.168.1.100:54321/api/v1/jsonrpc")
zem_api.device.set_work_mode(EnumCmdLevel.ADVANCED)

state = zem_api.status_rpc().optics
if state is None:
    raise RuntimeError("电镜端尚不支持光学状态，请更新电镜软件")
print("像散百分比:", state.astigmatism.x, state.astigmatism.y)
print("上对中百分比:", state.alignment.up.x, state.alignment.up.y)
print("下对中百分比:", state.alignment.down.x, state.alignment.down.y)

# 示例：只设置像散 X 和上对中 Y，其余轴保持不变。
actual = zem_api.set_astigmatism_rpc(x=1.0)
actual = zem_api.set_alignment_rpc(up_y=-0.5)
print(actual.alignment.up.y, actual.alignment.up.y_dac)

# 也可直接设置像散原始 DAC。
zem_api.set_ast_rpc(100, -200)
latest = zem_api.status_rpc()
print(latest.result["optics"])       # JSON 字典
print(zem_api.device.m.stig_x)        # Status 同步后的百分比缓存
print(zem_api.device.m.ast)           # Status 同步后的 (A, B) DAC 缓存
```

如果已经通过 UDP 连接，先调用 `device.get_protocol_ng()` 发现 HTTP 地址即可，
无需再次手工 `set_rpc_url()`。原有 `get_stig_x()` / `set_stig_x()` 等方法仍使用 UDP；
JSON-RPC 的读取统一使用 `status_rpc()`。

直接调用 JSON-RPC 的请求示例：

```json
{"jsonrpc":"2.0","id":1,"method":"SemSetAstigmatism","params":[1.0,null]}
{"jsonrpc":"2.0","id":2,"method":"SemSetAlignment","params":[null,-0.5,null,null]}
{"jsonrpc":"2.0","id":3,"method":"Status","params":[]}
```

SDK 对 JSON-RPC 写入执行已有的 `ADVANCED` 权限检查。远端错误会抛异常，
不会回退成 UDP 或自动重试。硬件异常可能发生在多轴写入中途；HTTP 超时也不能证明
命令未执行，此时应重新读取 `Status` 后决定下一步。`RpcCapabilities` 已包含三个新方法的语义与参数描述。

## UDP 接口与单位

| 操作 | Python 方法 | 线上的命令 | 单位 / 实际控制对象 |
| --- | --- | --- | --- |
| 物镜对焦 | `get_ob()`、`set_ob(value)` / `set_ob_raw(value)` | `GetOB`、`SetOBRaw` | 0～65535 整数 DAC；正常模式的 `FocusLens.FineValue` |
| 按工作距离对焦 | `get_wd()`、`set_wd(wd)` | `GetWD`、`SetWD` | mm；电镜按高压、工作距离标定表换算物镜值；不移动样品台 |
| 自动对焦 | `run_autofocus()` | `AutoFocus`、`CheckAutoFocus` | 电镜执行已配置的算法，SDK 等待完成，返回焦点值 |
| 指定范围精对焦 | `run_autofocus(seed_ob=32000, search_range_ob=1500)` | `AutoFocus:32000,1500` | 起始焦点与搜索范围；具体搜索由电镜的精对焦实现决定 |
| 鱼眼对焦 | `get_fisheye_focus()`、`set_fisheye_focus(value)` | `GetFisheyeFocus`、`SetFisheyeFocus` | 0～65535 整数手柄，由鱼眼策略映射到压缩镜；见[鱼眼说明](fisheye_mode.md) |
| 像散双轴原始值 | `get_ast()`、`set_ast(x, y)` | **`GetAst`、`SetAst`** | 两个有符号整数 DAC，−4095～4095；`AstigBiasA/B` |
| 像散 X | `get_stig_x()`、`set_stig_x(value)` | `GetStigX`、`SetStigX` | −100%～100%；`AstigBiasA` |
| 像散 Y | `get_stig_y()`、`set_stig_y(value)` | `GetStigY`、`SetStigY` | −100%～100%；`AstigBiasB` |
| 上对中 X | `get_up_center_x()`、`set_up_center_x(value)` | `GetUpCenterX`、`SetUpCenterX` | −100%～100%；**`AstigBiasC`** |
| 上对中 Y | `get_up_center_y()`、`set_up_center_y(value)` | `GetUpCenterY`、`SetUpCenterY` | −100%～100%；**`AstigBiasD`** |
| 下对中 X | `get_down_center_x()`、`set_down_center_x(value)` | `GetDownCenterX`、`SetDownCenterX` | −100%～100%；`DownCenterLens.CenterBiasX` |
| 下对中 Y | `get_down_center_y()`、`set_down_center_y(value)` | `GetDownCenterY`、`SetDownCenterY` | −100%～100%；`DownCenterLens.CenterBiasY` |

百分比以电镜配置的线圈范围换算。像散 X/Y 使用 `MaxAstigBiasA/B`；
上、下对中按正负方向分别使用对应的最大值和最小值绝对值。
SDK 不把百分比当成 DAC，也不假定真实机器的范围固定为虚拟电镜的 ±4095。
`set_ast()` 和六个百分比设置接口均在成功 ACK 后重新查询并返回实际值；
例如默认 ±4095 范围下，12.5% 转成 511 DAC，读回约 12.4786%。
越界、NaN、无穷值、布尔值或错误类型会在发包前拒绝。

“上对中”是旧远程协议的命名，源码映射为像散板 C/D，不能根据名称改写成
`UpCenterLens.CenterBiasX/Y`。电镜界面的枪头偏转/倾斜 `GunCenterDeflection*` /
`GunCenterTilt*` 会组合驱动 `UpCenterLens` 与 C/D；这里提供的是旧协议的独立线圈调节。
样品平面的 `set_beam_shift(x_um, y_um)` 则是扫描束移，单位为 µm，不能替代线圈对中。

## Python 示例

先连接实际电镜服务地址。像散、对中写入及自动对焦要求 `ADVANCED` 工作模式。
读取操作使用默认 `BASIC` 模式即可。以下调整量仅用于说明调用方式，应按当前样品选择步长。

```python
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.models import EnumCmdLevel

zem_api.update_remote_addr(("192.168.1.100", 61557), sync=False)
d = zem_api.device

# 只读取时不必做图像、导航或鱼眼能力同步。
print("焦点 DAC:", d.get_ob())
print("像散 DAC (A, B):", d.get_ast())
print("上对中 (%):", d.get_up_center_x(), d.get_up_center_y())
print("下对中 (%):", d.get_down_center_x(), d.get_down_center_y())

d.set_work_mode(EnumCmdLevel.ADVANCED)

# 正常模式下微调物镜；鱼眼模式使用 set_fisheye_focus。
ob = d.get_ob()
if ob + 10 <= 65535:
    d.set_ob_raw(ob + 10)

# 修改一个像散轴，另一个轴保持不变；数值是绝对百分比。
stig_x = d.get_stig_x()
if stig_x + 0.1 <= 100:
    print("像散 X 实际值:", d.set_stig_x(stig_x + 0.1))

up_x = d.get_up_center_x()
if up_x + 0.1 <= 100:
    print("上对中 X 实际值:", d.set_up_center_x(up_x + 0.1))

# 自动对焦：启动、等待结束、读取结果。
d.set_autofocus()
d.ensure_af_done()
print("自动对焦结果:", d.get_ob())
```

## Qt 上位机“像散”页

“像散”页通过上面的 UDP 接口（`get_ast` / `set_ast`、`get_stig_x/y` / `set_stig_x/y`）手动调节像散，不使用 JSON-RPC，也不涉及上下对中。

1. 在“连接”页选中电镜并同步；如需设置，把工作模式切到“高级模式”。
2. 打开本页不发送命令。点击“读取当前像散”同时读回 X/Y 百分比和 A/B DAC。
3. 编辑 X/Y 后点击“设置 X/Y”，或设置步长后点击 `−` / `+`；步进以设备刚读回的值为基准，在 ±100% 处钳位。
4. 编辑 A/B（−4095～4095）后点击“设置 A/B”直接写入 DAC。
5. 每次操作完成后再次读回两种刻度并刷新输入框，结果和失败原因按时间记录在页面下方。请求期间仅暂停本页按钮；失败不自动重发，请先读取核对。

两种刻度作用于同一对线圈，后写覆盖先写；编辑数值和接收读回都不会自动发送命令。

## 兼容性与本次补齐

- 原有像散双轴枚举的线名 `GetAST` / `SetAST` 修正为服务端的 `GetAst` / `SetAst`。
  Python 旧名称 `EnumCmd.GetAST` / `SetAST` 仍可用，并提供 `GetAst` / `SetAst` 别名；两种拼写的回包均可解析。
- 新增像散、上下对中的请求构建、回包解析、设备 API、上层 API 和可观测读回字段。
  新字段在未读取时为 `None`；连接同步不额外探测这些命令，因此旧电镜仍可正常连接。
- 电镜源码补注册并实现 `SetOBRaw`：直接写整数物镜值，保留旧 `SetOB` 的百分比语义。
  新命令仅允许正常成像模式的空闲/视频状态，并检查配置的焦点范围与电流源可用性。
  旧版本未实现该命令时会报不支持，需要更新电镜软件；SDK 不自动回退到会损失精度的百分比接口。
- VirtualZem 增加像散、上下对中状态与量化读回，并修复 `SetOBRaw` 曾按百分比放大值的问题。
  虚拟图像不模拟真实离焦、像散或对中变化，适合验证通讯和状态。

验证命令（不连接真实硬件）：

```powershell
# pyzemrpc 仓库
.venv/Scripts/python.exe -m pytest tests/test_optics_control.py tests/test_nextg_channel_frames.py -q
.venv/Scripts/python.exe -m pytest tests/test_optics_jsonrpc.py -q
.venv/Scripts/python.exe -m pytest tests/test_astigmatism_tab.py -q
# zeptools.instrument 仓库：开发验证构建，不生成交付包
dotnet run --project src/Test/OpticsProtocolTest/OpticsProtocolTest.csproj -p:GeneratePackageOnBuild=false
```

`OpticsProtocolTest` 同时检验真实 TouchSocket HTTP 参数绑定和 `Status` 序列化。
编译后可以从 pyzemrpc 运行跨语言测试，它只启动该假硬件服务，不接受真机地址：

```powershell
.venv/Scripts/python.exe tests/check_optics_jsonrpc_instrument.py --fixture ../zeptools.instrument/src/Test/OpticsProtocolTest/bin/Debug/net6.0-windows/OpticsProtocolTest.dll
```
