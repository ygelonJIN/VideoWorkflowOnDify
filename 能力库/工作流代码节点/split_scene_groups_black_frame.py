def main(approved_package_json: str, motion_plan_json: str) -> dict:
    import json
    import re

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
            "scene_payloads": [],
            "composition_ledger_json": "[]",
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

    # 构图账本：A08 已经按全片视野分配了每屏的构图，这里只做归一化和查重。
    # 查重结果写进 design_brief，场景组会照着避开；真正的验收在渲染前的
    # check_composition_variation.mjs（量真实 DOM，不看模型自报）。
    composition_warnings = []
    ledger = []
    seen_family = {}
    for index, scene in enumerate(scenes):
        raw = scene.get("composition") if isinstance(scene.get("composition"), dict) else {}
        family = str(raw.get("family") or "").strip()
        zone = str(raw.get("text_zone") or "").strip()
        align = str(raw.get("align") or "").strip().lower()
        scale = str(raw.get("scale") or "").strip()
        if align not in {"left", "center", "right"}:
            align = ""
        scene_id = str(scene.get("scene_id") or "s%02d" % (index + 1))
        if not family:
            family = "未分配-" + scene_id
            composition_warnings.append("%s 没有 composition.family：已标记未分配，场景组会按内容自拟" % scene_id)
        if not zone or not align or not scale:
            composition_warnings.append("%s 的 composition 缺 text_zone/align/scale：场景组只能按内容自拟" % scene_id)
        if family in seen_family:
            composition_warnings.append("%s 与 %s 用了同一个构图族「%s」：分镜必须逐屏变" % (
                scene_id, seen_family[family], family))
        else:
            seen_family[family] = scene_id
        entry = {
            "scene_id": scene_id,
            "family": family,
            "text_zone": zone,
            "align": align,
            "scale": scale,
            "why": str(raw.get("why") or "").strip(),
        }
        ledger.append(entry)

    for left, right in zip(ledger, ledger[1:]):
        if left["family"] and left["family"] == right["family"]:
            composition_warnings.append("相邻两屏构图族相同：%s 与 %s（%s）" % (
                left["scene_id"], right["scene_id"], left["family"]))
    if len(ledger) >= 2:
        first, last = ledger[0], ledger[-1]
        if (first["family"], first["text_zone"], first["scale"]) == (
                last["family"], last["text_zone"], last["scale"]):
            composition_warnings.append("首尾两屏构图三项全同（%s / %s）：必须做出对照" % (
                first["scene_id"], last["scene_id"]))
    composition_warnings = list(dict.fromkeys(composition_warnings))

    # 逐屏载荷：迭代节点一次只给模型一屏，附带前后屏的构图，方便它避开相邻同构。
    scene_payloads = []
    previous_component = ""
    for index, scene in enumerate(scenes):
        item = dict(scene)
        item["composition"] = dict(ledger[index]) if index < len(ledger) else {}
        item["index"] = index + 1
        item["total"] = len(scenes)
        item["prev_scene"] = ledger[index - 1]["scene_id"] if index > 0 else ""
        item["next_scene"] = ledger[index + 1]["scene_id"] if index + 1 < len(ledger) else ""
        item["prev_composition"] = ledger[index - 1] if index > 0 else {}
        item["next_composition"] = ledger[index + 1] if index + 1 < len(ledger) else {}
        # 全片视觉编号：背景 B + 组件 U，由这一个节点统一分配，画面阶段只套库、不自己画。
        background_pool = ["B05", "B01", "B03", "B06", "B04", "B07", "B02"]
        text = (str(item.get("on_screen_text") or "") + " " + str(item.get("voiceover_text") or "")).strip()
        component = "U01"
        if re.search(r"[0-9]+|[一二三四五六七八九十百千万亿]{1,}(?:万|亿|块|元|%|天|次)", text):
            component = "U05"
        elif text.count("、") >= 2 or "步骤" in text or ("先" in text and "再" in text):
            component = "U02"
        elif any(word in text for word in ("不是", "却", "选择", "对比")):
            component = "U03"
        if component == previous_component:
            order = ["U01", "U03", "U05", "U02", "U04"]
            component = order[(order.index(component) + 1) % len(order)]
        previous_component = component
        item["visual_budget"] = {
            "background": background_pool[index % len(background_pool)],
            "components": [component],
        }

        # 全片动效编号：逐屏循环前由这一个节点统一分配，相邻不重复、单编号不超过一半屏数。
        entrance_pool = ["T02", "T01", "T03", "T09"]
        state_pool = ["X02", "X01"]
        item["motion_budget"] = {
            "entrance": entrance_pool[index % len(entrance_pool)],
            "state": state_pool[index % len(state_pool)],
        }
        scene_payloads.append(json.dumps(item, ensure_ascii=False))
    distinct_families = len({entry["family"] for entry in ledger if entry["family"]})
    need_families = min(4, len(ledger))
    if ledger and distinct_families < need_families:
        composition_warnings.append("构图族只有 %d 种（%d 屏），至少需要 %d 种" % (
            distinct_families, len(ledger), need_families))

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

    # 版式与主运动不再按序号轮转：每屏的视觉承担者由 H01P 的 role 决定，
    # 版面与动作由 H02S / H02SM 按内容判断。这里只做分组和动效切片。

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
            "composition_ledger": ledger,
            "composition_warnings": composition_warnings,
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
        "composition_warnings": composition_warnings,
    }, ensure_ascii=False)
    keys = ["group_a_json", "group_b_json", "group_c_json", "group_d_json"]
    result = {key: payload[i] for i, key in enumerate(keys)}
    result.update({
        "scene_total": total,
        "design_brief": design_brief,
        "scene_payloads": scene_payloads,
        "composition_ledger_json": json.dumps(ledger, ensure_ascii=False),
    })
    return result
