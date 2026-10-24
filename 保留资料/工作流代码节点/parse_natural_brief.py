def main(structured_input_text: str) -> dict:
    import json
    import re

    raw = str(structured_input_text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    data = {}
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            data = parsed
    except Exception:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(cleaned[start:end + 1])
                if isinstance(parsed, dict):
                    data = parsed
            except Exception:
                data = {}

    def obj(value):
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return {}

    topic_record = obj(data.get("topic_record") or data.get("campaign"))
    creative = obj(data.get("creative"))
    context = obj(data.get("context") or data.get("brand"))
    history = obj(data.get("history"))

    topic = str(topic_record.get("topic") or topic_record.get("source_text") or raw or "当前主题").strip()
    source_text = str(topic_record.get("source_text") or raw or topic).strip()
    campaign = {
        "topic": topic,
        "source_text": source_text,
        "audience_hint": str(topic_record.get("audience_hint") or topic_record.get("audience") or "").strip(),
        "context": obj(topic_record.get("context")),
        "facts_confirmed": topic_record.get("facts_confirmed") if isinstance(topic_record.get("facts_confirmed"), list) else [],
        "constraints": topic_record.get("constraints") if isinstance(topic_record.get("constraints"), list) else [],
        "duration_seconds": topic_record.get("duration_seconds", 30),
    }
    for key in ("brand", "product", "audience", "pain", "offer", "cta", "tone", "platform", "proof"):
        value = topic_record.get(key)
        if value not in (None, "", [], {}):
            campaign[key] = value

    return {
        "campaign_json": json.dumps(campaign, ensure_ascii=False),
        "creative_json": json.dumps(creative, ensure_ascii=False),
        "brand_json": json.dumps(context, ensure_ascii=False),
        "history_json": json.dumps(history, ensure_ascii=False)
    }
