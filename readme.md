![pyzemrpc Banner](./doc/pyzemrpc_banner.png)

# pyzemrpc

**ZEM远程控制接口（python版本）**

`pyzemrpc` 是安徽泽攸科技（ZEPTOOLS）扫描电镜（SEM）的Python远程控制接口与工具集。它提供了一套Python API，允许开发者通过代码控制SEM设备，以及一个图形用户界面（GUI）用于交互式操作。

---

## ✨ 特性 (Features)

*   **远程控制**: 支持对ZEM系列扫描电镜的远程操作与监控。
*   **Python API**: 提供友好的Python接口，便于集成到自动化脚本或第三方软件中。
*   **图形界面**: 内置 `pyzemrpc` GUI 工具，开箱即用。
*   **配置灵活**: 基于 YAML 和 数据库 的灵活配置管理。

## 🚀 安装 (Installation)

### 依赖环境
*   Python 3.10+
*   Windows / Linux / MacOS

### 安装步骤

1.  克隆仓库：
    ```bash
    git clone https://gitee.com/zeyou-anhui/pyzemrpc.git
    cd pyzemrpc
    ```

2.  安装依赖并安装包：
    ```bash
    pip install .
    ```

    或者使用开发模式安装：
    ```bash
    pip install -e .
    ```

3.  或者使用pypi安装
    ```bash
    pip install pyzemrpc
    ```



## 🖥️ 使用 (Usage)

### 启动 GUI
安装完成后，可以直接在终端运行以下命令启动图形界面：
```bash
pyzemrpc
```

### 命令行工具
查看相关信息：
```bash
pyzemrpc_info
```

### Python 开发
在您的 Python 脚本中导入 `zemrpc`：

```python
import zemrpc
from zemrpc import app_cfg

# 示例代码 (具体API参考文档)
print(f"pyzemrpc version: {app_cfg.version}")
```

## 📄 文档 (Documentation)
更多详细文档和配置说明，请查阅 [doc](./doc) 目录。

## 🤝 贡献 (Contributing)
欢迎提交 Issue 或 Pull Request 来改进本项目。

## 📃 许可证 (License)
本项目采用 [MIT License](LICENSE) 开源。

---
Copyright © 2024-2026 ZEPTOOLS

