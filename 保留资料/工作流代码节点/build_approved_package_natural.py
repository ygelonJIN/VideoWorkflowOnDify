def main(brief_json: str, draft_script_json: str, storyboard_json: str, motion_plan_json: str, review_action: str) -> dict:
    import hashlib
    import json

    def parse(raw, label):
        try:
            data = json.loads(raw or "")
        except Exception:
            raise ValueError(label + " 不是合法 JSON")
        if not isinstance(data, dict):
            raise ValueError(label + " 必须是 JSON 对象")
        return data

    brief = parse(brief_json, "brief")
    script = parse(draft_script_json, "原始脚本")
    storyboard = parse(storyboard_json, "storyboard")
    motion = parse(motion_plan_json, "motion_plan")

    voiceover = str(script.get("voiceover_script", "")).strip()
    if not voiceover:
        raise ValueError("自动通过的口播不能为空")

    package = {
        "approval": {
            "status": "approved",
            "feedback": "自动生产模式：" + str(review_action or "approve"),
            "approved_script_hash": hashlib.sha256(voiceover.encode("utf-8")).hexdigest()
        },
        "brief": brief,
        "approved_script": script,
        "storyboard": storyboard,
        "motion_plan": motion
    }
    return {
        "approved_package_json": json.dumps(package, ensure_ascii=False),
        "approved_voiceover_script": voiceover,
        "approval_status": "approved"
    }
