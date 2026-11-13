"""Run the SDK against Instrument's local OpticsProtocolTest fake-hardware server.

Usage: python tests/check_optics_jsonrpc_instrument.py --dotnet PATH --fixture PATH.dll
This starts its own fixture; it never accepts a real microscope address.
"""

import argparse
from pathlib import Path
import queue
import subprocess
import sys
import threading
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zemrpc.zem.conn.rpc_protocol import JsonRpcBuilder
from zemrpc.zem.context import ctx
from zemrpc.zem.models import EnumCmdLevel, ZemException
from zemrpc.zem.zem_rpc_device import ZemModel, ZemRpcDevice


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dotnet", default="dotnet")
    parser.add_argument("--fixture", required=True, type=Path)
    args = parser.parse_args()
    process = subprocess.Popen(
        [args.dotnet, str(args.fixture.resolve()), "--serve-jsonrpc"],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = queue.Queue()

    def read_output():
        for line in process.stdout:
            output.put(line.rstrip())
        output.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    try:
        while True:
            line = output.get(timeout=60)
            if line is None:
                raise RuntimeError("Instrument fixture exited before announcing its endpoint")
            print(line)
            if line.startswith("READY: "):
                url = line.removeprefix("READY: ")
                break
        assert url.startswith("http://127.0.0.1:")
        device = object.__new__(ZemRpcDevice)
        device.m = ZemModel(ctx=ctx)
        device.rpc_builder = JsonRpcBuilder()
        device._work_mode = EnumCmdLevel.ADVANCED
        device.send = Mock(side_effect=AssertionError("Unexpected UDP"))
        device.set_rpc_url(url)
        assert device.status_rpc().optics.source == "instrument_model"
        result = device.set_ast_rpc(222, -333)
        assert result.astigmatism.x_dac == 222 and result.astigmatism.y_dac == -333
        result = device.set_astigmatism_rpc(y=25)
        assert result.astigmatism.x_dac == 222 and result.astigmatism.y_dac == 1023
        assert device.status_rpc().optics == result
        result = device.set_alignment_rpc(up_x=-50, down_y=25)
        # The fixture deliberately configures upper X's negative limit to -2000.
        assert result.alignment.up.x_dac == -1000 and result.alignment.up.x == -50
        assert result.alignment.down.y_dac == 1023
        assert device.status_rpc().optics == device.m.optics == result
        before = result
        invalid = device.zem_rpc({"jsonrpc": "2.0", "id": 999, "method": "SemSetAlignment", "params": [10, 20, 30, 101]})
        assert invalid.get("error") and device.status_rpc().optics == before
        device._work_mode = EnumCmdLevel.BASIC
        try:
            device.set_astigmatism_rpc(x=1)
        except ZemException:
            pass
        else:
            raise AssertionError("BASIC mode allowed an optical write")
        assert device.status_rpc().optics == before
        device.send.assert_not_called()
        print("PASS: Python SDK -> Instrument HTTP JSON-RPC -> fake hardware -> Status.")
    finally:
        if process.poll() is None:
            process.stdin.write("\n")
            process.stdin.flush()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        reader.join(timeout=5)


if __name__ == "__main__":
    main()
