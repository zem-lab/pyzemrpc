
# pyzemrpc 文档总览

pyzemrpc 是一个Python远程控制接口，用于ZEPTOOLS扫描电子显微镜(SEM)。本项目提供了Python API用于程序化控制和GUI用于交互操作。

## 主要组件

### GUI 应用
- **pyzemrpc** - 主GUI应用程序，提供图形界面进行SEM操作
  - [详细文档](pyzemrpc_gui.md)

### 工具集
- **pyzemrpc_info** - 显示包信息和系统配置
  - [详细文档](pyzemrpc_info.md)

- **pyzemrpc_virtual_zem** - 虚拟ZEM服务器，用于测试和开发
  - [详细文档](pyzemrpc_virtual_zem.md)

- **pyzemrpc_show_img_meta** - 显示图像元信息
  - [详细文档](pyzemrpc_show_img_meta.md)

## 安装和部署

### 用户安装

```bash
# 基础安装（纯 Python，无需 Rust 工具链）
pip install pyzemrpc

# 带 Rust 加速（可选，虚拟电镜图像生成快 10-50 倍）
pip install pyzemrpc[rust]
```

### 环境设置

```bash
# 安装开发依赖（使用内部镜像）
python -m pip install -i https://pypi.mirrors.ustc.edu.cn/simple -r requirements-dev.txt

# 安装主依赖（使用内部devpi服务器）
python -m pip install -i http://dc000.local:7104/zeptools/devpi/+simple/ --trusted-host dc000.local -r requirements.txt

# 安装包到开发模式
pip install -e .
```

### 构建

```bash
# 构建主包 wheel（纯 Python）
inv build

# 构建 Rust 加速包 wheel（平台相关）
inv build_rust

# 一键构建所有三个包
inv build_all

# 构建带文档
inv build --docs

# 将 GUI 入口编译为独立目录分发的 pyzemrpc.exe（需 Nuitka + MSVC，耗时长）
inv build_exe

# 辅助任务
inv git_info   # 将 git commit hash 写入 zemrpc/__commit__.py
inv ui2py      # 将 .ui Qt Designer 文件转换为 Python
```

Rust 加速包（`mandelbrot_zem_rs`、`perlin_zem_rs`）需安装 `maturin` 和 Rust 工具链。如未安装 Rust 环境，可跳过 `inv build_rust`，仅构建纯 Python 主包。

### 发布

- [PyPI/Twine 发布指南](twine_release.md) — 包含三包构建、上传和 CI 自动化说明

### 测试

```bash
# 运行所有测试
pytest tests/ -v -s

# 运行特定测试文件
pytest tests/test_zem_api.py -v -s

# 直接运行测试模块
python tests/test_zem_api.py
```

## 虚拟ZEM服务器

启动虚拟ZEM服务器用于测试：
```bash
python -m zemrpc.tools.virtual_zem.main
```

默认UDP端口是 `61557`，JSON-RPC服务器端口自动选择（`--port 0`）。

GUI 启动后设备下拉框默认选中 **本机**（`127.0.0.1:61557`）。本机已启动虚拟 ZEM 或电镜代理时，可直接点「同步状态」，不必先扫描。UDP 广播到不了回环，扫描时会额外单播探测 `127.0.0.1`。

## 2026-09 本机连接

从 `pyzemcap_v2` 迁入扫描设备时的本机方案，版本 `1.2.6.dev2026090902`。

- GUI 默认设备项 `本机` = `127.0.0.1:61557`。启动只写入地址，不自动同步。
- 目标为回环时，本地绑定和报文回包地址固定为 `127.0.0.1:<临时端口>`，避免 Windows `WinError 10049`。
- 扫描在线设备：各网卡广播 + `127.0.0.1` 单播；扫描结束后按当前目标恢复绑定，不改写本机回包地址。
- 本机服务未开时，同步失败提示：`命令超时，可能电镜服务未开启`。`zem_api.sync()` 失败会重新抛出异常。
- 普通协议命令超时默认按 3 倍等待；默认超时达到 10 秒的长命令保持原值。2026-09-20 起 Handshake 不参与倍率：loopback 探测固定 0.4 秒，广播发现窗口与 fallback 握手使用协议原始超时。可通过 `zem_api.set_timeout_multiple(1)` 恢复其他命令的原始超时，或设置其他正数倍数。
- `inv build` 产物：`dist/pyzemrpc-1.2.6.dev2026090902-py3-none-any.whl`。
- `inv build_exe` 用 Nuitka standalone 编译 `zemrpc/gui/zemrpc_main.py`，输出 `dist/exe/zemrpc_main.dist/pyzemrpc.exe`。该编译依赖 Nuitka 与 MSVC，耗时长；独立 exe 内 `sys.executable` 不是 Python，GUI「启动虚拟 ZEM」子进程不可用。

相关实现：
- `zemrpc/gui/zemrpc_win.py`、`zemrpc/gui/ui_utils.py`
- `zemrpc/zem/zem_rpc_device.py`、`zemrpc/zem/ip_util.py`、`zemrpc/zem/zem_api.py`、`zemrpc/zem/models.py`
- `tests/test_loopback_local.py`、`tests/test_exception.py`、`tests/test_ip_util.py`

## 架构概述

1. **zemrpc/zem/** - SEM控制层
   - `zem_api.py`: 主API类`ZemApi` - SEM操作的主要接口
   - `zem_rpc_device.py`: `ZemRpcDevice` - 管理RPC设备连接和协议通信
   - `conn/`: 协议实现
   - `models.py`: SEM数据结构的Pydantic模型

2. **zemrpc/gui/** - Qt/PySide6 GUI
   - `zemrpc_main.py`: GUI应用程序主入口点
   - `zemrpc_win.py`: 主窗口小部件
   - `widgets/`: 自定义Qt小部件

3. **zemrpc/tools/virtual_zem/** - 虚拟SEM仿真器
   - `virtual_zem.py`: 模拟SEM硬件进行测试
   - `jsonrpc_server.py`: 提供虚拟ZEM的JSON-RPC端点

## 2026-09-20 握手发现超时修复

`set_timeout_multiple()` 继续控制普通短命令，但不再延长网络发现等待。修复覆盖回环单播、多网卡广播窗口和经 `pubsub_send` 的 fallback Handshake。扫描结束后继续恢复当前目标连接；扫描不触发状态测试或设备运动。

回归：`python -m pytest tests/test_timeout_multiplier.py tests/test_loopback_local.py -q`，12 项通过。新增用例使用倍率 30 验证握手仍采用 0.4 秒 loopback 和原始广播时间。此修改为源码提交，未发布新 SDK wheel；调用方需要使用该源码或后续包含修复的发布包。
