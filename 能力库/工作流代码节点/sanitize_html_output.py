def main(html_document: str) -> dict:
    import json
    import re

    raw = str(html_document or "")
    notes = []
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
        notes.append("已去除 Markdown 代码围栏")
    cleaned = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", text, flags=re.I)
    if cleaned != text:
        notes.append("已移除 tool_call 工具调用块")
        text = cleaned
    low = text.lower()
    if "<html" not in low and "<!doctype" not in low:
        if text != raw.strip():
            notes.append("未提取到 HTML，保留原始输出供校验定位")
            text = raw.strip()
        low = text.lower()
    start = low.find("<!doctype html>")
    if start < 0:
        start = low.find("<html")
    end = low.rfind("</html>")
    if start > 0 and end > start:
        notes.append("已丢弃 HTML 之前的 " + str(start) + " 字符")
        text = text[start:end + 7]
    elif start > 0:
        notes.append("已丢弃 HTML 之前的 " + str(start) + " 字符，但没有 </html> 收尾")
        text = text[start:]
    elif end >= 0 and end + 7 < len(text):
        notes.append("已丢弃 </html> 之后的 " + str(len(text) - end - 7) + " 字符")
        text = text[:end + 7]
    html = text.strip()
    if not html:
        notes.append("没有从输出中提取到 HTML")
    return {
        "html_document": html,
        "html_guard_json": json.dumps({
            "applied": notes,
            "input_chars": len(raw),
            "output_chars": len(html),
            "has_doctype": "<!doctype html>" in html.lower(),
            "has_closing_html": "</html>" in html.lower(),
        }, ensure_ascii=False),
    }
