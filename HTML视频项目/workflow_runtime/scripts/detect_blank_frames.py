#!/usr/bin/env python3
"""Fail when the rendered MP4 contains an isolated near-empty frame (black flash).

2026-11-12 改：只判真正的"孤立单帧"——这一帧比紧邻的前后两帧都明显暗，
两帧本身都亮。多帧的暗段（场景淡入前几帧、暗色设计的屏）不算，那是
出场/入场过程；这类"先满后归零再回满"的逻辑问题由 check_html_timing.mjs
逐帧扫描负责，不靠亮度猜。
"""
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


def read_scene_starts(html: Path | None) -> list[float]:
    if not html or not html.exists():
        return []
    import re
    return [float(x) for x in re.findall(r'data-start="([0-9.]+)"', html.read_text(encoding="utf-8"))]


def find_isolated(means: list[float], starts: list[float], fps: float,
                  entrance: float, ratio: float = 0.4, floor: float = 22.0):
    """Return [(index, value, base)] for frames that are a lone dark frame.

    判据（三条同时满足）：
    1. 这一帧亮度低于两侧较亮邻帧的 40%；
    2. 两侧邻帧本身都不暗（都 ≥ 较亮那侧的 80%），否则就是暗段边缘/淡入淡出；
    3. 不在场景入场 0.35s 窗口内（首帧本来就是纯背景）。
    """
    bad = []
    for index in range(1, len(means) - 1):
        prev_value = means[index - 1]
        value = means[index]
        next_value = means[index + 1]
        base = max(prev_value, next_value)
        if base < floor:
            continue
        if value > base * ratio:
            continue
        if min(prev_value, next_value) < base * 0.8:
            continue
        moment = index / fps
        if any(0 <= moment - start <= entrance for start in starts):
            continue
        bad.append((index, value, base))
    return bad


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--html", type=Path, default=None, help="可选：读 data-start，忽略每屏入场前 0.35s")
    parser.add_argument("--entrance", type=float, default=0.35, help="场景入场窗口（秒）")
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--ratio", type=float, default=0.4, help="低于较亮邻帧的这个比例就判为黑闪")
    parser.add_argument("--floor", type=float, default=22.0, help="邻帧亮度低于这个值时不判（暗场景正常）")
    args = parser.parse_args()

    frames, _ = frame_content(args.video)
    if len(frames) < 5:
        print("BLANK FRAME CHECK: 跳过（帧数不足）")
        return

    means = [sum(f) / len(f) if f else 0.0 for f in frames]
    blank = find_isolated(means, read_scene_starts(args.html), args.fps, args.entrance,
                          ratio=args.ratio, floor=args.floor)

    if blank:
        detail = "，".join(
            f"第 {index} 帧（{index / args.fps:.2f}s，亮度 {value:.1f} / 邻帧 {base:.1f}）"
            for index, value, base in blank[:8]
        )
        print(f"BLANK FRAME CHECK: FAIL —— 检测到 {len(blank)} 个孤立空帧：{detail}")
        sys.exit(1)
    print("BLANK FRAME CHECK: PASS")


if __name__ == "__main__":
    main()
