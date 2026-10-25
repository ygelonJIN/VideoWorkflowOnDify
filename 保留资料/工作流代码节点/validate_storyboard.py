def main(storyboard_text: str, script_json: str) -> dict:
    import json
    import re

    def recover_objects(raw, key):
        marker = raw.find('"' + key + '"')
        if marker < 0:
            return []
        start = raw.find('[', marker)
        if start < 0:
            return []
        items = []
        depth = 0
        in_str = False
        esc = False
        obj_start = None
        for index in range(start, len(raw)):
            ch = raw[index]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                if depth == 0:
                    obj_start = index
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and obj_start is not None:
                    try:
                        items.append(json.loads(raw[obj_start:index + 1]))
                    except Exception:
                        pass
                    obj_start = None
        return items

    def parse(raw, label):
        value = str(raw or "").strip()
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I)
        value = value.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
        if not value:
            return {"__invalid_json__": True, "__label__": label}, "输出为空"
        try:
            return json.loads(value), ""
        except Exception as first_error:
            start = value.find("{")
            if start >= 0:
                depth = 0
                in_str = False
                esc = False
                for index in range(start, len(value)):
                    ch = value[index]
                    if in_str:
                        if esc:
                            esc = False
                        elif ch == "\\":
                            esc = True
                        elif ch == '"':
                            in_str = False
                        continue
                    if ch == '"':
                        in_str = True
                    elif ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            candidate = value[start:index + 1]
                            candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
                            try:
                                return json.loads(candidate), ""
                            except Exception:
                                break
            return {"__invalid_json__": True, "__label__": label}, "%s；长度 %d；开头 %s；结尾 %s" % (
                str(first_error)[:80],
                len(value),
                value[:60].replace("\n", " "),
                value[-60:].replace("\n", " "),
            )

    storyboard, storyboard_parse_error = parse(storyboard_text, "分镜")
    script, _ = parse(script_json, "文案")
    if not isinstance(script, dict):
        script = {}
    warnings = []
    if not isinstance(storyboard, dict) or storyboard.get("__invalid_json__"):
        recovered = recover_objects(str(storyboard_text or ""), "scenes")
        if len(recovered) >= 2:
            storyboard = {"scenes": recovered}
            warnings.append("分镜 JSON 被截断（" + storyboard_parse_error + "），已从中恢复 %d 个场景继续" % len(recovered))
        else:
            warnings.append("分镜 JSON 无法解析（" + storyboard_parse_error + "），已按口播句子生成基础分镜继续")
            storyboard = {}
    scenes = storyboard.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        sentences = [item for item in script.get("sentences", []) if isinstance(item, dict) and str(item.get("text", "")).strip()]
        if not sentences:
            sentences = [{"id": "s01", "text": str(script.get("voiceover_script") or "继续解释当前主题")}]
        scenes = [{
            "scene_id": "s%02d" % (index + 1),
            "sentence_ids": [str(item.get("id") or "s%02d" % (index + 1))],
            "voiceover_text": str(item.get("text", "")),
            "purpose": item.get("purpose") if item.get("purpose") in {"hook", "context", "pain", "insight", "solution", "proof", "example", "ending", "summary", "cta"} else ("hook" if index == 0 else ("ending" if index == len(sentences) - 1 else "insight")),
            "visual_source": "reusable_ui_template",
            "ui_template": "workflow",
            "on_screen_text": re.sub(r"\s+", "", str(item.get("text", ""))),
            "visual_brief": "展示当前口播对应的可复用界面、步骤、清单或信息组件",
            "motion": "关键信息逐项出现",
            "transition": "cut"
        } for index, item in enumerate(sentences)]
        storyboard = {"scenes": scenes}
        if not storyboard_parse_error:
            warnings.append("storyboard.scenes 为空，已生成基础分镜继续")
        scenes = storyboard["scenes"]

    sentence_ids = [str(item.get("id")) for item in script.get("sentences", []) if isinstance(item, dict) and item.get("id")]
    if not sentence_ids:
        sentence_ids = ["s%02d" % i for i in range(1, len(scenes) + 1)]
    seen_scene_ids = set()
    purposes = set()

    allowed_visual = {
        "reusable_ui_template", "real_footage", "supplied_image",
        "generated_image", "motion_graphic"
    }
    allowed_templates = {
        "dashboard", "list", "workflow", "comparison", "timeline",
        "planner", "tracker", "story", "none"
    }
    allowed_purposes = {"hook", "context", "pain", "insight", "solution", "proof", "example", "ending", "summary", "cta"}

    normalized_scenes = []
    for index, scene in enumerate(scenes, 1):
        if not isinstance(scene, dict):
            scene = {"voiceover_text": str(scene)}
            warnings.append("第 %d 个 scene 不是对象，已转换为简单场景" % index)

        scene_id = str(scene.get("scene_id") or "s%02d" % index)
        original_scene_id = scene_id
        while scene_id in seen_scene_ids:
            scene_id += "_dup"
        if scene_id != original_scene_id:
            warnings.append("scene_id 重复，%s 已改为 %s" % (original_scene_id, scene_id))
        seen_scene_ids.add(scene_id)
        scene["scene_id"] = scene_id

        refs = [str(x) for x in scene.get("sentence_ids", []) if str(x).strip()]
        valid_refs = [ref for ref in refs if ref in sentence_ids]
        if not valid_refs:
            fallback = sentence_ids[min(index - 1, len(sentence_ids) - 1)]
            valid_refs = [fallback]
            warnings.append("%s sentence_ids 缺失或无效，已绑定 %s" % (scene_id, fallback))
        elif len(valid_refs) != len(refs):
            warnings.append("%s 部分 sentence_ids 无效，已移除" % scene_id)
        scene["sentence_ids"] = valid_refs

        purpose = str(scene.get("purpose", "")).strip()
        if purpose not in allowed_purposes:
            old = purpose or "empty"
            purpose = "hook" if index == 1 else ("ending" if index == len(scenes) else "insight")
            warnings.append("%s purpose=%s 已归一化为 %s" % (scene_id, old, purpose))
        scene["purpose"] = purpose
        purposes.add(purpose)

        template = str(scene.get("ui_template", "none")).strip() or "none"
        if template not in allowed_templates:
            old = template
            template = "none"
            warnings.append("%s ui_template=%s 已归一化为 none" % (scene_id, old))
        source = str(scene.get("visual_source", "")).strip()
        if source not in allowed_visual:
            old = source or "empty"
            source = "reusable_ui_template" if template != "none" else "motion_graphic"
            warnings.append("%s visual_source=%s 已归一化为 %s" % (scene_id, old, source))
        if source == "generated_image" and template != "none":
            warnings.append("%s 生成图不能伪装为界面模板，ui_template 已改为 none" % scene_id)
            template = "none"
        scene["visual_source"] = source
        scene["ui_template"] = template

        scene["on_screen_text"] = re.sub(r"\s+", "", str(scene.get("on_screen_text", "")))

        avatar = scene.get("avatar_pip") if isinstance(scene.get("avatar_pip"), dict) else {}
        avatar["visible"] = True
        allowed_positions = {"composition", "top_left", "top_right", "bottom_left", "bottom_right", "custom"}
        position = str(avatar.get("position") or "composition").strip()
        avatar["position"] = position if position in allowed_positions else "composition"
        avatar["behavior"] = str(avatar.get("behavior") or "persistent")
        scene["avatar_pip"] = avatar

        variables = scene.get("content_variables")
        if variables is not None and not isinstance(variables, dict):
            warnings.append("%s content_variables 不是对象，已改为空对象" % scene_id)
            variables = {}
        if isinstance(variables, dict) and variables:
            labels = str(scene.get("labeling", ""))
            if "示例" not in labels and "场景演示" not in labels:
                scene["labeling"] = "场景演示"
                warnings.append("%s 已自动标记“场景演示”" % scene_id)
        scene["content_variables"] = variables if isinstance(variables, dict) else {}

        if not str(scene.get("voiceover_text", "")).strip():
            refs_text = [item.get("text", "") for item in script.get("sentences", []) if isinstance(item, dict) and str(item.get("id")) in valid_refs]
            scene["voiceover_text"] = " ".join(str(x) for x in refs_text if x).strip()
        normalized_scenes.append(scene)

    scenes = normalized_scenes
    if "hook" not in purposes:
        scenes[0]["purpose"] = "hook"
        warnings.append("缺少 hook，已将第一个场景设为 hook")
    if not {"ending", "summary", "cta"} & purposes:
        scenes[-1]["purpose"] = "ending"
        warnings.append("缺少结尾角色，已将最后一个场景设为 ending")
    if not {"insight", "solution"} & {item["purpose"] for item in scenes}:
        scenes[min(1, len(scenes) - 1)]["purpose"] = "insight"
        warnings.append("缺少核心内容角色，已将中间场景设为 insight")

    storyboard["scenes"] = scenes
    storyboard["validation"] = {"errors": [], "warnings": warnings}
    return {
        "storyboard_json": json.dumps(storyboard, ensure_ascii=False),
        "scene_count": len(scenes),
        "storyboard_valid": True,
        "storyboard_errors_json": "[]",
        "storyboard_warnings_json": json.dumps(warnings, ensure_ascii=False)
    }
