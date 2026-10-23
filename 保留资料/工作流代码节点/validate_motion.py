def main(motion_text: str, storyboard_json: str, recommended_motion_count_min: int) -> dict:
    import json
    import re

    def parse(raw, label):
        value = str(raw or "").strip()
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I)
        try:
            return json.loads(value)
        except Exception:
            start, end = value.find("{"), value.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(value[start:end + 1])
                except Exception:
                    pass
            return {"__invalid_json__": True, "__label__": label}

    motion = parse(motion_text, "动效")
    storyboard = parse(storyboard_json, "分镜")
    if not isinstance(storyboard, dict):
        storyboard = {}
    warnings = []
    if not isinstance(motion, dict) or motion.get("__invalid_json__"):
        warnings.append("动效 JSON 无法解析，已按分镜生成基础动效继续")
        motion = {}
    sequences = motion.get("sequences")
    if not isinstance(sequences, list) or not sequences:
        raw_scenes = storyboard.get("scenes", []) if isinstance(storyboard.get("scenes"), list) else []
        base_scenes = raw_scenes or [{"scene_id": "s01"}]
        actions = ["enter", "highlight", "state_change"]
        sequences = []
        for index in range(max(6, len(base_scenes) * 2)):
            scene = base_scenes[index % len(base_scenes)] if isinstance(base_scenes[index % len(base_scenes)], dict) else {}
            sequences.append({
                "motion_id": "m%02d" % (index + 1),
                "scene_id": str(scene.get("scene_id") or "s01"),
                "sentence_id": str(scene.get("sentence_id") or "s01"),
                "action": actions[index % len(actions)],
                "target": "focus_element",
                "duration_ms": 600,
                "easing": "power3.out",
                "start_trigger": "sentence_start",
                "semantic_reason": "与当前口播语义同步的基础动效"
            })
        motion = {"sequences": sequences}
        warnings.append("motion.sequences 为空，已生成基础动效继续")
    scenes = [str(x.get("scene_id")) for x in storyboard.get("scenes", []) if isinstance(x, dict) and x.get("scene_id")]
    if not scenes:
        scenes = ["s01"]
    sentences = []
    for scene in storyboard.get("scenes", []):
        if isinstance(scene, dict):
            sentences.extend(str(x) for x in scene.get("sentence_ids", []) if str(x).strip())
    if not sentences:
        sentences = ["s01"]

    allowed_actions = {
        "enter", "count_up", "highlight", "path_draw", "cursor_move",
        "click", "state_change", "zoom_focus", "keyword_highlight",
        "row_reveal", "status_update"
    }
    allowed_eases = {"power3.out", "power2.inOut", "expo.out", "power2.out"}
    seen_ids = set()
    normalized = []

    for index, item in enumerate(sequences, 1):
        if not isinstance(item, dict):
            item = {"target": str(item)}
            warnings.append("第 %d 条动效不是对象，已转换为简单动作" % index)

        motion_id = str(item.get("motion_id") or "m%02d" % index)
        while motion_id in seen_ids:
            motion_id += "_dup"
        seen_ids.add(motion_id)
        item["motion_id"] = motion_id

        scene_id = str(item.get("scene_id", ""))
        if scene_id not in scenes:
            old = scene_id or "empty"
            scene_id = scenes[min(index - 1, len(scenes) - 1)]
            item["scene_id"] = scene_id
            warnings.append("%s scene_id=%s 已归一化为 %s" % (motion_id, old, scene_id))
        sentence_id = str(item.get("sentence_id", ""))
        if sentence_id not in sentences:
            old = sentence_id or "empty"
            sentence_id = sentences[min(index - 1, len(sentences) - 1)]
            item["sentence_id"] = sentence_id
            warnings.append("%s sentence_id=%s 已归一化为 %s" % (motion_id, old, sentence_id))

        action = str(item.get("action", "")).strip()
        if action == "fade":
            item["action"] = "enter"
            warnings.append("%s action=fade 已改为 enter" % motion_id)
        elif action not in allowed_actions:
            item["action"] = "state_change"
            warnings.append("%s action=%s 已改为 state_change" % (motion_id, action or "empty"))

        for key in ("repeat", "loop"):
            if key in item:
                item.pop(key)
                warnings.append("%s 已移除禁止字段 %s" % (motion_id, key))

        try:
            duration = int(item.get("duration_ms") or 0)
        except Exception:
            duration = 0
        clamped = max(250, min(2200, duration or 600))
        if clamped != duration:
            warnings.append("%s duration_ms=%s 已归一化为 %s" % (motion_id, duration, clamped))
        item["duration_ms"] = clamped

        easing = str(item.get("easing", "")).strip()
        if easing not in allowed_eases:
            item["easing"] = "power3.out"
            warnings.append("%s easing=%s 已归一化为 power3.out" % (motion_id, easing or "empty"))

        if not str(item.get("start_trigger", "")).strip():
            item["start_trigger"] = "sentence_start"
            warnings.append("%s start_trigger 缺失，已设为 sentence_start" % motion_id)

        target = str(item.get("target", "")).strip()
        if item["action"] == "zoom_focus" and target in {"root", "screen", "global", ""}:
            item["action"] = "highlight"
            item["target"] = target or "focus_element"
            warnings.append("%s 整图 zoom_focus 已改为局部 highlight" % motion_id)

        if not str(item.get("semantic_reason", "")).strip():
            item["semantic_reason"] = "与当前句子的语义变化同步"
            warnings.append("%s semantic_reason 缺失，已生成默认说明" % motion_id)

        normalized.append(item)

    minimum = max(6, int(recommended_motion_count_min or 0))
    if len(normalized) < minimum:
        warnings.append("动效数量少于建议值 %d，已继续输出" % minimum)

    motion["sequences"] = normalized
    motion["validation"] = {"errors": [], "warnings": warnings}
    return {
        "motion_plan_json": json.dumps(motion, ensure_ascii=False),
        "motion_count": len(normalized),
        "motion_valid": True,
        "motion_errors_json": "[]",
        "motion_warnings_json": json.dumps(warnings, ensure_ascii=False)
    }
