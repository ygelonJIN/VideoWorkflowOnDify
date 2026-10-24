def main(copy_text: str, brief_json: str) -> dict:
    import hashlib
    import json
    import math
    import re

    def parse(raw, label):
        value = str(raw or "").strip()
        value = re.sub(r"^```(?:json)?\s*|\s*```$", "", value, flags=re.I)
        try:
            return json.loads(value)
        except Exception:
            start, end = value.find("{"), value.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(value[start:end + 1])
                except Exception:
                    pass
            return {"__invalid_json__": True, "__label__": label, "__excerpt__": value[:1000]}

    brief = parse(brief_json, "brief")
    data = parse(copy_text, "文案")
    if not isinstance(data, dict):
        data = {"__invalid_json__": True, "__label__": "文案", "__excerpt__": str(copy_text)[:1000]}
    if data.get("__invalid_json__"):
        excerpt = str(data.get("__excerpt__") or "")
        return {
            "script_json": json.dumps({"voiceover_script": excerpt, "sentences": [], "validation": {"errors": ["JSON 无法解析"]}}, ensure_ascii=False),
            "voiceover_script": excerpt,
            "estimated_duration_seconds": 0.0,
            "script_hash": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
            "copy_valid": False,
            "copy_errors_json": json.dumps(["口播 JSON 无法解析，请自动改写为严格 JSON"], ensure_ascii=False),
            "copy_warnings_json": "[]",
            "recommended_motion_count_min": 6
        }
    warnings = []
    errors = []

    supplied_sentences = data.get("sentences")
    if not isinstance(supplied_sentences, list):
        supplied_sentences = []
    script = str(data.get("voiceover_script", "")).strip()
    if not script and supplied_sentences:
        script = " ".join(str(item.get("text", "") if isinstance(item, dict) else item).strip() for item in supplied_sentences).strip()
    if not script:
        raise ValueError("voiceover_script 和 sentences 不能同时为空")
    data["voiceover_script"] = script

    # The final script is the text truth. Rebuild captions by complete sentences,
    # preserving terminal punctuation and never splitting or joining fragments.
    sentence_texts = [match.group(0).strip() for match in re.finditer(r".*?(?:[。！？!?]+|$)", script, flags=re.S) if match.group(0).strip()]
    sentences = [{"id": "s%02d" % (i + 1), "text": text} for i, text in enumerate(sentence_texts)]
    if not sentences:
        raise ValueError("口播中没有完整句子")

    compact = re.sub(r"\s+", "", script)
    target_duration = float(brief.get("target_duration_seconds", 30))
    min_voice_chars = int(target_duration * 2.67)
    max_voice_chars = int(target_duration * 16.67)
    if len(compact) < min_voice_chars:
        errors.append("口播偏短（%d 字，放行范围 %d-%d 字）" % (
            len(compact), min_voice_chars, max_voice_chars))
    if len(compact) > max_voice_chars:
        errors.append("口播偏长（%d 字，放行范围 %d-%d 字），请删减而不是加速" % (
            len(compact), min_voice_chars, max_voice_chars))

    banned = ["保证出单", "百分百", "马上爆单", "行业第一", "绝对第一", "最强", "最先进"]
    for word in banned:
        if word in script:
            warnings.append("口播包含待合规复核表达: " + word)

    allowed_purposes = {"hook", "pain", "solution", "proof", "cta"}
    normalized_sentences = []
    seen_ids = set()
    cursor = 0.0
    for index, item in enumerate(sentences, 1):
        if not isinstance(item, dict):
            item = {"text": str(item)}
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        sentence_id = str(item.get("id") or "s%02d" % index)
        while sentence_id in seen_ids:
            sentence_id = sentence_id + "_dup"
        seen_ids.add(sentence_id)
        purpose = str(item.get("purpose") or "").strip()
        if purpose not in allowed_purposes:
            old = purpose or "empty"
            purpose = "hook" if index == 1 else ("cta" if index == len(sentences) else "solution")
            warnings.append("%s purpose=%s 已归一化为 %s" % (sentence_id, old, purpose))
        estimated = max(1.2, len(re.sub(r"\s+", "", text)) / 4.35)
        normalized_sentences.append({
            "id": sentence_id,
            "text": text,
            "purpose": purpose,
            "estimated_start_seconds": round(cursor, 2),
            "estimated_end_seconds": round(cursor + estimated, 2)
        })
        cursor += estimated

    if not normalized_sentences:
        raise ValueError("sentences 中没有有效文本")
    if len(normalized_sentences) < 3:
        errors.append("口播至少需要 3 个完整句子")
    normalized_sentences[0]["purpose"] = "hook"
    normalized_sentences[-1]["purpose"] = "cta"
    if not any(item["purpose"] == "solution" for item in normalized_sentences):
        normalized_sentences[min(1, len(normalized_sentences) - 1)]["purpose"] = "solution"

    normalized_captions = [item["text"] for item in normalized_sentences]
    supplied_captions = data.get("burned_in_caption_lines")
    if isinstance(supplied_captions, list) and supplied_captions:
        supplied_clean = [re.sub(r"\s+", "", str(line)) for line in supplied_captions]
        expected_clean = [re.sub(r"\s+", "", line) for line in normalized_captions]
        if supplied_clean != expected_clean:
            warnings.append("burned_in_caption_lines 与完整句子不一致，已强制改为逐句完整字幕")
    data["burned_in_caption_lines"] = normalized_captions

    estimated_duration = round(cursor, 2)
    if estimated_duration > target_duration * 1.10:
        warnings.append("估算口播时长超过目标 10%，已继续输出供人工删减")
    elif estimated_duration > target_duration:
        warnings.append("估算口播略超目标，应在真实时间码阶段删减而非加速")

    data["sentences"] = normalized_sentences
    data["estimated_duration_seconds"] = estimated_duration
    data["validation"] = {"errors": errors, "warnings": warnings}
    script_hash = hashlib.sha256(re.sub(r"\s+", "", script).encode("utf-8")).hexdigest()
    return {
        "script_json": json.dumps(data, ensure_ascii=False),
        "voiceover_script": script,
        "estimated_duration_seconds": estimated_duration,
        "script_hash": script_hash,
        "copy_valid": not errors,
        "copy_errors_json": json.dumps(errors, ensure_ascii=False),
        "copy_warnings_json": json.dumps(warnings, ensure_ascii=False),
        "recommended_motion_count_min": max(6, int(math.ceil(target_duration / 2.5)))
    }
