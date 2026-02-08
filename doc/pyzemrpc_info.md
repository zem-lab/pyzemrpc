# pyzemrpc_info

显示pyzemrpc应用程序的版本和系统信息。

## 功能描述

`pyzemrpc_info`是一个命令行工具，用于显示pyzemrpc包的详细信息，包括应用版本、Git提交信息、系统环境、Python版本和依赖包版本等。这对于诊断问题、验证安装和收集环境信息非常有用。

## 使用方法

```bash
pyzemrpc_info
```

## 输出信息

运行后会显示以下信息：

### 应用信息
- App name: 应用名称
- App version: 应用版本
- Commit id: Git提交ID
- App home: 应用主目录
- Src home: 源码目录
- Run type: 运行类型
- Output directory: 输出目录
- Log directory: 日志目录
- Configuration file: 配置文件路径

### 系统信息
- Operating System: 操作系统
- CPU: 处理器信息
- MEM: 内存信息 (总计 - 已用 = 剩余)
- Python Version: Python版本

### 依赖包信息
- PySide6: PySide6版本
- opencv-python: OpenCV版本

## 示例

```bash
$ pyzemrpc_info
App name: pyzemrpc
App version: 0.1.0
Commit id: 4778269
...
```
