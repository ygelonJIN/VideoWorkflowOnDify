def main(campaign_json: str, creative_json: str, brand_json: str, history_json: str) -> dict:
    import json
    import re

    def load(value, fallback):
        try:
            parsed = json.loads(value or "")
            return parsed if isinstance(parsed, dict) else fallback
        except Exception:
            return fallback

    campaign = load(campaign_json, {})
    creative = load(creative_json, {})
    context = load(brand_json, {})
    history = load(history_json, {})

    topic = str(campaign.get("topic") or campaign.get("source_text") or campaign.get("product") or campaign.get("brand") or "当前主题").strip()
    source_text = str(campaign.get("source_text") or topic).strip()
    audience_hint = str(campaign.get("audience_hint") or campaign.get("audience") or "").strip()
    facts_confirmed = campaign.get("facts_confirmed") if isinstance(campaign.get("facts_confirmed"), list) else []
    constraints = campaign.get("constraints") if isinstance(campaign.get("constraints"), list) else []
    normalization_warnings = []
    if not str(campaign.get("topic") or "").strip():
        normalization_warnings.append("topic 缺失，已使用 source_text/当前主题作为主题")

    try:
        duration = float(campaign.get("duration_seconds") or 30)
    except Exception:
        duration = 30.0
        normalization_warnings.append("duration_seconds 无法解析，已使用默认 30 秒")
    duration = max(25.0, min(35.0, duration))

    brief = {
        "topic": topic,
        "source_text": source_text,
        "audience_hint": audience_hint,
        "context": context,
        "facts_confirmed": facts_confirmed,
        "constraints": constraints,
        "creative": creative,
        "history": history,
        "language": "zh-CN",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 25,
        "target_duration_seconds": duration,
        "normalization_warnings": normalization_warnings,
        "hard_rules": {
            "one_angle_per_video": True,
            "voice_chars_per_second": 4.2,
            "caption_unit": "complete_sentence",
            "content_assumptions": "none"
        }
    }
    for key in ("brand", "product", "audience", "pain", "offer", "cta", "tone", "platform", "proof"):
        value = campaign.get(key)
        if value not in (None, "", [], {}):
            brief[key] = value

    normalized_text = re.sub(r"\s+", "", source_text).lower()
    return {
        "brief_json": json.dumps(brief, ensure_ascii=False),
        "target_duration_seconds": duration,
        "max_voice_chars": int(duration * 4.6),
        "min_voice_chars": int(duration * 4.0),
        "proof_fingerprint": normalized_text,
        "validation_ok": True
    }
