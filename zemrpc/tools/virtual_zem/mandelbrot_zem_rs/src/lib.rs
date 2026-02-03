//! Mandelbrot 分形生成器 - 高性能 Rust 实现
//! 
//! 使用并行计算加速 Mandelbrot 集的生成

use ndarray::Array2;
use numpy::{IntoPyArray, PyArray2};
use pyo3::prelude::*;
use rayon::prelude::*;

/// Mandelbrot 分形生成器
#[pyclass]
pub struct MandelbrotGenerator {
    max_iter: u32,
}

#[pymethods]
impl MandelbrotGenerator {
    /// 创建新的 Mandelbrot 生成器
    /// 
    /// # Arguments
    /// * `max_iter` - 最大迭代次数，默认 100
    #[new]
    #[pyo3(signature = (max_iter=100))]
    pub fn new(max_iter: u32) -> Self {
        Self { max_iter }
    }

    /// 生成 Mandelbrot 分形图像
    /// 
    /// # Arguments
    /// * `xmin` - X 轴最小值
    /// * `xmax` - X 轴最大值
    /// * `ymin` - Y 轴最小值
    /// * `ymax` - Y 轴最大值
    /// * `width` - 图像宽度
    /// * `height` - 图像高度
    /// * `max_iter` - 可选的最大迭代次数，不指定则使用构造函数的值
    /// 
    /// # Returns
    /// 返回 uint32 类型的迭代次数数组
    #[pyo3(signature = (xmin, xmax, ymin, ymax, width, height, max_iter=None))]
    pub fn generate<'py>(
        &self,
        py: Python<'py>,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        max_iter: Option<u32>,
    ) -> Bound<'py, PyArray2<u32>> {
        let max_iter = max_iter.unwrap_or(self.max_iter);
        let result = self.compute_mandelbrot(xmin, xmax, ymin, ymax, width, height, max_iter);
        result.into_pyarray_bound(py)
    }

    /// 生成归一化的 Mandelbrot 分形图像 (用于直接显示)
    /// 
    /// # Returns
    /// 返回 [0.0, 1.0] 范围的 f64 数组
    #[pyo3(signature = (xmin, xmax, ymin, ymax, width, height, max_iter=None))]
    pub fn generate_normalized<'py>(
        &self,
        py: Python<'py>,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        max_iter: Option<u32>,
    ) -> Bound<'py, PyArray2<f64>> {
        let max_iter = max_iter.unwrap_or(self.max_iter);
        let fractal = self.compute_mandelbrot(xmin, xmax, ymin, ymax, width, height, max_iter);
        
        // 转换为归一化的 f64
        let result = fractal.mapv(|v| v as f64 / max_iter as f64);
        result.into_pyarray_bound(py)
    }

    /// 生成 uint8 图像 (直接可用于显示)
    #[pyo3(signature = (xmin, xmax, ymin, ymax, width, height, max_iter=None))]
    pub fn generate_u8<'py>(
        &self,
        py: Python<'py>,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        max_iter: Option<u32>,
    ) -> Bound<'py, PyArray2<u8>> {
        let max_iter = max_iter.unwrap_or(self.max_iter);
        let fractal = self.compute_mandelbrot(xmin, xmax, ymin, ymax, width, height, max_iter);
        
        // 转换为 uint8
        let result = fractal.mapv(|v| ((v as f64 / max_iter as f64) * 255.0) as u8);
        result.into_pyarray_bound(py)
    }

    /// 生成 uint16 图像
    #[pyo3(signature = (xmin, xmax, ymin, ymax, width, height, max_iter=None))]
    pub fn generate_u16<'py>(
        &self,
        py: Python<'py>,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        max_iter: Option<u32>,
    ) -> Bound<'py, PyArray2<u16>> {
        let max_iter = max_iter.unwrap_or(self.max_iter);
        let fractal = self.compute_mandelbrot(xmin, xmax, ymin, ymax, width, height, max_iter);
        
        // 转换为 uint16
        let result = fractal.mapv(|v| ((v as f64 / max_iter as f64) * 65535.0) as u16);
        result.into_pyarray_bound(py)
    }

    /// 设置最大迭代次数
    pub fn set_max_iter(&mut self, max_iter: u32) {
        self.max_iter = max_iter;
    }

    /// 获取最大迭代次数
    pub fn get_max_iter(&self) -> u32 {
        self.max_iter
    }
}

impl MandelbrotGenerator {
    /// 计算 Mandelbrot 分形
    /// 
    /// 使用 Rayon 并行计算每一行
    fn compute_mandelbrot(
        &self,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        max_iter: u32,
    ) -> Array2<u32> {
        // 预计算 X 坐标
        let x_coords: Vec<f64> = (0..width)
            .map(|i| xmin + (xmax - xmin) * i as f64 / (width - 1).max(1) as f64)
            .collect();
        
        // 预计算 Y 坐标
        let y_coords: Vec<f64> = (0..height)
            .map(|j| ymin + (ymax - ymin) * j as f64 / (height - 1).max(1) as f64)
            .collect();

        // 并行计算每一行
        let pixels: Vec<u32> = (0..height)
            .into_par_iter()
            .flat_map(|j| {
                let cy = y_coords[j];
                x_coords.iter().map(move |&cx| {
                    self.mandelbrot_escape(cx, cy, max_iter)
                }).collect::<Vec<_>>()
            })
            .collect();

        // 转换为 2D 数组
        Array2::from_shape_vec((height, width), pixels).unwrap()
    }

    /// 计算单个点的逃逸迭代次数
    /// 
    /// 使用优化的逃逸时间算法:
    /// - 提前边界检测 (|z| > 2)
    /// - 周期检测优化 (可选)
    #[inline]
    fn mandelbrot_escape(&self, cx: f64, cy: f64, max_iter: u32) -> u32 {
        let mut zx = 0.0_f64;
        let mut zy = 0.0_f64;
        let mut zx2 = 0.0_f64;
        let mut zy2 = 0.0_f64;
        let mut iteration = 0_u32;

        // 主循环: z = z² + c
        // 使用 zx² + zy² > 4 代替 |z| > 2 以避免开方
        while zx2 + zy2 <= 4.0 && iteration < max_iter {
            // z_new = z² + c
            // z_new.x = zx² - zy² + cx
            // z_new.y = 2 * zx * zy + cy
            zy = 2.0 * zx * zy + cy;
            zx = zx2 - zy2 + cx;
            
            zx2 = zx * zx;
            zy2 = zy * zy;
            
            iteration += 1;
        }

        iteration
    }
}

/// 独立函数：快速生成 Mandelbrot 图像
/// 
/// 不需要创建生成器实例，直接调用
#[pyfunction]
#[pyo3(signature = (xmin, xmax, ymin, ymax, width, height, max_iter=100))]
fn mandelbrot<'py>(
    py: Python<'py>,
    xmin: f64,
    xmax: f64,
    ymin: f64,
    ymax: f64,
    width: usize,
    height: usize,
    max_iter: u32,
) -> Bound<'py, PyArray2<u32>> {
    let gen = MandelbrotGenerator::new(max_iter);
    gen.generate(py, xmin, xmax, ymin, ymax, width, height, None)
}

/// 独立函数：生成归一化的 Mandelbrot 图像
#[pyfunction]
#[pyo3(signature = (xmin, xmax, ymin, ymax, width, height, max_iter=100))]
fn mandelbrot_normalized<'py>(
    py: Python<'py>,
    xmin: f64,
    xmax: f64,
    ymin: f64,
    ymax: f64,
    width: usize,
    height: usize,
    max_iter: u32,
) -> Bound<'py, PyArray2<f64>> {
    let gen = MandelbrotGenerator::new(max_iter);
    gen.generate_normalized(py, xmin, xmax, ymin, ymax, width, height, None)
}

/// Python 模块初始化
#[pymodule]
fn mandelbrot_zem_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<MandelbrotGenerator>()?;
    m.add_function(wrap_pyfunction!(mandelbrot, m)?)?;
    m.add_function(wrap_pyfunction!(mandelbrot_normalized, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_mandelbrot_escape_inside() {
        let gen = MandelbrotGenerator::new(100);
        // 原点在集合内，应该达到最大迭代
        let result = gen.mandelbrot_escape(0.0, 0.0, 100);
        assert_eq!(result, 100);
    }

    #[test]
    fn test_mandelbrot_escape_outside() {
        let gen = MandelbrotGenerator::new(100);
        // (2, 2) 在集合外，应该很快逃逸
        let result = gen.mandelbrot_escape(2.0, 2.0, 100);
        assert!(result < 10);
    }

    #[test]
    fn test_deterministic() {
        let gen = MandelbrotGenerator::new(100);
        let v1 = gen.mandelbrot_escape(0.5, 0.5, 100);
        let v2 = gen.mandelbrot_escape(0.5, 0.5, 100);
        assert_eq!(v1, v2);
    }

    #[test]
    fn test_boundary() {
        let gen = MandelbrotGenerator::new(100);
        // 边界附近的点
        let result = gen.mandelbrot_escape(-0.75, 0.0, 100);
        assert!(result > 0 && result <= 100);
    }
}
