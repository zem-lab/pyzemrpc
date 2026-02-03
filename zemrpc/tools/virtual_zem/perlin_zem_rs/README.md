# perlin_zem_rs

高性能柏林噪声图像生成器，用于虚拟电镜 (PerlinZem)。

使用 Rust 实现，通过 PyO3 提供 Python 接口，相比纯 Python 实现性能提升 10-50 倍。

## 安装依赖

### Windows

1. 安装 Rust 工具链：
   ```powershell
   # 下载并运行 rustup-init.exe
   # https://rustup.rs/
   ```

2. 安装 maturin：
   ```powershell
   pip install maturin
   ```

## 编译安装

### 开发模式（推荐调试时使用）

```powershell
cd zemrpc/tools/virtual_zem/perlin_zem_rs
maturin develop --release
```

### 构建 wheel 包

```powershell
cd zemrpc/tools/virtual_zem/perlin_zem_rs
maturin build --release
pip install target/wheels/perlin_zem_rs-*.whl
```

## 使用方式

安装后，`PerlinZem` 会自动检测并使用 Rust 实现：

```python
from zemrpc.tools.virtual_zem.virtual_zem import PerlinZem

# 自动使用 Rust 实现（如果已安装）
zem = PerlinZem(seed=42)
```

也可以直接使用 Rust 模块：

```python
from perlin_zem_rs import PerlinZemGenerator

# 创建生成器
gen = PerlinZemGenerator(
    seed=42,
    base_frequency=0.1,
    worley_scale=0.08,
    ridge_scale=0.06
)

# 生成图像 (返回 numpy 数组，值域 [0, 1])
img = gen.generate_image(
    xmin=-100, xmax=100,
    ymin=-100, ymax=100,
    width=1024, height=1024,
    mag_factor=500
)

# 生成导航图
nav_img = gen.generate_nav_image(width=640, height=480, nav_scale=500)
```

## API 参考

### `PerlinZemGenerator`

#### 构造函数

```python
PerlinZemGenerator(
    seed: int = 42,
    base_frequency: float = 0.1,
    worley_scale: float = 0.08,
    ridge_scale: float = 0.06
)
```

#### 方法

- `generate_image(xmin, xmax, ymin, ymax, width, height, mag_factor) -> np.ndarray`
  生成指定区域的噪声图像，返回 [0, 1] 范围的 float64 数组

- `generate_nav_image(width, height, nav_scale) -> np.ndarray`
  生成导航图像

- `fbm(x, y, octaves, lacunarity, persistence) -> np.ndarray`
  计算分形布朗运动噪声

- `worley_edge(x, y) -> np.ndarray`
  计算 Worley 边缘噪声

- `ridge_noise(x, y, octaves, lacunarity, persistence) -> np.ndarray`
  计算 Ridge 噪声

## 性能对比

| 图像尺寸  | Python 实现 | Rust 实现 | 加速比 |
| --------- | ----------- | --------- | ------ |
| 512x512   | ~2.5s       | ~0.08s    | 31x    |
| 1024x1024 | ~10s        | ~0.3s     | 33x    |
| 2048x2048 | ~40s        | ~1.2s     | 33x    |

*测试环境: Intel i7-12700H, Windows 11*
