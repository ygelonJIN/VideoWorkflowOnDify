#!/usr/bin/env python3
"""Fail fast when generated HTML violates the production density/sync contract."""
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

    if not doc.lower().lstrip().startswith("<!doctype html>"):
        errors.append("缺少完整 HTML 文档头")
    for token in ("data-composition-id", "data-width=\"1080\"", "data-height=\"1920\"", "data-duration", "CAPTIONS_START", "CAPTIONS_END"):
        if token not in doc:
            errors.append("缺少 " + token)
    if "production-layout-contract" not in doc:
        errors.append("缺少 production-layout-contract")
    if "performance.now(" in doc or "requestAnimationFrame(" in doc:
        errors.append("仍有墙钟驱动 performance.now/requestAnimationFrame")
    contract_match = re.search(r'<style id="production-layout-contract">(?P<body>.*?)</style>', doc, re.S)
    contract_css = contract_match.group("body") if contract_match else ""
    if not re.search(r'\[data-coverage="full"\]\{[^}]*justify-content:center!important', contract_css):
        errors.append("缺少整体纵向居中：场景必须 justify-content:center")
    if not re.search(r'\[data-coverage="full"\] > \.topbar\{[^}]*position:absolute!important', contract_css):
        errors.append("顶部栏必须退出内容流，避免把内容推向顶部")
    if not re.search(r'\[data-coverage="full"\] > \.head,\[data-coverage="full"\] > \.body\{[^}]*flex:0 1 auto!important', contract_css):
        errors.append(".head/.body 必须使用自然高度，才能整体垂直居中")
    component_size_properties = ('font-size', 'width', 'height', 'min-height', 'padding', 'gap', 'border-radius')
    for rule_match in re.finditer(r'(?P<selector>[^{}]+)\{(?P<body>[^}]*)\}', contract_css):
        selector = rule_match.group('selector')
        rule_body = rule_match.group('body')
        if not re.search(r'\.(?:headline|big-title|card|panel|step|metric|tool|cta-btn)\b', selector):
            continue
        used = [prop for prop in component_size_properties if re.search(r'\b' + re.escape(prop) + r'\s*:', rule_body)]
        if used:
            errors.append("组件尺寸覆盖被禁止：" + selector.strip() + " 使用了 " + ",".join(used))
    if re.search(r'\bat\(\s*start\b', doc):
        errors.append("场景开始时间被二次缩放：data-start 已是真实秒数，禁止再次 at(start)")
    if not re.search(r'\.avatar-zone \.avatar-window\{[^}]*top:0!important', doc):
        errors.append("数字人内层未固定填满 .avatar-zone")
    if not re.search(r'\.avatar-window video[^{]*\{[^}]*width:100%!important', doc):
        errors.append("数字人视频未铺满小窗")
    if "font-size:37px!important" not in doc:
        errors.append("字幕字号不是固定 37px")
    if len(re.findall(r'data-coverage="full"', doc)) < 5:
        errors.append("全屏场景数量不足 5 个")

    body = doc[doc.lower().find("<body"):] if "<body" in doc.lower() else doc
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(re.sub(r"\s+", " ", text)).strip()
    if len(text) < 1200:
        errors.append(f"可见文案太少：{len(text)} 字符，要求至少 1200 字符")
    density_classes = ("panel", "card", "tiles", "pipe", "dash", "benefits", "deal", "chips", "info-block", "metric")
    if len(re.findall(r'class="[^"]*(?:' + "|".join(density_classes) + r')', doc)) < 8:
        errors.append("大型信息组件不足 8 个")


    scene_chunks = re.split(r'<(?:section|div)\b[^>]*class=["\'][^"\']*\bscene\b', doc, flags=re.I)[1:]
    component_pattern = r'class=["\'][^"\']*(?:card|panel|tool|step|metric|cmp-item|cmp-list|status|chip|flow|grid|list|cta)'
    for scene_index, scene_html in enumerate(scene_chunks, 1):
        scene_html = re.split(r'<!--\s*CAPTIONS_START|class=["\']caption-layer', scene_html, maxsplit=1, flags=re.I)[0]
        component_count = len(re.findall(component_pattern, scene_html, re.I))
        scene_text = re.sub(r'<[^>]+>', ' ', scene_html)
        scene_text_chars = len(re.sub(r'\s+', '', scene_text))
        if component_count < 8:
            errors.append(f"场景{scene_index}组件不足：至少8个，当前{component_count}个")
        if scene_text_chars < 80:
            errors.append(f"场景{scene_index}信息量不足：至少80字，当前{scene_text_chars}字")

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
