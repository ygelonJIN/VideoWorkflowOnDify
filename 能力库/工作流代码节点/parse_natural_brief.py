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

    def str_list(value):
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    topic_record = obj(data.get("topic_record") or data.get("campaign"))
    distill_raw = obj(data.get("distill"))
    creative = obj(data.get("creative"))
    context = obj(data.get("context") or data.get("brand"))
    history = obj(data.get("history"))

    topic = str(topic_record.get("topic") or topic_record.get("source_text") or raw or "当前主题").strip()
    source_text = str(topic_record.get("source_text") or raw or topic).strip()

    arguments = []
    for index, item in enumerate(distill_raw.get("arguments") or []):
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        arguments.append({
            "id": str(item.get("id") or "a%d" % (index + 1)).strip(),
            "claim": claim,
            "evidence": str(item.get("evidence") or "").strip(),
            "support": str(item.get("support") or "none").strip(),
            "strength": str(item.get("strength") or "medium").strip(),
        })
    seen_ids = set()
    for argument in arguments:
        while argument["id"] in seen_ids:
            argument["id"] = argument["id"] + "_dup"
        seen_ids.add(argument["id"])

    thesis = str(distill_raw.get("thesis") or "").strip()
    if not thesis:
        thesis = topic
    distill = {
        "source_form": str(distill_raw.get("source_form") or "").strip() or "mixed",
        "thesis": thesis,
        "thesis_source": str(distill_raw.get("thesis_source") or "").strip() or "inferred_from_facts",
        "thesis_type": str(distill_raw.get("thesis_type") or "").strip() or "judgment",
        "arguments": arguments,
        "counterpoints": str_list(distill_raw.get("counterpoints")),
        "dropped": str_list(distill_raw.get("dropped")),
        "open_questions": str_list(distill_raw.get("open_questions")),
    }

    campaign = {
        "topic": topic,
        "source_text": source_text,
        "audience_hint": str(topic_record.get("audience_hint") or topic_record.get("audience") or "").strip(),
        "context": obj(topic_record.get("context")),
        "facts_confirmed": topic_record.get("facts_confirmed") if isinstance(topic_record.get("facts_confirmed"), list) else [],
        "constraints": topic_record.get("constraints") if isinstance(topic_record.get("constraints"), list) else [],
        "duration_seconds": topic_record.get("duration_seconds", 30),
        "distill": distill,
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
