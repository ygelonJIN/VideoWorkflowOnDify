def main(image_plan_text: str, approved_package_json: str) -> dict:
    """归一化图像计划：保证每个分镜都有图，字段合法，并拆出给 HTML 节点用的精简版。"""
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

    allowed_roles = {"full", "inset", "portrait", "texture"}
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
            zone = "bottom"
        motion = str(item.get("motion_hint") or "").strip().lower()
        if motion not in allowed_motion:
            motion = "hold"
        prompt = str(item.get("prompt") or "").strip()
        subject = str(item.get("subject") or "").strip()
        if not prompt:
            warnings.append("%s 没有 prompt，已用兜底镜头补上" % image_id)
            prompt = (
                "A quiet, empty interior consistent with the film's established look, "
                "soft directional daylight from one side, shallow depth of field, "
                "generous negative space, photographic, no people's faces."
            )
        entry = {
            "id": image_id,
            "scene_id": scene_id or image_id,
            "role": role,
            "subject": subject,
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

    # 每个分镜必须有图：缺的按场景内容补一张兜底镜头，不让 HTML 出现空屏。
    scene_ids = [str(scene.get("scene_id") or "").strip() for scene in scenes]
    missing = []
    for index, scene in enumerate(scenes):
        scene_id = str(scene.get("scene_id") or "").strip()
        if not scene_id or scene_id in by_scene:
            continue
        missing.append(scene_id)
        brief = str(scene.get("visual_brief") or scene.get("on_screen_text") or "").strip()[:60]
        entry = {
            "id": scene_id,
            "scene_id": scene_id,
            "role": "full",
            "subject": brief or "按分镜补的兜底镜头",
            "prompt": (
                "A quiet photographic scene that supports this beat: %s. "
                "Soft single-source daylight, shallow depth of field, generous negative space, "
                "no text, no faces." % (brief or "an empty room with light falling across it")
            ),
            "prompt_zh": "安静的现实场景，单一光源，浅景深，给文字留出空白。%s" % (brief or ""),
            "negative": "",
            "size": "1024x1536",
            "text_safe_zone": "bottom",
            "motion_hint": "push-in",
        }
        cleaned.append(entry)
        by_scene[scene_id] = entry
    if missing:
        warnings.append("这些分镜没有配图，已补兜底镜头：" + "、".join(missing[:8]))

    extra = [entry["scene_id"] for entry in cleaned if entry["scene_id"] and entry["scene_id"] not in scene_ids]
    if extra:
        warnings.append("图像计划里有分镜之外的多余图片（下游不会用）：" + "、".join(sorted(set(extra))[:8]))

    style_bible = plan.get("style_bible") if isinstance(plan.get("style_bible"), dict) else {}
    coverage = plan.get("coverage") if isinstance(plan.get("coverage"), dict) else {}
    full_plan = {
        "image_plan_version": plan.get("image_plan_version") or "1.0",
        "prompt_prefix": prefix,
        "style_bible": style_bible,
        "images": cleaned,
        "coverage": {
            "scene_count": len(scenes),
            "image_count": len(cleaned),
            "notes": str(coverage.get("notes") or ""),
        },
    }
    brief_items = [{
        "id": entry["id"],
        "scene_id": entry["scene_id"],
        "role": entry["role"],
        "size": entry["size"],
        "text_safe_zone": entry["text_safe_zone"],
        "motion_hint": entry["motion_hint"],
        "subject": entry["subject"][:60],
    } for entry in cleaned]

    return {
        "image_plan_json": json.dumps(full_plan, ensure_ascii=False),
        "image_brief_json": json.dumps({
            "prompt_prefix": prefix,
            "style_bible": {key: style_bible.get(key) for key in ("medium", "optics", "lighting", "palette", "texture", "avoid")},
            "images": brief_items,
        }, ensure_ascii=False),
        "image_count": len(cleaned),
        "image_valid": bool(cleaned) and len(missing) == 0,
        "image_warnings_json": json.dumps(warnings, ensure_ascii=False),
    }
