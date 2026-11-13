def main(response_json: str) -> dict:
    import json

    try:
        data = json.loads(response_json or "{}")
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}

    def find_value(value, names):
        if isinstance(value, dict):
            for name in names:
                if value.get(name) not in (None, ""):
                    return value[name]
            for child in value.values():
                found = find_value(child, names)
                if found not in (None, ""):
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find_value(child, names)
                if found not in (None, ""):
                    return found
        return None

    status = str(find_value(data, ["status", "state"]) or "").strip().lower()
    done = status in {"completed", "failed", "cancelled"}
    return {
        "status": status,
        "done": done,
        "response_json": json.dumps(data, ensure_ascii=False)
    }
