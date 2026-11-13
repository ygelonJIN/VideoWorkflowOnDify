#!/usr/bin/env python3
"""用前一帧替换孤立黑闪帧。

判据直接复用 detect_blank_frames.find_isolated，避免两个脚本各写一套、改了一处
另一处不生效（2026-11-12 之前就是这样，修复白跑一遍）。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import detect_blank_frames as detect


def repair(video: Path, indices: list[int], fps: float) -> None:
    total_segments = []
    cursor = 0
    for index in indices:
        if index - 1 > cursor:
            total_segments.append(("cut", cursor, index - 1))
        total_segments.append(("dup", index - 1, index - 1))
        cursor = index + 1
    total_segments.append(("cut", cursor, 10 ** 9))

    parts = []
    args = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(video)]
    filter_parts = []
    for i, (kind, a, b) in enumerate(total_segments):
        sel = "eq(n\\,%d)" % a if kind == "dup" else ("between(n\\,%d\\,%d)" % (a, b) if b < 10 ** 9 else "gte(n\\,%d)" % a)
        filter_parts.append("[0:v]select='%s',setpts=N/FRAME_RATE/TB[v%d]" % (sel, i))
        parts.append("[v%d]" % i)
    filter_parts.append("%sconcat=n=%d:v=1:a=0[vout]" % ("".join(parts), len(parts)))
    tmp = video.with_suffix(".repair.mp4")
    args += ["-filter_complex", ";".join(filter_parts), "-map", "[vout]", "-map", "0:a?",
             "-r", str(fps), "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p",
             "-c:a", "copy", "-movflags", "+faststart", str(tmp)]
    subprocess.run(args, check=True)
    tmp.replace(video)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--fps", type=float, default=30.0)
    ap.add_argument("--html", type=Path, default=None)
    ap.add_argument("--entrance", type=float, default=0.35)
    ap.add_argument("--ratio", type=float, default=0.4)
    ap.add_argument("--floor", type=float, default=22.0)
    args = ap.parse_args()

    frames, _ = detect.frame_content(args.video)
    if len(frames) < 5:
        print("BLANK FRAME REPAIR: 跳过（帧数不足）")
        return
    means = [sum(f) / len(f) if f else 0.0 for f in frames]
    found = detect.find_isolated(means, detect.read_scene_starts(args.html), args.fps,
                                 args.entrance, ratio=args.ratio, floor=args.floor)
    bad = [index for index, _value, _base in found]
    if not bad:
        print("BLANK FRAME REPAIR: 没有需要修复的帧")
        return
    print("BLANK FRAME REPAIR: 替换 %d 帧（共 %d 帧）：%s" % (len(bad), len(means), bad[:8]))
    repair(args.video, bad, args.fps)
    print("BLANK FRAME REPAIR: 完成")


if __name__ == "__main__":
    main()
