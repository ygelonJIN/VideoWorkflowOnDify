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
    brand = load(brand_json, {})
    history = load(history_json, {})

    required = ["brand", "product", "audience", "pain", "cta"]
    missing = [key for key in required if not str(campaign.get(key, "")).strip()]
    if missing:
        raise ValueError("缺少必填字段: " + ", ".join(missing))

    duration = float(campaign.get("duration_seconds") or 30)
    duration = max(25.0, min(35.0, duration))
    proof = str(campaign.get("proof") or "").strip()
    facts_confirmed = campaign.get("facts_confirmed")
    if not isinstance(facts_confirmed, list):
        facts_confirmed = [proof] if proof else []

    brief = {
        "brand": campaign.get("brand"),
        "product": campaign.get("product"),
        "audience": campaign.get("audience"),
        "pain": campaign.get("pain"),
        "facts_confirmed": facts_confirmed,
        "offer": campaign.get("offer", ""),
        "cta": campaign.get("cta"),
        "tone": campaign.get("tone", "专业、直接、可信"),
        "platform": campaign.get("platform", "douyin"),
        "language": "zh-CN",
        "aspect_ratio": "9:16",
        "resolution": "1080x1920",
        "fps": 25,
        "target_duration_seconds": duration,
        "creative": creative,
        "brand_system": brand,
        "history": history,
        "hard_rules": {
            "one_angle_per_video": True,
            "voice_chars_per_second": 4.2,
            "caption_unit": "complete_sentence",
            "avatar_pip_position": "top_right",
            "semantic_change_interval_seconds": 2.5
        }
    }

    normalized_text = re.sub(r"\s+", "", str(campaign.get("proof", ""))).lower()
    return {
        "brief_json": json.dumps(brief, ensure_ascii=False),
        "target_duration_seconds": duration,
        "max_voice_chars": int(duration * 4.6),
        "min_voice_chars": int(duration * 4.0),
        "proof_fingerprint": normalized_text,
        "validation_ok": True
    }
