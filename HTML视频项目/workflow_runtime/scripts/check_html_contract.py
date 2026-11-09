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
        'bottom:13%', 'width:80%', 'max-width:80%', 'font-size:45px',
        'line-height:1.35', 'font-weight:700', 'background:transparent',
        'text-shadow:',
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
    # 动效选择器全部命中 0 个元素时，成片是静帧；静态解析，和 H03 的 unmatched 同一套口径。
    motion_blocking = []
    _selectors = []
    for _call in re.finditer(r"\b(?:master|timeline)\.(?:from|fromTo|to|set)\s*\(([\s\S]*?)(?:,\s*\{|,\s*at\(|\)\s*;?\s*$)", doc):
        _pieces = re.findall(r"""(['"])((?:(?!\1).)+)\1""", _call.group(1))
        _joined = "".join(_piece for _q, _piece in _pieces)
        if _joined:
            _selectors.append(_joined)
    if _selectors:
        def _resolves(selector):
            tokens = re.findall(r'\[data-[\w-]+="[^"]*"\]|#[\w-]+|\.[\w-]+', selector)
            if not tokens:
                return False
            for token in tokens:
                if token.startswith("["):
                    if token not in doc:
                        return False
                elif token.startswith("#"):
                    if not re.search(r"(?<![\w-])id=[\"']" + re.escape(token[1:]) + r"[\"']", doc):
                        return False
                elif not re.search(r'class="[^"]*\b' + re.escape(token[1:]) + r'\b', doc):
                    return False
            return True
        # 有 canvas/three 场景时，动效由 hf-seek 里的时间函数驱动，DOM 选择器不适用，跳过这条门禁
        if "hf-seek" not in doc:
            _resolved = sum(1 for _sel in _selectors if _resolves(_sel))
            if _resolved == 0:
                motion_blocking.append("动效选择器 %d 个全部命中 0 个元素，成片会是静帧" % len(_selectors))
            elif _resolved < len(_selectors) * 0.6:
                motion_blocking.append("动效选择器只有 %d/%d 能命中元素，动效大面积失效" % (_resolved, len(_selectors)))
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
    scene_tags = re.findall(r'<section\b(?=[^>]*class=["\'][^"\']*\bscene\b)[^>]*>', doc, flags=re.I)
    structure_blocking = []
    # 场景显隐已交还给页面自己驱动（本地不再注入 scene-window-runtime），
    # 页面没写驱动的话所有 scene 会同时叠在画布上，必须拦。
    if len(scene_tags) >= 2:
        _scripts = "\n".join(re.findall(r'<script\b[^>]*>([\s\S]*?)</script>', doc, flags=re.I))
        if not ("data-start" in _scripts and re.search(r'visibility|opacity|clip-path|clipPath|display|translate|scale', _scripts)):
            structure_blocking.append("页面没有场景显隐驱动（需按 data-start/data-duration 自己切可见性，本地已不兜底）")
    missing_anchor = [tag for tag in scene_tags if not re.search(r'\bdata-sentence-ids="[^"]+"', tag)]
    if missing_anchor:
        structure_blocking.append("有 %d 个 scene 缺 data-sentence-ids 句子锚点（字幕无法对时）" % len(missing_anchor))
    missing_scene_id = [tag for tag in scene_tags if not re.search(r'\bdata-scene="[^"]+"', tag)]
    if missing_scene_id:
        structure_blocking.append("有 %d 个 scene 缺 data-scene（动效与场景判定会错位）" % len(missing_scene_id))
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

    # ---- 结构完整性：残缺 HTML（截断、标签没闭合、丢场景）不放行 ----
    blocking: list[str] = list(motion_blocking) + list(structure_blocking)
    # canvas：固定 1080×1920 backing，且不能按视口尺寸改（渲染时会被缩到 338×600，画面糊掉）
    for canvas_tag in re.findall(r"<canvas\b[^>]*>", doc, re.I):
        if not (re.search(r'width=["\']1080["\']', canvas_tag) and re.search(r'height=["\']1920["\']', canvas_tag)):
            blocking.append('canvas 必须固定 width="1080" height="1920"，否则分辨率被视口缩放压扁')
            break
    if re.search(r"[A-Za-z_$][\w$]*\.width\s*=\s*Math\.round\(", doc) and "getBoundingClientRect" in doc:
        blocking.append("canvas 不要按 getBoundingClientRect 改尺寸（渲染时被缩放，画面糊且元素错位）")
    if "</html>" not in doc.lower():
        blocking.append("HTML 结尾不完整（缺少 </html>），产物可能被截断")
    for tag in ("style", "script"):
        opens = len(re.findall(r"<%s\b" % tag, doc, flags=re.I))
        closes = len(re.findall(r"</%s\s*>" % tag, doc, flags=re.I))
        if opens != closes:
            blocking.append("<%s> 开闭不配对（%d 开 / %d 闭），标签后面整段内容会被吞掉" % (tag, opens, closes))
    markup = re.sub(r"<script\b.*?</script\s*>|<style\b.*?</style\s*>", " ", doc, flags=re.I | re.S)
    cursor = markup.find("<")
    while cursor >= 0:
        end = markup.find(">", cursor)
        if end < 0:
            blocking.append("标记在 char %d 处断了（没有闭合的 >）" % cursor)
            break
        if markup.find("<", cursor + 1, end) >= 0:
            blocking.append("char %d 起的标签里出现未闭合的属性引号，后面的标记会被当成属性值" % cursor)
            break
        cursor = markup.find("<", end + 1)
    caption_ids = {item.strip() for item in re.findall(r'\bdata-sentence-id="([^"]+)"', doc) if item.strip()}
    scene_sentence_ids: set[str] = set()
    for attr in re.findall(r'\bdata-sentence-ids="([^"]+)"', doc):
        scene_sentence_ids.update(part for part in re.split(r"[\s,]+", attr.strip()) if part)
    uncovered = sorted(caption_ids - scene_sentence_ids)
    if uncovered:
        blocking.append("有 %d 句口播没有对应场景：%s" % (len(uncovered), "、".join(uncovered[:8])))
    if not re.search(r'\b(?:master|timeline)\.(?:from|fromTo|to|set)\s*\(|\bgsap\.set\s*\(', doc):
        blocking.append("HTML 里没有任何 GSAP 动作，成片会是静止的")

    # ---- 转场把下一屏图片「动画到」opacity 0：那一屏会永远没有图 ----
    # 只看目标对象（第二个参数）；from 是 0、to 是 1 是正常的淡入。
    broken_transitions = []
    for match in re.finditer(
        r"fromTo\(\s*([A-Za-z_$][\w$]*)\s*,\s*\{[^{}]*\}\s*,\s*\{([^{}]*)\}",
        doc,
        re.S,
    ):
        name, target = match.group(1), match.group(2)
        if not name.lower().startswith("to"):
            continue
        if re.search(r"opacity\s*:\s*0(?![.\d])", target):
            broken_transitions.append(name)
    if broken_transitions:
        blocking.append(
            "转场把下一屏图片「动画到」opacity: 0（%s），转场后那一屏永远没有图：把目标改成 opacity: 1"
            % "、".join(sorted(set(broken_transitions))[:4])
        )

    # ---- 图片契约：每一屏的主视觉必须是真实照片 ----
    leftover_placeholders = re.findall(r"\{\{IMG:[A-Za-z0-9_-]+\}\}", doc)
    if leftover_placeholders:
        blocking.append("还有 %d 个 {{IMG:...}} 占位没替换成真实文件（生图没跑，或占位替换没执行）" % len(leftover_placeholders))
    image_refs = sorted(set(re.findall(r'媒体/图片/((?:[^"/\\]+/)*[^"/\\]+?)\.(?:png|jpe?g|webp)', doc)))
    if not image_refs:
        errors.append("HTML 里没有任何 媒体/图片/ 引用：主视觉仍是 HTML 画的图形，不是真实照片")
    else:
        base_dir = args.html.resolve().parent
        missing_files = [name for name in image_refs
                         if not any((base_dir / "媒体" / "图片" / (name + ext)).exists()
                                    for ext in (".png", ".jpg", ".jpeg", ".webp"))]
        if missing_files:
            blocking.append("图片文件不存在：" + "、".join(missing_files[:8]))
    scenes_without_image = []
    for tag in re.finditer(r"<section\b(?=[^>]*class=[\"\'][^\"\']*\bscene\b)[^>]*>", doc, flags=re.I):
        head = tag.group(0)
        sid_match = re.search(r'data-scene=["\']([^"\']+)["\']', head)
        end = doc.find("</section>", tag.end())
        inner = doc[tag.end():end if end >= 0 else len(doc)]
        if "媒体/图片/" not in inner:
            scenes_without_image.append(sid_match.group(1) if sid_match else "?")
    if scenes_without_image:
        blocking.append("这些场景没有图片（画面只剩文字和背景）：" + "、".join(scenes_without_image[:8]))
    if re.search(r"<canvas\b", doc, re.I) and image_refs:
        errors.append("HTML 里同时有 canvas 和照片：具象视觉归照片，canvas 只留背景氛围")

    body = doc[doc.lower().find("<body"):] if "<body" in doc.lower() else doc
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", body, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(re.sub(r"\s+", " ", text)).strip()
    # 渲染器找不到 composition、或产物结构残缺时致命；版面/密度问题只报告。
    fatal = blocking + [item for item in errors if any(key in item for key in (
        "缺少完整 HTML 文档头", "data-composition-id", "data-duration",
    ))]
    if fatal:
        print("HTML CONTRACT: FAIL (fatal)")
        for error in fatal:
            print("reason:", error)
        raise SystemExit(1)
    if errors:
        print("HTML CONTRACT: WARN —— %d 条问题，不阻塞渲染" % len(errors))
        for error in errors:
            print("warn:", error)
    print("HTML CONTRACT: PASS")
    print("visible_text_chars:", len(text))
    print("media_count:", len(media))
    print("media_duration:", durations[0] if durations else "(none)")

if __name__ == "__main__":
    main()
