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


def scene_windows(html_path: Path) -> list[tuple[str, float, float]]:
    import re
    try:
        html = html_path.read_text(encoding="utf-8")
    except OSError:
        return []
    windows = []
    for tag in re.findall(r"<section[^>]*data-scene=\"[^\"]+\"[^>]*>", html):
        name = re.search(r'data-scene="([^"]+)"', tag)
        start = re.search(r'data-start="([0-9.]+)"', tag)
        dur = re.search(r'data-duration="([0-9.]+)"', tag)
        if name and start and dur:
            windows.append((name.group(1), float(start.group(1)), float(dur.group(1))))
    return windows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--window", type=float, default=2.0)
    parser.add_argument("--min-change", type=float, default=0.01)
    parser.add_argument("--html", type=Path, help="index.html；给了就按屏输出可见变化报告")
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
    else:
        print("MOTION PROFILE: PASS —— 每段窗口都有可见变化")

    if args.html is None:
        return
    windows = scene_windows(args.html)
    if not windows:
        print("逐屏报告：没有从 HTML 读到场景窗（缺 data-scene/data-start/data-duration），跳过")
        return
    print("逐屏可见变化（含字幕；峰值为窗口内单帧最大变化率，可见=≥%.0f%%）：" % (args.min_change * 100))
    for name, start, dur in windows:
        begin = max(0, int(round(start * args.fps)))
        end = min(len(diffs), int(round((start + dur) * args.fps)))
        segment = diffs[begin:end]
        if not segment:
            print(f"  {name} {start:6.2f}+{dur:5.2f}s  无帧")
            continue
        mean = sum(segment) / len(segment)
        peak = max(segment)
        visible = sum(1 for value in segment if value >= args.min_change)
        flag = "弱" if peak < args.min_change * 2 else ("偏静" if visible < 2 else "OK")
        print(f"  {name} {start:6.2f}+{dur:5.2f}s  平均 {mean * 100:5.2f}%  峰值 {peak * 100:5.2f}%  可见帧 {visible:3d}  {flag}")


if __name__ == "__main__":
    main()
