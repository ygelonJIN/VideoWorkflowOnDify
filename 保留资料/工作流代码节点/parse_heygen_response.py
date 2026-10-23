def main(response_json: str) -> dict:
    import json

    try:
        data = json.loads(response_json or "{}")
    except Exception:
        raise ValueError("HeyGen 响应不是合法 JSON")
    if not isinstance(data, dict):
        raise ValueError("HeyGen 响应必须是对象")

    def find_value(value, names):
        if isinstance(value, dict):
            for key in names:
                candidate = value.get(key)
                if candidate not in (None, ""):
                    return candidate
            for child in value.values():
                found = find_value(child, names)
                if found not in (None, ""):
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_value(child, names)
                if found not in (None, ""):
                    return found
        return None

    def find_url(value, names):
        candidate = find_value(value, names)
        return str(candidate) if isinstance(candidate, str) and candidate.startswith(("http://", "https://")) else ""

    video_id = str(find_value(data, ["video_id", "videoId", "id"]) or "").strip()
    status = str(find_value(data, ["status", "state"]) or "").strip().lower()
    error = data.get("error")
    error_message = str(error.get("message") if isinstance(error, dict) else error or "")
    return {
        "heygen_video_id": video_id,
        "heygen_status": status,
        "heygen_video_url": find_url(data, ["video_url", "videoUrl", "url"]),
                "heygen_audio_url": find_url(data, ["audio_url", "audioUrl"]),
        "heygen_transcript_url": find_url(data, [
            "transcript_url", "transcriptUrl", "caption_url", "captionUrl",
            "subtitle_url", "subtitleUrl", "srt_url", "srtUrl",
        ]),
        "heygen_error_message": error_message,
        "heygen_response_json": json.dumps(data, ensure_ascii=False)
    }
