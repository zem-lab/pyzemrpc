# 样品台运动参数联调

本项目只发布 wheel。安装 wheel 后运行 `pyzemrpc` 使用 GUI 调试页；不提供独立 exe。

GUI 新增“样品台运动参数”tab，所有本页操作使用 HTTP JSON-RPC。可用当前设备连接发现的地址，也可直接填写完整 URL。打开页、载入正常/高速预设、编辑值均不发送命令；仅“读取设备参数”和“应用所选轴并核验”发请求。GUI 写入遵守已有 ADVANCED 工作模式。

正常参数为 P/I/D=2/0.1/0.1、最小/最大速度 320/9600；高速参数为 40/0.1/0.1、500/20000。速度单位为**脉冲/秒**。每轴独立读取和配置，读回与草稿分开，程序不自动重发失败命令。

JSON-RPC：`SemStageMotionParameters`，params `[]`；`SemConfigureStageMotion`，params `[{"axes":[{"axis":"X","p":2,"i":0.1,"d":0.1,"min_speed_pps":320,"max_speed_pps":9600}]}]`。

返回 `api_version=1`、`speed_unit=pulse/s`、`source=hardware_readback`、`observed_at`、`axes`；写入须返回 `applied=true` 且每项一致。设备必须停台且没有采集/自动调整。超时不能解释为未写入，先读取核对。

Python：`zem_api.get_stage_motion_parameters()` / `set_stage_motion_parameters(axes)` 默认 JSON-RPC；显式 `transport="udp"` 使用 `GetStageMotionParameters` / `SetStageMotionParameters`，请求与响应载荷均为 UTF-8 JSON 的 Base64。UDP 写入也不重试。`url=` 可显式指定 JSON-RPC 端点。

命令行只读：`.venv/Scripts/python.exe -m zemrpc.tools.stage_motion_parameters --url <电镜JSON-RPC地址>`。
显式应用：在上一命令后加 `--apply normal --axes X Y` 或 `--apply high --axes X Y`。此模块是现场手动联调入口，未连接真机执行。
