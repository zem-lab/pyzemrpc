//! 噪声算法实现
//! 包括 Perlin 噪声、Worley 噪声、Ridge 噪声

/// Perlin 噪声生成器
pub struct PerlinNoise {
    perm: [usize; 512],
    gradients: [[f64; 2]; 8],
}

impl PerlinNoise {
    pub fn new(seed: u64) -> Self {
        let mut perm = [0usize; 512];
        let mut p: Vec<usize> = (0..256).collect();
        
        // 使用 LCG 随机数生成器进行洗牌
        let mut rng_state = seed;
        for i in (1..256).rev() {
            rng_state = rng_state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let j = (rng_state >> 33) as usize % (i + 1);
            p.swap(i, j);
        }
        
        // 复制排列表
        for i in 0..256 {
            perm[i] = p[i];
            perm[i + 256] = p[i];
        }

        // 8 方向梯度向量
        let gradients = [
            [1.0, 1.0], [-1.0, 1.0], [1.0, -1.0], [-1.0, -1.0],
            [1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0],
        ];

        Self { perm, gradients }
    }

    /// 平滑插值函数: 6t^5 - 15t^4 + 10t^3
    #[inline]
    fn fade(&self, t: f64) -> f64 {
        t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
    }

    /// 计算梯度点积
    #[inline]
    fn grad_dot(&self, hash: usize, dx: f64, dy: f64) -> f64 {
        let g = &self.gradients[hash & 7];
        g[0] * dx + g[1] * dy
    }

    /// 2D Perlin 噪声
    pub fn noise_2d(&self, x: f64, y: f64) -> f64 {
        let xi = x.floor() as i32 & 255;
        let yi = y.floor() as i32 & 255;

        let xf = x - x.floor();
        let yf = y - y.floor();

        let u = self.fade(xf);
        let v = self.fade(yf);

        let xi_usize = xi as usize;
        let yi_usize = yi as usize;

        let aa = self.perm[self.perm[xi_usize] + yi_usize];
        let ab = self.perm[self.perm[xi_usize] + yi_usize + 1];
        let ba = self.perm[self.perm[xi_usize + 1] + yi_usize];
        let bb = self.perm[self.perm[xi_usize + 1] + yi_usize + 1];

        let n00 = self.grad_dot(aa, xf, yf);
        let n01 = self.grad_dot(ab, xf, yf - 1.0);
        let n10 = self.grad_dot(ba, xf - 1.0, yf);
        let n11 = self.grad_dot(bb, xf - 1.0, yf - 1.0);

        let nx0 = n00 + u * (n10 - n00);
        let nx1 = n01 + u * (n11 - n01);

        nx0 + v * (nx1 - nx0)
    }

    /// 分形布朗运动 (FBM)
    pub fn fbm(&self, x: f64, y: f64, octaves: usize, lacunarity: f64, persistence: f64) -> f64 {
        let mut value = 0.0;
        let mut amplitude = 1.0;
        let mut frequency = 1.0;
        let mut max_value = 0.0;

        for _ in 0..octaves {
            value += amplitude * self.noise_2d(x * frequency, y * frequency);
            max_value += amplitude;
            amplitude *= persistence;
            frequency *= lacunarity;
        }

        value / max_value
    }
}

/// Worley 噪声 (细胞噪声) 生成器
pub struct WorleyNoise {
    _seed: u64,
}

impl WorleyNoise {
    pub fn new(seed: u64) -> Self {
        Self { _seed: seed }
    }

    /// 使用哈希函数生成确定性的特征点位置
    #[inline]
    fn get_feature_point(&self, cell_x: i64, cell_y: i64) -> (f64, f64) {
        let h = ((cell_x.wrapping_mul(374761393) + cell_y.wrapping_mul(668265263)) as u64) & 0xFFFFFFFF;
        let h = ((h ^ (h >> 13)).wrapping_mul(1274126177)) & 0xFFFFFFFF;
        let px = (h & 0xFFFF) as f64 / 65536.0;
        let py = ((h >> 16) & 0xFFFF) as f64 / 65536.0;
        (cell_x as f64 + px, cell_y as f64 + py)
    }

    /// 计算到最近特征点的距离
    pub fn distance(&self, x: f64, y: f64) -> f64 {
        let cell_x = x.floor() as i64;
        let cell_y = y.floor() as i64;
        
        let mut min_dist = f64::MAX;

        // 搜索周围 3x3 的单元格
        for di in -1..=1 {
            for dj in -1..=1 {
                let ni = cell_x + di;
                let nj = cell_y + dj;
                let (px, py) = self.get_feature_point(ni, nj);
                let dist = ((x - px).powi(2) + (y - py).powi(2)).sqrt();
                min_dist = min_dist.min(dist);
            }
        }

        min_dist
    }

    /// 计算 Worley 边缘 (F2 - F1)
    pub fn edge(&self, x: f64, y: f64) -> f64 {
        let cell_x = x.floor() as i64;
        let cell_y = y.floor() as i64;
        
        let mut min_dist = f64::MAX;
        let mut second_dist = f64::MAX;

        // 搜索周围 3x3 的单元格
        for di in -1..=1 {
            for dj in -1..=1 {
                let ni = cell_x + di;
                let nj = cell_y + dj;
                let (px, py) = self.get_feature_point(ni, nj);
                let dist = ((x - px).powi(2) + (y - py).powi(2)).sqrt();
                
                if dist < min_dist {
                    second_dist = min_dist;
                    min_dist = dist;
                } else if dist < second_dist {
                    second_dist = dist;
                }
            }
        }

        second_dist - min_dist
    }
}

/// Ridge 噪声生成器
pub struct RidgeNoise {
    perlin: PerlinNoise,
}

impl RidgeNoise {
    pub fn new(seed: u64) -> Self {
        Self {
            perlin: PerlinNoise::new(seed),
        }
    }

    /// 生成 Ridge 噪声
    pub fn noise(&self, x: f64, y: f64, octaves: usize, lacunarity: f64, persistence: f64) -> f64 {
        let mut value = 0.0;
        let mut amplitude = 1.0;
        let mut frequency = 1.0;
        let mut max_value = 0.0;
        let mut weight = 1.0;

        for _ in 0..octaves {
            // 取绝对值并反转
            let mut noise = 1.0 - self.perlin.noise_2d(x * frequency, y * frequency).abs();
            // 平方使山脊更锐利
            noise = noise * noise;
            // 权重衰减
            noise *= weight;
            weight = (noise * 2.0).clamp(0.0, 1.0);

            value += amplitude * noise;
            max_value += amplitude;
            amplitude *= persistence;
            frequency *= lacunarity;
        }

        value / max_value
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_perlin_noise() {
        let perlin = PerlinNoise::new(42);
        let value = perlin.noise_2d(0.5, 0.5);
        assert!(value >= -1.0 && value <= 1.0);
    }

    #[test]
    fn test_worley_noise() {
        let worley = WorleyNoise::new(42);
        let dist = worley.distance(0.5, 0.5);
        assert!(dist >= 0.0);
    }

    #[test]
    fn test_ridge_noise() {
        let ridge = RidgeNoise::new(42);
        let value = ridge.noise(0.5, 0.5, 4, 2.0, 0.5);
        assert!(value >= 0.0 && value <= 1.0);
    }

    #[test]
    fn test_deterministic() {
        let perlin1 = PerlinNoise::new(42);
        let perlin2 = PerlinNoise::new(42);
        
        let v1 = perlin1.noise_2d(1.234, 5.678);
        let v2 = perlin2.noise_2d(1.234, 5.678);
        
        assert!((v1 - v2).abs() < 1e-10);
    }
}
