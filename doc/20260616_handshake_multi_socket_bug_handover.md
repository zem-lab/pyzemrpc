# 多网卡 Handshake / 后续通信 Bug — Agent 交接文档

**日期**: 2026-06-17  
**仓库**: `D:\WYM\pyzemrpc`  
**当前版本**: `1.2.6`（`zemrpc/__version__.py`）  
**关联文档**: [20260616_handshake_multi_socket.md](./20260616_handshake_multi_socket.md)（仅覆盖 handshake 广播，不含后续通信完整结论）  
**状态**: **未完全解决** — handshake 已可用，后续 `GetModel` / `StatusCheck` 在部分场景仍超时；Wireshark 证明设备有回包，应用层未稳定收到。

---

## 1. 问题一句话

双网卡 Windows 主机上，pyzemrpc 能 handshake 发现设备，但选择设备后发命令（如 `GetModel`、`StatusCheck`）经常 `TimeoutError`；抓包显示 **设备已从随机源端口回包到本机临时端口**，应用日志却 **没有** `received udp data`。

---

## 2. 环境（已复现）

| 项目 | 值 |
|------|-----|
| OS | Windows 11 |
| Python | 3.12 |
| 有线网卡 | `192.168.1.34` / `255.255.255.0` |
| WiFi 网卡 | `192.168.110.82` / `255.255.252.0`（即 `192.168.108.0/22`） |
| 典型目标设备 | `192.168.109.9:61557`（WiFi 子网内） |
| 消费方 | `pyzemcalib` 通过 `D:\Apps\PythonVenv\py312_pyzemcalib` 安装 site-packages 中的 `zemrpc` |
| 开发 venv | `D:\WYM\pyzemrpc\.venv` |

**依赖注意**：原版 `netifaces` 在 Python 3.12 + Windows 无 wheel，需编译失败。已改用 `netifaces-plus`（`requirements.txt` 已加入），import 名仍为 `netifaces`。

---

## 3. 协议与流量形态（读 Wireshark 前必知）

### 3.1 命令格式

每条 UDP 请求形如：

```text
$GetModel:,192.168.110.82:62520,AAAF%
  ^命令    ^本机回调 IP:port      ^CRC%
```

设备按报文内嵌的 **本机 IP:port** 回包，而不是回发到客户端发包用的临时源端口以外的逻辑。

### 3.2 正常 UDP 行为（不是 Bug）

用户 Wireshark 截图（过滤器 `udp.port == 62520`）显示：

| 方向 | 五元组 | 说明 |
|------|--------|------|
| 请求 | `192.168.110.82:62520` → `192.168.109.9:61557` | 本机临时端口 → 设备服务端口 |
| 响应 | `192.168.109.9:54484` → `192.168.110.82:62520` | **设备每次用新的临时源端口**（54481、54482…）回包 |

响应 payload 示例：`$GetModel:Zem20,F5FA%` — 说明 **设备已处理命令**。

**结论**：不要指望回包从 `61557` 发出；也 **不能** 对持久 socket 做 `connect(设备 IP, 61557)`，否则 Windows 可能丢弃来自 `544xx` 端口的回包（抓包仍可见，socket 收不到）。

---

## 4. 架构速览

```text
ZemRpcDevice
├── handshake()          # 每网卡临时 socket 广播 + 合并结果
├── _iface_by_device     # (device_ip, port) -> 收到 handshake 响应的 local_ip
├── 持久 socket          # jgb.conn.udp_socket.UdpSocket（lazy init）
│   ├── rcv_worker       # 后台线程 recvfrom -> m.data_received()
│   └── ReadWriteService # pubsub + SingleConsumer 解析
└── _do_write()          # 发送前 patch 报文内回调地址
```

**jgb 已知坑**（`jgb/conn/udp_socket.py`，未在本仓库修改）：

1. `sock` 属性首次访问会 `init_socket()`，按 `self.m.ip` 绑定；若 `m.ip` 不对，会先绑到错误网卡。
2. `SingleWorker.start()`：若 `self.thread is not None`（即使线程已死）则 **不会** 重启 recv 线程。
3. `ReadWriteService.pubsub_send` 通过 **线程池异步** 调用 `_do_write`，与 `wait()` 并发；一般可接受，但调试时序需注意。

---

## 5. 版本与提交脉络

| 版本 | 内容 | 效果 |
|------|------|------|
| `1.2.3` | `f1f1417` 多网卡 handshake 临时 socket 广播 | handshake 从 0 台 → 20+ 台 |
| `1.2.4` | `update_remote_addr` 按子网 rebind；`ip_util` 子网匹配 | 部分场景仍超时 |
| `1.2.5` | handshake 记录 `_iface_by_device`；`patch_request_callback`；`send_cmd` 走 `pubsub_send` | 逻辑更完整，实测仍不稳定 |
| `1.2.6` | 去掉 `get_route_local_ip`；lazy bind 避免错误 rebind；修复 rcv worker 重启；`GetModel`/`StatusCheck` 超时 100ms→2000ms | **当前 HEAD，问题未彻底关闭** |

---

## 6. 已做修改（文件级）

### `zemrpc/zem/zem_rpc_device.py`

- `handshake()`：每网卡广播；`resp.extra["local_ip"]`；写入 `_iface_by_device`
- `_resolve_local_ip_for_device()`：优先 handshake 网卡 → `get_real_local_ip(target_ip)`（**已移除** `get_route_local_ip`，因其在双网卡下常选中有线 `192.168.1.34`）
- `_ensure_socket_bind()`：**在首次访问 `sock` 前** 设置 `m.ip`；rebind 时强制 `rcv_worker.thread = None` 并 `_ensure_udp_rcv_worker()`
- `_prepare_comm()` / `update_remote_addr()`：选设备后绑定正确网卡
- `_do_write()`：非 handshake 时 `patch_request_callback` 刷新报文内 IP:port
- `send_cmd()`：改为 `pubsub_send(req)`（带 tenacity 重试）

### `zemrpc/zem/ip_util.py`

- `_get_interface_subnets()` / `_find_local_ip_for_target()`：基于 netmask 或 `/32`→`/24`→`/22`→`/16` 回退
- `get_route_local_ip()`：仍存在，但 **不应** 再用于选网卡（已证误选有线）

### `zemrpc/zem/conn/protocol.py`

- `patch_request_callback()`：发送前替换报文内回调地址并重算 CRC
- `GetModel` / `StatusCheck` 超时改为 `2000` ms

### `requirements.txt`

- 增加 `netifaces-plus>=0.12.5`

### 诊断脚本（`tests/demo/`，非 pytest 默认路径）

- `wireshark_udp_test.py` — handshake + 指定设备 + sync + GetModel/StatusCheck
- `raw_recv_test.py` — 对比临时 socket vs 持久 socket 的裸 `recvfrom`

---

## 7. 典型失败日志

### 7.1 网卡/embed 地址错误（早期）

```text
send to ('192.168.111.207', 61557): $GetModel:,192.168.1.34:62102,...
```

目标在 WiFi `/22`，命令却嵌入有线 `192.168.1.34`。

### 7.2 embed 正确仍超时（后期）

```text
Use handshake interface 192.168.110.82 for device 192.168.109.9:61557
UDP socket opened on 192.168.110.82:62520
send to ('192.168.109.9', 61557): $GetModel:,192.168.110.82:62520,...
# 无 "received udp data" 行
TimeoutError: GetModel命令超时
```

Wireshark 同期可见 `109.9:544xx -> 110.82:62520` 回包。

### 7.3 `get_route_local_ip` 误选（已回退，交接时勿恢复）

```text
[persist] send ('192.168.1.34', 57712) -> ('192.168.109.9', 61557): ...
```

---

## 8. 已尝试但无效或有害的方案

| 方案 | 结果 |
|------|------|
| 仅 handshake 多 socket | 发现设备 OK，后续通信仍失败 |
| `get_real_local_ip(target)` 仅 `/24` 匹配 | `/22` WiFi 子网匹配错误 |
| `get_route_local_ip()`（UDP connect 探测） | 常选默认路由网卡 `192.168.1.34`，**有害** |
| rebind 时不重置 `rcv_worker.thread` | 可能无 recv 线程，Wireshark 有包应用无日志 |
| 首次访问 `sock` 触发 lazy init 再 rebind | 同上，应先设 `m.ip` 再 init |
| `sock.connect(设备 61557)` | Windows 丢弃非 61557 源端口回包，**有害** |
| 仅把超时从 100ms 调到 2000ms | 单独不足以解决「完全收不到」 |

---

## 9. 当前未解问题（下一位 Agent 的重点）

1. **应用层收包不稳定**  
   - 现象：Wireshark 有回包，`zem_rpc_device._do_framing` 的 `received udp data` 不出现。  
   - 怀疑方向：jgb `UdpSocket` recv 线程生命周期、DDS `data_received` 订阅、rebind 与 `ReadWriteService` 生命周期、Windows 双网卡 + 防火墙。

2. **自动化测试与手动 GUI 行为不一致**  
   - `tests/demo/raw_recv_test.py` 在部分时段对 `192.168.109.9` 发 `GetModel` 也 3s 超时（含 handshake 风格临时 socket）。  
   - 用户 GUI + Wireshark 曾抓到成功回包。需确认：设备状态、是否需先 sync、是否仅特定设备响应 GetModel。

3. **持久 socket 与 handshake 临时 socket 路径不一致**  
   - handshake 在主线程 `recvfrom` 临时 socket 上 **能** 收到 `HandshakeResp`。  
   - 持久 socket 依赖 jgb 后台线程 + DDS + SingleConsumer，链路更长。

4. **未在 jgb 上游修 bug**  
   - 理想修复：`UdpSocket.rebind()` 内保证 worker 重启；或 `stop()` 始终 `thread=None`。当前仅在 `zem_rpc_device` 打补丁。

5. **pyzemcalib 侧**  
   - `zemcalib/instrument/conn/zemrpc.py` 调用 `update_remote_addr`；需确认安装的是哪个 wheel 版本。

---

## 10. 推荐排查顺序（给下一位 Agent）

### Step 0：安装与环境

```powershell
cd D:\WYM\pyzemrpc
.\.venv\Scripts\pip.exe install -e .
.\.venv\Scripts\pip.exe install netifaces-plus   # 若未装

# 消费方环境
D:\Apps\PythonVenv\py312_pyzemcalib\Scripts\pip.exe install D:\WYM\pyzemrpc\dist\pyzemrpc-1.2.6-py3-none-any.whl --force-reinstall
```

### Step 1：Wireshark 与用户同步抓包

```text
udp && (ip.addr == 192.168.109.9 || ip.addr == 192.168.110.82)
```

确认：

- [ ] 请求源 IP 是 `192.168.110.82`（不是 `192.168.1.34`）
- [ ] 响应目的端口 == 请求里 embed 的客户端端口
- [ ] 响应源端口为设备临时端口（非 61557）

### Step 2：跑诊断脚本（DEBUG 日志）

```powershell
cd D:\WYM\pyzemrpc
.\.venv\Scripts\python.exe tests\demo\wireshark_udp_test.py 192.168.109.9:61557
.\.venv\Scripts\python.exe tests\demo\raw_recv_test.py
```

关注日志关键字：

- `Use handshake interface`
- `UDP socket opened on` / `Rebind UDP socket`
- `UDP recv worker running=`
- `received udp data`（**关键**：有 send 无 receive 即应用层问题）
- `got response without subscriber`（jgb WARNING，表示晚到回包）

### Step 3：若仍无 `received udp`

优先验证 **jgb recv 线程是否真的在跑**：

- 在 `_ensure_socket_bind` 后断言 `socket.rcv_worker.is_running() is True`
- 临时在 `jgb.conn.udp_socket._do_rcv` 打日志（或子类化 `UdpSocket` 注入日志）
- 用 **同进程主线程** `recvfrom`（停掉 worker）对比 Wireshark — `raw_recv_test.py` 已部分覆盖

### Step 4：若已有 `received udp` 仍超时

查 pubsub 匹配：`Request/RespPacket.get_pubsub_key()` 均为 `cmd.name`（如 `"GetModel"`）。  
查 `ProtocolParser.append` 是否因 `addr`（设备随机源端口）分片缓冲异常（当前每包独立 `addr` 键，一般无妨）。

---

## 11. 建议的根治方向（未实现）

1. **在 pyzemrpc 内实现 `ZemUdpSocket(UdpSocket)`**  
   封装 `rebind(local_ip, peer=None)`，保证 socket + worker 原子切换；避免依赖 `zem_rpc_device` 里散落的 stop/thread=None 逻辑。

2. **后续通信与 handshake 统一模型**  
   考虑：选设备后，持久 socket 直接 bind 到 `_iface_by_device[addr]`，且 **永不** connect 到 61557。

3. **修 jgb 或 fork**  
   `SingleWorker.stop()` 应始终 `self.thread = None`；`init_socket()` 在 `_socket` 已存在但 worker 死掉时应能恢复。

4. **可选：握手后探测**  
   对选定设备发一次 `GetModel`，若超时则尝试 **另一张网卡** 的 local_ip（`_iface_by_device` 可扩展为多候选列表，而非 dedup 时只保留第一个）。

5. **单元测试**  
   - `tests/test_ip_util.py`  
   - `tests/test_request_callback.py`  
   缺集成测试：mock UDP 或 loopback 虚拟设备验证 recv 链路。

---

## 12. 构建与打包

```powershell
cd D:\WYM\pyzemrpc
$env:PATH = ".\.venv\Scripts;" + $env:PATH
inv ui2py          # 需 PATH 含 .venv\Scripts（pyside6-uic）
.\.venv\Scripts\python.exe setup.py bdist_wheel
# 产物: dist\pyzemrpc-1.2.6-py3-none-any.whl
```

---

## 13. 相关 Git 信息

- handshake 多网卡：`f1f1417` — `feat(handshake): broadcast on all network interfaces for device discovery`
- 后续通信修补：**未单独 commit**（截至交接时仍在工作区 / 本地 1.2.6）

---

## 14. 交接结论

| 项目 | 状态 |
|------|------|
| 多网卡 handshake 发现 | ✅ 已解决 |
| 选设备后 bind 正确网卡 | ⚠️ 逻辑已有，需实测确认 |
| 报文内回调地址正确 | ⚠️ `patch_request_callback` 已加 |
| 应用收到设备回包 | ❌ 不稳定 / 常失败 |
| 用户侧 GetModel/StatusCheck | ❌ 曾报告仍超时；Wireshark 显示设备有回 |

**下一位 Agent 请从「Wireshark 有回包但无 `received udp`」切入，优先查 jgb recv 线程与 rebind 生命周期，不要先再加子网启发式。**

---

## 15. 联系人 / 上下文

- 用户环境：双网卡 Windows，ZEM 设备多在 WiFi `192.168.108.0/22` 段
- 用户已安装 Wireshark，可配合 `tests/demo/wireshark_udp_test.py` 复现
- pyzemcalib 路径：`D:\WYM\pyzemcalib`，通过 `zem_api.update_remote_addr` 连接设备

---

*文档由 Agent 根据 2026-06-16 ~ 2026-06-17 会话整理，供后续 Agent 接手。*
