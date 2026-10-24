#!/usr/bin/env python3
"""Fail fast when generated HTML violates technical timeline/media synchronization."""
from __future__ import annotations

import argparse
import html as html_lib
import re
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("html", type=Path)
    args = parser.parse_args()
    doc = args.html.read_text(encoding="utf-8")
    errors: list[str] = []
    black_frame = 'data-render-mode="black-frame"' in doc

    if not doc.lower().lstrip().startswith("<!doctype html>"):
        errors.append("缺少完整 HTML 文档头")
    for token in (
        "data-composition-id", "data-width=\"1080\"", "data-height=\"1920\"",
        "data-duration", "data-caption-sync", "data-authoring-duration",
        "data-timeline-scale", "fitRootToViewport", "CAPTIONS_START", "CAPTIONS_END",
    ):
        if token not in doc:
            errors.append("缺少 " + token)
    if "production-layout-contract" not in doc:
        errors.append("缺少技术运行时 contract")
    for token in (
        'bottom:24%', 'width:62%', 'max-width:62%', 'font-size:37px',
        'line-height:1.35', 'font-weight:700', 'background:rgba(6,10,20,.72)',
    ):
        if token not in doc:
            errors.append("字幕契约缺少 " + token)
    if "performance.now(" in doc or "requestAnimationFrame(" in doc:
        errors.append("仍有墙钟驱动 performance.now/requestAnimationFrame")
    if "Math.random(" in doc:
        errors.append("禁止运行时 Math.random，随机性只能是作者期变体选择")
    if not re.search(r'\b(?:master|timeline)\.(?:from|fromTo|to|set)\s*\(|\bgsap\.set\s*\(', doc):
        errors.append("缺少时间线驱动的 GSAP from/fromTo/to/set 动作调用")
    if not re.search(r'window\.__timelines', doc):
        errors.append("缺少 window.__timelines 注册的可寻址时间线")
    if black_frame:
        if 'data-render-mode="black-frame"' not in doc:
            errors.append("缺少黑帧模式标记")
        avatar_tag = r'<(?:video|template|div)\b[^>]*(?:data-video-role="avatar"|data-media-id="heygen_avatar"|class="[^"]*(?:avatar-window|black-frame))'
        if re.search(avatar_tag, doc, re.I):
            errors.append("无数字人模式不得包含数字人媒体、avatar 角色、数字人窗口或黑帧占位")
        if re.search(r'\.(?:black-frame|avatar-window|avatar-zone)\s*(?:::(?:before|after))?\s*\{', doc, re.I):
            errors.append("无数字人模式不得保留黑帧/数字人占位 CSS 或布局避让规则")
        kicker_shift = re.search(r'\.kicker\s*\{[^}]*\bleft:\s*(\d+)px', doc, re.I)
        if kicker_shift and int(kicker_shift.group(1)) >= 300:
            errors.append("顶部内容仍向右避让旧数字人/黑帧占位")
        if 'data-audio-role="voiceover"' not in doc:
            errors.append("黑帧模式必须保留独立口播音频图层")
    else:
        avatar_template = r'<template\b[^>]*data-media-type="video"[^>]*data-video-role="avatar"[^>]*>'
        avatar_runtime = r'<video\b[^>]*data-video-role="avatar"[^>]*>'
        if not (re.search(avatar_template, doc, re.I) or re.search(avatar_runtime, doc, re.I)):
            errors.append("数字人模式必须保留 avatar 视频角色和媒体占位")
        if 'data-render-mode="full"' not in doc and 'data-render-mode="black-frame"' in doc:
            errors.append("数字人模式不得误标为无数字人 black-frame")

    if "data-start" not in doc or "data-duration" not in doc:
        errors.append("缺少时间片段属性")
    scene_chunks = re.split(r'<(?:section|div)\b[^>]*class=["\'][^"\']*\bscene\b', doc, flags=re.I)[1:]
    if not scene_chunks:
        errors.append("缺少 scene 时间片段")
    root_duration_match = re.search(r'\bdata-duration="([0-9.]+)"', doc)
    root_duration = float(root_duration_match.group(1)) if root_duration_match else 0.0
    scene_tags = re.findall(r'<(?:section|div)\b(?=[^>]*class=["\'][^"\']*\bscene\b)[^>]*>', doc, flags=re.I)
    if any(not re.search(r'\bdata-sentence-ids="[^"]+"', tag) for tag in scene_tags):
        errors.append("每个 scene 必须保留 data-sentence-ids 句子锚点")
    if not re.search(r'class=["\'][^"\']*\bcaption\b[^"\']*["\'][^>]*data-sentence-id=', doc, re.I):
        errors.append("字幕必须保留 data-sentence-id 句子锚点")
    scene_end = 0.0
    for tag in scene_tags:
        start = re.search(r'\bdata-start="([0-9.]+)"', tag)
        duration = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if start and duration:
            scene_end = max(scene_end, float(start.group(1)) + float(duration.group(1)))
    if root_duration and abs(scene_end - root_duration) > 0.05:
        errors.append(f"场景总时长 {scene_end:.3f}s 与根时间轴 {root_duration:.3f}s 不一致")
    caption_tags = re.findall(r'<div\b[^>]*class=["\'][^"\']*\bcaption\b[^>]*>', doc, flags=re.I)
    for tag in caption_tags:
        start = re.search(r'\bdata-start="([0-9.]+)"', tag)
        duration = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if start and duration and root_duration:
            end = float(start.group(1)) + float(duration.group(1))
            if end > root_duration + 0.05:
                errors.append(f"字幕结束时间 {end:.3f}s 超过根时间轴 {root_duration:.3f}s")
                break
    if "deterministic media-clock state controller" not in doc:
        errors.append("缺少媒体主时钟状态控制器")

    media = [match.group(0) for match in re.finditer(r'<(?:video|audio)\b[^>]*>', doc, re.I)]
    if not media:
        errors.append("未找到媒体元素")
    durations = []
    for tag in media:
        start = re.search(r'\bdata-start="([0-9.]+)"', tag)
        duration = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if not start or abs(float(start.group(1))) > 0.01:
            errors.append("媒体 data-start 必须统一为 0")
        if duration:
            durations.append(round(float(duration.group(1)), 3))
    if durations and max(durations) - min(durations) > 0.05:
        errors.append("视频、口播和背景音乐 data-duration 不一致")

    for tag in media:
        if 'data-audio-role="background-music"' not in tag:
            continue
        src_match = re.search(r'\bsrc="([^"]+)"', tag)
        duration_match = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if not src_match or not duration_match:
            continue
        bgm_path = args.html.resolve().parent / src_match.group(1)
        if not bgm_path.exists():
            errors.append("BGM 文件不存在：" + str(bgm_path))
            continue
        try:
            actual_duration = float(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(bgm_path),
            ], text=True).strip())
        except Exception as exc:
            errors.append("无法读取 BGM 实际时长：" + str(exc))
            continue
        declared_duration = float(duration_match.group(1))
        if actual_duration + 0.1 < declared_duration:
            errors.append(
                f"BGM 实际时长不足：文件 {actual_duration:.3f}s，成片需要 {declared_duration:.3f}s"
            )

    body = doc[doc.lower().find("<body"):] if "<body" in doc.lower() else doc
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(re.sub(r"\s+", " ", text)).strip()
    if errors:
        print("HTML CONTRACT: FAIL")
        for error in errors:
            print("reason:", error)
        raise SystemExit(1)
    print("HTML CONTRACT: PASS")
    print("visible_text_chars:", len(text))
    print("media_count:", len(media))
    print("media_duration:", durations[0] if durations else "(none)")

if __name__ == "__main__":
    main()
