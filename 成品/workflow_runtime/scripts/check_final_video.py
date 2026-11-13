#!/usr/bin/env python3
"""Validate that the rendered MP4 shares the real voice clock and has no avatar reserve."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path


def probe(path: Path) -> dict:
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path),
    ], check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def stream_duration(entry: dict, codec_type: str) -> float:
    streams = [item for item in entry.get("streams", []) if item.get("codec_type") == codec_type]
    if not streams:
        raise SystemExit(f"缺少 {codec_type} 流")
    values = [float(item.get("duration") or entry.get("format", {}).get("duration") or 0) for item in streams]
    return max(values)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--voice", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    args = parser.parse_args()

    for path in (args.video, args.voice, args.html):
        if not path.is_file():
            raise SystemExit(f"缺少文件：{path}")

    video_info = probe(args.video)
    voice_info = probe(args.voice)
    video_duration = stream_duration(video_info, "video")
    audio_duration = stream_duration(video_info, "audio")
    voice_duration = float(voice_info.get("format", {}).get("duration") or 0)
    html = args.html.read_text(encoding="utf-8")

    errors: list[str] = []
    if abs(video_duration - voice_duration) > 0.05:
        errors.append(f"视频 {video_duration:.3f}s 与口播 {voice_duration:.3f}s 不一致")
    if abs(audio_duration - voice_duration) > 0.05:
        errors.append(f"成片音轨 {audio_duration:.3f}s 与口播 {voice_duration:.3f}s 不一致")

    root_match = re.search(r'\bdata-duration="([0-9.]+)"', html)
    if not root_match or abs(float(root_match.group(1)) - voice_duration) > 0.05:
        errors.append("HTML 根时间轴未锁定到真实口播时长")

    if 'data-render-mode="black-frame"' in html:
        forbidden = re.compile(
            r'<(?:video|template|div)\b[^>]*(?:data-video-role="avatar"|data-media-id="heygen_avatar"'
            r'|class="[^"]*(?:avatar-window|black-frame))',
            re.I,
        )
        if forbidden.search(html):
            errors.append("无数字人成片仍包含数字人窗口或黑帧占位")

    if errors:
        print("FINAL VIDEO CONTRACT: FAIL")
        for error in errors:
            print("reason:", error)
        raise SystemExit(1)

    print("FINAL VIDEO CONTRACT: PASS")
    print(f"video_duration={video_duration:.3f}")
    print(f"audio_duration={audio_duration:.3f}")
    print(f"voice_duration={voice_duration:.3f}")


if __name__ == "__main__":
    main()
