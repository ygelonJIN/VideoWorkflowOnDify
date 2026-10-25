#!/usr/bin/env python3
"""Replace isolated blank frames in a rendered MP4 with the previous frame."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def probe(path: Path) -> tuple[int, int, float]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate", "-of", "json", str(path)],
        check=True, text=True, capture_output=True,
    )
    stream = json.loads(result.stdout)["streams"][0]
    num, den = stream["r_frame_rate"].split("/")
    return int(stream["width"]), int(stream["height"]), float(num) / float(den or 1)


def blank_frames(path: Path, width: int = 60, height: int = 106, threshold: int = 80,
                 ratio: float = 0.4, floor: float = 0.03) -> list[int]:
    result = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(path), "-vf", f"scale={width}:{height}",
         "-pix_fmt", "gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    )
    size = width * height
    data = result.stdout
    frames = [data[i:i + size] for i in range(0, len(data) - size + 1, size)]
    content = [sum(1 for value in frame if value > threshold) / size for frame in frames]
    bad = []
    for index in range(1, len(content) - 1):
        neighbour = max(content[index - 1], content[index + 1])
        if neighbour < floor or content[index] >= neighbour * ratio:
            continue
        left, right = frames[index - 1], frames[index + 1]
        changed = sum(1 for a, b in zip(left, right) if abs(a - b) > 8) / size
        if changed > 0.03:
            continue
        bad.append(index)
    return bad


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path)
    parser.add_argument("--limit", type=int, default=80, help="超过这个数量的空帧就拒绝自动修复")
    args = parser.parse_args()

    width, height, fps = probe(args.video)
    bad = set(blank_frames(args.video))
    if not bad:
        print("BLANK FRAME REPAIR: 没有需要修复的帧")
        return
    if len(bad) > args.limit:
        print(f"BLANK FRAME REPAIR: 空帧过多（{len(bad)}），拒绝自动修复")
        sys.exit(2)

    frame_bytes = width * height * 3
    temp = args.video.with_suffix(".repair.mp4")
    decoder = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-i", str(args.video), "-f", "rawvideo",
         "-pix_fmt", "rgb24", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    encoder = subprocess.Popen(
        ["ffmpeg", "-loglevel", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{width}x{height}", "-r", f"{fps:g}", "-i", "-",
         "-i", str(args.video),
         "-map", "0:v:0", "-map", "1:a:0?",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-c:a", "copy", "-movflags", "+faststart", str(temp)],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL,
    )
    assert decoder.stdout is not None and encoder.stdin is not None

    pending: list[int] = []
    replaced = 0
    last_good = None
    index = 0
    while True:
        frame = decoder.stdout.read(frame_bytes)
        if len(frame) < frame_bytes:
            break
        if index in bad:
            pending.append(index)
        else:
            if pending:
                for _ in pending:
                    encoder.stdin.write(frame)
                    replaced += 1
                pending.clear()
            encoder.stdin.write(frame)
            last_good = frame
        index += 1
    if pending and last_good is not None:
        for _ in pending:
            encoder.stdin.write(last_good)
            replaced += 1
    encoder.stdin.close()
    decoder.wait()
    encoder.wait()

    if encoder.returncode != 0 or replaced == 0:
        temp.unlink(missing_ok=True)
        print("BLANK FRAME REPAIR: FAIL")
        sys.exit(1)
    shutil.move(str(temp), str(args.video))
    print(f"BLANK FRAME REPAIR: 已用后一帧补齐 {replaced} 个空帧（{sorted(bad)[:8]}）")


if __name__ == "__main__":
    main()
