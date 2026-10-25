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

    distill = campaign.get("distill") if isinstance(campaign.get("distill"), dict) else {}
    arguments = [item for item in (distill.get("arguments") or []) if isinstance(item, dict) and str(item.get("claim") or "").strip()]
    thesis = str(distill.get("thesis") or "").strip()
    source_form = str(distill.get("source_form") or "").strip() or "mixed"
    if not thesis:
        thesis = topic
        normalization_warnings.append("distill.thesis 缺失，已回落到主题句")
    if not arguments:
        normalization_warnings.append("distill.arguments 为空，本次只能按单一论点展开")
    distill = {
        "source_form": source_form,
        "thesis": thesis,
        "thesis_source": str(distill.get("thesis_source") or "").strip() or "inferred_from_facts",
        "thesis_type": str(distill.get("thesis_type") or "").strip() or "judgment",
        "arguments": arguments,
        "counterpoints": [str(item).strip() for item in (distill.get("counterpoints") or []) if str(item).strip()],
        "dropped": [str(item).strip() for item in (distill.get("dropped") or []) if str(item).strip()],
        "open_questions": [str(item).strip() for item in (distill.get("open_questions") or []) if str(item).strip()],
    }
    argument_count = len(distill["arguments"])
    source_chars = len(re.sub(r"\s+", "", source_text))

    raw_duration = str(campaign.get("duration_seconds") or "").strip()
    duration = 0.0
    if raw_duration:
        try:
            duration = max(1.0, float(raw_duration))
        except Exception:
            duration = 0.0
    if duration <= 0:
        duration = 30.0
        normalization_warnings.append("未指定时长，编排参考时长取 30 秒；最终以真实口播为准")

    brief = {
        "topic": topic,
        "source_text": source_text,
        "source_chars": source_chars,
        "audience_hint": audience_hint,
        "context": context,
        "facts_confirmed": facts_confirmed,
        "constraints": constraints,
        "creative": creative,
        "history": history,
        "distill": distill,
        "argument_count": argument_count,
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
            "content_assumptions": "none",
            "argument_spine": True,
            "no_chronology_retelling": True,
            "source_text_is_material_only": True,
            "duration_is_reference_only": True,
            "no_length_quota": True,
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
        "proof_fingerprint": normalized_text,
        "validation_ok": True
    }
