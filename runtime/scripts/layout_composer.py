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

import math
import re

INK = {
    "dark": {"primary": "#eaf1ff", "secondary": "#93a4c6", "accent": "#38d6ff", "rule": "rgba(234,241,255,.18)"},
    "light": {"primary": "#182528", "secondary": "#526264", "accent": "#C64E37", "rule": "rgba(24,37,40,.16)"},
}

# left/right/top/bottom/width/transform/text-align 的来源
ZONES = {
    # 一栏式（2026-11-18 定）：所有版面只有一栏，左 120、宽 840。
    # zone 不再决定宽度和左右摆放，只保留名字给上游继续写；
    # 真正生效的是「照片在上还是在下」+「整块在 150–1533 之间垂直居中」。
    "top":             {"left": 120, "top": "150px", "width": 840},
    "upper-left":      {"left": 120, "top": "150px", "width": 840},
    "left-middle":     {"left": 120, "top": "150px", "width": 840},
    "lower-left":      {"left": 120, "top": "150px", "width": 840},
    "bottom-band":     {"left": 120, "top": "150px", "width": 840},
    "right-middle":    {"left": 120, "top": "150px", "width": 840},
    "upper-right":     {"left": 120, "top": "150px", "width": 840},
    "lower-right":     {"left": 120, "top": "150px", "width": 840},
    "center":          {"left": 120, "top": "150px", "width": 840},
    "full-bleed-edge": {"left": 120, "top": "150px", "width": 840},
}

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


# ---- 字号求解：只看几何，不看文案语义 ----
# 2026-11-17：整块删掉"四档字阶 + 关键词猜档"，原因写在设计原则里：
#   1) 拿字符串包含关系去猜"这屏要多大的字"，分镜写"大字结论""三条大字"全部漏判，
#      一律落到最保守一档（76/40/36），成片里正文 36px 比 45px 的字幕还小；
#   2) 猜出来之后只能单向往下缩，缺 title 的屏（模型漏写）永远抬不起来；
#   3) 于是"字号"这个视觉判断被交给了三个错误的东西：自由文本、子串匹配、单向缩字。
# 现在的定义：**字号 = 栏宽 ÷ 每行要放几个字**，输入只有栏宽、字数、硬换行、可用高度。
# 2026-11-19 补一条：主角色**先要一行装下**，装不下才折行（见 solve_scale 第一轮）。
# 模型不写 px，也不写档位；本地不再读 data-composition-scale 决定大小。
PRIMARY_ORDER = ("title", "num", "lead", "body", "note", "label", "accent")

# 单条文字的设计上限（px）。不是档位，是"再大就成海报了"的常识边界。
ROLE_CEIL = {"title": 110, "num": 110, "lead": 120, "body": 80,
             "note": 60, "label": 60, "accent": 100}
# 可读下沿。竖屏字幕 45px，任何正文都不能比它小。
# lead 的下沿 2026-11-19 从 60 降到 46：60 会在标题落到 70 档时把导语顶到 60，
# 70/60 = 0.86，主次又糊成一样大；降到 46 后 lead 永远严格是标题的 0.7。
ROLE_FLOOR = {"title": 70, "num": 70, "lead": 46, "body": 50,
              "note": 46, "label": 46, "accent": 60}
# 主副关系：副字号 = 主字号 × 相对比例。缺 title 时主角色自动变成 lead/body，
# 所以"模型漏写 title → 整屏只有 36px"这条路径不存在了。
# 2026-11-19：lead 从 0.90 降到 0.70。0.90 时 lead 和 title 只差 11px（110/99），
# 成片里两行字看着一样大，观众会以为"这一屏有两个标题"——主次在画面上读不出来。
# 0.70 让 lead 明确退到导语的位置（110/77），同时把 lead 的每行字数拉开，
# 9 个字的导语在 840 栏里一行就放得下，不再和标题一起折成两行。
ROLE_REL = {"title": 1.00, "num": 1.00, "lead": 0.70, "body": 0.40,
            "note": 0.50, "label": 0.50, "accent": 0.70}
BODY_RATIO = 0.40      # 正文 = 标题 × 0.4（2026-11-18 定，不再有上下限夹取）
BODY_FLOOR = 24        # 唯一的物理地板：再小就糊了

# 标题档位（2026-11-18 晚二次改）：110 → 70 五档，一屏一档，装不下就降一档。
# 取消"≤8 字可上 150"的特大档：150 在竖屏上已经不是标题而是海报字，
# 和 120 摆在同一支片里像两种字号体系。现在最大 110（TITLE_BIG_LIMIT=0 关掉大档分支），
# 标准档 100，往下 90 / 80 / 70；内容少不放大——「再空也用这个」。
TITLE_STEPS = (110, 100, 90, 80, 70)
TITLE_BIG = 110
TITLE_BIG_LIMIT = 0   # 0 = 不再有"短标题先试大档"这条分支
GAP = 26                      # 与 .scene-copy 的 gap 一致
ANCHOR_FLOOR = 70             # 整屏视觉锚的下沿：一屏里最大的字至少要这么大，否则竖屏读不出重点



def _em_units(text: str) -> int:
    """这段文字占几个字宽：中文 1em，西文 0.58em，空格 0.5em。"""
    total = 0.0
    for ch in str(text or ""):
        if ch.isspace():
            total += 0.5
        elif ord(ch) > 0x2E7F:
            total += 1.0
        elif ch.isdigit():
            total += 0.58
        else:
            total += 0.56
    return max(1, int(math.ceil(total - 1e-6)))


def _clamp(value, low, high):
    return int(max(int(low), min(int(high), int(round(value)))))


def _max_lines(width: int) -> int:
    """宽栏给 2 行（按行拆版更好看），窄栏给 3 行（482 里 18 个字硬压 2 行只会更小）。"""
    return 2 if width >= 620 else 3


def _size_for(role: str, units: int, seg_units: int, width: int) -> int:
    """填满栏宽所需的字号：栏宽 ÷ 每行字数，再受设计上限与硬换行约束。"""
    if units <= 0 or width <= 0:
        return ROLE_FLOOR.get(role, 46)
    per_line = int(math.ceil(units / float(_max_lines(width))))
    if seg_units:                      # 写了 <br> 的那一行不许再折
        per_line = max(per_line, seg_units)
    return _clamp(width / float(max(1, per_line)),
                  ROLE_FLOOR.get(role, 46), ROLE_CEIL.get(role, 200))


def _lines_of(units: int, segs, width: int, size: int) -> int:
    per = max(1, int(width / float(max(1, size))))
    if segs:
        return sum(max(1, -(-int(u) // per)) for u in segs)
    return max(1, -(-int(units) // per))


def _line_height(size: int) -> float:
    return 1.08 if size >= 120 else 1.2


def _lines_needed(units: int, width: int, size: int, segs=None) -> int:
    per = max(1, int(width / float(max(1, size))))
    if segs:
        return sum(max(1, -(-int(u) // per)) for u in segs)
    return max(1, -(-int(units) // per))


def solve_scale(roles: dict, width: int, avail_h: float) -> dict:
    """一栏式字号：在 110→70 五档里选「一行排得满、又装得下」的最大一档。

    2026-11-18 定：不再由栏宽连续反算（那会让同一部片出现 88/120/150/180 五级跳），
    也不再叠「正文 = 标题 × 比例」和「标题 ≤ 副角色 × 2.4」两道压制。
    依据只有两条：主角色能不能一行装下、这一屏的可用高度够不够。
    """
    items = {}
    for role, data in (roles or {}).items():
        if role not in ROLE_CEIL or not isinstance(data, dict):
            continue
        units = data.get("units")
        if units is None:
            units = _em_units(data.get("text") or "")
        units = int(units or 0)
        if units <= 0:
            continue
        segs = data.get("segs")
        if segs is None:
            segs = [_em_units(part) for part in (data.get("lines") or []) if str(part or "").strip()]
            if len(segs) < 2:
                segs = []
        segs = [int(x) for x in segs if int(x) > 0]
        items[role] = {"units": units, "segs": segs}

    if not items:
        return {role: ROLE_FLOOR[role] for role in ROLE_CEIL}

    primary = next((r for r in PRIMARY_ORDER if r in items), None) or next(iter(items))

    # 档位上限再受栏宽约束：栏宽只决定「能用到哪一档」，不够就整档往下跳。
    # （左右并排已删，栏宽恒为 840，这条只剩小窗让位时才起作用。）
    width_cap = max(ROLE_FLOOR.get(primary, 70), int(width // 5))

    # 2026-11-19：标题带硬换行（H02SK 按标点切好的 <br>）时，字号还要受「最长那一行」约束。
    # 以前只按整块字数算档位，8 个字的行配上 110px 就是 880px，整行顶出 840 栏，
    # 浏览器再折一次，换行点就落到词中间（s06「取消的是强制性，不是反对努力」折成
    # 「取消的是强 / 制性，不是 / 反对努力」）。现在 840/8 = 105 → 整档掉到 100。
    _segs = items[primary]["segs"]
    if _segs:
        _seg_cap = int(width / float(max(1, max(_segs))))
        width_cap = max(ROLE_FLOOR.get(primary, 70), min(width_cap, _seg_cap))

    # 2026-11-18 晚：档位只认 110/100/90/80/70，不再"取档位再按栏宽连续缩"。
    # 栏宽只决定**能用到哪一档**：宽度不够就整档往下跳，出片里出现的字号永远是这五个之一。
    # （以前 min(档位, 栏宽÷5) 会算出 87、75 这种中间值，一支片里像有好几套字号。）
    steps = [v for v in sorted(set(TITLE_STEPS), reverse=True) if v <= width_cap]
    if not steps:
        steps = [ROLE_FLOOR.get(primary, 70)]

    def build(title_size: int) -> dict:
        out = {primary: title_size}
        for role in items:
            if role == primary:
                continue
            if role == "body":
                # 正文只按比例走，不夹上下限（2026-11-18 定）：120→48、100→40、90→36、80→32
                out[role] = max(BODY_FLOOR, int(round(title_size * BODY_RATIO)))
            else:
                share = title_size * float(ROLE_REL.get(role, 0.6))
                out[role] = _clamp(share, ROLE_FLOOR.get(role, 46), ROLE_CEIL.get(role, 200))
        return out

    def height_of(sizes: dict) -> float:
        total = GAP * max(0, len(items) - 1)
        for role, data in items.items():
            size = sizes[role]
            total += _lines_needed(data["units"], width, size, data["segs"]) * size * _line_height(size)
        return total

    chosen = None
    # 第一轮（2026-11-19）：先要「主角色一行装下」，再谈装不装得下高度。
    # 以前只看总高度，110 在 840 栏里一行只放 7 个字，9 个字的标题折成两行
    # 总高 527.6 远小于可用 1383，于是"装得下"直接通过、再也不会试到能一行的 90；
    # 折出来的两行又被 text-wrap:balance 拉成 5+4，每行只用掉 550/440px，
    # 右边空 290px —— 观众看到的就是"明明还能塞三个字却换了行"。
    # 现在宁可降一档把一行排满：9 字→90（810/840），10 字→80，11–12 字→70。
    def fits_one_line(size: int) -> bool:
        data = items[primary]
        if data["segs"]:
            # 模型写了硬换行（<br>），折行是它自己定的版式，不在这里改它
            return False
        return _lines_needed(data["units"], width, size, data["segs"]) <= 1

    for step in steps:
        candidate = build(step)
        if fits_one_line(step) and height_of(candidate) <= avail_h:
            chosen = candidate
            break

    # 第二轮：字数超过一行上限（840 栏 @70px 最多 12 个字）或写了硬换行时，
    # 折行是必然的，这时回到「高度装得下的最大一档」，不再追求一行。
    if chosen is None:
        for step in steps:
            candidate = build(step)
            if height_of(candidate) <= avail_h:
                chosen = candidate
                break
    if chosen is None:
        chosen = build(steps[-1])

    base = chosen[primary]
    for role in ROLE_CEIL:
        if role in chosen:
            continue
        if role == "body":
            chosen[role] = max(BODY_FLOOR, int(round(base * BODY_RATIO)))
        else:
            chosen[role] = _clamp(base * float(ROLE_REL.get(role, 0.6)),
                                  ROLE_FLOOR.get(role, 46), ROLE_CEIL.get(role, 200))
    return chosen


# 每个 zone 的文字框"估算顶边"。只有它落在数字人小窗的竖直范围内（< 小窗底边）时，
# 才需要横向让位；居中/下半区的 zone 天然在小窗下方，不动。
CANVAS_H = 1920
ZONE_TOP = {
    "top": 200,
    "upper-left": int(CANVAS_H * 0.22),
    "upper-right": int(CANVAS_H * 0.22),
    "full-bleed-edge": int(CANVAS_H * 0.20),
    "left-middle": int(CANVAS_H * 0.5),
    "right-middle": int(CANVAS_H * 0.5),
    "center": int(CANVAS_H * 0.5),
    "lower-left": CANVAS_H - int(CANVAS_H * 0.28),
    "lower-right": CANVAS_H - int(CANVAS_H * 0.28),
    "bottom-band": CANVAS_H - int(CANVAS_H * 0.22),
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
    """一栏式只有左对齐（2026-11-18 定）。

    分镜的 align 是旧构图系统的字段：写 center 就整屏居中、写 right 就右对齐，
    同一部片子里混着三种对齐，看起来就是"有的居中有的没有"。现在一律左对齐，
    这个值只留作兼容，不再生效。
    """
    return "left"


def normalise_scale(scale: str | None) -> str:
    """一栏式之后没有"版面模式"这回事（2026-11-18 定）：竖排也取消。

    以前分镜写 `vertical` 就把整屏文字立起来（1145 的 s06 整页竖排就是这么来的），
    而那一条根本不在画面规则里。现在一律返回空串，`data-composition-scale` 彻底不读。
    """
    return ""


def center_y_of(top, bottom):
    return (float(top) + float(bottom)) / 2.0


def ui_grid_scale_cap(width: int, grid: dict | None) -> float | None:
    """栅格组件按格子字数反算 --ui-scale 上限。

    .ui-cell 基准 24px、左右 padding 各 22px、列间距 16px；cols 来自 .ui-grid c2/c3。
    floor 1.55：24px 基准只剩 37px，竖屏再小就不好读。到地板还装不下就折行
    （栅格列已是 minmax(0,1fr)，不会再顶出栏宽）。
    """
    if not isinstance(grid, dict):
        return None
    cols = int(grid.get("cols") or 0)
    cells = grid.get("cells") or []
    if cols < 2 or not cells:
        return None
    max_chars = 0
    for cell in cells:
        try:
            max_chars = max(max_chars, int(cell.get("chars") or 0))
        except Exception:
            continue
    if max_chars <= 0:
        return None
    budget = width - (cols - 1) * 16 - cols * 44
    if budget <= 0:
        return 1.55
    cap = budget / float(cols * max_chars * 24)
    return max(1.55, min(2.0, cap))


# .ui-card 的水平占位：左右 padding 30px×2 + 边框 1px×2（border-box）。
# 和 components.css 的 .ui-card 改动绑在一起，改 padding 必须同步这个数。
UI_CARD_PAD_X = 62
UI_GRID_GAP = 16


def ui_card_title_cap(width: int, grid: dict | None) -> int | None:
    """卡片栅格按列宽反算 --ui-card-title 上限（2026-11-25）。

    384f：两张 .ui-card 的标题各按 55px 撑到 502/447，第二张右边界顶到 1085。
    结构上限已在 components.css（列 minmax(0,1fr)，折行不越界），这里负责**尽量不折行**：
    标题字号 = (列宽−卡片水平占位) ÷ 最长标题字数，和本屏主字号×0.5 取小，下限 34px
    （再小就看不清，宁可折行）。单张卡占满整行（:only-child）时按整栏算。
    """
    if not isinstance(grid, dict):
        return None
    cards = grid.get("cards") or []
    cols = int(grid.get("cols") or 0)
    if cols < 2 or not cards:
        return None
    try:
        max_chars = max(int(card.get("title") or 0) for card in cards)
    except Exception:
        return None
    if max_chars <= 0:
        return None
    if len(cards) == 1:
        col = float(width)
    else:
        col = (width - (cols - 1) * UI_GRID_GAP) / float(cols)
    content = col - UI_CARD_PAD_X
    if content <= 0:
        return 34
    return max(34, int(content / max_chars))


def build_scene_css(scene_id: str, zone: str, align: str, scale: str, tone: str, chars: int = 0, media: dict | None = None, line_chars: int = 0, bg_family: str = "", avoid: dict | None = None, roles: dict | None = None, ui_grid: dict | None = None, ui_full: bool = False) -> str:
    """返回一段挂在 [data-scene="xx"] 下的 CSS。

    `avoid` 是数字人小窗的矩形（left/right/top/bottom）。有它时，顶部区的文字框
    必须让开右上角那块常驻视频窗：横向收得开就收右边界，收不开就把整块文字挪到小窗下方。
    04 黑帧线没有小窗，`avoid` 为 None，这条分支一行都不跑。
    """
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
    SAFE = 120
    # 2026-11-18 晚：图与字的间距 48 → 24，和 .scene-copy 的行间距分开。
    # 2026-11-19：左右并排已删，GAP 现在只用于「照片横带与文字带之间」和
    # 「文字块与数字人小窗之间」，不再有「图文左右间距」这回事。
    GAP = 24
    CANVAS_W, CANVAS_H = 1080, 1920
    MIN_TEXT = 330        # 数字人小窗让位后文字栏的最窄宽度（左右并排已删，正常版面恒为 840）
    TARGET_TEXT = 840     # 一栏式：文字栏就是整条内容区
    MIN_TEXT_BAND = 520   # 横带照片让开之后，文字区至少还能剩这么高，否则不算"分带"
    COPY_TOP = 150
    COPY_BOTTOM = 1533                    # 内容底线 y=1533：字幕带 1549–1670 一律不碰
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
    has_media = None not in (m_left, m_right, m_top, m_bottom)
    # 2026-11-17：横带判据从 95% 画幅放宽到 80%。照片档位改成小尺寸后，
    # 通栏横带是 900 宽（83%），按 95% 判就不再算"分带"，文字被推进旁边一条窄栏——
    # 图变小了、字反而更挤，正好反着。
    # 一栏式：照片宽度就是内容栏宽 840（= 1080 - 120×2），判据按可用宽度算，不再按画幅 80%。
    # 2026-11-19：**左右并排已从落版删除**，照片只剩上下通栏横带。
    # 所以"照片在侧 → 文字让位成窄栏"这条分支整段删掉：
    # 有照片时一律分带（另一带不够高由下面的 240 保底处理），文字永远占整条 120–960。
    # 满屏底纹（slot=full）不算内容，不参与分带。
    if has_media and slot != "full" and (m_right - m_left) >= (CANVAS_W - SAFE * 2) - 2:
        space_above = m_top - COPY_TOP
        space_below = COPY_BOTTOM - m_bottom
        band_split = True
    avail_w = right_edge - left_edge
    width = avail_w
    if texts_left:
        copy_left, copy_right = left_edge, left_edge + width
    else:
        copy_left, copy_right = right_edge - width, right_edge

    # ---- 数字人小窗（右上角常驻视频窗）----
    # 小窗在所有场景层之上，压上去就是把字遮掉。这里只有一个目标：文字框右边界不进小窗。
    # 收得开就收右边界；收不开就把整块文字挪到小窗下方（只有顶部区会走到这一步）。
    pip_rect = None
    if avoid and None not in (avoid.get("left"), avoid.get("right"), avoid.get("top"), avoid.get("bottom")):
        pip_rect = (int(avoid["left"]), int(avoid["bottom"]))

    def narrow_for_pip() -> bool:
        """把小窗那一侧收进来；收得开返回 True，收不开（剩余不足 MIN_TEXT）返回 False。"""
        nonlocal width, copy_left, copy_right, texts_left
        if not pip_rect:
            return False
        pip_left = pip_rect[0]
        if not (copy_left < pip_left < copy_right):
            return True          # 本来就不在小窗这一侧
        narrowed = pip_left - GAP - copy_left
        if narrowed < MIN_TEXT and not texts_left:
            # 右对齐、整条贴在小窗那一侧：改成贴左再算一次
            texts_left = True
            copy_left = left_edge
            narrowed = pip_left - GAP - copy_left
        if narrowed < MIN_TEXT:
            return False
        width = narrowed
        copy_right = copy_left + width
        return True

    def est_text_top() -> int:
        """文字块顶边估算：居中区的块高度按字数推，长文案会把整块往上撑。"""
        base_top = ZONE_TOP.get(z, COPY_TOP)
        if z in ("center", "left-middle", "right-middle"):
            base_top -= min(300, max(0, int(chars or 0) - 16) // 8 * 90)
        return base_top

    pip_push_top = None
    if pip_rect and est_text_top() < pip_rect[1] and not narrow_for_pip():
        pip_push_top = pip_rect[1] + GAP

    copy_top, copy_bottom = "%dpx" % COPY_TOP, "%dpx" % (CANVAS_H - COPY_BOTTOM)
    anchor = "center"

    # 照片和文字真的抢同一块地时：**等比缩小照片**（保比例、保外沿），
    # 不再把它压成一条窄边——2026-11-16 s01 的 930×1280 就是被压成了 397 宽。
    media_fix = ""
    align_next_to_photo = ""
    # 2026-11-17：新版照片框是行内 style + data-media-slot，没有 cls。
    # 以前判据写成 `rect.get("cls")`，这条"宁可缩照片也不压字"的分支对新页面全是死代码——
    # 照片挤过来时没人让，字被压成窄栏。现在 cls 和 slot 都能落选择器。
    media_target = ("." + rect["cls"]) if rect.get("cls") else (
        '[data-media-slot="%s"]' % slot if slot else "")
    if (media_target and not band_split
            and None not in (m_left, m_right, m_top, m_bottom)
            and copy_right >= m_left and copy_left < m_right):
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
            # 横向挤不出 240px：改成上下分带（左右并排已删，这里只作满屏图的兜底）。
            # 版面必须自己解决冲突，不能让"照片太大"变成"文字压在照片上"交给人去发现。
            band_h = min(m_bottom - m_top, 620)
            if center_y_of(m_top, m_bottom) < CANVAS_H / 2.0:
                top_new = max(COPY_TOP, 200)
                copy_top = "%dpx" % (top_new + band_h + GAP)
                anchor = "top"
            else:
                top_new = COPY_BOTTOM - band_h
                copy_bottom = "%dpx" % max(300, CANVAS_H - (top_new - GAP))
                anchor = "bottom"
            # !important：H02SK 把照片矩形写成行内 style，行内优先级高于普通选择器，
            # 不加 !important 这条让位规则整段失效，字就直接压在照片上（2026-11-17 s05 实测 110px）。
            media_fix = ('section[data-scene="%s"] %s{left:%dpx!important;top:%dpx!important;'
                         'width:%dpx!important;height:%dpx!important;}\n'
                         % (sid, media_target, SAFE, top_new, CANVAS_W - SAFE * 2, band_h))
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
            # !important：理由同上，行内 style 会盖掉让位结果（s05 文字压图 110px）。
            media_fix = ('section[data-scene="%s"] %s{left:%dpx!important;top:%dpx!important;'
                         'width:%dpx!important;height:%dpx!important;}\n'
                         % (sid, media_target, left_new, top_new, w_new, h_new))

    # 照片占了下半屏/上半屏时，文字区跟着让到另一半，别在中间和照片对着压。
    # 让位之后还要把这一半的"内容中心"留在构图舒适区内（700–1100）。
    # 2026-11-17：从 640 抬到 700——抬到硬边界下沿的时候文字虽然没越界，但成片里
    # 明显偏上（s02 实测 640），舒适区下沿才是应该守的那条线。
    # 两种方向统一用 space_above / space_below 判，不再各写一条死条件。
    CENTER_FLOOR = 700
    # 一栏式（2026-11-18 定）：文字只占「照片之外的那一段」，整块在这一段里垂直居中。
    # 不再贴图排、不再按舒适区抬顶——上下留白由居中自动算出来。
    if band_split:
        if space_above >= space_below:                 # 照片在下带，文字在上带
            band_top_px = COPY_TOP
            band_bottom_px = m_top - GAP
        else:                                          # 照片在上带，文字在下带
            band_top_px = m_bottom + GAP
            band_bottom_px = COPY_BOTTOM
        if pip_rect and space_above >= space_below:
            narrow_for_pip()
    else:
        band_top_px, band_bottom_px = COPY_TOP, COPY_BOTTOM
    band_top_px = int(round(band_top_px))
    band_bottom_px = int(round(band_bottom_px))
    if band_bottom_px - band_top_px < 240:             # 照片太大把文字带压没了：保底 240
        band_bottom_px = min(COPY_BOTTOM, band_top_px + 240)
    # 2026-11-19：照片和文字是**一组**——一起在 150–1533 里垂直居中，两者间距恒 GAP。
    # 用 flex 排，不用绝对定位算坐标：文字块的真实高度只有浏览器知道（换行、字体度量），
    # 自己算出来的 top 和真实高度差几十像素，就变成"规则写 24、实际 200"。
    flex_group = bool(has_media and slot != "full")

    # ---- 通栏组件层（span=full，2026-11-21）----
    # 组件原来一律渲染进 840 文字栏，对话气泡、表格这类"界面"被挤成两个小方块。
    # span=full 的组件由 R2 落到 .scene-ui（0–1080），这里给它一条横带、文字带让开，
    # 两边不抢地。带子上沿/下沿按"照片在哪一带"决定，和照片分带同一套规则。
    ui_band = None
    if ui_full:
        _ui_h = 560 if not band_split else 340
        if flex_group:
            # 照片和文字是一组 flex 排，组件带只能落在照片的**对面那一端**，
            # 让位靠 section 的 padding（下面 flex 那段），不靠改文字带上下沿。
            _ui_top = COPY_TOP if space_above >= space_below else COPY_BOTTOM - _ui_h
        else:
            _ui_top = COPY_BOTTOM - _ui_h           # 无照片 / 照片分带：组件放下带
            band_bottom_px = max(band_top_px + 240, _ui_top - GAP)
        ui_band = (int(_ui_top), int(_ui_h))
    copy_top = "%dpx" % band_top_px
    copy_bottom = "%dpx" % (CANVAS_H - band_bottom_px)

    # 2026-11-19：分带时文字**贴着照片排**，不再在带内居中。
    # 以前恒 center 的结果是：横带与文字带之间写着 24px，实际看到的空隙是 200–300px
    # （文字块在 863 高的空带里居中，离照片老远），"间距 24"名不副实。
    if band_split:
        if space_above >= space_below:      # 照片在下带 → 文字贴照片上沿
            anchor, align_next_to_photo = "bottom", "flex-end"
        else:                               # 照片在上带 → 文字贴照片下沿
            anchor, align_next_to_photo = "top", "flex-start"
    else:
        align_next_to_photo = "center"
        anchor = "center"

    # 2026-11-17：文字容器不再撑满整条带。以前 top/bottom 同时钉死，容器永远是
    # 780×1420（或 760×1420），柔光底衬照着容器画，就成了"占屏 80%、字只占中间一小条"
    # 的大暗块。现在 height:auto，容器内容多高就多高，anchor 只决定贴哪一端：
    #   top    → 贴在文字带上沿（照片在上半，字贴着照片）
    #   bottom → 贴在文字带下沿（照片在下半，字贴着照片）
    #   center → 居中在 200–1620 这条带的正中（无图屏 / 侧边照片）
    if pip_push_top is not None and band_split is False:
        # 横向让不开时，文字整块落在小窗下方（顶部区退化成上起排）
        copy_top = "%dpx" % pip_push_top
        anchor = "top"
    band_top = int(str(copy_top).replace("px", ""))
    band_bottom = int(str(copy_bottom).replace("px", ""))
    if flex_group:
        # 整组居中：文字块由 flex 排，不写 top/bottom/height（高度交给内容）
        copy_vpos = "  position:relative;top:auto;bottom:auto;left:auto;right:auto;width:%dpx;" % width
    elif anchor == "center":
        # 一栏式：容器撑满文字带，内容在带内垂直居中（内容多时自动等同顶对齐）
        copy_vpos = "  top:%dpx; height:%dpx;" % (band_top, max(240, (CANVAS_H - band_bottom) - band_top))
    elif anchor == "top":
        copy_vpos = "  top:%dpx;" % band_top
    else:
        copy_vpos = "  bottom:%dpx;" % band_bottom

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
    parts.append(copy_vpos)
    # flex 组里 .scene-copy 由容器居中放置，不能再写 left/right——
    # 写了就会在 flex 位置之上再偏移 120px（2026-11-19 实测：整块右移 120，看着像"横向居中"）。
    if not flex_group:
        parts.append("  left:%dpx;" % copy_left if texts_left else "  right:%dpx;" % (CANVAS_W - copy_right))
    parts.append("  width:%dpx;" % width)

    # 可用高度：文字带上下沿之间，扣掉字幕区之后的净高度
    _band_top = int(str(copy_top).replace("px", ""))
    _band_bottom = int(str(copy_bottom).replace("px", ""))
    if flex_group:
        avail_h = max(240, (COPY_BOTTOM - COPY_TOP) - GAP - (m_bottom - m_top)
                      - (ui_band[1] + GAP if ui_band is not None else 0))
    else:
        avail_h = max(240, (CANVAS_H - _band_bottom) - _band_top)
    fs = solve_scale(roles or {}, width, avail_h)
    _primary_size = max(fs.values()) if fs else ROLE_FLOOR["title"]

    parts.append("  display:flex;flex-direction:column;justify-content:%s;gap:26px;"
                 % (align_next_to_photo or "center"))
    parts.append("  text-align:%s;" % a)
    # 2026-11-17：给文字区一个跟随本屏明暗的继承色。组件里没显式上色的元素
    # （.ui-table 的 td、.ui-toast 这类）以前继承到文档默认黑，深底上整行看不见——
    # 第六屏的表格行就是这么"空"的。--ui-ink 本来就是按 tone 发的，这里让继承链也对上。
    parts.append("  color:var(--ui-ink);")
    # 组件字号跟着本屏主字号走，锚点重标（2026-11-19）：
    # 旧公式以"标题 96px → 1.55"起算，是给 120/150 那个年代写的。标题档改成 110–70 之后，
    # 110 只算出 1.61（.ui-card h3 = 34×1.61 ≈ 55px、正文 24×1.61 ≈ 39px），组件整体缩了一圈。
    # 现在锚在"标题 110 → 1.80"，往下到 70 → 1.60：h3 61–54px、组件正文 43–38px，
    # 和标题 110 / 正文 44 的层级对得上（组件是界面，要比正文大、比标题小）。
    _ui_scale = round(min(2.0, max(1.60, 1.60 + (_primary_size - 70) * 0.005)), 2)
    # 栅格组件的宽度契约（2026-11-21）：按最多字的格子反算上限，宁可整屏 UI 小一档，
    # 也不让 .ui-grid 撑出 840 栏。U54 的标签/值已在 components.css 分两行。
    _grid_cap = ui_grid_scale_cap(width, ui_grid)
    if _grid_cap is not None and _grid_cap < _ui_scale:
        _ui_scale = round(_grid_cap, 2)
    parts.append("  --ui-scale:%s;" % _ui_scale)
    parts.append("}\n")
    if flex_group:
        # section 自己当 flex 列：padding 把可用高度锁在 150–1533，justify-content 让整组居中。
        # 照片与文字的顺序按"照片在上带还是下带"用 order 换，不动 DOM（转场和动效都按 DOM 找元素）。
        _pad_top = COPY_TOP
        _pad_bottom = CANVAS_H - COPY_BOTTOM
        if pip_rect and space_above >= space_below:      # 文字在上带：让开右上角小窗
            _pad_top = max(COPY_TOP, int(pip_rect[1]) + GAP)
        # 通栏组件带在照片对面那一端：把那一端的 padding 撑开，flex 整组自然让开
        if ui_band is not None:
            if ui_band[0] <= COPY_TOP + 1:
                _pad_top = ui_band[0] + ui_band[1] + GAP
            else:
                _pad_bottom = CANVAS_H - ui_band[0] + GAP
        _order_copy, _order_media = (1, 2) if space_above >= space_below else (2, 1)
        parts.append('section[data-scene="%s"]{display:flex;flex-direction:column;'
                     'align-items:center;justify-content:center;box-sizing:border-box;'
                     'padding:%dpx 0 %dpx;gap:%dpx;}\n'
                     % (sid, _pad_top, _pad_bottom, GAP))
        parts.append('[data-scene="%s"] .scene-copy{order:%d;}\n' % (sid, _order_copy))
        parts.append('section[data-scene="%s"] .media[data-media-slot]{position:relative!important;'
                     'left:auto!important;top:auto!important;right:auto!important;bottom:auto!important;'
                     'inset:auto!important;flex:0 0 auto;width:%dpx!important;height:%dpx!important;'
                     'order:%d;}\n'
                     % (sid, m_right - m_left, m_bottom - m_top, _order_media))
    parts.append('[data-scene="%s"] .scene-copy > :only-child{margin-top:auto;margin-bottom:auto;}\n' % sid)
    # 一栏式只用一条左对齐的栏：卡片、组件不许自己居中（2026-11-18 定）。
    # 以前 `width:fit-content` 的 ui-card 在 flex 里被居中，同一屏出现"标题左对齐、卡片居中"两种对齐。
    parts.append('[data-scene="%s"] .scene-copy > *{align-self:flex-start;text-align:%s;}\n' % (sid, a))
    # 版面的唯一负责人是 composer：场景里给内容块写的绝对定位（top:1120px/left:90px 这种）
    # 一律不吃。2026-11-16 s07 的流程行就是这么双倍位移、右边界顶到 1080 的。
    parts.append('#stage [data-scene="%s"] .scene-copy > *{position:relative;top:auto;'
                 'left:auto;right:auto;bottom:auto;max-height:none!important;'
                 'max-width:100%%!important;'
                 'height:auto!important;overflow:visible!important;}\n' % sid)
    # 组件字号：不低于 1.55（24px 基准 ×1.55 ≈ 37px，竖屏小字下限 34px），
    # 也不低于本屏文字档位。以前直接吃 .scene-copy 上的档位值，窄栏里 5 个字
    # 会撑成 142px 高的一排砖；压小到 21px 又看不清，两头都不对。
    ui_scale = _ui_scale
    parts.append('[data-scene="%s"] .scene-copy [class*="ui-"]{--ui-scale:%s;}\n' % (sid, ui_scale))
    # 通栏组件层：整幅宽，字号档位和文字栏里的组件同一套（否则同一个 U11 在两屏里大小不一样）。
    # 位置/高度由上面算出的 ui_band 决定；这里只管"它是 1080 宽、内容在带内居中"。
    if ui_band is not None:
        parts.append('[data-scene="%s"] .scene-ui{position:absolute;z-index:5;left:0;width:%dpx;'
                     'top:%dpx;height:%dpx;display:flex;flex-direction:column;justify-content:center;'
                     'box-sizing:border-box;color:var(--ui-ink);}\n'
                     % (sid, CANVAS_W, ui_band[0], ui_band[1]))
        parts.append('[data-scene="%s"] .scene-ui [class*="ui-"]{--ui-scale:%s;}\n' % (sid, ui_scale))
    # 卡片字号直接锚在「本屏主字号 × 0.5 / 0.3」（2026-11-20 定）：
    # 34:24 不是同一个比例，用同一个 ui-scale 乘固定基准永远对不齐——
    # 标题 80px 时落到 56/40（实测 0.70 / 0.495），卡片比标题的层级差看不出来。
    # 这里按本屏主字号发两个变量，.ui-card 的 h3 / p 读它们；没有标题的屏退回旧公式。
    parts.append('[data-scene="%s"] .scene-copy{--ui-card-title:%dpx;--ui-card-body:%dpx;}\n'
                 % (sid, int(round(_primary_size * 0.5)), int(round(_primary_size * 0.3))))
    # 卡片栅格标题：按列宽反算上限（2026-11-25）。
    # 结构上列已经等分（components.css 的 minmax(0,1fr)），越界写不出来；
    # 这里只算"一行放得下"的字号，比本屏主字号×0.5 更小才下发，下限 34px。
    # 384f 的 8 字标题：列宽 412 → (412−62)/8 = 43px，一行放下。
    _card_layer_width = CANVAS_W if ui_band is not None else width
    _card_cap = ui_card_title_cap(_card_layer_width, ui_grid)
    _card_title = int(round(_primary_size * 0.5))
    if _card_cap is not None and _card_cap < _card_title:
        parts.append('[data-scene="%s"] .ui-grid{--ui-card-title:%dpx;}\n' % (sid, _card_cap))
    # 组件宽度不写死（2026-11-20 定）：.ui-steps 用 `minmax(max-content, 1fr)`，
    # 每列不窄于自己的内容，余量再均分；容器自适应时收敛到"n × 最宽那格 + 间距"。
    # .ui-grid 自 2026-11-25 起改成等分 + 0 下限（见 components.css），不写 width，
    # 窄栏只改方向和卡片。
    if width < 560:
        parts.append('[data-scene="%s"] .scene-copy .ui-grid{grid-template-columns:1fr;}\n' % sid)
        parts.append('[data-scene="%s"] .scene-copy .ui-steps{grid-auto-flow:row;gap:18px;}\n' % sid)
        parts.append('[data-scene="%s"] .scene-copy .ui-step{padding-top:0;}\n' % sid)
        parts.append('[data-scene="%s"] .scene-copy .ui-card{width:100%%!important;'
                     'max-width:100%%!important;min-width:0;}\n' % sid)
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
        # 只留 text-wrap:balance。不再叠 word-break:break-all：
        # balance 会在换行处自行均衡，break-all 允许在任意字符处断，两者叠加会把
        # "社会认可的成就，"这种 8 字标题切成 4+4、甚至把一个词从中间劈开
        # （2026-11-17 s07 实测"社会/认可"被拆到两行）。中文按标点和词边界折行才读得顺。
        return ('[data-scene="%s"] [data-role="%s"]{\n'
                '  margin:0;font-family:var(--font-stack);font-weight:%d;'
                'font-size:%dpx;line-height:%s;color:%s;'
                'text-wrap:balance;%s}\n' % (
                    sid, role, weight, size, _line_height(size), color, extra))

    parts.append(rule("title", fs["title"], 600, ink["primary"]))
    parts.append(rule("lead", fs["lead"], 500, ink["secondary"]))
    parts.append(rule("body", fs["body"], 400, ink["primary"], "opacity:.92;"))
    parts.append(rule("note", fs["note"], 400, ink["secondary"]))
    parts.append(rule("label", fs["label"], 500, ink["secondary"], "letter-spacing:.04em;"))
    parts.append('[data-scene="%s"] [data-role="num"]{\n'
                 '  margin:0;font-family:var(--font-stack);font-weight:600;'
                 'font-size:%dpx;line-height:1;color:%s;}\n' % (sid, fs["num"], ink["accent"]))
    # accent 是"被强调的一句/一个词"，必须自带字号：
    # 2026-11-14 踩过——只给 color，模型把它写在 <em>/<p> 上就用浏览器默认 16px。
    parts.append('[data-scene="%s"] [data-role="accent"]{\n'
                 '  margin:0;font-family:var(--font-stack);font-weight:600;'
                 '  font-size:%dpx;line-height:%s;color:%s;}\n' % (
                     sid, fs["accent"], _line_height(fs["accent"]), ink["accent"]))
    # 照片带和背景卡同屏时，边缘是硬切：棋盘/网点/扫描线在半屏照片旁边断成一条直线，
    # 看起来就是"两套背景拼在一起"（2026-11-16 s03 实测：B32 棋盘铺满，下带照片 760px，
    # 76px 的“两难”正好压在格子上）。给照片朝文字那一侧加一段到 --scene-base 的渐隐，
    # 缝就没了。只处理 top/bottom 这种整条带宽的槽位；left/right 的 inset 图自带留白，
    # full 满屏图不该被削边。
    # 新版照片框是 data-media-slot + 行内 style，没有可反查的 cls，所以用属性选择器定位。
    if slot in ("top", "bottom"):
        _edge = "bottom" if slot == "top" else "top"
        _target = ('[data-media-slot="%s"]' % slot) if not rect.get("cls") else ('.%s' % rect["cls"])
        # 2026-11-21：渐隐从「槽上的 ::after」改成「槽里的 .media-scrim 子元素」。
        # ::after 的问题：它在照片入场之前就已经画出来了，空槽 = 一块硬边深色板，
        # 看着就是占位框（s04 从 16.63s 到 19.26s 一直是这块板）。做成子元素以后，
        # 凡是动 media 子节点的卡都会把它一起带走，装饰只能跟内容同透明度。
        parts.append(
            'section[data-scene="%s"] %s > .media-scrim{position:absolute;inset:0;'
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
            # 2026-11-17：衬底原来 0.88/0.52 收在 -56/-44，成片里是一块看得见的"暗板"
            # （"每个文字都盖了一个透明背景"就是这么来的）。功能要保留（高密度底纹上压字），
            # 形状不能有：透明度压到 0.62/0.30，范围放大到 -120/-100，边界落在画面外。
            'inset:-120px -100px;z-index:-1;pointer-events:none;border-radius:120px;'
            'background:radial-gradient(ellipse at center, %s0.62) 0%%, %s0.30) 55%%, %s0) 88%%);}\n'
            % (sid, sid, _veil, _veil, _veil))
    if media_fix:
        parts.insert(0, media_fix)
    return "".join(parts)


def build_document_css(scenes, avoid: dict | None = None) -> str:
    """scenes: [{"id","zone","align","scale","tone","media"}, ...]；avoid 见 build_scene_css。"""
    blocks = []
    for item in scenes:
        css = build_scene_css(item.get("id"), item.get("zone"), item.get("align"),
                              item.get("scale"), item.get("tone"), item.get("chars") or 0,
                              item.get("media"), item.get("line_chars") or 0,
                              item.get("bg_family") or "", avoid,
                              item.get("roles") or {}, item.get("ui_grid"),
                              bool(item.get("ui_full")))
        if css:
            blocks.append(css)
    return "".join(blocks)


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    print(build_document_css(payload))
