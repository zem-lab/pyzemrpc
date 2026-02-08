
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
# 构建wheel包（更新git信息，转换UI文件到Python，清理构建目录）
inv build

# 构建带文档
inv build --docs

# 仅更新git信息
inv git_info

# 将.ui Qt Designer文件转换为Python
inv ui2py
```

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

默认UDP端口是 `61557`，JSON-RPC服务器监听在 `61600`。

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
