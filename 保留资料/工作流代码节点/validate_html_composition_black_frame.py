def main(html_document: str, production_requirements: str) -> dict:
    import json
    import re

    html = str(html_document or "")
    errors = []
    warnings = []
    if not re.search(r'<div\b[^>]*\bid=["\']stage["\'][^>]*\bdata-composition-id=', html, re.I):
        errors.append("根 composition 必须直接挂在 #stage，不能只放在内层 div")
    if "performance.now(" in html or "requestAnimationFrame(" in html:
        errors.append("禁止 performance.now/requestAnimationFrame，必须由 HyperFrames 时间线驱动")

    if "<!doctype html>" not in html.lower():
        errors.append("缺少完整 HTML 文档头")
    for token in [
        "data-composition-id", "data-width", "data-height", "data-duration",
        "window.__timelines", "CAPTIONS_START", "CAPTIONS_END", "data-caption-sync",
        "fitRootToViewport", "data-authoring-duration", "data-timeline-scale",
    ]:
        if token not in html:
            errors.append("缺少 " + token)
    if not re.search(r"width:\s*1080px[\s\S]*height:\s*1920px", html):
        errors.append("根画布必须固定为 CSS 1080×1920")
    if re.search(r'width\s*:\s*1920px|height\s*:\s*1080px|data-width="1920"|data-height="1080"', html):
        errors.append("禁止横屏/16:9 画布，必须是 1080×1920 竖屏")
    if 'data-render-mode="black-frame"' not in html:
        errors.append("缺少无数字人模式标记 data-render-mode=\"voice-only\"")
    if not re.search(r'\.avatar-black-frame\s*\{[^}]*top:\s*96px[^}]*right:\s*48px[^}]*width:\s*214px[^}]*height:\s*380px[^}]*background:\s*#000', html, re.I):
        errors.append("缺少固定 214×380 的右上角纯黑帧 .avatar-black-frame")
    if 'data-video-role="avatar"' in html or 'data-media-id="heygen_avatar"' in html or '.avatar-window' in html:
        errors.append("黑帧模式不得包含数字人媒体、avatar 角色或数字人窗口")
    if 'data-audio-role="voiceover"' not in html:
        errors.append("必须保留独立口播音频图层 data-audio-role=\"voiceover\"")
    if 'data-audio-role="background-music"' not in html:
        warnings.append("未发现背景音乐图层")
    if not re.search(r'<template[^>]+data-media-type="audio"[^>]+data-audio-role="voiceover"[^>]*>', html, re.I):
        errors.append("口播必须使用预览安全的 template 媒体占位")
    if re.search(r'(?<!data-)(?<!data-media-)src\s*=\s*["\'](?:媒体|素材)/', html):
        errors.append("H01 输出不得直接引用本地媒体，必须使用 data-media-src 占位")
    if not re.search(r'class=["\'][^["\']*\bclip\b', html):
        errors.append("缺少 clip 时间片段")
    if "data-start" not in html or "data-duration" not in html:
        errors.append("缺少时间片段属性")
    if html.count('data-coverage="full"') < 5:
        errors.append("五个场景都必须使用 data-coverage=\"full\" 全高布局")
    if not re.search(r'height:\s*100%', html):
        errors.append("场景内容未声明 height:100%，不能只占画面局部")
    if not re.search(r'justify-content:\s*center', html):
        errors.append("主要内容必须在安全可视区域内垂直居中")
    scene_chunks = re.split(r'<(?:section|div)\b[^>]*class=["\'][^"\']*\bscene\b', html, flags=re.I)[1:]
    if len(scene_chunks) < 5:
        errors.append("至少需要5个独立场景")
    component_pattern = r'class=["\'][^"\']*(?:card|panel|tool|step|metric|cmp-item|cmp-list|status|chip|flow|grid|list|cta)'
    for scene_index, scene_html in enumerate(scene_chunks, 1):
        scene_html = re.split(r'<!--\s*CAPTIONS_START|class=["\']caption-layer', scene_html, maxsplit=1, flags=re.I)[0]
        component_count = len(re.findall(component_pattern, scene_html, re.I))
        visible_text = re.sub(r'<[^>]+>', ' ', scene_html)
        text_chars = len(re.sub(r'\s+', '', visible_text))
        component_types = set(re.findall(component_pattern, scene_html, re.I))
        if component_count < 8:
            errors.append(f"场景{scene_index}组件不足：至少需要8个可见组件节点，当前只有{component_count}个")
        if len(component_types) < 3:
            errors.append(f"场景{scene_index}组件类型不足：至少需要3类卡片、列表、流程、指标、工具或CTA组件")
        if text_chars < 80:
            errors.append(f"场景{scene_index}信息量不足：可见文字至少80字，当前只有{text_chars}字")
    traditional_chars = "個們這為與後時問體驗網絡數據臺灣點擊開團隊發現溝銷線錄"
    used = sorted(set(html) & set(traditional_chars))
    if used:
        errors.append("HTML 文案必须使用简体中文，发现繁体字：" + "".join(used))

    for token in ["VIDEO_WORKER", "production-jobs", "webhook"]:
        if token.lower() in html.lower():
            errors.append("HTML 中不应引用 Worker/生产接口：" + token)
    if not re.search(r'(?:const|var)\s+at\s*=', html) or not re.search(r'\}\s*,\s*at\(', html):
        errors.append("所有 GSAP 时间位置必须使用 at()")
    if not re.search(r"(gsap|__timelines)", html, re.I):
        errors.append("未发现可寻址时间线")
    if len(html) > 800000:
        warnings.append("HTML 体积较大，建议拆分为模板和数据")

    return {
        "html_valid": not errors,
        "html_errors_json": json.dumps(errors, ensure_ascii=False),
        "html_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "production_requirements": str(production_requirements or "")
    }

