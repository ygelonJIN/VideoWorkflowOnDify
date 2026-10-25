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
        errors.append("口播里没有完整句子，无法生成逐句字幕")
        sentences = [{"id": "s01", "text": script}]

    compact = re.sub(r"\s+", "", script)
    target_duration = float(brief.get("target_duration_seconds") or 0) or 30.0

    banned = ["保证出单", "百分百", "马上爆单", "行业第一", "绝对第一", "最强", "最先进"]
    for word in banned:
        if word in script:
            warnings.append("口播包含待合规复核表达: " + word)

    # ---------------- 内容诊断：只提示，不限制长度和结构 ----------------
    distill = brief.get("distill") if isinstance(brief.get("distill"), dict) else {}
    thesis = str(distill.get("thesis") or "").strip()
    arguments = [item for item in (distill.get("arguments") or [])
                 if isinstance(item, dict) and str(item.get("claim") or "").strip()]
    source_text = str(brief.get("source_text") or "")
    compact_source = re.sub(r"\s+", "", source_text)

    def shingles(text, size=6):
        return {text[index:index + size] for index in range(max(0, len(text) - size + 1))}

    chronology_words = ["然后", "接着", "后来", "再后来", "之后", "当天", "第二天", "隔天", "那时候", "当时", "再往后"]
    chronology_count = sum(script.count(word) for word in chronology_words)

    verbatim_ratio = 0.0
    if len(compact_source) >= 400:
        script_shingles = shingles(compact, 8)
        source_shingles = shingles(compact_source, 8)
        verbatim_ratio = len(script_shingles & source_shingles) / float(max(1, len(script_shingles)))

    dialogue_marks = ["他说", "她说", "我说", "对方说", "他问", "我问", "有人问"]
    dialogue_count = sum(script.count(word) for word in dialogue_marks)

    argument_ids = [str(item.get("id") or "a%d" % (index + 1)) for index, item in enumerate(arguments)]
    coverage = data.get("argument_coverage")
    covered_ids = []
    if isinstance(coverage, list):
        for item in coverage:
            token = ""
            if isinstance(item, dict):
                token = str(item.get("id") or item.get("argument_id") or "").strip()
            else:
                token = str(item or "").strip()
            if token and token not in covered_ids:
                covered_ids.append(token)
    unknown_ids = [token for token in covered_ids if token not in argument_ids]
    if unknown_ids:
        warnings.append("argument_coverage 出现未知论点：" + "、".join(unknown_ids) + "（只提示，不拦截）")
    elif argument_ids and covered_ids:
        missing = [token for token in argument_ids if token not in covered_ids]
        if missing:
            warnings.append("自报覆盖里没提到论点 " + "、".join(missing) + "：可能是合并或略讲，按内容判断是否需要补（只提示，不拦截）")

    if len(re.sub(r"\s+", "", thesis)) >= 6:
        thesis_shingles = shingles(re.sub(r"\s+", "", thesis), 2)
        if thesis_shingles and not any(token in compact for token in thesis_shingles):
            warnings.append("全文没有明显回应 distill.thesis，检查是否换题了（只提示）")

    # 唯一的内容拦截：时间连接词成串说明在按过程复述。不设字数/句数配额。
    if chronology_count >= 5:
        errors.append("口播在按时间顺序复述（时间连接词 %d 处：%s）：改成论点结构，删掉过程衔接" % (
            chronology_count, "、".join(sorted({word for word in chronology_words if word in script}))))
    elif chronology_count >= 3:
        warnings.append("时间连接词 %d 处，偏多则可能在复述过程（只提示）" % chronology_count)

    data["sentences"] = sentences

    allowed_purposes = {"hook", "context", "pain", "insight", "solution", "proof", "example", "ending", "summary", "cta"}
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
            purpose = "hook" if index == 1 else ("ending" if index == len(sentences) else "insight")
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
    normalized_sentences[0]["purpose"] = "hook"
    if normalized_sentences[-1]["purpose"] not in {"ending", "summary", "cta"}:
        normalized_sentences[-1]["purpose"] = "ending"
    if not any(item["purpose"] in {"insight", "solution"} for item in normalized_sentences):
        normalized_sentences[min(1, len(normalized_sentences) - 1)]["purpose"] = "insight"

    normalized_captions = [item["text"] for item in normalized_sentences]
    supplied_captions = data.get("burned_in_caption_lines")
    if isinstance(supplied_captions, list) and supplied_captions:
        supplied_clean = [re.sub(r"\s+", "", str(line)) for line in supplied_captions]
        expected_clean = [re.sub(r"\s+", "", line) for line in normalized_captions]
        if supplied_clean != expected_clean:
            warnings.append("burned_in_caption_lines 与完整句子不一致，已强制改为逐句完整字幕")
    data["burned_in_caption_lines"] = normalized_captions

    estimated_duration = round(cursor, 2)

    data["sentences"] = normalized_sentences
    data["estimated_duration_seconds"] = estimated_duration
    data["argument_coverage"] = coverage if isinstance(coverage, list) else []
    data["content_diagnostics"] = {
        "thesis": thesis,
        "argument_ids": argument_ids,
        "covered_argument_ids": covered_ids,
        "chronology_words": chronology_count,
        "verbatim_ratio": round(verbatim_ratio, 3),
        "dialogue_marks": dialogue_count,
        "characters": len(compact),
        "sentences": len(normalized_sentences),
    }
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
