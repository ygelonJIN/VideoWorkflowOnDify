def main(skeleton_html: str, group_a: str, group_b: str, group_c: str, group_d: str, motion_script: str, transition_script: str, scene_total: int, image_plan_json: str = "") -> dict:
    import json
    import re

    html = str(skeleton_html or "")
    warnings = []

    def strip_scripts(text, label):
        """只移除场景组里误写的 GSAP 时间线脚本；canvas / 三维的模块脚本必须保留。"""
        removed = 0

        def _keep(match):
            nonlocal removed
            block = match.group(0)
            head = match.group(1).lower()
            body = match.group(2)
            is_module = "module" in head
            uses_seek = "hf-seek" in body
            if is_module or uses_seek:
                return block
            if "timeline." in body:
                removed += 1
                return ""
            return block

        text = re.sub(r"(<script\b[^>]*>)([\s\S]*?)</script>", _keep, text, flags=re.I)
        if removed:
            warnings.append("场景组 " + label + " 误写了 GSAP 时间线脚本，已移除（动效应由动效节点统一写）")
        return text

    groups = {}
    for label, part in (("A", group_a), ("B", group_b), ("C", group_c), ("D", group_d)):
        body = strip_scripts(str(part or "").strip(), label).strip()
        groups[label] = body
        marker = "<!-- SCENES_" + label + " -->"
        if marker not in html:
            warnings.append("骨架缺少占位 " + marker)
            continue
        if not body:
            warnings.append("场景组 " + label + " 为空")
            body = "<!-- empty group " + label + " -->"
        html = html.replace(marker, body, 1)

    # 场景 id 清单：用于把 #s01 这类失效锚点改写成 [data-scene="s01"]
    known_scene_ids = []
    for body in groups.values():
        for tag in re.finditer(r"<(?:section|div)\b[^>]*>", body, flags=re.I):
            sid = re.search(r'data-scene=["\']([^"\']+)["\']', tag.group(0))
            if sid and sid.group(1) not in known_scene_ids:
                known_scene_ids.append(sid.group(1))

    # ---- 脚本插入（页内动效 / 页间转场各占一个槽位）----
    def place_script(raw, label, marker, empty_comment):
        nonlocal html
        code = str(raw or "").strip()
        bodies = re.findall(r"<script\b[^>]*>([\s\S]*?)</script>", code, flags=re.I)
        code = "\n".join(bodies).strip() if bodies else code
        rewritten = []
        for sid in known_scene_ids:
            # 本地同步阶段会把 section 的 id 改写成 scene-<id>，所以 #<id> 一律改写，
            # 不再"看到 HTML 里有 id 就跳过"——那会在渲染前一刻失效。
            pattern = re.compile(r"#%s(?![\w-])" % re.escape(sid))

            def _swap(match, _sid=sid):
                head = match.string[:match.start()]
                last_double, last_single = head.rfind('"'), head.rfind("'")
                outer = '"' if last_double > last_single else "'"
                quote = "'" if outer == '"' else '"'
                return "[data-scene=%s%s%s]" % (quote, _sid, quote)

            if pattern.search(code):
                code = pattern.sub(_swap, code)
                rewritten.append(sid)
        if rewritten:
            warnings.append(label + "用了 #场景ID 选择器，已改写为 [data-scene=...]：" + "、".join(rewritten))
        if code and "__sceneBuilders" not in code:
            warnings.append(label + "没有 window.__sceneBuilders.push，动作不会执行")
        if re.search(r"yoyo|repeat\s*:|repeatDelay|infinite", code, flags=re.I):
            warnings.append(label + "出现 yoyo/repeat/infinite（禁止循环动画），请检查")
        if re.search(r"Math\.random|performance\.now|requestAnimationFrame|setTimeout", code):
            warnings.append(label + "出现禁止的运行时 API（随机、墙钟或 rAF/setTimeout）")
        block = ("<script>\n" + code + "\n</script>") if code else empty_comment
        if marker in html:
            html = html.replace(marker, block, 1)
        else:
            warnings.append("骨架缺少占位 " + marker + "，" + label + "已插入到主时间线脚本之前")
            pos = html.find("__timelines")
            start_at = html.rfind("<script", 0, pos) if pos >= 0 else -1
            if start_at < 0:
                start_at = html.lower().rfind("</body>")
            if start_at < 0:
                html = html + "\n" + block
            else:
                html = html[:start_at] + block + "\n" + html[start_at:]
        return code

    motion_code = place_script(motion_script, "动效脚本", "<!-- MOTION_SCRIPTS -->", "<!-- no motion -->")
    place_script(transition_script, "转场脚本", "<!-- TRANSITION_SCRIPTS -->", "<!-- no transition -->")

    if "__timelines" not in html:
        warnings.append("合并后的 HTML 没有 window.__timelines 注册，渲染器找不到时间线")

    # ---- 报告：每组的动作、覆盖、密度 ----
    def scene_blocks(text):
        """返回 [(scene_id, 该 scene 的内部 HTML)]，只认 class 里独立成词的 scene。"""
        blocks = []
        for match in re.finditer(r"<(?:section|div)\b[^>]*>", text, flags=re.I):
            tag = match.group(0)
            cls = re.search(r'class=["\']([^"\']*)["\']', tag)
            if not cls or "scene" not in cls.group(1).split():
                continue
            sid = re.search(r'data-scene=["\']([^"\']+)["\']', tag) or re.search(r'\bid=["\']([^"\']+)["\']', tag)
            end = text.find("</section>", match.end())
            inner = text[match.end():end if end >= 0 else len(text)]
            blocks.append((sid.group(1) if sid else "", inner))
        return blocks

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

    # 展开 `var s1 = '...'` 这类字符串变量，再按字面量统计；模型用变量拼接选择器也能被统计到。
    string_vars = {}
    for name, _quote, value in re.findall(r"(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*(['\"])((?:(?!\2).)*)\2", motion_code):
        string_vars[name] = value
    def expand(line):
        for name in sorted(string_vars, key=len, reverse=True):
            line = re.sub(r"(?<![\w$.])" + re.escape(name) + r"(?![\w$])", "'" + string_vars[name].replace("'", "") + "'", line)
        return line
    lines = [expand(ln) for ln in motion_code.splitlines() if "timeline." in ln]
    STATE_KEYS = ("scale", "color", "backgroundColor", "borderColor", "width", "height",
                  "strokeDashoffset", "x", "rotation", "value", "v")
    report = {}
    for label in ("A", "B", "C", "D"):
        body = groups[label]
        blocks = scene_blocks(body)
        scene_ids = [sid for sid, _ in blocks if sid]
        def belongs(ln, sid):
            return re.search(
                r"data-scene=[\"']" + re.escape(sid) + r"[\"']|[.#](?:[\w]+-)?(?:scene-)?" + re.escape(sid) + r"(?![\w-])",
                ln,
            ) is not None
        group_lines = [ln for ln in lines if any(belongs(ln, sid) for sid in scene_ids)]
        selectors = []
        for ln in group_lines:
            m = re.search(r"timeline\.(?:from|to|fromTo|set)\(([\s\S]*?)(?:,\s*\{|,\s*at\(|\)\s*;?\s*$)", ln)
            if not m:
                continue
            pieces = re.findall(r"(['\"])((?:(?!\1).)+)\1", m.group(1))
            joined = "".join(piece for _q, piece in pieces)
            if joined:
                selectors.append(joined)
        anim_names = sorted(set(re.findall(r'data-anim="([^"]*)"', body)))
        targeted = set()
        for sel in selectors:
            n = re.search(r'data-anim="([^"]+)"', sel)
            if n:
                targeted.add(n.group(1))
        enter_count = sum(1 for ln in group_lines if "timeline.from(" in ln or "timeline.fromTo(" in ln)
        state_count = sum(1 for ln in group_lines if any(('"%s"' % k) in ln or (" %s:" % k) in ln or ("{%s:" % k) in ln or (",%s:" % k) in ln for k in STATE_KEYS))
        unmatched = [sel for sel in selectors if not selector_exists(sel)]
        density = []
        for sid, inner in blocks:
            elements = len(re.findall(r"<(?!/)(?!script|style|!)[a-zA-Z][\w-]*\b", inner))
            density.append({"scene": sid, "elements": elements})
        report[label] = {
            "scenes": len(blocks),
            "actions": len(group_lines),
            "enter_actions": enter_count,
            "state_actions": state_count,
            "unmatched": unmatched[:6],
            "anim_elements": len(anim_names),
            "animated_elements": len(targeted),
            "coverage": round(len(targeted) / float(len(anim_names)), 3) if (anim_names and targeted) else None,
            "uncovered": sorted(set(anim_names) - targeted)[:8],
            "density": density,
        }
        if not blocks:
            warnings.append("场景组 " + label + " 没有任何 scene")
        if blocks and not group_lines:
            warnings.append("场景组 " + label + " 没有任何动效动作")
        if unmatched:
            warnings.append("场景组 " + label + " 有 %d 个动作选择器找不到目标：%s" % (len(unmatched), "、".join(unmatched[:3])))
        if report[label]["uncovered"]:
            warnings.append("场景组 " + label + " 有组件没有动作：%s" % "、".join(report[label]["uncovered"][:4]))

    # 动效引用的 data-anim 是否真的出现在标记里（脚本里的字符串不算）
    markup_only = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
    markup_names = set(re.findall(r'data-anim="([^"]+)"', markup_only))
    referenced = set(re.findall(r'\[data-anim="([^"]+)"\]', motion_code))
    missing_targets = sorted(referenced - markup_names)
    if referenced and len(missing_targets) > max(2, int(len(referenced) * 0.3)):
        warnings.append(
            "动效引用的 data-anim 有 %d/%d 个在页面里不存在（动作会被静默跳过，表现为整片没动效）：%s"
            % (len(missing_targets), len(referenced), "、".join(missing_targets[:6]))
        )

    # ---- 图片覆盖：每一屏都必须有真实图像承担主视觉 ----
    image_ids = sorted(set(re.findall(r"\{\{IMG:([A-Za-z0-9_-]+)\}\}", html)))
    scene_images = {}
    for sid, inner in scene_blocks(html):
        refs = re.findall(r"\{\{IMG:([A-Za-z0-9_-]+)\}\}|媒体/图片/([A-Za-z0-9_-]+)\.(?:png|jpg|jpeg|webp)", inner)
        found = [a or b for a, b in refs]
        scene_images[sid] = sorted(set(found))
    scenes_without_image = sorted(sid for sid, found in scene_images.items() if sid and not found)
    if scenes_without_image:
        warnings.append("这些场景没有配图（画面只剩文字和背景）：" + "、".join(scenes_without_image[:8]))
    if not image_ids and "媒体/图片/" not in html:
        warnings.append("整份 HTML 没有任何图片引用：检查 H01P 图像计划是否被拼进场景组")

    leftovers = re.findall(r"<!-- SCENES_[ABCD] -->", html)
    if leftovers:
        warnings.append("仍有未替换的占位：" + "、".join(sorted(set(leftovers))))
    all_scenes = scene_blocks(html)
    ids = [sid for sid, _ in all_scenes if sid]
    duplicated = sorted({x for x in ids if ids.count(x) > 1})
    if duplicated:
        warnings.append("scene id 重复：" + "、".join(duplicated))
    if scene_total and len(all_scenes) != int(scene_total):
        warnings.append("场景数量 %d 与分镜 %s 不一致" % (len(all_scenes), scene_total))
    if "<!doctype html>" not in html.lower() or "</html>" not in html.lower():
        warnings.append("合并后的 HTML 不完整：骨架或场景组被截断，本地无法渲染")
        return {
            "html_document": "",
            "merge_warnings_json": json.dumps(warnings, ensure_ascii=False),
            "motion_report_json": "{}",
            "scene_count": 0,
            "image_plan_json": str(image_plan_json or ""),
            "image_coverage_json": "{}",
        }
    return {
        "html_document": html,
        "merge_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "motion_report_json": json.dumps(report, ensure_ascii=False),
        "scene_count": len(all_scenes),
        "image_plan_json": str(image_plan_json or ""),
        "image_coverage_json": json.dumps({
            "image_refs": image_ids,
            "scenes": scene_images,
            "scenes_without_image": scenes_without_image,
        }, ensure_ascii=False),
    }
