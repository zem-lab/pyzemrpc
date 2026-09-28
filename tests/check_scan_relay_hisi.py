"""Run against the C# fake-hardware harness, never against an actual microscope.

Usage: python tests/check_scan_relay_hisi.py <ScanRelayMaskTest.exe>
"""

from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zemrpc.zem.conn.rpc_protocol import RespProtocolNg
from zemrpc.zem.zem_rpc_device import ZemRpcDevice


def main():
    executable = Path(sys.argv[1]).resolve()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    child = subprocess.Popen([str(executable), "--serve-udp", str(port)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace",
                             creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
    lines = queue.Queue()
    threading.Thread(target=lambda: [lines.put(line) for line in child.stdout], daemon=True).start()
    device = None
    try:
        while True:
            line = lines.get(timeout=30)
            if line.startswith("READY: "):
                url = line.removeprefix("READY: ").strip()
                break
        device = ZemRpcDevice(name="scan_relay_loopback")
        device.update_remote_addr(("127.0.0.1", port))
        device.m.protocol_ng = RespProtocolNg(name="ZEMRPC-202409", url=url)
        assert device.get_scan_relay_mask() == 15
        for mask in (7, 4, 1, 15):
            assert device.set_scan_relay_mask(mask) == mask
            assert device.get_scan_relay_mask() == mask
            assert device.status_rpc().scan_relay_mask == mask
            state = device.zem_rpc({"jsonrpc": "2.0", "id": mask, "method": "SemControlState", "params": []})
            assert state["result"]["scan_relay_mask"] == mask
        print("PASS: real pyzemrpc UDP set/get and HTTP Status/SemControlState against C# fake hardware (15, 7, 4, 1, 15).")
    finally:
        if device is not None:
            device.disconnect()
        if child.poll() is None:
            try:
                child.stdin.write("stop\n")
                child.stdin.flush()
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    main()
