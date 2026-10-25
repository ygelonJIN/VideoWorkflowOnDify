def main(approved_package_json: str) -> dict:
    import json

    package = json.loads(approved_package_json or "{}")
    storyboard = package.get("storyboard") or {}
    scenes = [s for s in (storyboard.get("scenes") or []) if isinstance(s, dict)]
    total = len(scenes)
    if total == 0:
        raise ValueError("分镜为空，无法分组")

    brief = package.get("brief") if isinstance(package.get("brief"), dict) else {}
    distill = brief.get("distill") if isinstance(brief.get("distill"), dict) else {}
    thesis = str(distill.get("thesis") or "").strip()
    arguments = [item for item in (distill.get("arguments") or []) if isinstance(item, dict)]
    claims = {}
    for index, item in enumerate(arguments):
        claim = str(item.get("claim") or "").strip()
        if claim:
            claims[str(item.get("id") or "a%d" % (index + 1))] = claim

    size = (total + 3) // 4
    groups = [scenes[i * size:(i + 1) * size] for i in range(4)]

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

    payload = []
    for index, group in enumerate(groups):
        previous = groups[index - 1] if index > 0 else []
        following = groups[index + 1] if index < 3 else []
        group_argument_ids = []
        for scene in group:
            token = str(scene.get("argument_id") or "").strip()
            if token and token in claims and token not in group_argument_ids:
                group_argument_ids.append(token)
        payload.append(json.dumps({
            "thesis": thesis,
            "arguments": [{"id": key, "claim": claims[key]} for key in group_argument_ids] or [
                {"id": key, "claim": claims[key]} for key in list(claims.keys())[:1]
            ],
            "scenes": group,
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
