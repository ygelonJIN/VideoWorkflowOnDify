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
# 模型不写 px，也不写档位；本地不再读 data-composition-scale 决定大小。
PRIMARY_ORDER = ("title", "num", "lead", "body", "note", "label", "accent")

# 单条文字的设计上限（px）。不是档位，是"再大就成海报了"的常识边界。
ROLE_CEIL = {"title": 200, "num": 260, "lead": 132, "body": 104,
             "note": 76, "label": 76, "accent": 116}
# 可读下沿。竖屏字幕 45px，任何正文都不能比它小。
ROLE_FLOOR = {"title": 76, "num": 76, "lead": 48, "body": 46,
              "note": 42, "label": 42, "accent": 48}
# 主副关系：副字号 = 主字号 × 相对比例。缺 title 时主角色自动变成 lead/body，
# 所以"模型漏写 title → 整屏只有 36px"这条路径不存在了。
ROLE_REL = {"title": 1.00, "num": 1.00, "lead": 1.00, "body": 0.80,
            "note": 0.66, "label": 0.66, "accent": 0.90}
GAP = 26                      # 与 .scene-copy 的 gap 一致
ANCHOR_FLOOR = 88             # 整屏视觉锚的下沿：一屏里最大的字至少要这么大，否则竖屏读不出重点



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


def solve_scale(roles: dict, width: int, avail_h: float) -> dict:
    """roles: {"title": {"units": 8, "segs": []}, ...} → {"title": 112, ...}

    步骤：每条按自己字数填满栏宽 → 主副比例压副标题 → 整块高度装不下就等比收（不低于下沿）。
    没有一步依赖"这句话里有没有出现某个词"。
    """
    items = {}
    for role, data in (roles or {}).items():
        if role not in ROLE_CEIL or not isinstance(data, dict):
            continue
        units = data.get("units")
        if units is None:                       # 原始文案：占几个字宽由这里算，不在上游算
            units = _em_units(data.get("text") or "")
        units = int(units or 0)
        if units <= 0:
            continue
        segs = data.get("segs")
        if segs is None:
            segs = [_em_units(part) for part in (data.get("lines") or []) if str(part or "").strip()]
            if len(segs) < 2:                   # 只有一段 = 没有硬换行
                segs = []
        segs = [int(x) for x in segs if int(x) > 0]
        items[role] = {"units": units, "segs": segs,
                       "seg_max": max(segs) if segs else 0}
    if not items:
        return {role: ROLE_FLOOR[role] for role in ROLE_CEIL}

    primary = next((r for r in PRIMARY_ORDER if r in items), None) or next(iter(items))
    out = {}
    for role, data in items.items():
        out[role] = _size_for(role, data["units"], data["seg_max"], width)
    # 主字号不许把小字甩开太远：主字号 ≤ 副角色里最大的那条 × 2.4。
    # 2026-11-17 实测：s04 的 body 写了 <br>，最长一行 10 字在 482 栏里最多 48px，
    # 标题照算能到 200px——同一屏 200px 标题配 48px 正文，看起来就是两屏拼在一起。
    # 这一条只压主字号，不抬副字号（副字号受几何硬约束，抬不动）。
    out[primary] = _clamp(max(out[primary], ANCHOR_FLOOR),
                          ROLE_FLOOR.get(primary, 76), ROLE_CEIL.get(primary, 200))
    _others = [v for k, v in out.items() if k != primary]
    if _others:
        out[primary] = _clamp(min(out[primary], max(_others) * 2.4),
                              ROLE_FLOOR.get(primary, 76), ROLE_CEIL.get(primary, 200))
    # 主副：副字号不超过 主字号 × 相对比例，避免"引子和标题一样大"
    base_rel = ROLE_REL.get(primary, 1.0)
    for role in list(out):
        if role == primary:
            continue
        share = out[primary] * float(ROLE_REL.get(role, 0.8)) / max(1e-6, base_rel)
        out[role] = _clamp(min(out[role], share),
                           ROLE_FLOOR.get(role, 46), ROLE_CEIL.get(role, 200))
    # 高度收敛：装不下就整块收，但绝不低于可读下沿（宁可多折一行）
    for _ in range(24):
        total = GAP * max(0, len(items) - 1)
        for role, data in items.items():
            size = out[role]
            total += _lines_of(data["units"], data["segs"], width, size) * size * _line_height(size)
        if total <= avail_h:
            break
        shrunk = False
        for role in out:
            floor = ROLE_FLOOR.get(role, 46)
            nxt = _clamp(int(out[role] * 0.94), floor, ROLE_CEIL.get(role, 200))
            if nxt < out[role]:
                out[role] = nxt
                shrunk = True
        if not shrunk:
            break
    # 这一屏没出现的角色也给一个值：CSS 依旧按 7 个角色出规则，只是没人用到
    base = out.get(primary) or ROLE_FLOOR["title"]
    for role, ceil_v in ROLE_CEIL.items():
        if role in out:
            continue
        out[role] = _clamp(base * float(ROLE_REL.get(role, 0.8)) / max(1e-6, base_rel),
                           ROLE_FLOOR.get(role, 46), ceil_v)
    return out


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
    value = str(align or "").strip().lower()
    if value in ("left", "center", "right"):
        return value
    return "center" if zone == "center" else "left"


def normalise_scale(scale: str | None) -> str:
    """`data-composition-scale` 只认排版模式这种真枚举，不再参与字号大小。

    写别的（"两条大字""流程节点+大字结论"这类自由文本）一律当没写——字号由几何算，
    读文本只是为了让"竖排"这种版面模式还能生效。
    """
    value = str(scale or "").strip().lower()
    if value in ("vertical", "竖排", "竖版"):
        return "vertical"
    return ""


def center_y_of(top, bottom):
    return (float(top) + float(bottom)) / 2.0


def build_scene_css(scene_id: str, zone: str, align: str, scale: str, tone: str, chars: int = 0, media: dict | None = None, line_chars: int = 0, bg_family: str = "", avoid: dict | None = None, roles: dict | None = None) -> str:
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
    has_media = None not in (m_left, m_right, m_top, m_bottom)
    # 2026-11-17：横带判据从 95% 画幅放宽到 80%。照片档位改成小尺寸后，
    # 通栏横带是 900 宽（83%），按 95% 判就不再算"分带"，文字被推进旁边一条窄栏——
    # 图变小了、字反而更挤，正好反着。
    if has_media and (m_right - m_left) >= CANVAS_W * 0.80:
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
    # 2026-11-17：无图屏用满安全宽度。以前无图屏也吃 zone 的 780/760，
    # 右侧（左对齐）或左侧（右对齐）整条留白空着，字还在窄栏里自己折行——
    # 画面里没有任何东西要避让，凭什么收窄。有图的屏才按让位后的宽度收。
    width = avail_w if not has_media else min(max(width, min(MIN_TEXT, avail_w)), avail_w)
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
        # 数字人小窗：文字带在上方（照片在下带）时，右上角同样要让开。
        if pip_rect and space_above >= space_below:
            narrow_for_pip()
        # 文字块贴着自己那张照片，留白放在画面外侧（2026-11-17）：
        # 居中放的时候，照片在上带的屏文字会一路掉到底、贴住字幕（s07 实测中心 1284），
        # 照片在下带的屏文字又悬在上方。贴图排之后两行字和图片是一组，外沿留白更像版式。
        align_next_to_photo = "flex-end" if space_above >= space_below else "flex-start"
        anchor = "bottom" if space_above >= space_below else "top"

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
    if anchor == "top":
        copy_vpos = "  top:%dpx;" % band_top
    elif anchor == "bottom":
        copy_vpos = "  bottom:%dpx;" % band_bottom
    else:
        band_center = (band_top + (CANVAS_H - band_bottom)) / 2.0
        copy_vpos = "  top:%dpx;transform:translateY(-50%%);" % int(round(band_center))

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
    parts.append("  left:%dpx;" % copy_left if texts_left else "  right:%dpx;" % (CANVAS_W - copy_right))
    parts.append("  width:%dpx;" % width)

    # 可用高度：文字带上下沿之间，扣掉字幕区之后的净高度
    _band_top = int(str(copy_top).replace("px", ""))
    _band_bottom = int(str(copy_bottom).replace("px", ""))
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
    # 组件字号跟着本屏主字号走：主字号 96px 时 1.55，200px 时 2.0（夹在 [1.55, 2.0]）
    _ui_scale = round(min(2.0, max(1.55, 1.55 + (_primary_size - 96) * 0.0045)), 2)
    parts.append("  --ui-scale:%s;" % _ui_scale)
    if s == "vertical":
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
    ui_scale = _ui_scale
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
                              item.get("roles") or {})
        if css:
            blocks.append(css)
    return "".join(blocks)


if __name__ == "__main__":
    import json
    import sys
    payload = json.loads(sys.argv[1]) if len(sys.argv) > 1 else []
    print(build_document_css(payload))
