#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版面本地渲染：把分镜的 composition 枚举翻成 CSS，模型不再手写文字样式。

输入只有四个枚举 + 一个明暗标记：

    zone  : top / upper-left / left-middle / lower-left / bottom-band /
            right-middle / upper-right / lower-right / center / full-bleed-edge
    align : left / center / right
    scale : 超大单行 / 三行块 / 小标题 + 大字数字 / 竖排 …（自由文本，按关键词归到四档）
    tone  : dark / light

输出一段挂在 `[data-scene="sXX"]` 下的 CSS，作用到 `.scene-copy` 和
`[data-role="title|lead|body|note|num|label"]`。

这样"白字压在浅底上""字号失控""每屏字色各写一套"在语法上就写不出来：
字色只能从 tone 取，字号只能从档位取。
"""
from __future__ import annotations

import re

INK = {
    "dark": {"primary": "#eaf1ff", "secondary": "#93a4c6", "accent": "#38d6ff", "rule": "rgba(234,241,255,.18)"},
    "light": {"primary": "#182528", "secondary": "#526264", "accent": "#C64E37", "rule": "rgba(24,37,40,.16)"},
}

# left/right/top/bottom/width/transform/text-align 的来源
ZONES = {
    "top":             {"left": 90, "top": "200px", "width": 900},
    "upper-left":      {"left": 90, "top": "22%",   "width": 780},
    "left-middle":     {"left": 90, "top": "50%",   "width": 780, "ty": "-50%"},
    "lower-left":      {"left": 90, "bottom": "28%", "width": 780},
    "bottom-band":     {"left": 90, "bottom": "22%", "width": 900},
    "right-middle":    {"right": 90, "top": "50%",  "width": 700, "ty": "-50%"},
    "upper-right":     {"right": 90, "top": "22%",  "width": 700},
    "lower-right":     {"right": 90, "bottom": "28%", "width": 700},
    "center":          {"left": 90, "top": "50%",   "width": 900, "ty": "-50%"},
    "full-bleed-edge": {"left": 90, "top": "20%",   "width": 900},
}

# 四档字阶：title / lead / body / note / num
SCALES = {
    "hero":   {"title": 124, "lead": 48, "body": 44, "note": 36, "num": 168, "lh": 1.08},
    "large":  {"title": 96,  "lead": 44, "body": 40, "note": 34, "num": 132, "lh": 1.14},
    "medium": {"title": 76,  "lead": 40, "body": 36, "note": 32, "num": 104, "lh": 1.2},
    "small":  {"title": 60,  "lead": 36, "body": 34, "note": 30, "num": 84,  "lh": 1.3},
}


def normalise_tone(tone: str | None) -> str:
    value = str(tone or "").strip().lower()
    return "light" if value in ("light", "浅", "浅色", "亮") else "dark"


def normalise_zone(zone: str | None) -> str:
    value = str(zone or "").strip().lower()
    if value in ZONES:
        return value
    # 常见别名
    alias = {
        "left": "left-middle", "right": "right-middle", "middle": "center",
        "upper": "top", "top-left": "upper-left", "top-right": "upper-right",
        "bottom-left": "lower-left", "bottom-right": "lower-right",
        "bottom": "bottom-band", "lower": "lower-left", "upper-middle": "top",
    }
    return alias.get(value, "left-middle")


def normalise_align(align: str | None, zone: str) -> str:
    value = str(align or "").strip().lower()
    if value in ("left", "center", "right"):
        return value
    return "center" if zone == "center" else "left"


def normalise_scale(scale: str | None) -> str:
    value = str(scale or "").strip()
    if not value:
        return "medium"
    if re.search(r"超大|巨大|hero|铺满", value):
        return "hero"
    if re.search(r"竖排|竖版", value):
        return "small"
    if re.search(r"数字|数值|统计", value):
        return "large"
    if re.search(r"三行|多行|块|段", value):
        return "large"
    return "medium"


MAX_H = 1420          # 顶 200 + 底 300（字幕区）之间的可用高度
MIN_TITLE = 44        # 再小就不如换锚点了


def _height(fs: dict, chars: int, width: int) -> float:
    """标题块高度：中文一字约等于 1em，每行字数 = floor(宽 / 字号)。"""
    per_line = max(1, int(width / max(1, fs["title"])))
    lines = max(1, -(-chars // per_line))
    return lines * fs["title"] * fs["lh"]


def _lines(fs: dict, chars: int, width: int) -> int:
    per_line = max(1, int(width / max(1, fs["title"])))
    return max(1, -(-chars // per_line))


def _downgrade(fs: dict, chars: int, width: int = 780, line_chars: int = 0) -> dict:
    """标题字数多时把整档字阶按比例收小，保证 780px 宽内不溢出。

    2026-11-14 踩过：124px 的 hero 档放 14 个字，780px 宽只装得下 6 字，
    结果三行大字把整屏压满、还顶到字幕区。
    """
    if not chars:
        return fs
    out = dict(fs)
    # 目标：标题 2 行以内。按"每行字数 = 宽 / 字号"反推，只缩字号，不缩行高。
    guard = 0
    while _lines(out, chars, width) > 2 and out["title"] > MIN_TITLE and guard < 16:
        out["title"] = round(out["title"] * 0.94)
        for key in ("lead", "body", "note", "label", "num"):
            if isinstance(out.get(key), (int, float)):
                out[key] = round(out[key] * 0.96)
        guard += 1
    while _height(out, chars, width) > MAX_H and out["title"] > MIN_TITLE and guard < 24:
        out["title"] = round(out["title"] * 0.94)
        guard += 1
    # 有硬换行（br）时最长那行不会被折行，必须让 字号×字数 ≤ 可用宽度，
    # 否则这行直接顶出卡片和安全区（2026-11-15 s01 实测：124px×8 字 = 992px）。
    if line_chars:
        while out["title"] * line_chars > width and out["title"] > MIN_TITLE and guard < 40:
            out["title"] = round(out["title"] * 0.94)
            for key in ("lead", "body", "note", "label", "num"):
                if isinstance(out.get(key), (int, float)):
                    out[key] = round(out[key] * 0.97)
            guard += 1
    return out


def build_scene_css(scene_id: str, zone: str, align: str, scale: str, tone: str, chars: int = 0, media: dict | None = None, line_chars: int = 0) -> str:
    """返回一段挂在 [data-scene="xx"] 下的 CSS。"""
    sid = str(scene_id or "").strip()
    if not sid:
        return ""
    z = normalise_zone(zone)
    a = normalise_align(align, z)
    s = normalise_scale(scale)
    t = normalise_tone(tone)
    ink = INK[t]
    geo = ZONES[z]
    geo_w = int(geo.get('width', 780))
    # 文字区占满可用高度（顶 200 / 底 300 字幕区），但要先给照片让位：
    # 照片是绝对定位的一块矩形，文字区必须落在它的另一侧，否则必然压上去。
    # 2026-11-15：s03/s04/s06 全是"文字叠在照片上"，就是因为版面不知道照片在哪。
    SAFE = 90
    GAP = 48
    rect = media or {}
    m_left = rect.get("left")
    m_right = rect.get("right")
    texts_left = ("right" not in geo)
    width = max(geo["width"], 760)
    left_edge = SAFE
    right_edge = 1080 - SAFE
    if m_left is not None and m_right is not None:
        # 按照片实际占的那半边让位，不要按 zone 猜。
        # 2026-11-15 踩过：zone=right-middle（文字该在右）碰上照片放在左边，
        # 旧判断只看 m_right>540 就认定"照片在右"，把文字挪到左侧压在照片上。
        photo_center = (m_left + m_right) / 2.0
        if photo_center < 540:                    # 照片在左 → 文字在右
            left_edge = min(m_right + GAP, 1080 - SAFE - 420)
        else:                                     # 照片在右 → 文字在左
            right_edge = max(m_left - GAP, SAFE + 420)
    width = min(width, right_edge - left_edge)

    # 照片和文字抢同一块地：两侧都塞不下 470px 时收窄照片，别让文字压在图上。
    # 2026-11-15：s05 的照片 720×1080 落在右下，文字区 780 宽，整块文字压在照片主体上。
    media_fix = ""
    m_top = rect.get("top")
    m_bottom = rect.get("bottom")
    # 照片整块落在下方/上方带里（和文字不在同一条水平带上）时不用收窄，
    # 否则会把"上图下字"的版式误判成抢地。
    band_split = (m_top is not None and m_top >= 880) or (m_bottom is not None and m_bottom <= 900)
    # 照片占了下半屏/上半屏时，文字区跟着让到另一半，别在中间和照片对着压。
    copy_top, copy_bottom = "200px", "300px"
    if band_split and m_top is not None and m_top >= 880:
        copy_bottom = "%dpx" % max(300, 1920 - m_top + GAP)
    elif band_split and m_bottom is not None and m_bottom <= 900:
        copy_top = "%dpx" % max(200, m_bottom + GAP)
    if rect.get("cls") and m_left is not None and m_right is not None and not band_split:
        RESERVE = 470
        if texts_left:
            room = min(right_edge, m_left - GAP) - left_edge
            if room < RESERVE and m_right > left_edge + RESERVE + GAP + 240:
                new_left = left_edge + RESERVE + GAP
                # 用 section[...] 抬一级优先级：场景自己的 <style> 在后面，同权重会把它盖掉
                media_fix = 'section[data-scene="%s"] .%s{left:%dpx;width:%dpx;}\n' % (
                    sid, rect["cls"], new_left, m_right - new_left)
                right_edge = min(right_edge, new_left - GAP)
        else:
            room = right_edge - max(left_edge, m_right + GAP)
            if room < RESERVE and m_left < right_edge - RESERVE - GAP - 240:
                new_right = right_edge - RESERVE - GAP
                media_fix = 'section[data-scene="%s"] .%s{right:%dpx;width:%dpx;}\n' % (
                    sid, rect["cls"], 1080 - new_right, new_right - m_left)
                left_edge = max(left_edge, new_right + GAP)
        width = min(width, right_edge - left_edge)

    parts = ['[data-scene="%s"] .scene-copy{position:absolute;z-index:5;' % sid]
    parts.append("  top:%s;bottom:%s;" % (copy_top, copy_bottom))
    parts.append("  left:%dpx;" % left_edge if texts_left else "  right:%dpx;" % (1080 - right_edge))
    parts.append("  width:%dpx;" % max(width, 420))

    fs = _downgrade(SCALES[s], int(chars or 0), max(width, 420), int(line_chars or 0))

    parts.append("  display:flex;flex-direction:column;justify-content:center;gap:26px;")
    parts.append("  text-align:%s;" % a)
    parts.append("  --ui-scale:%s;" % {"hero": "1.8", "large": "1.5", "medium": "1.3", "small": "1.15"}[s])
    if s == "small" and re.search(r"竖排", str(scale or "")):
        parts.append("  writing-mode:vertical-rl;")
    parts.append("}\n")
    parts.append('[data-scene="%s"] .scene-copy > :only-child{margin-top:auto;margin-bottom:auto;}\n' % sid)

    def rule(role, size, weight, color, extra=""):
        return ('[data-scene="%s"] [data-role="%s"]{\n'
                '  margin:0;font-family:var(--font-stack);font-weight:%d;'
                'font-size:%dpx;line-height:%s;color:%s;%s}\n' % (
                    sid, role, weight, size, fs["lh"], color, extra))

    parts.append(rule("title", fs["title"], 600, ink["primary"]))
    parts.append(rule("lead", fs["lead"], 500, ink["secondary"]))
    parts.append(rule("body", fs["body"], 400, ink["primary"], "opacity:.92;"))
    parts.append(rule("note", fs["note"], 400, ink["secondary"]))
    parts.append(rule("label", fs["note"], 500, ink["secondary"], "letter-spacing:.04em;"))
    parts.append('[data-scene="%s"] [data-role="num"]{\n'
                 '  margin:0;font-family:var(--font-stack);font-weight:600;'
                 'font-size:%dpx;line-height:1;color:%s;}\n' % (sid, fs["num"], ink["accent"]))
    # accent 是"被强调的一句/一个词"，必须自带字号：
    # 2026-11-14 踩过——只给 color，模型把它写在 <em>/<p> 上就用浏览器默认 16px。
    parts.append('[data-scene="%s"] [data-role="accent"]{\n'
                 '  margin:0;font-family:var(--font-stack);font-weight:600;'
                 'font-size:%dpx;line-height:%s;color:%s;}\n' % (
                     sid, fs["lead"], fs["lh"], ink["accent"]))
    if media_fix:
        parts.insert(0, media_fix)
    return "".join(parts)


def build_document_css(scenes) -> str:
    """scenes: [{"id","zone","align","scale","tone"}, ...]"""
    blocks = []
    for item in scenes:
        css = build_scene_css(item.get("id"), item.get("zone"), item.get("align"),
                              item.get("scale"), item.get("tone"), item.get("chars") or 0,
                              item.get("media"), item.get("line_chars") or 0)
        if css:
            blocks.append(css)
    return "".join(blocks)


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    print(build_document_css(payload))
