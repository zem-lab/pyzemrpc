# pyzemrpc

ZEPTOOLS扫描电子显微镜(SEM)远程控制图形界面应用。

## 功能描述

`pyzemrpc`是pyzemrpc包的主图形用户界面(GUI)应用程序，提供了交互式的扫描电子显微镜控制界面。

## 使用方法

```bash
pyzemrpc
```

## 主要特性

- 图形化控制界面
- 实时图像显示
- SEM参数控制
- 工作台位置管理
- 扫描参数配置
- 图像保存和元信息管理

## 系统要求

- Python 3.11+
- PySide6 (Qt绑定)
- pyqtgraph (数据可视化)
- opencv-python (图像处理)

## 配置文件

应用程序使用配置文件 `conf/config.yml`，安装时位于:
- Windows: `%APPDATA%/zemrpc/conf/`
- Linux/macOS: `~/.local/share/zemrpc/conf/`
