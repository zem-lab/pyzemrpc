# pyzemrpc_virtual_zem

虚拟扫描电子显微镜(JSON-RPC服务器)。

## 功能描述

`pyzemrpc_virtual_zem`是pyzemrpc包的虚拟ZEM服务器，用于在不连接真实SEM硬件的情况下进行测试和开发。它模拟了ZEPTOOLS扫描电子显微镜的行为，并提供JSON-RPC接口供客户端调用。

该工具使用FastAPI构建JSON-RPC服务器，并利用Rust编写的子模块(`mandelbrot_zem_rs`, `perlin_zem_rs`)生成模拟的SEM图像。

## 使用方法

### 基本用法

```bash
pyzemrpc_virtual_zem
```

### 指定端口和主机

```bash
pyzemrpc_virtual_zem --port 61600 --host 0.0.0.0
```

### 使用短参数

```bash
pyzemrpc_virtual_zem -p 61600
```

## 命令行参数

| 参数 | 短参数 | 类型 | 默认值 | 描述 |
|------|--------|------|--------|------|
| `--port` | `-p` | int | 61600 | JSON-RPC服务器监听端口 |
| `--host` | 无 | str | 0.0.0.0 | 服务器绑定地址 |

## 默认配置

- **UDP端口**: 61557 (虚拟ZEM的UDP通信端口)
- **JSON-RPC端口**: 61600
- **随机种子**: 3366 (用于生成可重复的测试图像)

## 使用场景

1. **开发和测试**: 在没有真实SEM硬件的情况下开发和测试应用程序
2. **CI/CD**: 在持续集成环境中运行自动化测试
3. **演示和培训**: 用于演示和培训，无需昂贵设备
4. **问题诊断**: 隔离硬件相关问题

## 启动示例

### 在前台运行

```bash
pyzemrpc_virtual_zem
```

### 在后台运行 (Linux/macOS)

```bash
pyzemrpc_virtual_zem &
```

### 在后台运行 (Windows PowerShell)

```powershell
Start-Process pyzemrpc_virtual_zem
```

## 停止服务器

按 `Ctrl+C` 停止服务器。

## 注意事项

- 虚拟ZEM生成的图像是模拟数据，不代表真实的SEM图像
- 某些真实SEM的高级特性可能在虚拟版本中不支持
- 虚拟服务器的性能可能与真实硬件不同
