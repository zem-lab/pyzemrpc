# 对焦、像散和对中

接口已经对照 `zeptools.instrument` 的 `ExternModel.cs`、`OpticalModel.cs` 核对。
以下方法同时提供在 `zem_api` 和 `zem_api.device` 上，使用现有 UDP 协议，
不需要 JSON-RPC/HTTP 服务。`run_autofocus()` 是 `zem_api` 的等待完成封装；
设备层对应 `set_autofocus()`、`get_autofocus_status()`、`ensure_af_done()`。

## 接口与单位

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
# zeptools.instrument 仓库：开发验证构建，不生成交付包
dotnet run --project src/Test/OpticsProtocolTest/OpticsProtocolTest.csproj -p:GeneratePackageOnBuild=false
```
