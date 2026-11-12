def main(html: str, script: str) -> dict:
    """把本屏 HTML 与动效脚本合并；给没被动作命中的元素补一个默认入场，避免永远隐藏。"""
    import re

    h = str(html or "").strip()
    s = str(script or "").strip()
    m = re.search(r"<script[^>]*>[\s\S]*?</script>", s, re.I)
    block = m.group(0) if m else (("<script>\n" + s + "\n</script>") if s else "")

    sid_match = re.search(r'data-scene="([^"]+)"', h)
    sid = sid_match.group(1) if sid_match else ""
    if sid:
        names = {n for n in re.findall(r'data-anim="([\w-]+)"', h) if n}
        referenced = {n for n in re.findall(r'data-anim="([\w-]+)"', s) if n}
        missing = sorted(names - referenced - {"bg", "scrim"})
        if missing:
            lines = []
            for name in missing:
                lines.append(
                    "timeline.fromTo('[data-scene=\"%s\"] [data-anim=\"%s\"]', {opacity:0, y:'0.3em'}, "
                    "{opacity:1, y:0, duration:0.5, ease:'power2.out'}, at(0.6));" % (sid, name))
            extra = ("<script>\nwindow.__sceneBuilders.push(function(timeline, at){\n  "
                     + "\n  ".join(lines) + "\n});\n</script>")
            block = (block + "\n" + extra).strip()

    return {"output": (h + "\n" + block).strip()}
