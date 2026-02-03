---
name: test-zem-protocol
description: 测试 ZEM 协议命令是否正常工作。当用户说"测试协议"、"测试命令"、"帮我测试 XXX"（如"帮我测试获取高压"、"测试 GetHV"）时使用此技能。支持测试 protocol.py 中定义的所有 EnumCmd 命令。
---

# 测试 ZEM 协议

此技能用于快速验证 ZEM 协议命令是否正常工作。

## 触发场景

用户说以下类似的话时触发：
- "帮我测试获取高压"
- "测试 GetHV 协议"
- "测试设置放大倍数命令"
- "帮我验证 SetMag 协议是否通"

## 测试流程

### 步骤 1：识别要测试的命令

从用户输入中提取要测试的命令，匹配 `zemrpc/zem/conn/protocol.py` 中的 `EnumCmd` 枚举：

| 用户输入关键词 | 对应 EnumCmd | 测试方法 |
|---------------|-------------|---------|
| 获取高压/GetHV | `GetHV` | `zem_api.get_hv()` |
| 设置高压/SetHV | `SetHV` | `zem_api.set_hv(kv)` |
| 获取放大倍数/GetMag | `GetMag` | `zem_api.device.get_mag()` |
| 设置放大倍数/SetMag | `SetMag` | `zem_api.set_mag(mag)` |
| 获取坐标/GetStagePos | `GetStagePos` | `zem_api.get_stage_pos()` |
| 设置坐标/SetStagePos | `SetStagePos` | `zem_api.stage_xy_goto((x, y))` |
| 获取物镜/GetOB | `GetOB` | `zem_api.get_ob()` |
| 设置物镜/SetOB | `SetOB` | `zem_api.set_ob(ob)` |
| 拍图/Snap | `Snap` | `zem_api.snap()` |
| 获取BSE配置/GetBseCfg | `GetBseCfg` | `zem_api.get_bse_cfg()` |
| 获取型号/GetModel | `GetModel` | `zem_api.device.get_model()` |

### 步骤 2：启动虚拟 ZEM 服务器

在终端中运行：

```bash
# 激活虚拟环境
.venv/Scripts/activate  # Windows
# 或 source .venv/bin/activate  # Linux/Mac

# 启动虚拟ZEM
python -m zemrpc.tools.virtual_zem.main
```

服务器启动后会监听：
- UDP 61557（设备通信）
- HTTP 61600（JSON-RPC）

### 步骤 3：生成并运行测试脚本

在 `tests/` 目录下创建测试脚本 `test_protocol_temp.py`：

```python
from jgb.util import loguru_util
from zemrpc import app_cfg
from zemrpc.zem.zem_api import zem_api


def main():
    loguru_util.init_log(app_cfg.log_dir)
    
    # 连接虚拟ZEM
    addr = ("127.0.0.1", 61557)
    zem_api.handshake()
    zem_api.update_remote_addr(addr)
    zem_api.sync()
    
    # === 在此处添加测试代码 ===
    # 根据用户要测试的命令，调用对应的 API
    
    print("测试完成")


if __name__ == "__main__":
    main()
```

### 步骤 4：验证结果

运行测试脚本：

```bash
python tests/test_protocol_temp.py
```

检查：
1. 无异常抛出 → 协议通信正常
2. 返回值符合预期 → 解析正确
3. 日志中显示请求/响应内容 → 可排查问题

## 测试代码示例

### 测试获取高压 (GetHV)

```python
result = zem_api.get_hv()
print(f"高压信息: 加速电压={result.acc_v}V, 束流={result.beam_i}uA")
```

### 测试设置放大倍数 (SetMag)

```python
zem_api.set_mag(1000)
mag = zem_api.device.get_mag()
print(f"当前放大倍数: {mag}")
```

### 测试获取坐标 (GetStagePos)

```python
pos = zem_api.get_stage_pos()
print(f"当前坐标: x={pos.x}, y={pos.y}")
```

### 测试拍图 (Snap)

```python
from zemrpc.zem.models import EnumImageSize, SnapArgs

snap_args = SnapArgs(pixel_avg=5, size=EnumImageSize.S512x512)
img = zem_api.snap(snap_args=snap_args)
print(f"图像尺寸: {img.img.shape}")
```

### 测试 BSE 配置 (GetBseCfg/SetBseCfg)

```python
# 获取
cfg = zem_api.get_bse_cfg()
print(f"BSE配置: {cfg}")

# 设置
from zemrpc.zem.conn.protocol import BseInfo, BseQuadrant, EnumBsePhase
new_cfg = BseInfo()
zem_api.set_bse_cfg(new_cfg)
```

## 常见问题

### Q: 连接超时？
确保虚拟ZEM服务器已启动，检查端口 61557 是否被占用。

### Q: 命令返回 Invalid command？
检查虚拟ZEM的 `RemoteZem.process_packet()` 是否已添加该命令的处理分支。

### Q: 协议解析错误？
检查 `RespPacket` 中的 `parse_xxx()` 方法正则表达式是否正确。
