def main(brief_json: str, draft_script_json: str, storyboard_json: str, motion_plan_json: str, compliance_json: str, review_action: str, tts_provider: str, tts_base_url: str, tts_model: str, tts_voice: str) -> dict:
    import hashlib
    import json

    def fail(message):
        return {
            "approved_package_json": "{}",
            "approved_voiceover_script": "",
            "approval_status": "failed",
            "package_error": message,
        }

    def parse(raw, label):
        try:
            data = json.loads(raw or "")
        except Exception as exc:
            raise ValueError(label + " 不是合法 JSON（" + str(exc)[:120] + "）")
        if not isinstance(data, dict):
            raise ValueError(label + " 必须是 JSON 对象")
        return data

    try:
        brief = parse(brief_json, "brief")
        script = parse(draft_script_json, "原始脚本")
        storyboard = parse(storyboard_json, "storyboard")
        motion = parse(motion_plan_json, "motion_plan")
    except ValueError as exc:
        return fail(str(exc))

    try:
        compliance = parse(compliance_json, "合规审核")
    except ValueError:
        compliance = {}
    if str(compliance.get("decision", "")).strip().lower() == "rejected":
        reasons = []
        for item in compliance.get("violations") or []:
            if isinstance(item, dict) and str(item.get("text") or "").strip():
                reasons.append(str(item.get("text")).strip())
        for item in compliance.get("unverified_claims") or []:
            if isinstance(item, dict) and str(item.get("text") or "").strip():
                reasons.append(str(item.get("text")).strip())
        for item in compliance.get("revision_instructions") or []:
            reasons.append(str(item))
        return fail("合规审核判定 rejected，禁止打包" + ("：" + "；".join(reasons[:5]) if reasons else ""))

    voiceover = str(script.get("voiceover_script", "")).strip()
    if not voiceover:
        return fail("人工确认后的口播为空：A06/A07 没有产出可用文案")

    base_url_options = {
        "默认（按量付费）": "https://api.xiaomimimo.com/v1",
        "Token Plan - 中国": "https://token-plan-cn.xiaomimimo.com/v1",
        "Token Plan - 新加坡": "https://token-plan-sgp.xiaomimimo.com/v1",
        "Token Plan - 欧洲": "https://token-plan-ams.xiaomimimo.com/v1",
    }
    raw_base_url = str(tts_base_url or "").strip()
    tts_config = {
        "provider": str(tts_provider or "mimo").strip() or "mimo",
        "base_url": base_url_options.get(raw_base_url, raw_base_url),
        "model": str(tts_model or "").strip(),
        "voice": str(tts_voice or "").strip(),
    }
    scenes = storyboard.get("scenes") if isinstance(storyboard.get("scenes"), list) else []
    normalized_scenes = []
    for index, scene in enumerate(scenes):
        if isinstance(scene, dict) and str(scene.get("visual_source", "")).strip() == "generated_image":
            scene = dict(scene)
            scene["visual_source"] = "reusable_ui_template"
            if str(scene.get("ui_template") or "").strip() in ("", "none"):
                scene["ui_template"] = "story"
            scenes[index] = scene
            normalized_scenes.append(str(scene.get("scene_id") or index))
    if normalized_scenes:
        validation = storyboard.get("validation") if isinstance(storyboard.get("validation"), dict) else {}
        warnings = validation.get("warnings") if isinstance(validation.get("warnings"), list) else []
        warnings.append("黑帧模式没有出图能力，" + "、".join(normalized_scenes) + " 的 generated_image 已归一为 reusable_ui_template")
        validation["warnings"] = warnings
        storyboard["validation"] = validation

    package = {
        "approval": {
            "status": "approved",
            "feedback": "人工审核动作：" + str(review_action or "approve"),
            "approved_script_hash": hashlib.sha256(voiceover.encode("utf-8")).hexdigest()
        },
        "brief": brief,
        "approved_script": script,
        "storyboard": storyboard,
        "motion_plan": motion,
        "compliance": {
            "decision": str(compliance.get("decision") or ""),
            "risk_level": str(compliance.get("risk_level") or ""),
            "violations": compliance.get("violations") or [],
            "unverified_claims": compliance.get("unverified_claims") or [],
        },
        "tts_config": tts_config,
    }
    return {
        "approved_package_json": json.dumps(package, ensure_ascii=False),
        "approved_voiceover_script": voiceover,
        "approval_status": "approved",
        "package_error": "",
    }
