def main(transition_text: str, storyboard_json: str) -> dict:
    import json
    import re

    def strip_fence(raw):
        value = str(raw or "").strip()
        return re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I)

    def scene_ids_from(raw):
        try:
            data = json.loads(raw or "{}")
        except Exception:
            return []
        scenes = data.get("scenes") if isinstance(data, dict) else None
        if not isinstance(scenes, list):
            return []
        return [str(item.get("scene_id")) for item in scenes
                if isinstance(item, dict) and str(item.get("scene_id") or "").strip()]

    scene_ids = scene_ids_from(storyboard_json)
    if not scene_ids:
        scene_ids = ["s01"]

    warnings = []
    text = strip_fence(transition_text)
    plan = None
    if text:
        try:
            plan = json.loads(text)
        except Exception as error:
            start = text.find("{")
            if start >= 0:
                for index in range(len(text) - 1, start, -1):
                    if text[index] != "}":
                        continue
                    candidate = re.sub(r",\s*([}\]])", r"\1", text[start:index + 1])
                    try:
                        plan = json.loads(candidate)
                        break
                    except Exception:
                        continue
            if plan is None:
                warnings.append("转场计划 JSON 无法解析（%s），已按相邻屏生成直接硬切" % str(error)[:60])

    if not isinstance(plan, dict):
        plan = {}
    transitions = plan.get("transitions")
    if not isinstance(transitions, list):
        transitions = []

    allowed_triggers = {"sentence_start", "word", "explicit_time"}
    allowed_scope = {"scene", "background", "foreground", "mixed"}
    normalized = []
    seen = set()

    for index, item in enumerate(transitions, 1):
        if not isinstance(item, dict):
            warnings.append("第 %d 条转场不是对象，已丢弃" % index)
            continue
        tid = str(item.get("transition_id") or "t%02d" % index)
        while tid in seen:
            tid += "_dup"
        seen.add(tid)
        item["transition_id"] = tid

        source = str(item.get("from_scene") or "")
        target = str(item.get("to_scene") or "")
        if source not in scene_ids or target not in scene_ids:
            warnings.append("%s 的 from/to 不在分镜里（%s→%s），已丢弃" % (tid, source or "空", target or "空"))
            continue

        trigger = str(item.get("at_trigger") or "sentence_start").strip()
        head = trigger.split(":", 1)[0]
        if head not in allowed_triggers:
            item["at_trigger"] = "sentence_start"
            warnings.append("%s at_trigger=%s 已归一化为 sentence_start" % (tid, trigger))
        elif head == "word" and ":" not in trigger:
            item["at_trigger"] = "sentence_start"
            warnings.append("%s at_trigger=word 缺少关键词，已归一化为 sentence_start" % tid)
        elif head == "explicit_time":
            try:
                item["at_trigger"] = "explicit_time:%0.3f" % float(trigger.split(":", 1)[1])
            except Exception:
                item["at_trigger"] = "sentence_start"
                warnings.append("%s explicit_time 无法解析，已归一化为 sentence_start" % tid)

        scope = str(item.get("target_scope") or "scene").strip()
        if scope not in allowed_scope:
            item["target_scope"] = "scene"
            warnings.append("%s target_scope=%s 已归一化为 scene" % (tid, scope))

        try:
            duration = int(item.get("duration_ms") or 0)
        except Exception:
            duration = 0
        clamped = max(120, min(1400, duration or 400))
        if clamped != duration:
            warnings.append("%s duration_ms=%s 已归一化为 %s" % (tid, duration, clamped))
        item["duration_ms"] = clamped

        if not str(item.get("family") or "").strip():
            item["family"] = "crossfade"
            warnings.append("%s 缺少 family，已标记为交叉淡化" % tid)
        if not isinstance(item.get("motion"), dict):
            item["motion"] = {}
        for key in ("outgoing", "incoming"):
            if not str(item["motion"].get(key) or "").strip():
                item["motion"][key] = "按 family 的标准动作处理"
                warnings.append("%s motion.%s 缺失，已补默认描述" % (tid, key))
        if not str(item.get("reason") or "").strip():
            item["reason"] = "对应这一处语义停顿"
            warnings.append("%s 缺少 reason，已补默认说明" % tid)

        normalized.append(item)

    # 兜底：分镜里相邻两屏之间必须有转场记录，缺的补硬切（硬切也是一种转场）。
    covered = {(item["from_scene"], item["to_scene"]) for item in normalized}
    for index in range(len(scene_ids) - 1):
        pair = (scene_ids[index], scene_ids[index + 1])
        if pair in covered:
            continue
        normalized.append({
            "transition_id": "t%02d_auto" % (index + 1),
            "from_scene": pair[0],
            "to_scene": pair[1],
            "at_trigger": "sentence_start",
            "trigger_detail": "自动补齐的相邻屏切点",
            "family": "hard_cut",
            "motion": {"outgoing": "直接结束", "incoming": "直接开始", "overlap": "无"},
            "target_scope": "scene",
            "target_hint": "整屏",
            "duration_ms": 1,
            "easing": "none",
            "reason": "转场计划未覆盖该切点，按硬切补齐",
        })
        warnings.append("补齐缺失切点 %s→%s（硬切）" % pair)

    plan["transition_version"] = str(plan.get("transition_version") or "1.0")
    plan["transitions"] = normalized
    plan["validation"] = {"errors": [], "warnings": warnings}

    errors = [w for w in warnings if "无法解析" in w]
    return {
        "transition_plan_json": json.dumps(plan, ensure_ascii=False),
        "transition_count": len(normalized),
        "transition_valid": not errors,
        "transition_errors_json": json.dumps(errors, ensure_ascii=False),
        "transition_warnings_json": json.dumps(warnings, ensure_ascii=False),
    }
