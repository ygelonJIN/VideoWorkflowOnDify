def main(background_spec_text: str) -> dict:
    import json
    import re

    raw = str(background_spec_text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    warnings = []
    spec = None

    if raw:
        try:
            spec = json.loads(raw)
        except Exception as error:
            start = raw.find("{")
            if start >= 0:
                for index in range(len(raw) - 1, start, -1):
                    if raw[index] != "}":
                        continue
                    candidate = re.sub(r",\s*([}\]])", r"\1", raw[start:index + 1])
                    try:
                        spec = json.loads(candidate)
                        break
                    except Exception:
                        continue
            if spec is None:
                warnings.append("背景规格 JSON 无法解析（%s）" % str(error)[:60])

    if not isinstance(spec, dict):
        spec = {}

    css = spec.get("css")
    css = "" if css is None else str(css)
    js = spec.get("js")
    js = "" if js is None else str(js)

    # 去掉可能被包进来的标签，只留纯 CSS / JS
    css = re.sub(r"^\s*<style[^>]*>|</style>\s*$", "", css.strip(), flags=re.I)
    js = re.sub(r"^\s*<script[^>]*>|</script>\s*$", "", js.strip(), flags=re.I)

    if not css:
        warnings.append("背景规格没有给出 css：背景层会是空的")
    if re.search(r"\.scene\b|#scenes\b|\bcaption\b", css):
        warnings.append("背景 css 里出现了场景或字幕选择器（不允许），已保留原文但需要人工复核")
    if re.search(r"Math\.random|performance\.now|requestAnimationFrame|setInterval|setInterval", js):
        warnings.append("背景 js 用了非确定性 API（随机/墙钟/rAF/定时器），渲染会不稳定")

    design = spec.get("design") if isinstance(spec.get("design"), dict) else {}
    must_not = spec.get("must_not") if isinstance(spec.get("must_not"), list) else []

    return {
        "background_css": css,
        "background_js": js,
        "background_spec_json": json.dumps({
            "background_version": spec.get("background_version") or "1.0",
            "design": design,
            "must_not": must_not,
            "has_css": bool(css),
            "has_js": bool(js),
        }, ensure_ascii=False),
        "background_valid": bool(css),
        "background_warnings_json": json.dumps(warnings, ensure_ascii=False),
    }
