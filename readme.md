# ZEM远程控制接口（python版本）

## 项目简介

**pyzemrpc** 是一个用于电镜设备进行远程通信的 Python 库。它提供了完整的设备控制接口，包括图像采集、样品台定位、电镜参数调整等功能。

## 为什么需要这个项目

电子显微镜设备通常需要通过专用软件进行操作，这限制了自动化、批量处理和远程控制的能力。pyzemrpc 解决了这些问题：

- **远程控制**：通过网络远程操作电子显微镜设备


## 实现方式

pyzemrpc 通过以下技术实现远程控制：

- **UDP Socket + RPC 协议**：基于 UDP 通信，实现设备发现和命令传输
- **设备抽象层**：封装不同型号设备（ZEM15、ZEM18 等）的协议差异，提供统一接口
- **图像接收器**：异步接收和处理显微镜图像数据
- **GUI 工具**：提供图形界面方便用户操作
- **虚拟设备模拟器**：支持在无实际硬件的情况下进行开发和测试

## 如何测试新协议是否通过

当你添加了新的通信协议/命令后，可以通过以下方式快速验证协议是否正常工作。

### 步骤一：确保虚拟ZEM支持你的新协议

如果添加了新命令，需要修改以下文件：

**1. `zemrpc/zem/conn/protocol.py`**
- 在 `EnumCmd` 枚举中添加新命令
- 在 `ProtocolBuilder` 类中添加 `build_xxx()` 方法构建请求
- 在 `RespPacket` 类中添加 `parse_xxx()` 方法解析响应

**2. `zemrpc/tools/virtual_zem/virtual_zem.py`**
- 在 `ZemRespBuilder` 类中添加 `build_xxx()` 方法构建模拟响应
- 在 `RemoteZem.process_packet()` 方法中添加命令处理分支

### 步骤二：启动虚拟ZEM服务器

```bash
# 激活虚拟环境后运行
python -m zemrpc.tools.virtual_zem.main
```

服务器默认监听：
- UDP 端口：61557（设备通信）
- HTTP 端口：61600（JSON-RPC 服务）

### 步骤三：编写测试脚本验证

创建一个简单的测试脚本：

```python
from jgb.util import loguru_util
from zemrpc import app_cfg
from zemrpc.zem.zem_api import zem_api
from zemrpc.zem.conn.protocol import EnumCmd

def main():
    # 初始化日志
    loguru_util.init_log(app_cfg.log_dir)
    
    # 连接虚拟ZEM（本地测试）
    addr = ("127.0.0.1", 61557)
    zem_api.handshake()
    zem_api.update_remote_addr(addr)
    zem_api.sync()
    
    # 测试你新加的协议
    # 方式1：如果已经在 zem_api 或 device 中封装了方法
    # result = zem_api.your_new_method()
    
    # 方式2：直接发送原始命令测试
    # zem_api.send_cmd(EnumCmd.YourNewCmd, "参数")
    
    print("协议测试完成")

if __name__ == "__main__":
    main()
```

### 示例：添加 GetFoo 命令的完整流程

| 文件 | 修改内容 |
|------|----------|
| `protocol.py` | `EnumCmd.GetFoo = "GetFoo", False, 100, "获取Foo值"` |
| `protocol.py` | `ProtocolBuilder.build_get_foo()` 方法 |
| `protocol.py` | `RespPacket.parse_foo()` 方法 |
| `virtual_zem.py` | `ZemRespBuilder.build_get_foo()` 方法 |
| `virtual_zem.py` | `RemoteZem.process_packet()` 添加 `elif cmd == EnumCmd.GetFoo:` 分支 |
