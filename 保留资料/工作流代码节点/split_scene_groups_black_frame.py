def main(approved_package_json: str, motion_plan_json: str) -> dict:
    import json

    package = json.loads(approved_package_json or "{}")
    storyboard = package.get("storyboard") or {}
    scenes = [s for s in (storyboard.get("scenes") or []) if isinstance(s, dict)]
    total = len(scenes)
    if total == 0:
        empty = json.dumps({"thesis": "", "arguments": [], "scenes": [], "motion": [],
                            "motion_note": "分镜为空：A09 没有产出 scenes", "prev_hook": "", "next_hook": ""},
                           ensure_ascii=False)
        return {
            "group_a_json": empty, "group_b_json": empty, "group_c_json": empty, "group_d_json": empty,
            "scene_total": 0,
            "design_brief": json.dumps({"error": "分镜为空，无法分组"}, ensure_ascii=False),
        }

    brief = package.get("brief") if isinstance(package.get("brief"), dict) else {}
    distill = brief.get("distill") if isinstance(brief.get("distill"), dict) else {}
    thesis = str(distill.get("thesis") or "").strip()
    arguments = [item for item in (distill.get("arguments") or []) if isinstance(item, dict)]
    claims = {}
    for index, item in enumerate(arguments):
        claim = str(item.get("claim") or "").strip()
        if claim:
            claims[str(item.get("id") or "a%d" % (index + 1))] = claim

    # 均衡切分：前 total % 4 组多 1 屏，任何场景数（>=4）下都不会出现空组。
    base, extra = divmod(total, 4)
    groups = []
    cursor = 0
    for index in range(4):
        size = base + (1 if index < extra else 0)
        groups.append(scenes[cursor:cursor + size])
        cursor += size

    try:
        motion = json.loads(motion_plan_json or "{}")
    except Exception:
        motion = {}
    sequences = [m for m in (motion.get("sequences") or []) if isinstance(m, dict)] if isinstance(motion, dict) else []

    def first_line(group):
        for scene in group:
            text = str(scene.get("voiceover_text") or scene.get("on_screen_text") or "").strip()
            if text:
                return text[:40]
        return ""

    def last_line(group):
        for scene in reversed(group):
            text = str(scene.get("voiceover_text") or scene.get("on_screen_text") or "").strip()
            if text:
                return text[:40]
        return ""

    # 版式与主运动槽位：按全局序号轮转，保证相邻两屏不重复，模型没有"全用同一套"的机会。
    LAYOUT_SLOTS = ["full-bleed", "split-left", "split-right", "inset-offset", "texture-under", "framed"]
    MOTION_SLOTS = ["push-in", "pan-x", "mask-reveal", "parallax", "path-draw", "state-flip", "type-stagger"]
    slot_index = 0
    for group in groups:
        for scene in group:
            if isinstance(scene, dict):
                scene["layout_slot"] = LAYOUT_SLOTS[slot_index % len(LAYOUT_SLOTS)]
                scene["motion_slot"] = MOTION_SLOTS[slot_index % len(MOTION_SLOTS)]
            slot_index += 1

    payload = []
    for index, group in enumerate(groups):
        previous = groups[index - 1] if index > 0 else []
        following = groups[index + 1] if index < 3 else []
        group_argument_ids = []
        for scene in group:
            token = str(scene.get("argument_id") or "").strip()
            if token and token in claims and token not in group_argument_ids:
                group_argument_ids.append(token)
        scene_ids = [str(scene.get("scene_id") or "") for scene in group]
        group_motion = [m for m in sequences if str(m.get("scene_id") or "") in scene_ids]
        payload.append(json.dumps({
            "thesis": thesis,
            "arguments": [{"id": key, "claim": claims[key]} for key in group_argument_ids] or [
                {"id": key, "claim": claims[key]} for key in list(claims.keys())[:1]
            ],
            "scenes": group,
            "motion": group_motion,
            "motion_note": "" if group_motion else "本组没有动效计划切片：按本屏组件自拟语义化 data-anim 名称",
            "prev_hook": last_line(previous),
            "next_hook": first_line(following),
        }, ensure_ascii=False))

    strategy = storyboard.get("creative_strategy") or {}
    design_brief = json.dumps({
        "title": strategy.get("title", ""),
        "subtitle": strategy.get("subtitle", ""),
        "visual_style": strategy.get("visual_style", ""),
        "core_message": strategy.get("core_message", ""),
        "thesis": thesis,
        "argument_claims": [{"id": key, "claim": claims[key]} for key in claims],
        "aspect": "9:16 1080x1920",
    }, ensure_ascii=False)
    keys = ["group_a_json", "group_b_json", "group_c_json", "group_d_json"]
    result = {key: payload[i] for i, key in enumerate(keys)}
    result.update({"scene_total": total, "design_brief": design_brief})
    return result
