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

    campaign = obj(data.get("campaign"))
    creative = obj(data.get("creative"))
    brand = obj(data.get("brand"))
    history = obj(data.get("history"))

    if not campaign:
        fallback_text = raw or "未提供活动需求"
        campaign = {
            "brand": "未提供品牌",
            "product": "未提供产品",
            "audience": "目标客户",
            "pain": fallback_text[:120],
            "facts_confirmed": [fallback_text[:200]] if fallback_text else [],
            "offer": "",
            "cta": "进一步了解",
            "duration_seconds": 30,
            "platform": "douyin"
        }

    return {
        "campaign_json": json.dumps(campaign, ensure_ascii=False),
        "creative_json": json.dumps(creative, ensure_ascii=False),
        "brand_json": json.dumps(brand, ensure_ascii=False),
        "history_json": json.dumps(history, ensure_ascii=False)
    }
