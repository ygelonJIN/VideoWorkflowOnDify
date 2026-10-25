def main(html_document: str, production_requirements: str) -> dict:
    import json
    import re

    html = str(html_document or "")
    errors = []
    warnings = []
    if "<tool_call>" in html.lower() or re.search(r"<function\s*=", html, re.I):
        errors.append("输出中残留工具调用文本，必须只输出 HTML")
    if not re.search(r'<div\b[^>]*\bid=["\']stage["\']', html, re.I):
        errors.append("缺少 #stage 根画布（本地无法渲染）")
    elif not re.search(r'<div\b[^>]*\bid=["\']stage["\'][^>]*\bdata-composition-id=', html, re.I):
        warnings.append("#stage 没有 data-composition-id（本地会补齐，不拦截）")
    if "performance.now(" in html or "requestAnimationFrame(" in html:
        errors.append("禁止 performance.now/requestAnimationFrame，必须由 HyperFrames 时间线驱动")
    if "Math.random(" in html:
        warnings.append("禁止运行时 Math.random，随机性只能是作者期变体选择")
    if not re.search(r'window\.__timelines', html):
        errors.append("缺少 window.__timelines 注册的可寻址时间线")
    if not re.search(r'(?:^|[\s;{}])(?:[A-Za-z_$][\w$]*\.)*(?:from|fromTo|to|set)\s*\(', html):
        errors.append("缺少时间线驱动的 GSAP from/fromTo/to/set 动作调用")
    if not re.search(r'(?:const|var)\s+at\s*=', html) or not re.search(r'\}\s*,\s*at\(', html):
        warnings.append("所有 GSAP 时间位置必须使用 at()")
    if "<!doctype html>" not in html.lower():
        errors.append("缺少完整 HTML 文档头")
    for token in ["CAPTIONS_START", "CAPTIONS_END"]:
        if token not in html:
            warnings.append("缺少字幕占位 " + token + "（本地会注入字幕容器，不拦截）")
    for token in ["data-composition-id", "data-duration"]:
        if token not in html:
            warnings.append("缺少 " + token + "（本地会补齐，不拦截）")
    # 以下由本地 sync_video.py 在渲染前补齐，Dify 阶段只提示，避免挡掉可渲染的 HTML
    for token in ["data-width", "data-height", "data-caption-sync"]:
        if token not in html:
            warnings.append("缺少 " + token + "（本地会补齐，不拦截）")
    # fitRootToViewport / data-authoring-duration / data-timeline-scale 由本地 sync_video.py
    # 在渲染前注入，Dify 阶段不拦截，避免每次运行都刷屏假错误。
    for token in ["fitRootToViewport", "data-authoring-duration", "data-timeline-scale"]:
        if token not in html:
            warnings.append("缺少 " + token + "（本地渲染前会注入，不拦截）")
    if not re.search(r"width:\s*1080px[\s\S]*height:\s*1920px", html):
        warnings.append("根画布必须固定为 CSS 1080×1920")
    if re.search(r'width\s*:\s*1920px|height\s*:\s*1080px|data-width="1920"|data-height="1080"', html):
        warnings.append("禁止横屏/16:9 画布，必须是 1080×1920 竖屏")
    if "data-start" not in html or "data-duration" not in html:
        warnings.append("缺少时间片段属性")
    if not re.search(r'class=["\'][^\'"]*\bscene\b', html):
        warnings.append("缺少 scene 时间片段")
    if re.search(r'(?<!data-)(?<!data-media-)src\s*=\s*["\'](?:媒体|素材)/[^"\']*\.(?:mp3|mp4|m4a|wav|png|jpe?g|webp|gif)', html, re.I):
        warnings.append("H01 输出不得直接引用本地媒体，必须使用 data-media-src 占位")
    if not re.search(r'<template[^>]+data-media-type="audio"[^>]+data-audio-role="voiceover"[^>]*>', html, re.I):
        warnings.append("口播必须使用预览安全的 template 媒体占位")
    if 'data-audio-role="voiceover"' not in html:
        warnings.append("必须保留独立口播音频图层 data-audio-role=\"voiceover\"")
    if 'data-audio-role="background-music"' not in html:
        warnings.append("未发现背景音乐图层")
    for token in ["VIDEO_WORKER", "production-jobs", "webhook"]:
        if token.lower() in html.lower():
            warnings.append("HTML 中不应引用 Worker/生产接口：" + token)
    if len(html) > 800000:
        warnings.append("HTML 体积较大，建议拆分为模板和数据")

    return {
        "html_valid": not errors,
        "html_errors_json": json.dumps(errors, ensure_ascii=False),
        "html_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "production_requirements": str(production_requirements or "")
    }
