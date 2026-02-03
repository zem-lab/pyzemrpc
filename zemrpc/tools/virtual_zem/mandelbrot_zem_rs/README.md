# mandelbrot_zem_rs

高性能 Mandelbrot 分形生成器 - Rust 实现

## 功能

- 使用 Rust 和 Rayon 实现并行 Mandelbrot 分形计算
- 比纯 Python/NumPy 实现快 10-50 倍
- 支持多种输出格式 (u8, u16, f64)
- 通过 PyO3 提供 Python 绑定

## 安装要求

- Rust 工具链 (https://rustup.rs/)
- Python 3.9+
- maturin (`pip install maturin`)

## 编译安装

```powershell
# Windows PowerShell
.\build.ps1

# 或者手动
maturin develop --release
```

## 使用方法

```python
from mandelbrot_zem_rs import MandelbrotGenerator, mandelbrot

# 方法1: 使用生成器类
gen = MandelbrotGenerator(max_iter=100)
img = gen.generate(xmin=-2.0, xmax=1.0, ymin=-1.5, ymax=1.5, width=800, height=600)

# 直接生成 uint8 图像
img_u8 = gen.generate_u8(-2.0, 1.0, -1.5, 1.5, 800, 600)

# 直接生成 uint16 图像
img_u16 = gen.generate_u16(-2.0, 1.0, -1.5, 1.5, 800, 600)

# 方法2: 使用独立函数
img = mandelbrot(-2.0, 1.0, -1.5, 1.5, 800, 600, max_iter=100)
```

## API

### MandelbrotGenerator 类

- `MandelbrotGenerator(max_iter=100)` - 创建生成器
- `generate(xmin, xmax, ymin, ymax, width, height, max_iter=None)` - 生成 uint32 迭代次数数组
- `generate_normalized(...)` - 生成 [0, 1] 范围的 f64 数组
- `generate_u8(...)` - 生成 uint8 图像
- `generate_u16(...)` - 生成 uint16 图像

### 独立函数

- `mandelbrot(xmin, xmax, ymin, ymax, width, height, max_iter=100)` - 快速生成 uint32 数组
- `mandelbrot_normalized(...)` - 快速生成归一化 f64 数组

## 性能对比

| 分辨率 | Python (NumPy) | Rust | 加速比 |
|--------|----------------|------|--------|
| 512x512 | ~150ms | ~5ms | 30x |
| 1024x1024 | ~600ms | ~15ms | 40x |
| 2048x2048 | ~2.5s | ~55ms | 45x |

*测试环境: Intel i7, max_iter=100*

## 算法优化

1. **并行计算**: 使用 Rayon 并行计算每一行
2. **避免开方**: 使用 |z|² > 4 代替 |z| > 2
3. **预计算坐标**: 提前计算 X/Y 坐标数组
4. **内联优化**: 关键函数使用 `#[inline]` 标记
5. **LTO 优化**: Release 构建启用链接时优化
