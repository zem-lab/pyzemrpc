"""Manual JSON-RPC integration utility. Defaults to read-only; never retries writes."""
import argparse
import json
from zemrpc.zem.stage_motion_parameters import PROFILES, StageMotionJsonRpc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="完整 JSON-RPC HTTP 地址")
    parser.add_argument("--apply", choices=PROFILES, help="显式应用正常/高速预设；不指定时只读")
    parser.add_argument("--axes", nargs="+", choices=("X", "Y"), default=["X", "Y"])
    args = parser.parse_args()
    client = StageMotionJsonRpc(args.url)
    result = client.configure([{"axis": axis, **PROFILES[args.apply]} for axis in args.axes]) if args.apply else client.read()
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
