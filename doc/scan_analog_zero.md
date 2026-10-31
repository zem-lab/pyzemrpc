# 正常扫描模拟调零

需要 ZemController 1.5.40 或包含同一接口的版本。使用现有协议协商获得 JSON-RPC URL，不增加 UDP 命令。

`device.get_scan_analog_zero()` 读取现有 `Status.scan_analog_zero`。字段包括 `schema=normal-scan-analog-zero-v1`、当前 `sin/cos`、`sin_range/cos_range`、独立已保存值 `saved`（旧配置可为 null）、`beam_raw`、扫描继电器、扫描幅度 DAC 和数字偏置。该状态是仪器模型缓存，不是 DAC 硬件回读。

`device.set_scan_analog_zero(sin, cos)` 发送 `SemSetScanAnalogZero`，只改变主扫描 CHC/CHD 活值。
`device.save_scan_analog_zero(expected_sin, expected_cos)` 发送 `SemSaveScanAnalogZero`，要求当前活值与验证值一致，再调用仪器原有持久化流程。
两者要求正常模式、束偏转归零、空闲或视频播放，完整校验两个通道范围后才能执行。

设置和保存分离。先记录原状态，临时扰动采图，求解后独立复拍验证，最后保存；异常应恢复原活值。SDK 校验请求编号、错误响应及返回值，超时不自动重发。`device.json_rpc(method, params, timeout=20)` 可调用已协商的其他 JSON-RPC；拍图应为传输和扫描预留更长超时。
