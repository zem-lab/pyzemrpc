# pyzemrpc_show_img_meta

显示ZEM图像的元信息。

## 功能描述

`pyzemrpc_show_img_meta`是一个命令行工具，用于读取和显示ZEPTOOLS扫描电子显微镜(SEM)图像文件的元信息。支持PNG和TIFF格式，可以将元信息以易读的格式或JSON格式输出。

## 使用方法

### 基本用法 (显示格式化输出)

```bash
pyzemrpc_show_img_meta -i path/to/image.png
```

### 使用完整参数名

```bash
pyzemrpc_show_img_meta --img path/to/image.tif
```

### 输出JSON格式

```bash
pyzemrpc_show_img_meta -i path/to/image.png --json
```

## 命令行参数

| 参数 | 短参数 | 类型 | 必需 | 描述 |
|------|--------|------|------|------|
| `--img` | `-i` | str | 是 | 图像文件路径 (PNG/TIF) |
| `--json` | `-j` | flag | 否 | 以JSON格式输出元信息 |

## 元信息字段

运行后会显示以下元信息字段：

| 字段 | 描述 |
|------|------|
| `model` | SEM型号 |
| `firmware_version` | 固件版本 |
| `version` | 软件版本 |
| `date` | 图像采集日期 |
| `acc_voltage` | 加速电压 |
| `avg_length` | 平均长度 |
| `detector` | 探测器类型 |
| `field_size` | 视野大小 (单位: um) |
| `objective_lens` | 物镜设置 |
| `position` | 工作台位置 |
| `pressure` | 真空室压力 |
| `zoom` | 放大倍数 |
| `pixel_length` | 像素长度 (单位: um) |
| `significant_bit` | 有效位数 |
| `significant_high` | 有效位高位 |
| `significant_low` | 有效位低位 |
| `title` | 图像标题 |
| `note` | 备注信息 |
| `metainfo_valid` | 元信息有效性标志 |

## 示例

### 格式化输出

```bash
$ pyzemrpc_show_img_meta -i sample.png

============================================================
完整的元信息:
============================================================
模型 (model): ZEPTOOLS-SEM
固件版本 (firmware_version): 1.2.3
...
============================================================
```

### JSON输出

```bash
$ pyzemrpc_show_img_meta -i sample.png --json
{
  "model": "ZEPTOOLS-SEM",
  "firmware_version": "1.2.3",
  ...
}
```

### 错误处理

如果文件不存在:

```bash
$ pyzemrpc_show_img_meta -i nonexistent.png
usage: pyzemrpc_show_zimg_meta [-h] -i IMG [--json]
pyzemrpc_show_zimg_meta: error: File not found: nonexistent.png
```

如果元信息无效:

```bash
$ pyzemrpc_show_img_meta -i invalid_image.png
Warning: Metadata in file 'invalid_image.png' is not valid.
```

## 注意事项

- 只支持包含ZEM元信息的PNG或TIFF文件
- 元信息需要嵌入在图像文件的元数据块中
- 如果元信息无效，工具会显示警告但不报错
