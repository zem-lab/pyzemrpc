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

**Mandatory release order:** follow [AGENTS.md](AGENTS.md). Commit all release-related source, version and build changes first, record the full commit, then regenerate git metadata and rebuild from that clean commit before packaging. Never release binaries built before the commit, include unrelated uncommitted changes, or merely rewrite the manifest's commit. After any further source change, commit and rebuild again. Verify the embedded commit in the actual artifact.

```bash
# Build pure Python wheel (updates git info, converts UI files to Python, cleans build dir)
inv build

# Build Rust accelerator wheels (mandelbrot_zem_rs, perlin_zem_rs) for current platform
inv build_rust

# Compatibility entry point: build only the main pure-Python wheel
inv build_all

# Build with docs
inv build --docs

# Update git info only
inv git_info

# Convert .ui Qt Designer files to Python
inv ui2py

# Run the GUI after installing the wheel
pyzemrpc
```

The current deliverable is only the main pure-Python wheel. Do not generate standalone GUI executables or use PyInstaller, Nuitka, or C/C++ compilation. The GUI and JSON-RPC stage-parameter tab remain in the wheel; launch with `pyzemrpc` after installation. `inv build_all` is a wheel-only compatibility entry point. Optional Rust accelerators have a separate `build_rust` entry point outside the current release workflow. Follow [AGENTS.md](AGENTS.md).


### Testing

**Important:** Always use the project virtual environment (`venv`) for Python operations to ensure consistent behavior across different systems and terminal versions.

```bash
# On Windows (Git Bash, PowerShell, or CMD)
.venv/Scripts/python.exe -c "your code"
.venv/Scripts/python.exe tests/test_zem_api.py
.venv/Scripts/pytest.exe tests/ -v -s

# On Linux/macOS
.venv/bin/python -c "your code"
.venv/bin/python tests/test_zem_api.py
.venv/bin/pytest tests/ -v -s

# Alternative: activate venv first
# Windows
.venv/Scripts/activate
python tests/test_zem_api.py

# Linux/macOS
source .venv/bin/activate
python tests/test_zem_api.py
```

**Note:**
- Different operating systems (Windows vs Linux/macOS) may have different path separators and Python script locations
- Different terminals (Git Bash, PowerShell, CMD, zsh, bash) may handle path escaping differently
- Always use the absolute path to the Python executable in the venv to avoid issues with system Python

Example test commands:
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

The virtual ZEM UDP port is `61557` and the JSON-RPC server port is auto-selected (default 0) via `--port`. The UDP service binds to `0.0.0.0:61557`, while handshake and image download responses advertise a concrete reachable local IP.

GUI defaults to **本机** (`127.0.0.1:61557`). Handshake also unicasts loopback because UDP broadcast cannot reach `127.0.0.1`. Connecting to loopback binds and embeds `127.0.0.1:<ephemeral-port>` as the callback address.

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
   - `virtual_zem.py`: Simulates SEM hardware for testing. Two engines: `MandelbrotZem` (fractal-based) and `PerlinZem` (noise-based). Both prefer Rust acceleration and fall back to Python/NumPy automatically.
   - `jsonrpc_server.py`: FastAPI server with JSON-RPC endpoints for the virtual ZEM
   - `mandelbrot_zem_rs/`: Rust-accelerated Mandelbrot fractal generator (optional, `pip install pyzemrpc[rust]`)
   - `perlin_zem_rs/`: Rust-accelerated Perlin noise generator (optional, `pip install pyzemrpc[rust]`)

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

## Command Permission System

The Z command system implements a two-level permission model to control which operations can be performed:

### Command Levels

- **BASIC** - Read-only and safe operations that can be called at any time
  - Examples: `GetModel`, `GetMag`, `GetStagePos`, `GetNavImg`, `GetHV`, `Snap`, `VideoPlay`
  - These commands represent status queries and non-destructive operations

- **ADVANCED** - Write operations that require explicit authorization
  - Examples: `SetHV`, `SetMag`, `SetStagePos`, `GunOn`, `AutoFocus`, `SetWD`, `SetBseCfg`
  - These commands modify device state and require the work mode to be set to ADVANCED

### Work Mode Management

The `ZemRpcDevice` class maintains a work mode state that controls which commands can be executed:

```python
from zemrpc.zem.conn.protocol import EnumCmdLevel

# Check current mode
current_mode = device.get_work_mode()  # Defaults to EnumCmdLevel.BASIC

# Switch to advanced mode to enable advanced commands
device.set_work_mode(EnumCmdLevel.ADVANCED)

# Switch back to basic mode (restricts to basic commands only)
device.set_work_mode(EnumCmdLevel.BASIC)
```

### Command Level Enforcement

Command permissions are enforced at the protocol level in:
- `ZemRpcDevice.send_cmd()` - Direct command sending
- `ZemRpcDevice.pubsub_send()` - PubSub-based command sending
- All high-level methods that use the above

Attempting to execute an ADVANCED command while in BASIC mode will raise:
```
ZemException: 命令 SetHV (设置加速电压) 是高级命令，需要先设置工作模式为 ADVANCED。当前模式: BASIC
```

### Implementation Details

- Each `EnumCmd` value has a `cmd_level` property returning `EnumCmdLevel.BASIC` or `EnumCmdLevel.ADVANCED`
- Permission checking is done via `ZemRpcDevice._check_cmd_permission(cmd)` before any command is sent
- This provides a centralized, type-safe mechanism for command authorization
