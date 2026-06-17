# 多网卡 Handshake 广播支持

**日期**: 2026-06-16  
**版本**: pyzemrpc >= 1.2.3  
**作者**: tribf

## 问题背景

`ZemRpcDevice.handshake()` 通过 UDP broadcast 发现局域网中的 ZEM 设备。
原有实现将 UDP socket 绑定到单个本地 IP（通过 `ip_util.get_real_local_ip()` 获取），
然后发送广播包。

在 Windows 上，绑定到特定 IP 的 UDP socket 执行 broadcast 时，数据包**仅从该 IP
对应的网卡发出**。如果 ZEM 设备连接在另一张网卡所在的子网，广播包无法到达设备，
handshake 返回空列表。

### 典型场景

| 网卡 | IP | 子网 | 用途 |
|------|-----|------|------|
| 有线 Ethernet | 192.168.1.34 | 192.168.1.0/24 | ZEM 设备连接 |
| WiFi | 192.168.110.82 | 192.168.108.0/22 | 外网 / 其他设备 |

- `get_real_local_ip()` 可能返回任一 IP（取决于 `getaddrinfo()` 的顺序）
- 若返回 `192.168.1.34` → socket 绑定有线网卡 → broadcast 仅走有线 → 只能发现有线子网的设备
- 若返回 `192.168.110.82` → socket 绑定 WiFi → broadcast 仅走 WiFi → 只能发现 WiFi 子网的设备
- **无法同时发现两个子网上的设备**

## 解决方案

### 思路

对每个本地私有 IP 创建独立的临时 UDP socket，各自 bind 到对应 IP，各自发送 broadcast，
各自收集响应，最后合并去重。

### 不可行的方案

| 方案 | 结果 | 原因 |
|------|------|------|
| bind `0.0.0.0` (INADDR_ANY) | 0 设备 | `getsockname()` 返回 `0.0.0.0:port`，写入 handshake 请求后 ZEM 无法回包；且 Windows 无 `SO_BINDTODEVICE`，无法控制从哪张网卡发出 |
| 单 socket + 手动构造不同 IP 的请求 | 0 设备 | socket 已 bind 到固定 IP:port，手动填入的 IP 与实际源地址不匹配，ZEM 回包到错误地址 |

### 实现

修改 `ZemRpcDevice.handshake()` 方法 (`zemrpc/zem/zem_rpc_device.py`):

```python
def handshake(self):
    # 1. 收集所有本地私有 IP
    all_ips = ip_util._get_all_local_ips()
    local_ips = [ip for ip in all_ips
                 if ip_util._is_private_ip(ip)
                 and not ip_util._is_loopback_ip(ip)
                 and not ip_util._is_clash_fake_ip(ip)]

    if not local_ips:
        # Fallback: 使用原有的单 socket 方式
        resp = self.send(self.build_handshake_request())
        return [...]

    # 2. 在每个网卡上分别广播
    all_packets = []
    deadline = time.time() + (EnumCmd.Handshake.timeout / 1000)

    for ip in local_ips:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.settimeout(0.3)
        sock.bind((ip, 0))  # 绑定到该网卡的 IP

        local_ip, local_port = sock.getsockname()
        self.builder.ip, self.builder.port = local_ip, local_port
        req = self.builder.build_handshake_request()

        sock.sendto(req.data, ("<broadcast>", self.m.addr[1]))

        # 3. 收集该网卡的响应
        while time.time() < deadline:
            data, addr = sock.recvfrom(4096)
            for packet_data in self.parser.append(addr, data):
                resp = RespPacket(packet_data)
                resp.extra["addr"] = addr
                if resp.cmd == EnumCmd.HandshakeResp and not resp.is_error():
                    all_packets.append(resp)

        sock.close()

    # 4. 去重 (同一设备可能被多个网卡发现)
    seen = set()
    unique = []
    for pkt in all_packets:
        ipport = pkt.parse_ip_port()
        if ipport not in seen:
            seen.add(ipport)
            unique.append(pkt)

    return [packet.parse_ip_port() for packet in unique]
```

### 行为变化

| 项目 | 修改前 | 修改后 |
|------|--------|--------|
| Socket 数量 | 1 个 (持久) | N+1 个 (1 个持久用于后续通信 + N 个临时用于 handshake) |
| Broadcast 范围 | 单个网卡所在子网 | 所有网卡所在子网 |
| 发现的设备 | 仅部分子网 | 所有子网的合并结果 |
| 去重 | 无 | 按 (ip, port) 去重 |
| 向后兼容 | - | 完全兼容，返回格式不变 |

### 性能

- 每个临时 socket 生命周期 < 1 秒（handshake 总超时 1 秒）
- N 个网卡的 broadcast 并发发出（不等待前一个完成）
- 典型场景 2-3 个网卡，性能影响可忽略

## 验证

在双网卡 Windows 11 环境测试:

```
修改前: handshake 结果: []                           (0 设备, socket bind 到错误网卡)
修改后: Handshake found 21 device(s) on 2 interface(s) (21 设备, 两个网卡均广播)
```

## 后续通信（1.2.4 修复）

Handshake 修复后，持久 UDP socket 仍绑定在 `get_real_local_ip()` 返回的**第一个**私有 IP 上。
选择远程设备后若目标在另一子网，命令里嵌入的回调地址（`builder.ip:port`）与发包网卡不一致，
设备回包无法到达，表现为 `GetModel命令超时`。

### 修复

1. **`update_remote_addr`**：根据目标设备 IP 将持久 socket **重绑定**到同子网本地 IP。
2. **`get_real_local_ip(target_ip)`**：使用网卡真实 netmask 匹配子网；无 netifaces 时回退 `/32`→`/24`→`/22`→`/16`。

典型日志（修复前）：

```
send to ('192.168.111.207', 61557): $GetModel:,192.168.1.34:62102,...
```

目标在 `192.168.111.x`（/22），但命令嵌入 `192.168.1.34`（另一网卡），导致超时。

- `zemrpc/zem/zem_rpc_device.py` — `handshake()` 方法实现
- `zemrpc/zem/ip_util.py` — IP 获取与过滤工具
- `zemrpc/zem/conn/protocol.py` — 协议定义 (`EnumCmd.Handshake`, `RespPacket`)
- `jgb/conn/udp_socket.py` — UDP socket 封装 (持久 socket 仍用于后续通信)

---

## 后续通信仍超时的真正根因：Windows 防火墙丢弃「随机源端口」回包（2026-06-17）

> 背景：1.2.5/1.2.6 补齐了网卡锁定（`_iface_by_device`）、回调地址重写（`patch_request_callback`）、
> recv worker 生命周期修复、超时 100ms→2000ms 后，**选设备后发单播命令仍超时**。本节记录该现象的最终排查与结论。

### 现象

- 双网卡 Windows，设备在 WiFi `192.168.108.0/22`。Handshake 能正常发现 20+ 台设备。
- 选定设备后发单播命令（`GetModel` / `StatusCheck`）超时；**Wireshark 能看到设备回包**
  （如 `192.168.109.9:544xx -> 192.168.110.82:62520`），但应用层 `_do_framing` 没有 `received udp data`。

### 排查与证据

| 实验 | 结果 | 排除/指向 |
|------|------|-----------|
| 纯 socket 阻塞 `recvfrom`（绕开 jgb worker/DDS/framer） | 同样收不到 | **不在** Python 收包链 |
| `ping 192.168.109.9` / ARP / 路由 | 通；ARP 正常；走 WLAN(110.82) | 网络层、L2、路由**正常** |
| 广播 handshake | 发现 24+ 台（广播回包本身是设备→主机单播，能收到） | 收包路径本身可用 |
| 全部已发现设备逐台发**单播** `GetModel` | 23 台中**仅 VirtualZem(`110.74`) 回** | 见下「为何只有 VirtualZem」 |
| 给 `python.exe` 加防火墙入站 allow 规则后重测 | 仍 0/3 | （见备注，存在设备间歇性混淆，未最终定论） |
| **在安全中心关闭防火墙后重测 `109.9`** | **0/3 → 3/3** | **坐实是防火墙** |

### 结论（根因）

**Windows Defender 防火墙（设备网卡 WLAN = 专用/Private 配置文件）丢弃真实 ZEM 设备从「随机源端口」发回的单播命令回包。**

- 我们把命令单播发到 `设备:61557`，防火墙据此建立有状态入站 pinhole，**期待回包来自 `61557`**；
  而设备每次从**随机源端口**（`544xx`）回包 → 被当作「未经请求的入站 UDP」丢弃。
- Wireshark 抓包点在防火墙**之下**，所以仍能看到这些被丢的回包。

**为何 handshake 能成、为何只有 VirtualZem 能回：**

- 广播 handshake 不受影响 —— 广播会打开一个**更宽的入站 pinhole**，允许来自本网段任意主机/端口的回包。
- VirtualZem(`110.74`) 是唯一在防火墙开启时也能收到的端点 —— 因为它**从固定 `61557` 回包**
  （日志 `received udp data from ('192.168.110.74', 61557)`），正好匹配单播 pinhole；真实设备从随机端口回，故被丢。

### 已排除（不是这些原因）

- **客户端 pyzemrpc 1.2.6**：对会回包的端点（VirtualZem）走完整 `zem_api` 栈，`get_model()` 正常返回
  `VirtualZem/PerlinZem`、`StatusCheck=Idle`，`received udp data` 正常出现 —— 收包链健康。
- **jgb recv worker / DDS / framer**：纯 socket 裸 `recvfrom` 同样收不到，问题在更底层。
- **网络 / ARP / 路由 / strong-host**：ping 通、ARP 正常、路由正确；WeakHostReceive 虽为 Disabled，
  但回包到 `110.82` 正好从拥有该 IP 的 WLAN 进，strong-host 不丢。

> 注：消费端（pyzemcalib 的 `py312_pyzemcalib` venv）此前长期是旧版 **1.2.4**（缺 1.2.5/1.2.6 全部修复、
> 超时仍 100ms），排查中已 `force-reinstall` 到 1.2.6。

### 当前处理与永久修复候选

- **当前**：暂时在 Windows 安全中心关闭防火墙作为临时绕过；此问题暂不继续深入。
- **永久修复（保持防火墙开启，未实施）**：加一条按**设备子网**放行入站 UDP 的规则（仅放行实验室网段，范围可控、且不绑进程，GUI 一并覆盖）：

  ```powershell
  netsh advfirewall firewall add rule name="pyzem-lab-udp-in" dir=in action=allow protocol=UDP remoteip=192.168.108.0/22 enable=yes profile=any
  ```

  （按 `program` 的入站 allow 规则在本次测试中未能放行随机端口回包，但该次存在设备间歇性混淆，
  是否真的无效需「防火墙开+规则→探同一台设备」A/B 复测确认。子网规则更可靠。）

### 诊断脚本

- `tests/demo/net_probe.py` — 单目标纯 socket 探针（绑定/embed/发收，多次统计）
- `tests/demo/raw_recv_test.py` — handshake → 临时 socket / 持久 socket 裸 `recvfrom` 对比
- 全部已发现设备逐台单播 `GetModel` 扫描（判断哪些设备在线且真的回单播）
