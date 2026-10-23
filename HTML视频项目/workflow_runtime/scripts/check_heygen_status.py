#!/usr/bin/env python3
import argparse
import json
import os
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video_id")
    parser.add_argument("--output", type=Path, default=Path("heygen_response.json"))
    parser.add_argument("--api-base", default=os.environ.get("HEYGEN_API_BASE", "https://api.heygen.com"))
    args = parser.parse_args()
    api_key = os.environ.get("HEYGEN_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("请先设置 HEYGEN_API_KEY")

    url = args.api_base.rstrip("/") + "/v3/videos/" + args.video_id
    request = urllib.request.Request(url, headers={"X-Api-Key": api_key, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = response.read().decode("utf-8")
    args.output.write_text(payload, encoding="utf-8")
    data = json.loads(payload)
    status = data.get("status") or data.get("data", {}).get("status")
    print("status:", status)
    print("saved:", args.output)
    if status == "completed":
        print("next: python3 脚本/download_heygen_media.py", args.output)
    else:
        print("next: 等待完成后再次运行本脚本")


if __name__ == "__main__":
    main()
