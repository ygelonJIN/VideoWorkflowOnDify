#!/usr/bin/env python3
"""Normalize final MP4 loudness without changing the rendered video timeline."""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def ffmpeg_loudness(path: Path) -> dict:
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
        "-af", "loudnorm=I=-14.0:TP=-1.5:LRA=11:print_format=json",
        "-f", "null", "-",
    ], text=True, capture_output=True, check=False)
    matches = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr, flags=re.S)
    if not matches:
        raise SystemExit("无法测量成片响度：" + result.stderr[-500:])
    return json.loads(matches[-1])


def media_duration(path: Path) -> float:
    return float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ], text=True).strip())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    args = parser.parse_args()
    source = args.video
    if not source.is_file():
        raise SystemExit(f"缺少文件：{source}")

    duration = media_duration(source)
    before = ffmpeg_loudness(source)
    temporary = source.with_name(source.stem + ".loudness-normalized.mp4")
    temporary.unlink(missing_ok=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(source),
        "-map", "0:v:0", "-map", "0:a:0", "-map_metadata", "0",
        "-c:v", "copy",
        "-af", "loudnorm=I=-14.0:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
        "-t", f"{duration:.6f}",
        "-movflags", "+faststart",
        str(temporary),
    ], check=True)
    after = ffmpeg_loudness(temporary)
    integrated = float(after.get("input_i", "-99"))
    true_peak = float(after.get("input_tp", "0"))
    if not -14.8 <= integrated <= -14.1 or true_peak > -1.3:
        temporary.unlink(missing_ok=True)
        raise SystemExit(f"响度标准化未达标：I={integrated:.2f} LUFS, TP={true_peak:.2f} dBTP")
    os.replace(temporary, source)
    print("AUDIO LOUDNESS: PASS")
    print(f"before_i={float(before.get('input_i', -99)):.2f}")
    print(f"after_i={integrated:.2f}")
    print(f"after_tp={true_peak:.2f}")


if __name__ == "__main__":
    main()
