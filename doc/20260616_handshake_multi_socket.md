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
