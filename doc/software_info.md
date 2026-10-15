# 远程软件版本与电镜 SN

## 发布前必须提交

所有后续打包遵守根目录 [AGENTS.md](../AGENTS.md)：完成本次修改（包括版本号）并提交，记录完整 commit，再从干净提交重新生成 Git 元数据、构建和打包；验证实际包内提交、发布清单与构建提交一致。提交后再改源码，就必须重新提交和重建，不能仅修改清单。Shell 和 pyzemrpc 分别执行此流程，分别记录各自提交，不能互相代替。

## 软件版本

Shell 1.5.6 起提供 UDP GetSoftwareInfo，并在 JSON-RPC Status / SemControlState 中增加 software：

    {"version": "1.5.6", "commit_id": "完整 Git 提交号"}

示例（已有 device 连接）：

    info = device.get_software_info()
    if info is not None:
        print(info.version, info.commit_id)
    assert device.status_rpc().software == info

高层接口 zem_api.get_software_info() 只发版本查询，无需先同步光学状态或协商 HTTP。底层 ProtocolBuilder.build_get_software_info() / RespPacket.parse_software_info() 同步支持。

device.m.software 保存最近一次返回值，切换远程地址、断开或遇到旧服务端时清空。旧服务端没有 software 字段或明确返回 Invalid command 时得到 None；无编译提交信息时 commit_id 为空字符串。超时、服务端错误及损坏的数据不伪装成旧版本或成功。

version/commit_id 表示远程服务端构建，绝不是本机 SDK 版本。VirtualZem 测试服务返回其自身的 pyzemrpc 版本与构建提交。

## 电镜 SN

Shell 1.5.12 起提供 UDP GetSN（`$GetSN:<sn>,<crc>%`），JSON-RPC Status / SemControlState 同时返回 `sn`。SN 取自电镜机型配置，Shell 用它核对鱼眼与束偏转标定的归属，详见 Shell 仓库 `doc/zem_hisi/instrument_sn_calibration.md`。

    sn = device.get_sn()            # 或 zem_api.get_sn()
    assert device.status_rpc().sn == sn

ProtocolBuilder.build_get_sn() / RespPacket.parse_sn() 为底层接口。device.m.sn 保存最近一次返回值，与 software 一样在切换远程地址、断开时清空；旧服务端返回 Invalid command 或 Status 无 `sn` 字段时为 None，配置为空时为空字符串。VirtualZem 返回固定的 `VIRTUALZEM`。

## 验证

.venv/Scripts/python.exe -m pytest tests --ignore=tests/test_zem_api.py -q；跨语言端到端验证使用 tests/check_scan_relay_hisi.py <ScanRelayMaskTest.exe>，仅连接该脚本启动的本地假硬件服务。
