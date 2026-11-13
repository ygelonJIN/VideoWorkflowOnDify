def main(strategy_text: str) -> dict:
    import json
    import re

    raw = str(strategy_text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    try:
        data = json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        data = {}
        if start >= 0 and end > start:
            try:
                data = json.loads(raw[start:end + 1])
            except Exception:
                data = {}
    if not isinstance(data, dict):
        data = {}
    fallback_warning = ""
    if not data:
        fallback_warning = "内容策略 JSON 无法解析，已生成基础角度继续"
        data = {"core_message": raw[:200] or "聚焦一个具体业务问题", "angle_id": "angle_generated"}

    warnings = [fallback_warning] if fallback_warning else []
    core_message = str(data.get("core_message", "")).strip()
    hook = str(data.get("hook", "")).strip()
    hooks = data.get("hook_candidates")
    if not isinstance(hooks, list):
        hooks = []
    hooks = [str(item).strip() for item in hooks if str(item).strip()]
    if not hooks:
        hooks = [hook or core_message or "聚焦一个具体业务问题"]
        warnings.append("hook_candidates 缺失，已使用 hook/core_message 生成")
    data["hook_candidates"] = hooks
    data["hook"] = hooks[0]

    if not core_message:
        core_message = data["hook"]
        data["core_message"] = core_message
        warnings.append("core_message 缺失，已使用 hook 生成")
    if not str(data.get("angle_id", "")).strip():
        data["angle_id"] = "angle_generated"
        warnings.append("angle_id 缺失，已生成 angle_generated")

    claims_raw = data.get("argument_claims")
    claims = {}
    if isinstance(claims_raw, dict):
        for key, value in claims_raw.items():
            text = str(value or "").strip()
            if text:
                claims[str(key).strip()] = text
    order_raw = data.get("argument_order")
    order = []
    if isinstance(order_raw, list):
        for item in order_raw:
            token = str(item or "").strip()
            if token and token not in order:
                order.append(token)
    if not order:
        order = list(claims.keys())
        if order:
            warnings.append("argument_order 缺失，已按 argument_claims 顺序展开")
    missing_claims = [token for token in order if token not in claims]
    if missing_claims:
        warnings.append("argument_order 中的 " + "、".join(missing_claims) + " 没有对应 argument_claims")
    data["argument_order"] = order
    data["argument_claims"] = claims
    if not order:
        warnings.append("本次没有论点排序，视频只能按单一论点展开")

    data["normalization_warnings"] = warnings

    return {
        "strategy_json": json.dumps(data, ensure_ascii=False),
        "angle_id": str(data["angle_id"]),
        "hook": str(data["hook"]),
        "core_message": core_message,
        "parse_ok": True
    }
