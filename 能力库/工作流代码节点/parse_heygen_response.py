def main(response_json: str) -> dict:
    import json

    try:
        data = json.loads(response_json or "{}")
    except Exception:
        raise ValueError("HeyGen 响应不是合法 JSON")
    if not isinstance(data, dict):
        raise ValueError("HeyGen 响应必须是对象")

    def path_value(root, *path):
        value = root
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value if value not in (None, "") else None

    def find_key(value, names):
        if isinstance(value, dict):
            for name in names:
                candidate = value.get(name)
                if candidate not in (None, ""):
                    return candidate
            for child in value.values():
                found = find_key(child, names)
                if found not in (None, ""):
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_key(child, names)
                if found not in (None, ""):
                    return found
        return None

    def find_url(names):
        candidate = find_key(data, names)
        return str(candidate) if isinstance(candidate, str) and candidate.startswith(("http://", "https://")) else ""

    video_id = str(
        path_value(data, "data", "id") or path_value(data, "data", "video_id") or
        path_value(data, "data", "videoId") or path_value(data, "id") or
        path_value(data, "video_id") or path_value(data, "videoId") or ""
    ).strip()
    status = str(
        path_value(data, "data", "status") or path_value(data, "data", "state") or
        path_value(data, "status") or path_value(data, "state") or ""
    ).strip().lower()
    error = data.get("error") or path_value(data, "data", "error")
    error_message = str(error.get("message") if isinstance(error, dict) else error or "")

    video_url = find_url(["video_url", "videoUrl"])
    if video_url and video_id and video_id not in video_url:
        raise ValueError("HeyGen video_url 与 video_id 不一致，拒绝返回可能串片的旧视频")
    if status == "completed" and not video_url:
        raise ValueError("HeyGen completed 响应缺少明确 video_url")

    return {
        "heygen_video_id": video_id,
        "heygen_status": status,
        "heygen_video_url": video_url,
        "heygen_audio_url": find_url(["audio_url", "audioUrl"]),
        "heygen_transcript_url": find_url([
            "transcript_url", "transcriptUrl", "caption_url", "captionUrl",
            "subtitle_url", "subtitleUrl", "srt_url", "srtUrl",
        ]),
        "heygen_error_message": error_message,
        "heygen_response_json": json.dumps(data, ensure_ascii=False)
    }
