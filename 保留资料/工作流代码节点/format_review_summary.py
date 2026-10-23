def main(strategy_json: str, script_json: str, storyboard_json: str, motion_plan_json: str, compliance_json: str) -> dict:
    import json

    def parse(raw):
        try:
            data = json.loads(raw or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    strategy = parse(strategy_json)
    script = parse(script_json)
    storyboard = parse(storyboard_json)
    motion = parse(motion_plan_json)
    compliance = parse(compliance_json)

    lines = ["# 视频内容人工审核", ""]
    lines.append("## 内容角度")
    lines.append("- 核心结论：" + str(strategy.get("core_message") or script.get("hook") or "未填写"))
    hook = str(strategy.get("hook") or script.get("hook") or "")
    if hook:
        lines.append("- Hook：" + hook)

    lines.extend(["", "## 口播草稿", str(script.get("voiceover_script") or "未生成")])
    captions = script.get("burned_in_caption_lines") or []
    if captions:
        lines.extend(["", "## 字幕"])
        lines.extend("- " + str(item) for item in captions)

    lines.extend(["", "## 分镜"])
    for index, scene in enumerate(storyboard.get("scenes", []), 1):
        if not isinstance(scene, dict):
            continue
        lines.append("%d. %s｜目的：%s｜画面：%s｜屏幕文字：%s" % (
            index,
            scene.get("scene_id", "s%02d" % index),
            scene.get("purpose", ""),
            scene.get("visual_brief", scene.get("ui_template", "")),
            scene.get("on_screen_text", "")
        ))

    lines.extend(["", "## 动效计划"])
    for index, item in enumerate(motion.get("sequences", []), 1):
        if not isinstance(item, dict):
            continue
        lines.append("%d. %s｜%s｜%s｜%sms｜%s" % (
            index,
            item.get("motion_id", "m%02d" % index),
            item.get("scene_id", ""),
            item.get("action", ""),
            item.get("duration_ms", ""),
            item.get("semantic_reason", "")
        ))

    lines.extend(["", "## 合规提示"])
    lines.append("- 审核结论：%s" % compliance.get("decision", "待人工确认"))
    lines.append("- 风险等级：%s" % compliance.get("risk_level", "待人工确认"))
    for item in compliance.get("required_changes", []) or []:
        lines.append("- 需要修改：" + str(item))
    note = compliance.get("review_note_for_human")
    if note:
        lines.append("- 审核重点：" + str(note))

    return {"review_summary": "\n".join(lines)}
