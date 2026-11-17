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
MIN_TITLE = 60        # 四档里最小一档（small）的标题字号
# 字阶下沿：缩字只能缩到档位最小一档为止。
# 2026-11-16 踩过：没有下限时 s01 标题被收到 43px、正文 25px，
# 1080×1920 上比 45px 的字幕还小，"标题为什么这么小"就是这么来的。
# 到下限还放不下就让它多折一行，不再牺牲可读性。
ROLE_FLOOR = {"title": 60, "lead": 36, "body": 34, "note": 34, "label": 34, "num": 84}

# 组件（U 系列）的调色板：跟着"这一屏"的明暗走，不跟根节点。
# components.css 里同一套变量挂在 :root / #stage[data-bg-tone] 上，
# 只要模型把根节点写成 light、背景卡却是深色，组件就是深墨压黑底（2026-11-16 实测）。
UI_VARS = {
    "dark": {
        "ink": "#eaf1ff", "muted": "#93a4c6", "accent": "#38d6ff",
        "border": "rgba(255,255,255,.10)",
        "surface": "rgba(255,255,255,.045)",
        "surface2": "rgba(255,255,255,.075)",
    },
    "light": {
        "ink": "#182528", "muted": "#526264", "accent": "#C64E37",
        "border": "rgba(24,37,40,.14)",
        "surface": "rgba(24,37,40,.045)",
        "surface2": "rgba(24,37,40,.075)",
    },
}


def _height(fs: dict, chars: int, width: int) -> float:
    """标题块高度：中文一字约等于 1em，每行字数 = floor(宽 / 字号)。"""
    per_line = max(1, int(width / max(1, fs["title"])))
    lines = max(1, -(-chars // per_line))
    return lines * fs["title"] * fs["lh"]


def _lines(fs: dict, chars: int, width: int) -> int:
    per_line = max(1, int(width / max(1, fs["title"])))
    return max(1, -(-chars // per_line))


def _downgrade(fs: dict, chars: int, width: int = 780, line_chars: int = 0) -> dict:
    """标题字数多时把字阶收小，但**只收到档位下沿为止**（ROLE_FLOOR）。

    2026-11-14 踩过：124px 的 hero 档放 14 个字，780px 宽只装得下 6 字，
    结果三行大字把整屏压满、还顶到字幕区。
    2026-11-16 踩过：没有下限时一路收到 43px 标题 / 25px 正文。
    """
    if not chars:
        return fs
    out = dict(fs)

    def floor_of(key: str) -> int:
        return int(ROLE_FLOOR.get(key, 0))

    def shrink(keys, ratio_title: float, ratio_rest: float) -> bool:
        if out["title"] <= floor_of("title"):
            return False
        out["title"] = round(out["title"] * ratio_title)
        for key in keys:
            value = out.get(key)
            if isinstance(value, (int, float)) and value > floor_of(key):
                out[key] = max(floor_of(key), round(value * ratio_rest))
        return True

    rest = ("lead", "body", "note", "label", "num")
    guard = 0
    # 目标：标题 2 行以内。按"每行字数 = 宽 / 字号"反推，只缩字号，不缩行高。
    while _lines(out, chars, width) > 2 and guard < 16 and shrink(rest, 0.94, 0.96):
        guard += 1
    while _height(out, chars, width) > MAX_H and guard < 24 and shrink((), 0.94, 1.0):
        guard += 1
    # 有硬换行（br）时最长那行不会被折行，必须让 字号×字数 ≤ 可用宽度，
    # 否则这行直接顶出卡片和安全区（2026-11-15 s01 实测：124px×8 字 = 992px）。
    if line_chars:
        while out["title"] * line_chars > width and guard < 40 and shrink(rest, 0.94, 0.97):
            guard += 1
    for key in ROLE_FLOOR:
        if isinstance(out.get(key), (int, float)):
            out[key] = max(ROLE_FLOOR[key], out[key])
    return out


def center_y_of(top, bottom):
    return (float(top) + float(bottom)) / 2.0


def build_scene_css(scene_id: str, zone: str, align: str, scale: str, tone: str, chars: int = 0, media: dict | None = None, line_chars: int = 0, bg_family: str = "") -> str:
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
    # 文字区占满可用高度（顶 200 / 底 300 字幕区），但要先给照片让位：
    # 照片是绝对定位的一块矩形，文字区必须落在它的另一侧，否则必然压上去。
    # 2026-11-15：s03/s04/s06 全是"文字叠在照片上"，就是因为版面不知道照片在哪。
    SAFE = 90
    GAP = 48
    CANVAS_W, CANVAS_H = 1080, 1920
    MIN_TEXT = 480        # 文字栏最窄宽度：420 时 8 字标题 60px 会折成 7+1（单字成行）
    TARGET_TEXT = 760     # 没有照片冲突时的常规栏宽
    MIN_TEXT_BAND = 520   # 横带照片让开之后，文字区至少还能剩这么高，否则不算"分带"
    COPY_TOP = 200
    COPY_BOTTOM = CANVAS_H - 300          # 底部 300 留给字幕
    rect = media or {}
    SLOT_RECTS = {
        "top":    {"left": 0, "right": 1080, "top": 0, "bottom": 760},
        "bottom": {"left": 0, "right": 1080, "top": 1160, "bottom": 1920},
        "left":   {"left": 0, "right": 460, "top": 200, "bottom": 1720},
        "right":  {"left": 620, "right": 1080, "top": 200, "bottom": 1720},
        "full":   {"left": 0, "right": 1080, "top": 0, "bottom": 1920},
    }
    slot = rect.get("slot")
    # 2026-11-17：行内矩形是 H02SK 按 role 算出来的（large 840 / inset 620×1280 /
    # portrait 460×1100 各不相同），只有老页面没写行内数值时才退回这张表覆盖。
    if slot in SLOT_RECTS and None in (rect.get("left"), rect.get("right"),
                                      rect.get("top"), rect.get("bottom")):
        rect = dict(SLOT_RECTS[slot])
    m_left = rect.get("left")
    m_right = rect.get("right")
    m_top = rect.get("top")
    m_bottom = rect.get("bottom")
    texts_left = ("right" not in geo)
    width = max(int(geo["width"]), TARGET_TEXT)
    left_edge = SAFE
    right_edge = CANVAS_W - SAFE
    # 照片整块落在下方/上方带里（和文字不在同一条水平带上）时不算抢地：
    # 这种版式文字区可以让满宽度，只把纵向让开。
    # 2026-11-17：判据从"top>=880 / bottom<=900"两个死阈值改成"让开之后还剩多少字位"。
    # 死阈值下，按 role 算出来的 large 横带（例如 720–1560）两头都不满足，会被判成
    # "照片抢满整宽"，文字被压成 480 窄栏——这是"图片位置放不好"的另一半原因。
    space_above = space_below = 0
    band_split = False
    if None not in (m_left, m_right, m_top, m_bottom) and (m_right - m_left) >= CANVAS_W * 0.95:
        space_above = m_top - COPY_TOP
        space_below = COPY_BOTTOM - m_bottom
        band_split = max(space_above, space_below) >= MIN_TEXT_BAND
    if m_left is not None and m_right is not None and not band_split:
        # 按照片实际占的那半边让位，不要按 zone 猜。
        # 2026-11-15 踩过：zone=right-middle（文字该在右）碰上照片放在左边，
        # 旧判断只看 m_right>540 就认定"照片在右"，把文字挪到左侧压在照片上。
        if (m_left + m_right) / 2.0 < CANVAS_W / 2.0:     # 照片在左 → 文字在右
            left_edge = min(m_right + GAP, CANVAS_W - SAFE - MIN_TEXT)
        else:                                             # 照片在右 → 文字在左
            right_edge = max(m_left - GAP, SAFE + MIN_TEXT)
    avail_w = right_edge - left_edge
    width = min(max(width, min(MIN_TEXT, avail_w)), avail_w)
    if texts_left:
        copy_left, copy_right = left_edge, left_edge + width
    else:
        copy_left, copy_right = right_edge - width, right_edge

    copy_top, copy_bottom = "%dpx" % COPY_TOP, "%dpx" % (CANVAS_H - COPY_BOTTOM)

    # 照片和文字真的抢同一块地时：**等比缩小照片**（保比例、保外沿），
    # 不再把它压成一条窄边——2026-11-16 s01 的 930×1280 就是被压成了 397 宽。
    media_fix = ""
    align_next_to_photo = ""
    if (rect.get("cls") and not band_split
            and None not in (m_left, m_right, m_top, m_bottom)
            and copy_right > m_left and copy_left < m_right):
        photo_w = max(1, m_right - m_left)
        photo_h = max(1, m_bottom - m_top)
        if texts_left:
            inner_edge = copy_right + GAP
            outer_edge = max(m_right, CANVAS_W - SAFE)
            # 照片不能为了保宽度贴到安全边外：留出 GAP，宁可窄一点也不压字。
            avail = min(outer_edge - inner_edge, CANVAS_W - SAFE - inner_edge)
        else:
            inner_edge = copy_left - GAP
            outer_edge = min(m_left, SAFE)
            avail = min(inner_edge - outer_edge, inner_edge - SAFE)
        if avail < 240:
            # 横向挤不出 240px：放弃左右分栏，改成上下分带。
            # 版面必须自己解决冲突，不能让"照片太大"变成"文字压在照片上"交给人去发现。
            band_h = min(m_bottom - m_top, 620)
            if center_y_of(m_top, m_bottom) < CANVAS_H / 2.0:
                top_new = max(COPY_TOP, 200)
                copy_top = "%dpx" % (top_new + band_h + GAP)
            else:
                top_new = COPY_BOTTOM - band_h
                copy_bottom = "%dpx" % max(300, CANVAS_H - (top_new - GAP))
            media_fix = ('section[data-scene="%s"] .%s{left:%dpx;top:%dpx;width:%dpx;height:%dpx;}\n'
                         % (sid, rect["cls"], SAFE, top_new, CANVAS_W - SAFE * 2, band_h))
        if avail >= 240:
            scale = min(1.0, avail / float(photo_w))
            w_new = int(round(photo_w * scale))
            h_new = int(round(photo_h * scale))
            center_y = (m_top + m_bottom) / 2.0
            top_new = int(round(center_y - h_new / 2.0))
            top_new = max(COPY_TOP, min(top_new, COPY_BOTTOM - h_new))
            left_new = inner_edge if texts_left else inner_edge - w_new
            left_new = max(SAFE, min(left_new, CANVAS_W - SAFE - w_new))
            # 用 section[...] 抬一级优先级：场景自己的 <style> 在后面，同权重会把它盖掉
            media_fix = ('section[data-scene="%s"] .%s{left:%dpx;top:%dpx;width:%dpx;height:%dpx;}\n'
                         % (sid, rect["cls"], left_new, top_new, w_new, h_new))

    # 照片占了下半屏/上半屏时，文字区跟着让到另一半，别在中间和照片对着压。
    # 让位之后还要把这一半的"内容中心"留在构图舒适区内（700–1100）。
    # 2026-11-17：从 640 抬到 700——抬到硬边界下沿的时候文字虽然没越界，但成片里
    # 明显偏上（s02 实测 640），舒适区下沿才是应该守的那条线。
    # 两种方向统一用 space_above / space_below 判，不再各写一条死条件。
    CENTER_FLOOR = 700
    if band_split:
        if space_above >= space_below:                 # 照片在下半，文字在上
            bottom_px = max(300, CANVAS_H - m_top + GAP)
            top_px = max(COPY_TOP, CENTER_FLOOR * 2 - (CANVAS_H - bottom_px))
            # 抬 top 是为了把内容中心拉回 640 以上；只有当空间还够时才能抬，
            # 否则 780–1620 这种"照片抬高的下带"会被压成 184px 一条（2026-11-17 实测）。
            if CANVAS_H - top_px - bottom_px < MIN_TEXT_BAND:
                top_px = COPY_TOP
        else:                                          # 照片在上半，文字在下
            top_px = max(COPY_TOP, m_bottom + GAP)
            bottom_px = CANVAS_H - COPY_BOTTOM
        copy_top, copy_bottom = "%dpx" % top_px, "%dpx" % bottom_px
        # 文字块贴着自己那张照片，留白放在画面外侧（2026-11-17）：
        # 居中放的时候，照片在上带的屏文字会一路掉到底、贴住字幕（s07 实测中心 1284），
        # 照片在下带的屏文字又悬在上方。贴图排之后两行字和图片是一组，外沿留白更像版式。
        align_next_to_photo = "flex-end" if space_above >= space_below else "flex-start"

    # 组件的调色板跟着"这一屏"的 tone 走。
    # components.css 的同一套变量挂在 :root / #stage[data-bg-tone] 上，
    # 模型把根节点写成 light、背景卡却是深色时，组件就是深墨压黑底（2026-11-16 实测：
    # .ui-cell 算出 color:#182528，背景 #0B0F18，整行看不见）。
    ui = UI_VARS[t]
    parts = []
    parts.append((
        '[data-scene="%s"]{--ui-ink:%s;--ui-muted:%s;--ui-accent:%s;'
        '--ui-border:%s;--ui-surface:%s;--ui-surface-2:%s;}\n'
    ) % (sid, ui["ink"], ui["muted"], ui["accent"], ui["border"], ui["surface"], ui["surface2"]))

    parts.append('[data-scene="%s"] .scene-copy{position:absolute;z-index:5;' % sid)
    parts.append("  top:%s;bottom:%s;" % (copy_top, copy_bottom))
    parts.append("  left:%dpx;" % copy_left if texts_left else "  right:%dpx;" % (CANVAS_W - copy_right))
    parts.append("  width:%dpx;" % width)

    fs = _downgrade(SCALES[s], int(chars or 0), width, int(line_chars or 0))

    parts.append("  display:flex;flex-direction:column;justify-content:%s;gap:26px;"
                 % (align_next_to_photo or "center"))
    parts.append("  text-align:%s;" % a)
    parts.append("  --ui-scale:%s;" % {"hero": "1.8", "large": "1.5", "medium": "1.3", "small": "1.15"}[s])
    if s == "small" and re.search(r"竖排", str(scale or "")):
        parts.append("  writing-mode:vertical-rl;")
    parts.append("}\n")
    parts.append('[data-scene="%s"] .scene-copy > :only-child{margin-top:auto;margin-bottom:auto;}\n' % sid)
    # 版面的唯一负责人是 composer：场景里给内容块写的绝对定位（top:1120px/left:90px 这种）
    # 一律不吃。2026-11-16 s07 的流程行就是这么双倍位移、右边界顶到 1080 的。
    parts.append('#stage [data-scene="%s"] .scene-copy > *{position:relative;top:auto;'
                 'left:auto;right:auto;bottom:auto;max-height:none!important;'
                 'height:auto!important;overflow:visible!important;}\n' % sid)
    # 组件字号：不低于 1.55（24px 基准 ×1.55 ≈ 37px，竖屏小字下限 34px），
    # 也不低于本屏文字档位。以前直接吃 .scene-copy 上的档位值，窄栏里 5 个字
    # 会撑成 142px 高的一排砖；压小到 21px 又看不清，两头都不对。
    ui_scale = max(1.55, {"hero": 1.8, "large": 1.5, "medium": 1.3, "small": 1.15}[s])
    parts.append('[data-scene="%s"] .scene-copy [class*="ui-"]{--ui-scale:%s;}\n' % (sid, ui_scale))
    # 窄栏里再排 2/3 列就等于每格 100px，词只能逐字换行。
    # 栏宽不到 560 时，网格和步骤条一律退成单列（每行通栏），不再硬塞多列。
    if width < 560:
        parts.append('[data-scene="%s"] .scene-copy .ui-grid{grid-template-columns:1fr;}\n' % sid)
        parts.append('[data-scene="%s"] .scene-copy .ui-steps{flex-direction:column;gap:18px;}\n' % sid)
        parts.append('[data-scene="%s"] .scene-copy .ui-step{padding-top:0;}\n' % sid)
        # 竖栏只有 480 时，width:fit-content 的组件照内容撑宽就顶出安全区
        # （2026-11-17 s06 实测：.ui-card 右缘 1044，安全区 990）。窄栏里一律按栏宽排。
        parts.append('[data-scene="%s"] .scene-copy .ui-card,\n'
                     '[data-scene="%s"] .scene-copy .ui-grid,\n'
                     '[data-scene="%s"] .scene-copy .ui-bento,\n'
                     '[data-scene="%s"] .scene-copy .ui-masonry,\n'
                     '[data-scene="%s"] .scene-copy .ui-swipe,\n'
                     '[data-scene="%s"] .scene-copy .ui-timeline,\n'
                     '[data-scene="%s"] .scene-copy .ui-file,\n'
                     '[data-scene="%s"] .scene-copy .ui-form,\n'
                     '[data-scene="%s"] .scene-copy .ui-toc,\n'
                     '[data-scene="%s"] .scene-copy .ui-price,\n'
                     '[data-scene="%s"] .scene-copy .ui-map'
                     '{width:100%%!important;max-width:100%%!important;min-width:0;}\n'
                     % ((sid,) * 11))
    # 网格/弹性容器的子项默认 min-width:auto，内容一长就顶破栏宽：
    # 482 的竖栏里 .ui-card 的正文把整块撑到 632，"退成单列"也救不回来（2026-11-17 s06 实测）。
    # 子项允许收缩，文字才会按栏宽换行。
    parts.append('[data-scene="%s"] .scene-copy .ui-grid > *,\n'
                 '[data-scene="%s"] .scene-copy .ui-bento > *,\n'
                 '[data-scene="%s"] .scene-copy .ui-masonry > *,\n'
                 '[data-scene="%s"] .scene-copy .ui-swipe > *,\n'
                 '[data-scene="%s"] .scene-copy .ui-timeline > *{min-width:0;}\n'
                 % (sid, sid, sid, sid, sid))
    parts.append('[data-scene="%s"]{--font-stack:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC","Hiragino Sans GB",sans-serif;}\n' % sid)

    def rule(role, size, weight, color, extra=""):
        # text-wrap:balance + word-break:break-all：
        # 中文没有空格，一行会整块折行，贪心断行经常留下"就"这种单字成行；
        # 均衡折行让每行字数接近，成片里不会出现孤字（2026-11-16 s01 实测 7+1）。
        return ('[data-scene="%s"] [data-role="%s"]{\n'
                '  margin:0;font-family:var(--font-stack);font-weight:%d;'
                'font-size:%dpx;line-height:%s;color:%s;'
                'text-wrap:balance;word-break:break-all;%s}\n' % (
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
    # 照片带和背景卡同屏时，边缘是硬切：棋盘/网点/扫描线在半屏照片旁边断成一条直线，
    # 看起来就是"两套背景拼在一起"（2026-11-16 s03 实测：B32 棋盘铺满，下带照片 760px，
    # 76px 的“两难”正好压在格子上）。给照片朝文字那一侧加一段到 --scene-base 的渐隐，
    # 缝就没了。只处理 top/bottom 这种整条带宽的槽位；left/right 的 inset 图自带留白，
    # full 满屏图不该被削边。
    # 新版照片框是 data-media-slot + 行内 style，没有可反查的 cls，所以用属性选择器定位。
    if slot in ("top", "bottom"):
        _edge = "bottom" if slot == "top" else "top"
        _target = ('[data-media-slot="%s"]' % slot) if not rect.get("cls") else ('.%s' % rect["cls"])
        parts.append(
            'section[data-scene="%s"] %s::after{content:"";position:absolute;inset:0;'
            'pointer-events:none;z-index:3;'
            'background:linear-gradient(to %s,var(--scene-base,#0b0f18) 0%%,transparent 240px);}\n'
            % (sid, _target, _edge))
    # 高密度底纹（棋盘 / 扫描线 / 网点）与文字同屏时，文字直接坐在图案上：
    # 76px 的“两难”跨在明暗格之间，笔画和格子同权重，读起来是糊的（2026-11-16 s03）。
    # 这里给文字块垫一层向外的柔光，只压背景不压内容；缝在 82% 处收干净，
    # 边界看不出来。只在文字块本身有内容时加，空屏不加。
    DENSE_BG = ("block", "line", "dot")
    if bg_family in DENSE_BG and copy_top and copy_bottom:
        _veil = "rgba(8,12,20," if t == "dark" else "rgba(238,237,231,"
        parts.append(
            '[data-scene="%s"] .scene-copy{isolation:isolate;}\n'
            '[data-scene="%s"] .scene-copy::before{content:"";position:absolute;'
            'inset:-56px -44px;z-index:-1;pointer-events:none;border-radius:44px;'
            'background:radial-gradient(ellipse at center, %s0.88) 0%%, %s0.52) 58%%, %s0) 84%%);}\n'
            % (sid, sid, _veil, _veil, _veil))
    if media_fix:
        parts.insert(0, media_fix)
    return "".join(parts)


def build_document_css(scenes) -> str:
    """scenes: [{"id","zone","align","scale","tone"}, ...]"""
    blocks = []
    for item in scenes:
        css = build_scene_css(item.get("id"), item.get("zone"), item.get("align"),
                              item.get("scale"), item.get("tone"), item.get("chars") or 0,
                              item.get("media"), item.get("line_chars") or 0,
                              item.get("bg_family") or "")
        if css:
            blocks.append(css)
    return "".join(blocks)


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    print(build_document_css(payload))
