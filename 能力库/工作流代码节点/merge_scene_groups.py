def main(skeleton_html: str, group_a: str, group_b: str, group_c: str, group_d: str, scene_total: int) -> dict:
    import json
    import re

    html = str(skeleton_html or "")
    warnings = []
    for marker, part, label in (
        ("<!-- SCENES_A -->", group_a, "A"),
        ("<!-- SCENES_B -->", group_b, "B"),
        ("<!-- SCENES_C -->", group_c, "C"),
        ("<!-- SCENES_D -->", group_d, "D"),
    ):
        body = str(part or "").strip()
        if marker not in html:
            warnings.append("骨架缺少占位 " + marker)
            continue
        if not body:
            warnings.append("场景组 " + label + " 为空")
            body = "<!-- empty group " + label + " -->"
        if "DOMContentLoaded" in body or "window.onload" in body:
            warnings.append("场景组 " + label + " 的脚本包了 DOMContentLoaded/onload，builder 不会执行")
        html = html.replace(marker, body, 1)

    # 只包装"裸的"场景脚本。骨架主脚本、以及任何已经接触
    # __sceneBuilders / __timelines / gsap.timeline 的脚本必须原样保留，
    # 否则主时间线永远不会被创建，整片静止。
    def wrap_scripts(text):
        def repl(match):
            code = match.group(1)
            if "timeline." not in code:
                return match.group(0)
            if "__sceneBuilders" in code or "__timelines" in code or "gsap.timeline(" in code:
                return match.group(0)
            return "<script>window.__sceneBuilders.push(function(timeline, at){" + code + "});</script>"
        return re.sub(r"<script>(.*?)</script>", repl, text, flags=re.S | re.I)

    html = wrap_scripts(html)

    if "gsap.timeline(" not in html:
        warnings.append("合并后的 HTML 没有任何 gsap.timeline 创建，整片不会是动画")
    if "__timelines" not in html:
        warnings.append("合并后的 HTML 没有 window.__timelines 注册，渲染器找不到时间线")

    def scene_tags_in(text):
        """只认 class 里独立成词的 scene，避免把 gD-scene 这类前缀类名当成场景。"""
        tags = []
        for tag in re.findall(r'<(?:section|div)\b[^>]*>', text, flags=re.I):
            match = re.search(r'class=["\']([^"\']*)["\']', tag)
            if match and "scene" in match.group(1).split():
                tags.append(tag)
        return tags

    # ---- 动效覆盖率：动作选择器是否能在 markup 里找到目标 ----
    def class_exists(cls):
        return re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b', html) is not None

    def selector_exists(selector):
        tokens = re.findall(r'\[data-[\w-]+="[^"]*"\]|#[\w-]+|\.[\w-]+', selector)
        if not tokens:
            return False
        for token in tokens:
            if token.startswith("["):
                if token not in html:
                    return False
            elif token.startswith("#"):
                if 'id="' + token[1:] + '"' not in html:
                    return False
            elif not class_exists(token[1:]):
                return False
        return True

    def scan(body):
        scripts = re.findall(r"<script[^>]*>(.*?)</script>", body, flags=re.S | re.I)
        selectors = []
        for code in scripts:
            selectors.extend(re.findall(r"timeline\.(?:from|to|fromTo|set)\(\s*['\"]([^'\"]+)['\"]", code))
        unmatched = [s for s in selectors if not selector_exists(s)]
        return len(selectors), unmatched

    report = {}
    for label, part in (("A", group_a), ("B", group_b), ("C", group_c), ("D", group_d)):
        body = str(part or "")
        total, unmatched = scan(body)
        scene_tags = scene_tags_in(body)
        markup = re.sub(r"<script\b.*?</script>", "", body, flags=re.S | re.I)
        script_text = "".join(re.findall(r"<script\b.*?</script>", body, flags=re.S | re.I))
        anim_names = re.findall(r'\bdata-anim="([^"]*)"', markup)
        anim_elements = len(anim_names)
        selectors = [m.group(2) for m in re.finditer(r"(?:from|to|fromTo|set)\(\s*(['\"])(.+?)\1", body, re.S)]
        dynamic = bool(re.search(r"['\"]\s*\+|\+\s*['\"]|`", script_text))
        animated_names = {name for name in anim_names if any('data-anim="' + name + '"' in sel for sel in selectors)}
        uncovered = [] if dynamic else sorted(set(anim_names) - animated_names)
        coverage = None if (dynamic or not anim_elements) else round(len(animated_names) / float(anim_elements), 3)
        report[label] = {
            "actions": total,
            "unmatched": unmatched,
            "scenes": len(scene_tags),
            "anim_elements": anim_elements,
            "animated_elements": len(animated_names),
            "coverage": coverage,
            "uncovered": uncovered[:8],
            "per_scene_ok": bool(scene_tags) and total >= 2 * len(scene_tags),  # 仅作参考信号
        }
        if total == 0:
            warnings.append("场景组 " + label + " 没有任何 timeline 动作")
        elif unmatched:
            warnings.append("场景组 " + label + " 有 %d 个动作选择器找不到目标：%s" % (len(unmatched), "、".join(unmatched[:3])))
        elif scene_tags and total < 2 * len(scene_tags) and anim_elements < 2 * len(scene_tags):
            warnings.append("场景组 " + label + " 只有 %d 个动作、%d 个场景，动效偏少（只提示，不拦截）" % (total, len(scene_tags)))
        if scene_tags and anim_elements == 0:
            warnings.append("场景组 " + label + " 没有任何 data-anim 标记，动效契约未执行")
        elif uncovered:  # 只有静态选择器才判断覆盖率，动态拼接的选择器跳过
            warnings.append("场景组 " + label + " 有 %d 个组件从头到尾没有动作：%s" % (len(uncovered), "、".join(uncovered[:4])))

    leftovers = re.findall(r"<!-- SCENES_[ABCD] -->", html)
    if leftovers:
        warnings.append("仍有未替换的占位：" + "、".join(sorted(set(leftovers))))
    scenes = scene_tags_in(html)
    ids = [m.group(1) for tag in scenes for m in [re.search(r'\bid="([^"]+)"', tag)] if m]
    duplicated = sorted({x for x in ids if ids.count(x) > 1})
    if duplicated:
        warnings.append("scene id 重复：" + "、".join(duplicated))
    if scene_total and len(scenes) != scene_total:
        warnings.append("场景数量 %d 与分镜 %d 不一致" % (len(scenes), scene_total))
    if "<!doctype html>" not in html.lower() or "</html>" not in html.lower():
        raise ValueError("合并后的 HTML 不完整")
    return {
        "html_document": html,
        "merge_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "motion_report_json": json.dumps(report, ensure_ascii=False),
        "scene_count": len(scenes),
    }
