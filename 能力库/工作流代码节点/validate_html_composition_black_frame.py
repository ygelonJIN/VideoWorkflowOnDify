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

    # 本地不再替页面切场景显隐，页面必须自己按 data-start/data-duration 驱动，
    # 否则所有 scene 会同时叠在画布上（成片是九屏混在一起）。
    scene_tags = [tag for tag in re.findall(r"<(?:section|div)\b[^>]*>", html, flags=re.I)
                  if "scene" in (re.search(r'class=["\']([^"\']*)["\']', tag).group(1).split()
                                 if re.search(r'class=["\']([^"\']*)["\']', tag) else [])]
    if len(scene_tags) >= 2:
        scripts = "\n".join(re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", html, flags=re.I))
        reads_window = "data-start" in scripts and "data-duration" in scripts
        writes_visibility = re.search(r"visibility|opacity|clip-path|clipPath|display|translate|scale", scripts) is not None
        if not (reads_window and writes_visibility):
            errors.append("没有场景显隐驱动：页面必须自己按 data-start/data-duration 决定每屏何时可见（本地已不兜底）")
        elif not re.search(r"\[data-scene|\\.scene", scripts):
            warnings.append("场景显隐驱动没有按 [data-scene] / .scene 选择场景，需人工确认")
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
    # 字幕由本地 sync_video.py 注入（13% / 45px / 无底板），HTML 里不该写字幕样式
    if re.search(r'\.caption\b|#captions\b', html):
        warnings.append("HTML 里出现了字幕样式或容器：字幕由本地注入，模型不应写")
    if "data-start" not in html or "data-duration" not in html:
        warnings.append("缺少时间片段属性")
    if not re.search(r'class=["\'][^\'"]*\bscene\b', html):
        warnings.append("缺少 scene 时间片段")
    def scene_is(tag):
        match = re.search(r'class=["\']([^"\']*)["\']', tag)
        return bool(match) and "scene" in match.group(1).split()

    scene_tags = [tag for tag in re.findall(r'<(?:section|div)\b[^>]*>', html, flags=re.I) if scene_is(tag)]
    scene_names = [m.group(1) for tag in scene_tags for m in [re.search(r'\bdata-scene=["\']([^"\']+)["\']', tag)] if m]
    duplicated_scenes = sorted({name for name in scene_names if scene_names.count(name) > 1})
    if duplicated_scenes:
        errors.append("scene id 重复（同一屏被合并了多次，成片会出现重复/空背景）：" + "、".join(duplicated_scenes[:8]))
    # 本地 sync_video.py 会给每个 scene 补 id="scene-<名字>"，这里只提示不拦截
    if any(not re.search(r'(?<![\w-])id="[^"]+"', tag) for tag in scene_tags):
        warnings.append("部分 scene 没有 id（本地渲染前会补齐）")
    if any(not re.search(r'\bdata-sentence-ids="[^"]+"', tag) for tag in scene_tags):
        warnings.append("每个 scene 必须包含 data-sentence-ids 以绑定已批准句子")
    # 字幕块由本地 sync_video.py 按真实时间码重建，Dify 阶段不强制
    if not re.search(r'class=["\'][^"\']*\bcaption\b[^"\']*["\'][^>]*data-sentence-id=', html, re.I):
        warnings.append("字幕块没有 data-sentence-id（本地渲染前会按真实时间码重建）")
    root_duration_match = re.search(r'\bdata-duration="([0-9.]+)"', html)
    root_duration = float(root_duration_match.group(1)) if root_duration_match else 0.0
    scene_end = 0.0
    for tag in scene_tags:
        start = re.search(r'\bdata-start="([0-9.]+)"', tag)
        duration = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if start and duration:
            scene_end = max(scene_end, float(start.group(1)) + float(duration.group(1)))
    if root_duration and abs(scene_end - root_duration) > 0.05:
        warnings.append("场景总时长与根 data-duration 相差 %.2f 秒（本地会按真实口播重排）" % abs(scene_end - root_duration))
    if re.search(r'(?<!data-)(?<!data-media-)src\s*=\s*["\'](?:媒体|素材)/[^"\']*\.(?:mp3|mp4|m4a|wav|png|jpe?g|webp|gif)', html, re.I):
        warnings.append("H01 输出不得直接引用本地媒体，必须使用 data-media-src 占位")
    # 媒体占位由本地 ensure_media_placeholders 兜底重建；属性不全只提示
    if not re.search(r'<template[^>]*data-media-type=["\']audio["\'][^>]*>', html, re.I):
        warnings.append("缺少 audio 媒体占位（本地会补标准占位）")
    elif not re.search(r'<template[^>]*data-media-type=["\']audio["\'][^>]*data-(?:audio|media)-role=["\']voiceover["\']', html, re.I):
        warnings.append("口播占位没写 data-audio-role=\"voiceover\"（本地会补标准占位）")
    if 'data-render-mode="black-frame"' not in html:
        warnings.append("缺少 data-render-mode=black-frame（本地会按媒体文件推断模式，不拦截）")
    if re.search(r'\.(?:black-frame|avatar-window|avatar-zone)\s*(?:::(?:before|after))?\s*\{', html, re.I):
        warnings.append("无数字人模式不得保留黑帧/数字人占位 CSS 或布局避让规则")
    kicker_shift = re.search(r'\.kicker\s*\{[^}]*\bleft:\s*(\d+)px', html, re.I)
    if kicker_shift and int(kicker_shift.group(1)) >= 300:
        warnings.append("顶部内容仍向右避让旧数字人/黑帧占位")
    avatar_tag = r'<(?:video|template|div)\b[^>]*(?:data-video-role="avatar"|data-media-id="heygen_avatar"|class="[^"]*(?:avatar-window|black-frame))'
    if re.search(avatar_tag, html, re.I):
        warnings.append("无数字人模式不得包含数字人媒体、avatar 角色、数字人窗口或黑帧占位")
    if 'data-audio-role="voiceover"' not in html and 'data-media-role="voiceover"' not in html:
        warnings.append("未发现口播图层标记（本地会补 data-audio-role=voiceover）")
    if 'data-audio-role="background-music"' not in html:
        warnings.append("未发现背景音乐图层")
    for token in ["VIDEO_WORKER", "production-jobs", "webhook"]:
        if token.lower() in html.lower():
            warnings.append("HTML 中不应引用 Worker/生产接口：" + token)
    # ---- 画面承担者契约：照片屏必须有 {{IMG}}，无图屏必须声明 data-visual="html" ----
    image_refs = sorted(set(re.findall(r"\{\{IMG:([A-Za-z0-9_-]+)\}\}", html)))
    if not image_refs:
        errors.append("整份 HTML 没有任何 {{IMG:图片id}} 引用：整片至少需要一张真实照片；无图屏用 data-visual=\"html\" + data-anim=\"bg\"")
    scenes_without_image = []
    html_scenes = []
    for tag in re.finditer(r"<(?:section|div)\b[^>]*>", html, flags=re.I):
        head = tag.group(0)
        cls = re.search(r'class=["\']([^"\']*)["\']', head)
        if not cls or "scene" not in cls.group(1).split():
            continue
        sid = re.search(r'data-scene=["\']([^"\']+)["\']', head)
        scene_id = sid.group(1) if sid else "?"
        visual = re.search(r'data-visual=["\']([^"\']+)["\']', head)
        visual = visual.group(1).strip().lower() if visual else ""
        end = html.find("</section>", tag.end())
        inner = html[tag.end():end if end >= 0 else len(html)]
        has_image = re.search(r"\{\{IMG:[A-Za-z0-9_-]+\}\}", inner) is not None
        if visual == "html":
            html_scenes.append(scene_id)
            if not re.search(r'data-anim=["\']bg["\']', inner):
                warnings.append("%s 声明了 data-visual=html，但没有 data-anim=bg 背景层" % scene_id)
            if has_image:
                warnings.append("%s 声明了 data-visual=html，却也放了 {{IMG:...}} 图片" % scene_id)
        elif not has_image:
            scenes_without_image.append(scene_id)
    if scenes_without_image:
        errors.append("这些场景没有 {{IMG:...}} 图片，也没有 data-visual=\"html\"：%s" % "、".join(scenes_without_image[:8]))
    if html_scenes and not image_refs:
        errors.append("全片都是无图屏（%d 屏）：至少保留一张真实照片" % len(html_scenes))
    if re.search(r"<canvas\b", html, re.I):
        warnings.append("HTML 里出现 canvas：具象视觉必须由照片承担，canvas 只允许做背景氛围")
    if re.search(r"<svg\b", html, re.I):
        warnings.append("HTML 里出现内联 SVG：插画/示意图/图标应由照片替代，只保留线条与排版")
    if re.search(r"class=[\"'][^\"']*\b(?:chart|diagram|illustration|icon-)\b", html, re.I):
        warnings.append("HTML 里出现图表/示意/插画类 class：这类图形应换成照片")
    if "媒体/图片/" in html or "素材/图片/" in html:
        warnings.append("图片路径必须写 {{IMG:图片id}}，本地渲染前才替换成真实文件")

    if len(html) > 800000:
        warnings.append("HTML 体积较大，建议拆分为模板和数据")

    return {
        "html_valid": not errors,
        "html_errors_json": json.dumps(errors, ensure_ascii=False),
        "html_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "production_requirements": str(production_requirements or "")
    }
