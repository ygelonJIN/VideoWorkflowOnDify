def main(request_id: str, html_document: str, voiceover_script: str, heygen_response_json: str) -> dict:
    import json

    html = str(html_document or "").strip()
    voiceover = str(voiceover_script or "").strip()
    if "<!doctype html>" not in html.lower():
        raise ValueError("html_document 不是完整 HTML")
    if not voiceover:
        raise ValueError("voiceover_script 已批准口播不能为空；字幕必须以它为文字真值")
    try:
        response = json.loads(heygen_response_json or "{}")
    except Exception as exc:
        raise ValueError("heygen_response_json 不是合法 JSON") from exc
    if not isinstance(response, dict):
        raise ValueError("heygen_response_json 必须是对象")

    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    video_id = str(data.get("id") or data.get("video_id") or data.get("videoId") or response.get("video_id") or "").strip()
    status = str(data.get("status") or data.get("state") or response.get("status") or response.get("state") or "").strip().lower()
    video_url = str(data.get("video_url") or data.get("videoUrl") or response.get("video_url") or response.get("videoUrl") or "").strip()
    if status != "completed":
        raise ValueError("HeyGen 未完成，禁止输出 processing/failed 的最终构建包：status=" + status)
    if not video_url:
        raise ValueError("HeyGen completed 响应缺少明确 video_url")
    if video_id and video_id not in video_url:
        raise ValueError("video_url 与 video_id 不一致，拒绝输出可能串片的构建包")

    package = {
        "request_id": str(request_id or "").strip(),
        "html_document": html,
        "voiceover_script": voiceover,
        "heygen_response_json": response,
        "heygen_video_id": video_id,
        "heygen_status": status,
        "heygen_video_url": video_url,
    }
    return {
        "build_package_json": json.dumps(package, ensure_ascii=False),
        "voiceover_script": voiceover,
    }
