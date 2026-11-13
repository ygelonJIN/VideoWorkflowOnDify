def main(image_plan_text: str, approved_package_json: str) -> dict:
    """归一化图像计划：保证每个分镜都有画面承担者，字段合法，并拆出给 HTML 节点用的精简版。"""
    import json
    import re

    warnings = []
    raw = str(image_plan_text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    plan = None
    if raw:
        try:
            plan = json.loads(raw)
        except Exception as error:
            start = raw.find("{")
            if start >= 0:
                for index in range(len(raw) - 1, start, -1):
                    if raw[index] != "}":
                        continue
                    candidate = re.sub(r",\s*([}\]])", r"\1", raw[start:index + 1])
                    try:
                        plan = json.loads(candidate)
                        break
                    except Exception:
                        continue
            if plan is None:
                warnings.append("图像计划 JSON 无法解析（%s）" % str(error)[:60])
    if not isinstance(plan, dict):
        plan = {}

    try:
        package = json.loads(approved_package_json or "{}")
    except Exception:
        package = {}
    storyboard = package.get("storyboard") if isinstance(package.get("storyboard"), dict) else {}
    scenes = [item for item in (storyboard.get("scenes") or []) if isinstance(item, dict)]

    # html = 这一屏不生成照片，由场景组用 CSS 背景承担画面。
    allowed_roles = {"full", "inset", "portrait", "texture", "html"}
    allowed_sizes = {"1024x1536", "1536x1024", "1024x1024"}
    allowed_motion = {"push-in", "pull-out", "pan-left", "pan-right", "tilt-up", "reveal", "parallax", "hold"}
    allowed_zones = {"top", "bottom", "left", "right", "center"}

    items = plan.get("images") if isinstance(plan.get("images"), list) else []
    by_scene = {}
    cleaned = []
    used_ids = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        scene_id = str(item.get("scene_id") or "").strip()
        image_id = str(item.get("id") or scene_id or "img%02d" % (index + 1)).strip()
        image_id = re.sub(r"[^A-Za-z0-9_-]", "", image_id) or "img%02d" % (index + 1)
        while image_id in used_ids:
            image_id += "_b"
        used_ids.add(image_id)
        role = str(item.get("role") or "full").strip().lower()
        if role not in allowed_roles:
            warnings.append("%s role=%s 已归一化为 full" % (image_id, role))
            role = "full"
        size = str(item.get("size") or "").strip().lower()
        if size not in allowed_sizes:
            size = "1536x1024" if role == "inset" else "1024x1536"
        zone = str(item.get("text_safe_zone") or "").strip().lower()
        if zone not in allowed_zones:
            zone = "center" if role == "html" else "bottom"
        motion = str(item.get("motion_hint") or "").strip().lower()
        if motion not in allowed_motion:
            motion = "reveal" if role == "html" else "hold"
        prompt = str(item.get("prompt") or "").strip()
        subject = str(item.get("subject") or "").strip()
        html_brief = str(item.get("html_brief") or "").strip()
        why = str(item.get("why") or "").strip()
        if role == "html":
            if not html_brief and subject:
                html_brief = subject
            if not html_brief:
                warnings.append("%s 是 html 屏但没有 html_brief：场景组只能按背景语言兜底" % image_id)
        else:
            if not prompt:
                warnings.append("%s 没有 prompt，已用兜底镜头补上" % image_id)
                prompt = (
                    "A quiet photographic scene consistent with the film's established look, "
                    "soft directional daylight from one side, shallow depth of field, "
                    "generous negative space, photographic, no text, no logos."
                )
        entry = {
            "id": image_id,
            "scene_id": scene_id or image_id,
            "role": role,
            "subject": subject,
            "why": why,
            "html_brief": html_brief,
            "prompt": prompt,
            "prompt_zh": str(item.get("prompt_zh") or "").strip(),
            "negative": str(item.get("negative") or "").strip(),
            "size": size,
            "text_safe_zone": zone,
            "motion_hint": motion,
        }
        cleaned.append(entry)
        if scene_id and scene_id not in by_scene:
            by_scene[scene_id] = entry

    prefix = str(plan.get("prompt_prefix") or "").strip()
    if not prefix:
        warnings.append("图像计划没有 prompt_prefix：每张图的风格一致性没有统一来源")

    # 每个分镜都必须有画面承担者。漏掉的屏不再补通用照片（那样只会生成无关画面），
    # 改为补一屏 HTML 背景，交给场景组按本片背景语言做。
    scene_ids = [str(scene.get("scene_id") or "").strip() for scene in scenes]
    missing = []
    for scene in scenes:
        scene_id = str(scene.get("scene_id") or "").strip()
        if not scene_id or scene_id in by_scene:
            continue
        missing.append(scene_id)
        brief = str(scene.get("visual_brief") or scene.get("on_screen_text") or "").strip()[:80]
        entry = {
            "id": scene_id,
            "scene_id": scene_id,
            "role": "html",
            "subject": brief or "按分镜补的无图屏",
            "why": "图像计划漏了这一屏，先用 HTML 背景兜底，避免出现无关照片",
            "html_brief": "按本片 art_direction 的底色、材质和线条做一屏抽象背景，文字为主；不画具象物体。%s" % (brief or ""),
            "prompt": "",
            "prompt_zh": "",
            "negative": "",
            "size": "1024x1536",
            "text_safe_zone": "center",
            "motion_hint": "reveal",
        }
        cleaned.append(entry)
        by_scene[scene_id] = entry
    if missing:
        warnings.append("这些分镜没有配图，已补 HTML 背景兜底：" + "、".join(missing[:8]))

    extra = [entry["scene_id"] for entry in cleaned if entry["scene_id"] and entry["scene_id"] not in scene_ids]
    if extra:
        warnings.append("图像计划里有分镜之外的多余图片（下游不会用）：" + "、".join(sorted(set(extra))[:8]))

    photo_count = sum(1 for entry in cleaned if entry["role"] != "html")
    html_count = sum(1 for entry in cleaned if entry["role"] == "html")
    if photo_count == 0:
        warnings.append("全片没有任何真实照片：至少需要一张，否则会退化成纯文字 PPT")

    ordered = [entry for entry in cleaned if entry["scene_id"] in scene_ids]
    for left, right in zip(ordered, ordered[1:]):
        if left["role"] == right["role"]:
            warnings.append("%s 与 %s 的 role 都是 %s：相邻两屏画面用法重复" % (
                left["scene_id"], right["scene_id"], left["role"]))

    style_bible = plan.get("style_bible") if isinstance(plan.get("style_bible"), dict) else {}
    coverage = plan.get("coverage") if isinstance(plan.get("coverage"), dict) else {}
    role_mix = {}
    for entry in cleaned:
        role_mix[entry["role"]] = role_mix.get(entry["role"], 0) + 1
    full_plan = {
        "image_plan_version": plan.get("image_plan_version") or "1.1",
        "prompt_prefix": prefix,
        "style_bible": style_bible,
        "images": cleaned,
        "coverage": {
            "scene_count": len(scenes),
            "photo_count": photo_count,
            "html_count": html_count,
            "role_mix": role_mix,
            "notes": str(coverage.get("notes") or ""),
        },
    }
    brief_items = [{
        "id": entry["id"],
        "scene_id": entry["scene_id"],
        "role": entry["role"],
        "why": entry["why"],
        "html_brief": entry["html_brief"],
        "size": entry["size"],
        "text_safe_zone": entry["text_safe_zone"],
        "motion_hint": entry["motion_hint"],
        "subject": entry["subject"][:80],
    } for entry in cleaned]

    return {
        "image_plan_json": json.dumps(full_plan, ensure_ascii=False),
        "image_brief_json": json.dumps({
            "prompt_prefix": prefix,
            "style_bible": {key: style_bible.get(key) for key in ("medium", "optics", "lighting", "palette", "texture", "avoid")},
            "images": brief_items,
        }, ensure_ascii=False),
        "image_count": photo_count,
        "image_valid": photo_count >= 1 and len(missing) == 0,
        "image_warnings_json": json.dumps(warnings, ensure_ascii=False),
    }
