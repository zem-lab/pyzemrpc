# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`pyzemrpc` is a Python remote control interface for ZEPTOOLS Scanning Electron Microscopes (SEM). It provides both a Python API for programmatic control and a GUI for interactive operation.

## Development Commands

### Environment Setup

```bash
# Install development dependencies (using internal mirror)
python -m pip install -i https://pypi.mirrors.ustc.edu.cn/simple -r requirements-dev.txt

# Install main dependencies (using internal devpi server)
python -m pip install -i http://dc000.local:7104/zeptools/devpi/+simple/ --trusted-host dc000.local -r requirements.txt

# Install package in development mode
pip install -e .
```

### Build

```bash
# Build wheel (updates git info, converts UI files to Python, cleans build dir)
inv build

# Build with docs
inv build --docs

# Update git info only
inv git_info

# Convert .ui Qt Designer files to Python
inv ui2py
```

### Testing

```bash
# Run all tests
pytest tests/ -v -s

# Run a specific test file
pytest tests/test_zem_api.py -v -s

# Run tests with pytest using the test module directly
python tests/test_zem_api.py
```

### Virtual ZEM Server

For testing, start the virtual ZEM server:

```bash
python -m zemrpc.tools.virtual_zem.main
```

The virtual ZEM udp port is `61557` and json rpc server listens on `61600` by default.

## High-Level Architecture

### Core Components

1. **zemrpc/zem/** - SEM Control Layer
   - `zem_api.py`: Main API class `ZemApi` - the primary interface for SEM operations. Uses a metaclass (`ZemApiMeta`) to automatically wrap public methods with `ensure_sync_done` decorator for synchronization.
   - `zem_rpc_device.py`: `ZemRpcDevice` - manages RPC device connection and protocol communication.
   - `conn/protocol.py`: Binary protocol implementation with CRC calculation and command/response handling.
   - `conn/rpc_protocol.py`: JSON-RPC protocol layer for higher-level communication.
   - `conn/img_receiver.py`: Image receiving and processing.
   - `models.py`: Pydantic models for SEM data structures (StagePos, ScanInfo, ZemImage, etc.)

2. **zemrpc/gui/** - Qt/PySide6 GUI
   - `zemrpc_main.py`: Main entry point for GUI application
   - `zemrpc_win.py`: Main window widget
   - `widgets/`: Custom Qt widgets (image viewers, etc.)

3. **zemrpc/tools/virtual_zem/** - Virtual SEM Emulator
   - `virtual_zem.py`: Simulates SEM hardware for testing
   - `jsonrpc_server.py`: FastAPI server with JSON-RPC endpoints for the virtual ZEM
   - Uses Rust-based sub-modules (`mandelbrot_zem_rs`, `perlin_zem_rs`) for image generation

4. **Configuration & Logging**
   - `__init__.py`: `AppConfig` class manages YAML config files and database-backed configuration via `CfgDb`
   - Uses `jgb.util` utilities for app management, logging, and persistence

### Key Patterns

- **Synchronization Pattern**: The `ZemApi` class uses a decorator pattern via `ZemApiMeta` metaclass to automatically call `sync()` before any public method (except those marked with `@skip_sync_check`).
- **Data Tree Pattern**: Uses `jgb.util.dds_util.AppTreeNode` for hierarchical data management with publish/subscribe patterns.
- **Protocol Pattern**: Low-level binary protocol with CRC validation in `protocol.py`, layered with JSON-RPC in `rpc_protocol.py`.

### Entry Points

- `pyzemrpc` - Launch GUI application
- `pyzemrpc_info` - Display package information
- `pyzemrpc_virtual_zem` - Start virtual ZEM server
- `pyzemrpc_show_img_meta` - Show image metadata tool

## Important Notes

- Python 3.11+ required
- Package uses PySide6 for Qt bindings
- Configuration stored in app home directory (typically `~/zemrpc/`)
- Internal package `jgb.util` is a core dependency for many utilities
