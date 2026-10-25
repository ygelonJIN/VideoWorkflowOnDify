#!/usr/bin/env python3
"""Report how much visible motion each part of the rendered video has."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def frame_diffs(path: Path, width: int = 60, height: int = 106) -> list[float]:
    result = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf", f"scale={width}:{height}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    )
    size = width * height
    data = result.stdout
    frames = [data[i:i + size] for i in range(0, len(data) - size + 1, size)]
    diffs = []
    for index in range(1, len(frames)):
        changed = sum(1 for a, b in zip(frames[index], frames[index - 1]) if abs(a - b) > 8)
        diffs.append(changed / size)
    return diffs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--window", type=float, default=2.0)
    parser.add_argument("--min-change", type=float, default=0.01)
    args = parser.parse_args()

    diffs = frame_diffs(args.video)
    span = max(1, int(args.window * args.fps))
    static = []
    for start in range(0, max(1, len(diffs) - span + 1), span):
        peak = max(diffs[start:start + span])
        if peak < args.min_change:
            static.append((start / args.fps, peak))

    if static:
        detail = "，".join(f"{begin:.1f}s 起 {args.window:.0f}s 内最大变化 {peak * 100:.1f}%" for begin, peak in static[:8])
        print(f"MOTION PROFILE: WARN —— {len(static)} 个静止窗口：{detail}")
        return
    print("MOTION PROFILE: PASS —— 每段窗口都有可见变化")


if __name__ == "__main__":
    main()
