def main(approved_package_json: str, copy_warnings_json: str, storyboard_warnings_json: str, motion_warnings_json: str) -> dict:
    import json

    def parse(raw):
        try:
            data = json.loads(raw or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def arr(raw):
        try:
            data = json.loads(raw or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    package = parse(approved_package_json)
    brief = package.get("brief") if isinstance(package.get("brief"), dict) else {}
    script = package.get("approved_script") if isinstance(package.get("approved_script"), dict) else {}
    storyboard = package.get("storyboard") if isinstance(package.get("storyboard"), dict) else {}
    motion = package.get("motion_plan") if isinstance(package.get("motion_plan"), dict) else {}

    lines = ["# 视频内容生产资料", "", "审核状态：已批准", ""]
    strategy = storyboard.get("creative_strategy") if isinstance(storyboard.get("creative_strategy"), dict) else {}
    info = []
    topic = str(brief.get("topic") or "").strip()
    if topic:
        info.append("- 主题：" + topic)
    duration = brief.get("target_duration_seconds")
    if duration:
        info.append("- 目标时长：%s 秒" % duration)
    core_message = str(strategy.get("core_message") or "").strip()
    if core_message:
        info.append("- 核心结论：" + core_message)
    if info:
        lines.append("## 内容信息")
        lines.extend(info)

    lines.extend(["", "## 口播全文", str(script.get("voiceover_script") or "未生成")])
    captions = script.get("burned_in_caption_lines") or []
    if captions:
        lines.extend(["", "## 字幕"])
        lines.extend("- " + str(item) for item in captions)

    title = script.get("title")
    if title:
        lines.extend(["", "## 发布标题", str(title)])
    hashtags = script.get("hashtags") or []
    if hashtags:
        lines.extend(["", "## 标签", " ".join(str(item) for item in hashtags)])

    lines.extend(["", "## 分镜"])
    for index, scene in enumerate(storyboard.get("scenes", []), 1):
        if not isinstance(scene, dict):
            continue
        lines.append("%d. 场景 %s｜目的：%s｜画面来源：%s｜模板：%s｜画面：%s｜屏幕文字：%s" % (
            index,
            scene.get("scene_id", "s%02d" % index),
            scene.get("purpose", ""),
            scene.get("visual_source", ""),
            scene.get("ui_template", ""),
            scene.get("visual_brief", ""),
            scene.get("on_screen_text", "")
        ))

    lines.extend(["", "## 动效"])
    for index, item in enumerate(motion.get("sequences", []), 1):
        if not isinstance(item, dict):
            continue
        lines.append("%d. %s｜场景 %s｜动作：%s｜触发：%s｜时长：%sms｜原因：%s" % (
            index,
            item.get("motion_id", "m%02d" % index),
            item.get("scene_id", ""),
            item.get("action", ""),
            item.get("start_trigger", ""),
            item.get("duration_ms", ""),
            item.get("semantic_reason", "")
        ))

    warnings = []
    warnings.extend(arr(copy_warnings_json))
    warnings.extend(arr(storyboard_warnings_json))
    warnings.extend(arr(motion_warnings_json))
    if warnings:
        lines.extend(["", "## 需要注意"])
        lines.extend("- " + str(item) for item in warnings)

    return {"result_summary": "\n".join(lines)}
