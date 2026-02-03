# mandelbrot_zem_rs 构建脚本 (Windows PowerShell)
# 使用方法: .\build.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== mandelbrot_zem_rs 构建脚本 ===" -ForegroundColor Cyan

# 检查 Rust 是否安装
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未检测到 Rust 工具链" -ForegroundColor Red
    Write-Host "请先安装 Rust: https://rustup.rs/" -ForegroundColor Yellow
    exit 1
}

# 检查 maturin 是否安装
if (-not (Get-Command maturin -ErrorAction SilentlyContinue)) {
    Write-Host "正在安装 maturin..." -ForegroundColor Yellow
    pip install maturin
}

# 获取脚本所在目录
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "当前目录: $ScriptDir" -ForegroundColor Gray

# 编译并安装到当前 Python 环境
Write-Host "正在编译 Rust 扩展..." -ForegroundColor Yellow
maturin develop --release

if ($LASTEXITCODE -eq 0) {
    Write-Host "=== 编译成功! ===" -ForegroundColor Green
    Write-Host "mandelbrot_zem_rs 已安装到当前 Python 环境" -ForegroundColor Green
    
    # 验证安装
    Write-Host ""
    Write-Host "验证安装..." -ForegroundColor Yellow
    python -c "from mandelbrot_zem_rs import MandelbrotGenerator; print('导入成功!')"
} else {
    Write-Host "=== 编译失败 ===" -ForegroundColor Red
    exit 1
}
