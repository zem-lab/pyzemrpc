# PyPI 发布指南

pyzemrpc 项目包含三个独立的 PyPI 包，发布时需按顺序构建并上传。

## 包结构

| 包名 | 类型 | 说明 |
|---|---|---|
| `pyzemrpc` | 纯 Python (`py3-none-any`) | 主包，SEM 远程控制接口 |
| `mandelbrot_zem_rs` | 平台相关 (如 `cp312-win_amd64`) | Rust 加速 Mandelbrot 分形生成器 |
| `perlin_zem_rs` | 平台相关 (如 `cp312-win_amd64`) | Rust 加速 Perlin 噪声生成器 |

## 依赖关系

```
pyzemrpc
  └── [rust] extra → mandelbrot_zem_rs  (可选)
  └── [rust] extra → perlin_zem_rs    (可选)
```

两个 Rust 包为可选加速模块。用户安装 `pip install pyzemrpc` 时不会自动安装 Rust 包，需显式指定 `pip install pyzemrpc[rust]`。如 Rust 包未安装，虚拟电镜自动回退到纯 Python/NumPy 实现。

## 环境准备

```bash
# 安装发布工具
pip install twine maturin

# 配置 PyPI 凭证（选一种）
# 方式1: 环境变量
export TWINE_USERNAME=__token__
export TWINE_PASSWORD=pypi-xxxxxxxx

# 方式2: ~/.pypirc 文件
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers = pypi

[pypi]
username = __token__
password = pypi-xxxxxxxx
EOF

# 方式3: 内部 devpi 服务器（仅限内部发布）
export TWINE_REPOSITORY_URL=http://dc000.local:7104/zeptools/devpi/+simple/
export TWINE_USERNAME=your_username
export TWINE_PASSWORD=your_password
```

## 构建流程

### 一键构建

```bash
# 构建所有三个包
inv build_all
```

构建产物位置：
- `pyzemrpc` → `dist/pyzemrpc-{version}-py3-none-any.whl`
- `mandelbrot_zem_rs` → `zemrpc/tools/virtual_zem/mandelbrot_zem_rs/target/wheels/`
- `perlin_zem_rs` → `zemrpc/tools/virtual_zem/perlin_zem_rs/target/wheels/`

### 分步构建

```bash
# 1. 构建主包（纯 Python wheel）
inv build

# 2. 构建 Rust 加速包（平台相关 wheel）
inv build_rust

# 或手动逐个构建 Rust 包
cd zemrpc/tools/virtual_zem/mandelbrot_zem_rs
maturin build --release

cd ../perlin_zem_rs
maturin build --release
```

### 多平台构建

Rust 包是原生二进制，需在目标平台分别构建。以 Windows 为例：

```powershell
# Windows x86_64
maturin build --release --target x86_64-pc-windows-msvc
```

Linux 和 macOS 需在对应系统上构建，或通过 CI 矩阵自动化。

## 发布到 PyPI

### 首次发布

```bash
# 1. 先上传 Rust 包（主包的可选依赖必须先存在）
twine upload zemrpc/tools/virtual_zem/mandelbrot_zem_rs/target/wheels/*.whl
twine upload zemrpc/tools/virtual_zem/perlin_zem_rs/target/wheels/*.whl

# 2. 再上传主包
twine upload dist/pyzemrpc-*.whl
```

### 版本更新

```bash
# 1. 更新版本号（三处需手动同步）
#    - zemrpc/__version__.py          (pyzemrpc 主包)
#    - mandelbrot_zem_rs/Cargo.toml   (Rust 包)
#    - mandelbrot_zem_rs/pyproject.toml
#    - perlin_zem_rs/Cargo.toml
#    - perlin_zem_rs/pyproject.toml

# 2. 重新构建
inv build_all

# 3. 上传
twine upload dist/pyzemrpc-*.whl
twine upload zemrpc/tools/virtual_zem/mandelbrot_zem_rs/target/wheels/*.whl
twine upload zemrpc/tools/virtual_zem/perlin_zem_rs/target/wheels/*.whl
```

### 发布到内部 devpi

```bash
# 上传到内部 devpi 服务器
twine upload --repository-url http://dc000.local:7104/zeptools/devpi/+simple/ \
    dist/pyzemrpc-*.whl

twine upload --repository-url http://dc000.local:7104/zeptools/devpi/+simple/ \
    zemrpc/tools/virtual_zem/mandelbrot_zem_rs/target/wheels/*.whl

twine upload --repository-url http://dc000.local:7104/zeptools/devpi/+simple/ \
    zemrpc/tools/virtual_zem/perlin_zem_rs/target/wheels/*.whl
```

## 验证安装

发布后验证各包可正常安装和导入：

```bash
# 验证主包
pip install pyzemrpc
python -c "import zemrpc; print(zemrpc.__version__)"

# 验证 Rust 加速包
pip install pyzemrpc[rust]
python -c "from mandelbrot_zem_rs import MandelbrotGenerator; print('OK')"
python -c "from perlin_zem_rs import PerlinZemGenerator; print('OK')"

# 验证虚拟电镜（自动使用 Rust 加速）
pyzemrpc_virtual_zem --port 0
```

## CI 自动化（建议）

推荐使用 GitHub Actions + `PyO3/maturin-action` 实现多平台自动构建和发布。核心流程：

1. 推送 tag 触发 workflow
2. 矩阵构建：`ubuntu-latest` / `windows-latest` / `macos-latest`
3. `maturin build --release` 生成各平台 wheel
4. `twine upload` 上传到 PyPI（或内部 devpi）

CI 配置模板（`.github/workflows/release.yml`）可根据实际需求补充。
