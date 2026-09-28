# 正常扫描档位使能掩码

需要支持 `SetScanRelayMask` / `GetScanRelayMask` 的海思上位机（Shell 1.5.3+）；SDK 版本 `1.2.6.dev2026092801`。

| 位 | 档位 | 值 |
|---|---|---:|
| bit0 | K1 | 1 |
| bit1 | K2 | 2 |
| bit2 | K3 | 4 |
| bit3 | K4 | 8 |

掩码 15 全启用，7 禁用 K4，4 仅启用 K3。合法值为整数 1–15，拒绝 0、负数、高位、浮点数、bool 和字符串。与控制板继电器字节不同，K3 的硬件继电器值为 32，不应传入此接口。

```python
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.scan_relay import ScanRelayMask

device = zem_api.device  # 按原流程连接电镜后使用
mask = ScanRelayMask.K1 | ScanRelayMask.K2 | ScanRelayMask.K3
result = device.set_scan_relay_mask(mask)
if result is None:
    raise RuntimeError("电镜拒绝修改档位掩码")
assert result == 7
print(device.get_scan_relay_mask())           # 7，UDP 实际读回
status = device.status_rpc()
print(status.scan_relay_mask)                # 7，JSON-RPC Status 的字段
print(status.result["scan_relay_mask"])       # 原始字段仍然可用
print(device.m.scan_relay_mask)              # 最近一次读回缓存
device.set_scan_relay_mask(ScanRelayMask.ALL)  # 恢复默认
```

`zem_api.set_scan_relay_mask(mask)` 与 `zem_api.get_scan_relay_mask()` 是高层封装。底层 builder 为 `build_set_scan_relay_mask` / `build_get_scan_relay_mask`，命令为 BASIC 等级；SDK 负责 UDP CRC、回调地址和 ACK。设置成功后再次查询，返回实际读回值。失败沿用 SDK 的协议异常/None 语义，不更新缓存为请求值。

掩码默认 15，选择顺序仍为 K4→K3→K2→K1。上位机在正常模式空闲/视频播放时立即重新计算并选档；拍照、自动调节、鱼眼模式或当前场宽无法由启用档位覆盖时拒绝修改，保留原状态。鱼眼独立 K1 路径不使用正常扫描掩码。参数按上位机既有配置保存流程持久化，设置命令不单独保存文件。

JSON-RPC `Status`、`SemControlState` 返回顶层 `result.scan_relay_mask`，值为整数。老服务器缺少该字段时 `status.scan_relay_mask` 返回 None，缓存也设为 None，不把未知状态当成 15。不要对旧固件静默模拟设置成功。

虚拟电镜支持相同的设置/查询和 `Status` 字段，便于离线协议联调；虚拟图像没有实体继电器和真实 DAC 标定，不能用于验证 K3 的硬件图像质量。

回归测试（无需真实硬件）：

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_scan_relay_mask.py tests/test_nextg_channel_frames.py tests/test_compress_lens.py tests/test_snap_image_geometry.py -q
```

跨项目本机 UDP/HTTP 联调：先构建海思上位机的 `src/Test/ScanRelayMaskTest`，再运行 `python tests/check_scan_relay_hisi.py <ScanRelayMaskTest.exe>`。该脚本启动 C# 模拟硬件测试服务并在结束时关闭，用实际客户端验证设置、查询和两个 JSON-RPC 状态，不使用真实电镜。
