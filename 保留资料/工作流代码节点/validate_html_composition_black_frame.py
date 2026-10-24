def main(html_document: str, production_requirements: str) -> dict:
    import json
    import re

    html = str(html_document or "")
    errors = []
    warnings = []
    if not re.search(r'<div\b[^>]*\bid=["\']stage["\'][^>]*\bdata-composition-id=', html, re.I):
        errors.append("根 composition 必须直接挂在 #stage")
    if "performance.now(" in html or "requestAnimationFrame(" in html:
        errors.append("禁止 performance.now/requestAnimationFrame，必须由 HyperFrames 时间线驱动")
    if "Math.random(" in html:
        errors.append("禁止运行时 Math.random，随机性只能是作者期变体选择")
    if not re.search(r'window\.__timelines', html):
        errors.append("缺少 window.__timelines 注册的可寻址时间线")
    if not re.search(r'\b(?:master|timeline)\.(?:from|fromTo|to|set)\s*\(|\bgsap\.set\s*\(', html):
        errors.append("缺少时间线驱动的 GSAP from/fromTo/to/set 动作调用")
    if not re.search(r'(?:const|var)\s+at\s*=', html) or not re.search(r'\}\s*,\s*at\(', html):
        errors.append("所有 GSAP 时间位置必须使用 at()")
    if "<!doctype html>" not in html.lower():
        errors.append("缺少完整 HTML 文档头")
    for token in [
        "data-composition-id", "data-width", "data-height", "data-duration",
        "CAPTIONS_START", "CAPTIONS_END", "data-caption-sync",
        "fitRootToViewport", "data-authoring-duration", "data-timeline-scale",
    ]:
        if token not in html:
            errors.append("缺少 " + token)
    if not re.search(r"width:\s*1080px[\s\S]*height:\s*1920px", html):
        errors.append("根画布必须固定为 CSS 1080×1920")
    if re.search(r'width\s*:\s*1920px|height\s*:\s*1080px|data-width="1920"|data-height="1080"', html):
        errors.append("禁止横屏/16:9 画布，必须是 1080×1920 竖屏")
    for token in (
        "bottom:24%", "width:62%", "max-width:62%", "font-size:37px",
        "line-height:1.35", "font-weight:700", "background:rgba(6,10,20,.72)",
    ):
        if token not in html:
            errors.append("字幕契约缺少 " + token)
    if "data-start" not in html or "data-duration" not in html:
        errors.append("缺少时间片段属性")
    if not re.search(r'class=["\'][^\'"]*\bscene\b', html):
        errors.append("缺少 scene 时间片段")
    scene_tags = re.findall(r'<(?:section|div)\b(?=[^>]*class=["\'][^"\']*\bscene\b)[^>]*>', html, flags=re.I)
    if any(not re.search(r'(?<![\w-])id="[^"]+"', tag) for tag in scene_tags):
        errors.append("每个 scene 必须有稳定 id")
    if any(not re.search(r'\bdata-sentence-ids="[^"]+"', tag) for tag in scene_tags):
        errors.append("每个 scene 必须包含 data-sentence-ids 以绑定已批准句子")
    if not re.search(r'class=["\'][^"\']*\bcaption\b[^"\']*["\'][^>]*data-sentence-id=', html, re.I):
        errors.append("字幕必须包含 data-sentence-id 以绑定已批准句子")
    root_duration_match = re.search(r'\bdata-duration="([0-9.]+)"', html)
    root_duration = float(root_duration_match.group(1)) if root_duration_match else 0.0
    scene_end = 0.0
    for tag in scene_tags:
        start = re.search(r'\bdata-start="([0-9.]+)"', tag)
        duration = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if start and duration:
            scene_end = max(scene_end, float(start.group(1)) + float(duration.group(1)))
    if root_duration and abs(scene_end - root_duration) > 0.05:
        errors.append("场景总时长与根 data-duration 不一致")
    if re.search(r'(?<!data-)(?<!data-media-)src\s*=\s*["\'](?:媒体|素材)/', html):
        errors.append("H01 输出不得直接引用本地媒体，必须使用 data-media-src 占位")
    if not re.search(r'<template[^>]+data-media-type="audio"[^>]+data-audio-role="voiceover"[^>]*>', html, re.I):
        errors.append("口播必须使用预览安全的 template 媒体占位")
    if 'data-render-mode="black-frame"' not in html:
        errors.append("缺少 data-render-mode=black-frame")
    if re.search(r'\.(?:black-frame|avatar-window|avatar-zone)\s*(?:::(?:before|after))?\s*\{', html, re.I):
        errors.append("无数字人模式不得保留黑帧/数字人占位 CSS 或布局避让规则")
    kicker_shift = re.search(r'\.kicker\s*\{[^}]*\bleft:\s*(\d+)px', html, re.I)
    if kicker_shift and int(kicker_shift.group(1)) >= 300:
        errors.append("顶部内容仍向右避让旧数字人/黑帧占位")
    avatar_tag = r'<(?:video|template|div)\b[^>]*(?:data-video-role="avatar"|data-media-id="heygen_avatar"|class="[^"]*(?:avatar-window|black-frame))'
    if re.search(avatar_tag, html, re.I):
        errors.append("无数字人模式不得包含数字人媒体、avatar 角色、数字人窗口或黑帧占位")
    if 'data-audio-role="voiceover"' not in html:
        errors.append("必须保留独立口播音频图层 data-audio-role=\"voiceover\"")
    if 'data-audio-role="background-music"' not in html:
        warnings.append("未发现背景音乐图层")
    for token in ["VIDEO_WORKER", "production-jobs", "webhook"]:
        if token.lower() in html.lower():
            errors.append("HTML 中不应引用 Worker/生产接口：" + token)
    if len(html) > 800000:
        warnings.append("HTML 体积较大，建议拆分为模板和数据")

    return {
        "html_valid": not errors,
        "html_errors_json": json.dumps(errors, ensure_ascii=False),
        "html_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "production_requirements": str(production_requirements or "")
    }
