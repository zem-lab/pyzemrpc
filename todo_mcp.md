# 只读协议清单（protocol.py）

只读协议：仅查询/读取状态或获取数据，不改变电镜配置。用于标记 MCP 包装及测试完成情况。

## 连接与状态

- [x] StatusCheck - 获取服务端状态
- [x] ServerName - 获取服务主机名称

## 图像与视频

- [ ] GetImg - 请求发送当前内存中的图片
- [ ] GetNavImg - 获取导航图片
- [ ] VideoPlay - 播放视频
- [ ] IsVideoAlive - 获取视频状态
- [ ] Snap - 拍摄一张图片

## 电镜参数（光学/扫描）

- [x] GetWD - 获取工作距离
- [x] GetCofPS - 获取像素脉冲系数
- [x] GetEDChanel - 获取电子信号通道
- [x] GetRotation - 获取扫描场旋转
- [x] GetOB - 获取物镜值
- [x] GetAST - 获取像散
- [x] GetStigX - 获取像散X
- [x] GetStigY - 获取像散Y
- [x] GetImgSz - 获取图片尺寸
- [x] GetWindowPos - 获取小窗位置
- [x] GetMag - 获取放大倍数
- [x] GetBeamSz - 获取束斑大小
- [x] GetScanInfo - 获取扫描场信息
- [x] GetPixelSz - 获取像素尺寸(um)

## 高压与真空

- [ ] GetHV - 获取加速电压
- [ ] GetHvStatus - 获取高压状态
- [ ] GetSetHV - 获取设置高压
- [ ] GetVAC - 获取真空度
- [ ] GetGunVac - 获取枪头真空
- [ ] GetSamVac - 获取样品仓真空

## 探测器（SE/BSE）

- [ ] GetSECV - 获取SE收集电压
- [ ] GetSEGain - 获取SE增益
- [ ] GetBseCfg - 获取BSE探测器设置

## 样品台与视场

- [ ] GetStagePos - 获取视场坐标
- [ ] GetStgStatus - 获取样品台状态
- [ ] GetStageXStatus - 获取X坐标
- [ ] GetStageYStatus - 获取Y坐标
- [ ] GetStageZStatus - 获取Z坐标
- [ ] GetStageRStatus - 获取R坐标
- [ ] GetStageTStatus - 获取T坐标
- [ ] GetNavPara - 获取光导系数

## 对焦与其它状态

- [ ] CheckAutoFocus - 自动对焦是否结束
- [ ] IsOpenGun - 是否打开枪头
- [ ] IsChangingSamp - 是否正在换样
- [ ] GetModel - 获取型号
- [ ] GetCompressA - 获取压缩A值
- [ ] GetCompressB - 获取压缩B值

---

# MCP 包装开发计划

已完成 16/44 个只读协议的 MCP 包装（连接与状态 2 个 + 电镜参数 14 个）。
剩余 28 个按以下阶段推进，每阶段包含：server.py 新增工具、虚拟电镜适配、单元测试。

## Phase 3: 高压与真空（6 个）

简单数值查询，和 Phase 2 模式一致，可直接用 `_parse_1()` 或专用 parse 方法。

| 协议 | MCP 工具名 | 返回值 |
|------|-----------|--------|
| GetHV | get_hv | 加速电压 (kV) |
| GetHvStatus | get_hv_status | 高压状态字符串 |
| GetSetHV | get_set_hv | 设置高压值 |
| GetVAC | get_vac | 真空度 |
| GetGunVac | get_gun_vac | 枪头真空 |
| GetSamVac | get_sam_vac | 样品仓真空 |

工作项：
1. `server.py` 新增 6 个 `@mcp.tool()`
2. 确认 `virtual_zem.py` 已支持对应命令响应
3. `test_mini_mcp.py` 新增 `TestPhase3HvAndVacuum` 测试类

## Phase 4: 探测器（3 个）

| 协议 | MCP 工具名 | 返回值 |
|------|-----------|--------|
| GetSECV | get_se_cv | SE 收集电压 |
| GetSEGain | get_se_gain | SE 增益值 |
| GetBseCfg | get_bse_cfg | BSE 探测器配置（可能为多字段） |

工作项：
1. `server.py` 新增 3 个工具
2. `GetBseCfg` 返回结构化数据，需确认 parse 方法和返回格式
3. `test_mini_mcp.py` 新增 `TestPhase4Detector` 测试类

## Phase 5: 样品台与视场（8 个）

| 协议 | MCP 工具名 | 返回值 |
|------|-----------|--------|
| GetStagePos | get_stage_pos | x,y,z,r,t 五轴坐标 |
| GetStgStatus | get_stg_status | 样品台状态 |
| GetStageXStatus | get_stage_x | X 坐标值 |
| GetStageYStatus | get_stage_y | Y 坐标值 |
| GetStageZStatus | get_stage_z | Z 坐标值 |
| GetStageRStatus | get_stage_r | R 坐标值 |
| GetStageTStatus | get_stage_t | T 坐标值 |
| GetNavPara | get_nav_para | 光导系数 |

工作项：
1. `server.py` 新增 8 个工具
2. `GetStagePos` 返回结构化坐标，需设计返回格式（如 `x=1.0,y=2.0,...`）
3. 单轴状态可能包含移动中/就绪等信息，需确认
4. `test_mini_mcp.py` 新增 `TestPhase5Stage` 测试类

## Phase 6: 对焦与其它状态（6 个）

| 协议 | MCP 工具名 | 返回值 |
|------|-----------|--------|
| CheckAutoFocus | check_auto_focus | 是否完成 (bool) |
| IsOpenGun | is_open_gun | 枪头是否打开 (bool) |
| IsChangingSamp | is_changing_samp | 是否换样中 (bool) |
| GetModel | get_model | 型号字符串 |
| GetCompressA | get_compress_a | 压缩 A 值 |
| GetCompressB | get_compress_b | 压缩 B 值 |

工作项：
1. `server.py` 新增 6 个工具
2. 布尔型返回值统一用 `"true"` / `"false"` 字符串
3. `test_mini_mcp.py` 新增 `TestPhase6Misc` 测试类

## Phase 7: 图像与视频（5 个）

此阶段最复杂，涉及二进制图像数据传输，放在最后。

| 协议 | MCP 工具名 | 说明 |
|------|-----------|------|
| GetImg | get_img | 返回当前内存图片（需处理二进制→base64） |
| GetNavImg | get_nav_img | 返回导航图片 |
| VideoPlay | video_play | 触发视频播放 |
| IsVideoAlive | is_video_alive | 视频是否在播 |
| Snap | snap | 拍摄一张图片 |

工作项：
1. 确定 MCP 协议下图像传输方案（base64 编码 / 文件路径 / URL）
2. `VideoPlay` 和 `Snap` 虽在只读清单但会触发动作，需确认是否纳入
3. `server.py` 新增工具，图像类需特殊返回格式
4. `test_mini_mcp.py` 新增 `TestPhase7Image` 测试类
