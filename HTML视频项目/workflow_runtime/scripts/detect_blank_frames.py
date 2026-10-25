#!/usr/bin/env python3
"""Fail when the rendered MP4 contains an isolated near-empty frame (black flash)."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def frame_content(path: Path, width: int = 60, height: int = 106, threshold: int = 80):
    """Return the share of visible pixels per frame; a blank frame drops to near zero."""
    result = subprocess.run(
        [
            "ffmpeg", "-loglevel", "error", "-i", str(path),
            "-vf", f"scale={width}:{height}", "-pix_fmt", "gray", "-f", "rawvideo", "-",
        ],
        check=True,
        capture_output=True,
    )
    size = width * height
    data = result.stdout
    frames = [data[i:i + size] for i in range(0, len(data) - size + 1, size)]
    return frames, [sum(1 for value in frame if value > threshold) / size for frame in frames]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--ratio", type=float, default=0.4, help="可见像素占比低于相邻帧的这个比例就判为黑闪")
    parser.add_argument("--floor", type=float, default=0.03, help="相邻帧可见像素低于这个比例时不判黑闪（场景淡入前几帧属于正常）")
    args = parser.parse_args()

    frames, content = frame_content(args.video)
    size = len(frames[0]) if frames else 1
    if len(content) < 3:
        print("BLANK FRAME CHECK: 跳过（帧数不足）")
        return

    blank = []
    for index in range(1, len(content) - 1):
        neighbour = max(content[index - 1], content[index + 1])
        if neighbour < args.floor or content[index] >= neighbour * args.ratio:
            continue
        # 前后两帧差异大 = 场景切换/淡入的正常过渡，不算黑闪
        left, right = frames[index - 1], frames[index + 1]
        changed = sum(1 for a, b in zip(left, right) if abs(a - b) > 8) / size
        if changed > 0.03:
            continue
        blank.append((index, content[index], neighbour))

    if blank:
        detail = "，".join(
            f"第 {index} 帧（{index / args.fps:.2f}s，可见像素 {value * 100:.2f}% / 相邻 {base * 100:.2f}%）"
            for index, value, base in blank[:8]
        )
        print(f"BLANK FRAME CHECK: FAIL —— 检测到 {len(blank)} 个孤立空帧：{detail}")
        sys.exit(1)
    print("BLANK FRAME CHECK: PASS")


if __name__ == "__main__":
    main()
