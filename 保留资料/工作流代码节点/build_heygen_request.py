def main(request_id: str, approved_package_json: str, production_requirements: str, avatar_id: str, voice_id: str) -> dict:
    import json

    try:
        package = json.loads(approved_package_json or "{}")
    except Exception:
        raise ValueError("approved_package_json 不是合法 JSON")
    if not isinstance(package, dict):
        raise ValueError("approved_package_json 必须是对象")

    script = package.get("approved_script") if isinstance(package.get("approved_script"), dict) else {}
    brief = package.get("brief") if isinstance(package.get("brief"), dict) else {}
    voiceover = str(script.get("voiceover_script") or "").strip()
    if not voiceover:
        raise ValueError("缺少已批准口播")

    title = str(request_id or "").strip() or str(brief.get("topic") or brief.get("source_text") or "video")
    payload = {
        "type": "avatar",
        "title": title,
        "avatar_id": str(avatar_id or "").strip(),
        "voice_id": str(voice_id or "").strip(),
        "script": voiceover,
        "resolution": "1080p",
        "aspect_ratio": "9:16",
        "output_format": "mp4"
    }
    return {"heygen_request_json": json.dumps(payload, ensure_ascii=False)}
