"""U 卡槽位引擎：把组件的示例 HTML 变成「文本洞模板」，落版节点只填文字。

- 模板是字符串级的：只把文本节点换成 {sN}，其它字节（属性大小写、SVG path、自闭合）原样保留；
- 只在「结构、骨架、class 完全一致且连续」时才认作可重复行；混着状态类的列表保持固定槽位，
  避免把 is-done / is-on 复制到每一行；
- 渲染只接受纯文本，统一 HTML 转义。模型拿不到任何标签。
"""
import argparse
import json
import pathlib
import re
import sys
import re
from html import escape

VOID = {"br", "img", "input", "hr", "meta", "link", "source", "track", "wbr"}
SYMBOL = set("▾▸▴·•—–-|/\\:：,，.。!！?？()（）[]【】<>«»←→↑↓✓✔✕★☆●○◆◇")
STATE_CLASS = {"is-on", "is-done", "on", "hot", "big", "active", "w2", "h2", "right"}


class El:
    __slots__ = ("tag", "attrs", "start", "end", "open_end", "close_start", "children", "parent", "texts", "selfclose")

    def __init__(self, tag, attrs, start, open_end, parent):
        self.tag = tag
        self.attrs = attrs
        self.start = start
        self.open_end = open_end
        self.end = None
        self.close_start = None
        self.children = []
        self.parent = parent
        self.texts = []
        self.selfclose = False


TAG_RE = re.compile(r"<(/?)([a-zA-Z][\w:-]*)((?:\s+[^<>]*?)?)(/?)>", re.S)


def parse(html):
    root = El("#root", "", 0, 0, None)
    stack = [root]
    pos = 0
    for m in TAG_RE.finditer(html):
        if m.start() > pos:
            stack[-1].texts.append((pos, m.start()))
        closing, tag, attrs, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if closing:
            for i in range(len(stack) - 1, 0, -1):
                if stack[i].tag == tag:
                    node = stack[i]
                    node.close_start = m.start()
                    node.end = m.end()
                    for j in range(len(stack) - 1, i - 1, -1):
                        if stack[j].end is None:
                            stack[j].end = m.end()
                    del stack[i:]
                    break
        else:
            node = El(tag, attrs, m.start(), m.end(), stack[-1])
            stack[-1].children.append(node)
            if selfclose or tag in VOID:
                node.selfclose = True
                node.end = m.end()
            else:
                stack.append(node)
        pos = m.end()
    if pos < len(html):
        stack[-1].texts.append((pos, len(html)))
    for node in stack:
        if node.end is None:
            node.end = len(html)
    return root


def _attr(node, name):
    m = re.search(r'\b%s\s*=\s*"([^"]*)"' % name, node.attrs or "", re.I)
    return m.group(1) if m else ""


def shape(node):
    classes = [c for c in _attr(node, "class").split() if c not in STATE_CLASS]
    return node.tag + "." + ".".join(sorted(classes))


def skeleton(node):
    if not node.children:
        return node.tag
    return node.tag + "(" + ",".join(skeleton(c) for c in node.children) + ")"


def is_symbol(text):
    s = text.strip()
    if not s:
        return True
    return all(ch in SYMBOL for ch in s) and len(s) <= 3


def holes_of(html, node):
    """node 区间内的文本洞：返回 [(start,end,text)]，按文档顺序。"""
    out = []
    for a, b in node.texts:
        raw = html[a:b]
        if raw.strip() and not is_symbol(raw):
            out.append((a, b, raw))
    for child in node.children:
        if child.selfclose:
            continue
        out.extend(holes_of(html, child))
    out.sort()
    return out


def build(code, repeat_hint=None):
    root = parse(code)
    top = [c for c in root.children if c.tag != "#root"]
    if not top:
        return None
    if len(top) > 1:
        wrapper = El("#frag", "", top[0].start, top[0].start, None)
        wrapper.children = top
        wrapper.close_start = top[-1].end
        wrapper.end = top[-1].end
        wrapper.texts = []
        for left, right in zip(top, top[1:]):
            if right.start > left.end:
                wrapper.texts.append((left.end, right.start))
    else:
        wrapper = top[0]
    groups = {}
    for child in wrapper.children:
        if child.tag == "#text":
            continue
        groups.setdefault((shape(child), skeleton(child)), []).append(child)
    unit = None
    for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        # 只有在「结构、骨架、class 完全一致」时才认作可重复行；
        # 混着状态类（is-done / is-on / w2）的列表保持固定槽位，避免把状态复制到每一行。
        if len(items) >= 2 and len({(skeleton(i), i.attrs) for i in items}) == 1:
            idx = [wrapper.children.index(i) for i in items]
            if idx == list(range(idx[0], idx[0] + len(idx))):
                unit = items
                break
    if unit is None and repeat_hint:
        if repeat_hint.get("self"):
            unit = [wrapper]
            wrapper_is_unit = True
        else:
            tag = repeat_hint.get("tag")
            needle = repeat_hint.get("class_contains")
            skip = int(repeat_hint.get("skip") or 0)
            picked = [c for c in wrapper.children
                      if c.tag == tag and (not needle or needle in _attr(c, "class"))][skip:]
            if picked:
                unit = picked

    if unit and len(unit) == 1 and unit[0] is wrapper:
        # 整个组件就是一行：模板是 {r0}，行模板是整段
        row_tpl, row_slots = _hole_slice(code, wrapper)
        return {"tpl": code[:wrapper.start] + "{r0}" + code[wrapper.end:], "before": 0, "row_slots": row_slots,
                "after": 0, "row": row_tpl, "repeat": True, "rows_default": 1,
                "outer_tpl": code[:wrapper.start] + "{r0}" + code[wrapper.end:]}

    if unit:
        unit_holes = holes_of(code, unit[0])
        if not unit_holes:
            unit = None
    if unit:
        n = len(unit_holes)
        unit_ids = {id(x) for x in unit}
        outer_holes = [(a, b, t) for a, b, t in holes_of(code, wrapper)
                       if not any(u.start <= a < u.end for u in unit)]
        before = sum(1 for a, b, t in outer_holes if a < unit[0].start)
        after = len(outer_holes) - before
        outer_tpl = _slice(code, wrapper, unit, unit_ids, outer_holes, n, before, after)
        row_tpl, row_slots = _hole_slice(code, unit[0])
        return {"tpl": outer_tpl, "before": before, "row_slots": row_slots, "after": after,
                "row": row_tpl, "repeat": True, "rows_default": len(unit), "outer_tpl": outer_tpl}

    tpl, slots = _hole_slice(code, wrapper)
    return {"tpl": tpl, "before": slots, "row_slots": 0, "after": 0, "row": None,
            "repeat": False, "rows_default": 1, "outer_tpl": tpl}


def _hole_slice(code, node):
    holes = holes_of(code, node)
    out = [code[node.start:node.open_end]]
    pos = node.open_end
    for i, (a, b, t) in enumerate(holes):
        out.append(code[pos:a])
        out.append("{s%d}" % i)
        pos = b
    out.append(code[pos:node.close_start or node.end])
    out.append(code[node.close_start or node.end:node.end])
    return "".join(out), len(holes)


def _slice(code, wrapper, unit, unit_ids, outer_holes, n, before, after):
    def emit(a, b):
        seg = []
        pos = a
        for idx, (ha, hb, _t) in enumerate(outer_holes):
            if a <= ha and hb <= b:
                seg.append(code[pos:ha])
                seg.append("{s%d}" % (n + idx))
                pos = hb
        seg.append(code[pos:b])
        return "".join(seg)

    out = [code[wrapper.start:wrapper.open_end]]
    cursor = wrapper.open_end
    emitted = False
    for child in sorted(wrapper.children, key=lambda c: c.start):
        if id(child) in unit_ids:
            out.append(emit(cursor, child.start))
            if not emitted:
                out.append("{r0}")
                emitted = True
            cursor = child.end
            continue
        out.append(emit(cursor, child.end))
        cursor = child.end
    out.append(emit(cursor, wrapper.close_start or wrapper.end))
    out.append(code[wrapper.close_start or wrapper.end:wrapper.end])
    return "".join(out)


def render(info, texts):
    values = [str(x) for x in texts]
    need = info["before"] + info["row_slots"] + info["after"]
    if len(values) < need:
        values = values + [""] * (need - len(values))
    if info["repeat"]:
        before_vals = values[:info["before"]]
        rest = values[info["before"]:len(values) - info["after"] if info["after"] else len(values)]
        after_vals = values[len(values) - info["after"]:] if info["after"] else []
        chunk = info["row_slots"] or 1
        rows = [rest[i:i + chunk] for i in range(0, len(rest), chunk)]
        rows = [row + [""] * (chunk - len(row)) for row in rows]
        r0 = "".join(info["row"].format(**{("s%d" % i): escape(v, quote=False) for i, v in enumerate(row)}) for row in rows)
        outer_vals = {("s%d" % (info["row_slots"] + i)): escape(v, quote=False) for i, v in enumerate(before_vals + after_vals)}
        return info["tpl"].format(r0=r0, **outer_vals)
    return info["tpl"].format(**{("s%d" % i): escape(v, quote=False) for i, v in enumerate(values)})


REPEAT_HINTS = {
    # 整张卡就是一行：重复整个组件（U05 数据行）
    "U05": {"self": True},
    # 表头之外的数据行可重复（U12 表格只有 1 行数据）
    "U12": {"tag": "tr", "skip": 1},
}


def catalog_entry(card, info):
    """给 S2 的目录行：编号、名字、一句话、槽位数、是否可重复。"""
    return {
        "id": card["id"],
        "name": card.get("name", ""),
        "note": card.get("note", ""),
        "repeat": bool(info["repeat"]),
        "before": info["before"],
        "row": info["row_slots"],
        "after": info["after"],
        "rows_default": info["rows_default"],
    }


def template_entry(info):
    return {key: info[key] for key in ("tpl", "before", "row_slots", "after", "row", "repeat")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    here = pathlib.Path(__file__).resolve().parent
    cards = [c for c in json.loads((here / "presets.json").read_text(encoding="utf-8"))["presets"]
             if c.get("role") == "component"]
    strip = lambda text: re.sub(r">\s*[^<>]*\s*<", "><", text)
    bad, repeat = [], []
    for card in cards:
        info = build(card["code"], REPEAT_HINTS.get(card["id"]))
        if info is None:
            bad.append((card["id"], "no template"))
            continue
        if info["repeat"]:
            repeat.append(card["id"])
        count = info["before"] + info["row_slots"] * info["rows_default"] + info["after"]
        rendered = render(info, ["X"] * count)
        if strip(rendered) != strip(card["code"]):
            bad.append((card["id"], "structure changed"))
    if bad:
        print("槽位模板不通过：", bad)
        return 1
    print("槽位模板一致：%d 张卡，可重复 %d 张（%s）" % (len(cards), len(repeat), " ".join(repeat)))
    if not args.check:
        catalog = {c["id"]: catalog_entry(c, build(c["code"], REPEAT_HINTS.get(c["id"]))) for c in cards}
        print("目录 %d 字；模板 %d 字" % (
            len(json.dumps(catalog, ensure_ascii=False)),
            len(json.dumps({c["id"]: template_entry(build(c["code"], REPEAT_HINTS.get(c["id"]))) for c in cards}, ensure_ascii=False))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
