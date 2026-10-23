def main(review_text: str) -> dict:
    import json
    import re

    raw = str(review_text or "").strip()
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
    if not data:
        data = {
            "decision": "needs_changes",
            "risk_level": "medium",
            "violations": [],
            "unverified_claims": [],
            "normalization_warnings": ["合规 JSON 无法解析，已按 needs_changes 继续人工审核"]
        }

    warnings = list(data.get("normalization_warnings", [])) if isinstance(data.get("normalization_warnings"), list) else []
    decision = str(data.get("decision", "")).strip().lower()
    if decision not in {"approved", "needs_changes", "rejected"}:
        decision = "needs_changes"
        data["decision"] = decision
        warnings.append("decision 缺失或无效，已归一化为 needs_changes")
    risk_level = str(data.get("risk_level", "")).strip().lower()
    if risk_level not in {"low", "medium", "high"}:
        risk_level = "medium"
        data["risk_level"] = risk_level
        warnings.append("risk_level 缺失或无效，已归一化为 medium")

    violations = data.get("violations")
    if not isinstance(violations, list):
        violations = []
        data["violations"] = violations
    unverified = data.get("unverified_claims")
    if not isinstance(unverified, list):
        unverified = []
        data["unverified_claims"] = unverified

    error_count = len(unverified)
    error_count += sum(1 for item in violations if isinstance(item, dict) and item.get("severity") == "error")
    if decision == "rejected":
        error_count += 1
    data["normalization_warnings"] = warnings

    return {
        "compliance_json": json.dumps(data, ensure_ascii=False),
        "compliance_decision": decision,
        "risk_level": risk_level,
        "compliance_error_count": error_count
    }
