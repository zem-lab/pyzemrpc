use ndarray::{Array1, Array2, Zip};
use numpy::{IntoPyArray, PyArray2, PyReadonlyArray2};
use pyo3::prelude::*;
use rayon::prelude::*;

mod noise;
use noise::{PerlinNoise, WorleyNoise, RidgeNoise};

/// 高性能柏林噪声图像生成器
#[pyclass]
pub struct PerlinZemGenerator {
    perlin: PerlinNoise,
    worley: WorleyNoise,
    ridge: RidgeNoise,
    base_frequency: f64,
    worley_scale: f64,
    ridge_scale: f64,
}

#[pymethods]
impl PerlinZemGenerator {
    #[new]
    #[pyo3(signature = (seed=42, base_frequency=0.1, worley_scale=0.08, ridge_scale=0.06))]
    pub fn new(seed: u64, base_frequency: f64, worley_scale: f64, ridge_scale: f64) -> Self {
        Self {
            perlin: PerlinNoise::new(seed),
            worley: WorleyNoise::new(seed + 1000),
            ridge: RidgeNoise::new(seed),
            base_frequency,
            worley_scale,
            ridge_scale,
        }
    }

    /// 生成指定区域的噪声图像
    /// 返回 [0, 1] 范围的浮点数组
    pub fn generate_image<'py>(
        &self,
        py: Python<'py>,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        mag_factor: f64,
    ) -> Bound<'py, PyArray2<f64>> {
        let result = self.generate_perlin_image(xmin, xmax, ymin, ymax, width, height, mag_factor);
        result.into_pyarray_bound(py)
    }

    /// 生成导航图像
    pub fn generate_nav_image<'py>(
        &self,
        py: Python<'py>,
        width: usize,
        height: usize,
        nav_scale: f64,
    ) -> Bound<'py, PyArray2<f64>> {
        let aspect = width as f64 / height as f64;
        let half_scale = nav_scale / 2.0;

        let xmin = -half_scale * aspect;
        let xmax = half_scale * aspect;
        let ymin = -half_scale;
        let ymax = half_scale;

        let result = self.generate_perlin_image(xmin, xmax, ymin, ymax, width, height, 100.0);
        result.into_pyarray_bound(py)
    }

    /// 批量计算 Perlin FBM 噪声
    pub fn fbm<'py>(
        &self,
        py: Python<'py>,
        x: PyReadonlyArray2<f64>,
        y: PyReadonlyArray2<f64>,
        octaves: usize,
        lacunarity: f64,
        persistence: f64,
    ) -> Bound<'py, PyArray2<f64>> {
        let x = x.as_array();
        let y = y.as_array();
        let shape = x.shape();
        
        let mut result = Array2::<f64>::zeros((shape[0], shape[1]));
        
        Zip::from(&mut result)
            .and(&x)
            .and(&y)
            .par_for_each(|r, &xi, &yi| {
                *r = self.perlin.fbm(xi, yi, octaves, lacunarity, persistence);
            });

        result.into_pyarray_bound(py)
    }

    /// 批量计算 Worley 边缘噪声
    pub fn worley_edge<'py>(
        &self,
        py: Python<'py>,
        x: PyReadonlyArray2<f64>,
        y: PyReadonlyArray2<f64>,
    ) -> Bound<'py, PyArray2<f64>> {
        let x = x.as_array();
        let y = y.as_array();
        let shape = x.shape();
        
        let mut result = Array2::<f64>::zeros((shape[0], shape[1]));
        
        Zip::from(&mut result)
            .and(&x)
            .and(&y)
            .par_for_each(|r, &xi, &yi| {
                *r = self.worley.edge(xi, yi);
            });

        result.into_pyarray_bound(py)
    }

    /// 批量计算 Ridge 噪声
    pub fn ridge_noise<'py>(
        &self,
        py: Python<'py>,
        x: PyReadonlyArray2<f64>,
        y: PyReadonlyArray2<f64>,
        octaves: usize,
        lacunarity: f64,
        persistence: f64,
    ) -> Bound<'py, PyArray2<f64>> {
        let x = x.as_array();
        let y = y.as_array();
        let shape = x.shape();
        
        let mut result = Array2::<f64>::zeros((shape[0], shape[1]));
        
        Zip::from(&mut result)
            .and(&x)
            .and(&y)
            .par_for_each(|r, &xi, &yi| {
                *r = self.ridge.noise(xi, yi, octaves, lacunarity, persistence);
            });

        result.into_pyarray_bound(py)
    }
}

impl PerlinZemGenerator {
    /// 内部方法：生成完整的柏林噪声图像
    fn generate_perlin_image(
        &self,
        xmin: f64,
        xmax: f64,
        ymin: f64,
        ymax: f64,
        width: usize,
        height: usize,
        mag_factor: f64,
    ) -> Array2<f64> {
        // 创建坐标网格
        let x_coords: Vec<f64> = (0..width)
            .map(|i| xmin + (xmax - xmin) * i as f64 / (width - 1) as f64)
            .collect();
        let y_coords: Vec<f64> = (0..height)
            .map(|i| ymin + (ymax - ymin) * i as f64 / (height - 1) as f64)
            .collect();

        // 计算动态参数
        let base_octaves = 6usize;
        let extra_octaves = if mag_factor > 100.0 {
            ((mag_factor / 100.0).log2() as usize).min(10)
        } else {
            0
        };
        let octaves = (base_octaves + extra_octaves).min(16);

        let worley_freq = self.worley_scale * (1.0 + 0.1 * (mag_factor / 100.0).max(1.0).log2());
        let ridge_freq = self.ridge_scale * (1.0 + 0.1 * (mag_factor / 100.0).max(1.0).log2());
        let perlin_freq = self.base_frequency;

        // 并行计算每个像素
        let pixels: Vec<f64> = (0..height)
            .into_par_iter()
            .flat_map(|j| {
                let y = y_coords[j];
                (0..width)
                    .map(|i| {
                        let x = x_coords[i];
                        self.compute_pixel(
                            x, y, 
                            worley_freq, ridge_freq, perlin_freq,
                            octaves, mag_factor,
                        )
                    })
                    .collect::<Vec<_>>()
            })
            .collect();

        // 转换为 2D 数组
        let mut result = Array2::from_shape_vec((height, width), pixels).unwrap();

        // 直方图拉伸增强对比度
        self.histogram_stretch(&mut result);

        result
    }

    /// 计算单个像素的噪声值
    fn compute_pixel(
        &self,
        x: f64,
        y: f64,
        worley_freq: f64,
        ridge_freq: f64,
        perlin_freq: f64,
        octaves: usize,
        mag_factor: f64,
    ) -> f64 {
        // 1. Worley 噪声 - 晶粒结构
        let worley_x = x * worley_freq;
        let worley_y = y * worley_freq;
        
        // 多尺度 Worley
        let scales = [1.0, 2.5, 6.0];
        let weights = [0.5, 0.3, 0.2];
        let worley_multi: f64 = scales.iter().zip(weights.iter())
            .map(|(&s, &w)| w * self.worley.edge(worley_x * s, worley_y * s))
            .sum::<f64>() / weights.iter().sum::<f64>();

        // 基本 Worley 距离场
        let worley_dist = self.worley.distance(worley_x, worley_y);

        // 2. Ridge 噪声 - 锐利的线性结构
        let ridge_x = x * ridge_freq;
        let ridge_y = y * ridge_freq;
        let ridge = self.ridge.noise(ridge_x, ridge_y, octaves.min(8), 2.0, 0.5);

        // 3. Perlin FBM - 平滑的背景
        let perlin_x = x * perlin_freq;
        let perlin_y = y * perlin_freq;
        let perlin = (self.perlin.fbm(perlin_x, perlin_y, octaves, 2.0, 0.5) + 1.0) / 2.0;

        // 4. 高频细节噪声
        let detail = if mag_factor > 1000.0 {
            let detail_freq = perlin_freq * 20.0 * (1.0 + (mag_factor / 1000.0).log10());
            let detail_x = x * detail_freq;
            let detail_y = y * detail_freq;
            self.perlin.noise_2d(detail_x, detail_y) * 0.1
        } else {
            0.0
        };

        // 组合各种噪声
        let edge_strength = (worley_multi * 2.0).clamp(0.0, 1.0);
        // Sigmoid 函数使边缘更锐利
        let edge_sharp = 1.0 / (1.0 + (-10.0 * (edge_strength - 0.3)).exp());

        // 晶粒内部的灰度变化
        let grain_interior = worley_dist * 0.5 + perlin * 0.3 + ridge * 0.2;

        // 组合：边界暗，内部有纹理
        let combined = grain_interior * edge_sharp + (1.0 - edge_sharp) * 0.1 + detail;

        combined.clamp(0.0, 1.0)
    }

    /// 直方图拉伸增强对比度
    fn histogram_stretch(&self, data: &mut Array2<f64>) {
        // 计算 2% 和 98% 分位数
        let mut values: Vec<f64> = data.iter().cloned().collect();
        values.sort_by(|a, b| a.partial_cmp(b).unwrap());
        
        let n = values.len();
        let p2 = values[(n as f64 * 0.02) as usize];
        let p98 = values[(n as f64 * 0.98) as usize];

        if p98 > p2 {
            data.mapv_inplace(|v| ((v - p2) / (p98 - p2)).clamp(0.0, 1.0));
        }
    }
}

/// Python 模块初始化
#[pymodule]
fn perlin_zem_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PerlinZemGenerator>()?;
    Ok(())
}
