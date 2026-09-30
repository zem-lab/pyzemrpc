# 远程软件版本（1.2.6.dev2026093001）

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

验证：.venv/Scripts/python.exe -m pytest tests --ignore=tests/test_zem_api.py -q；跨语言端到端验证使用 tests/check_scan_relay_hisi.py <ScanRelayMaskTest.exe>，仅连接该脚本启动的本地假硬件服务。
