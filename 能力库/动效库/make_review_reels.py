#!/usr/bin/env python3
"""把 presets.json 里的卡逐张做成 1080×1920 的审阅样片（真合成，不是格子）。

用法：
    python3 make_review_reels.py            # 生成 HTML 工程到 样片/全卡审阅/
    python3 make_review_reels.py --list     # 只打印分批

产物：能力库/动效库/样片/全卡审阅/reel-NN/index.html
每张卡 3 秒，左上角标编号 + 名字 + 族，右下角是「第几张 / 共几张」。
卡片的 code 原样展开（{{sel}}/{{at}}/参数），和管线里产出的代码是同一份。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
WORKSPACE = ROOT.parent.parent
PRESETS = ROOT / "presets.json"
OUT = WORKSPACE / "能力库" / "动效库" / "样片" / "全卡审阅"
VENDOR = WORKSPACE / "成品" / "workflow_runtime" / "assets" / "vendor"
PHOTO = WORKSPACE / "能力库" / "动效库" / "assets" / "demo" / "photo.png"

SECONDS = 3.0          # 每张卡时长
AT = 0.7               # 卡开始的时间点（屏内）
MAX_DUR = 2.0

# 分批：族 -> reel
BATCHES = [
    ("reel-01", "入场 + 字形", ["入场", "字形"]),
    ("reel-02", "状态与数据", ["状态"]),
    ("reel-03", "UI 组件", ["UI"]),
    ("reel-04", "离场与转场", ["离场", "结构"]),
    ("reel-05", "材质", ["材质"]),
    ("reel-06", "背景", ["背景"]),
    ("reel-07", "镜头 · 版面 · 照片", ["镜头", "版面", "绘制", "照片"]),
    ("reel-08", "交互 · 三维 · 候选", ["交互", "三维"]),
    ("reel-09", "转场（GT）", ["转场"]),
]

# 舞台类型：default=文字，ui=卡片行，media=图块，bg=canvas，three=canvas+three
STAGE = {}


SEL_MAP = {
    "T06": ".num", "DA01": ".num", "DA04": ".num", "DA02": ".bars b",
    "DA03": ".row", "S04": ".row", "S05": ".ph",
    "S06": ".row", "S07": ".row", "S09": ".row",
    "S11": ".row", "S08": ".panel", "S10": ".bars",
    "UA01": ".panel", "UA02": ".row", "UA03": ".row em", "UA04": ".bars b",
    "UA05": ".bars", "UA06": ".row", "UA07": ".row span",
    "I01": ".ptr", "I02": ".ptr", "G03": ".morph", "W02": ".shot", "S12": ".page", "Z02": "canvas",
}


def stage_of(card):
    cid, fam = card["id"], card.get("family", "")
    if cid.startswith("GT"):
        return "shot"
    if cid in ("G02",):
        return "flip"
    if cid in ("G03",):
        return "morph"
    if cid in ("W02",):
        return "frame"
    if cid == "S12":
        return "scroll"
    if cid == "I02":
        return "pointer2"
    if cid == "Z02":
        return "three"
    if cid == "I01":
        return "pointer"
    if cid == "Z01":
        return "three"
    if fam == "背景":
        return "bg"
    if fam in ("材质", "镜头"):
        return "media"
    if fam in ("状态", "UI") or cid in ("T06",):
        return "ui"
    return "text"


SUBJECT_TEXT = {
    "T01": ("还在手动复制", ""), "T02": ("外贸老板的效率困境", ""), "T03": ("线索在一个平台", ""),
    "T04": ("报价单", ""), "T05": ("$ npx build", ""), "T07": ("SYNC ENGINE", ""),
    "T08": ("V2.4", ""), "T09": ("128", ""), "T11": ("效率", ""),
    "K01": ("爆发式增长", ""), "K03": ("字自己落下", ""), "K04": ("把字收紧", ""),
    "K05": ("从一边揭开", ""), "K06": ("关键的一步", ""), "K07": ("画一条下划线", ""),
    "K08": ("32%", ""), "K09": ("正在同步", ""), "K10": ("纵横四海", ""),
    "K12": ("不靠加班", ""), "K13": ("先有线", ""), "K20": ("撑满这一行", ""),
    "W01": ("", ""), "G01": ("", ""), "X01": ("换一版", ""),
    "X03": ("切点前的收尾", ""), "X05": ("横向飞出去", ""), "X11": ("左擦除", ""),
    "X14": ("下擦除", ""), "X21": ("甩镜", ""),
}


def default_vars(card, sel, at, sel2):
    v = {"dur": 0.6, "stagger": 0.05, "from": 0, "to": 100, "seed": 7,
         "color": "#38d6ff", "child": ".b", "ratio": 0.98, "r": 26, "len": 26,
         "size": "340px", "radius": 520, "alpha": 0.6, "rx": 5, "ry": 7,
         "perspective": 1200, "h": 6, "w": 3, "op": 0.6, "z": 25, "speed": 0.05,
         "cursor": "#7BE8BE", "heights": "24,86,52,100", "text": "已成交",
         "steps": 6, "stepdur": 0.09, "ease": "power3.out", "dist": 40,
         "move": 0.8, "hold": 0.3, "press": 0.42, "hit": "rgba(134,240,192,.42)",
         "camZ": 8.6, "fogNear": 12, "fogFar": 30, "outOp": 0.12,
         "sel": sel, "sel2": sel2, "at": "at(%.2f)" % at}
    for k, val in (card.get("params") or {}).items():
        v[k] = val
    if "dur" in v:
        try:
            v["dur"] = min(float(v["dur"]), MAX_DUR)
        except Exception:
            v["dur"] = 0.6
    return v


def expand(code: str, v: dict) -> str:
    def rep(m):
        k = m.group(1)
        if k not in v:
            raise KeyError(k)
        return str(v[k])
    return re.sub(r"\{\{(\w+)\}\}", rep, code)



# ---------- 2026-11-13 新卡专用舞台 ----------

def _paper(inner, extra=""):
    return '<div class="paper" %s>%s</div>' % (extra, inner)


def _svg_stage(inner, h=1920):
    return ('<svg style="position:absolute;inset:0;width:1080px;height:1920px;display:block;overflow:visible">'
            '%s</svg>' % inner)


def _grid(n, cols=3, cls="gtile", gap=20):
    cells = "".join('<div class="%s">0%d</div>' % (cls, i + 1) for i in range(n))
    return ('<div id="grid" style="position:absolute;left:64px;right:64px;top:620px;display:grid;'
            'grid-template-columns:repeat(%d,1fr);gap:%dpx">%s</div>' % (cols, gap, cells))


def _card(inner, w=120, h=120, radius=20, fs=30):
    return ('<div id="sub" style="position:absolute;left:120px;top:820px;width:%dpx;height:%dpx;'
            'border-radius:%dpx;background:linear-gradient(140deg,#2f6b5c,#152a26);'
            'border:1px solid rgba(134,240,192,.45);display:grid;place-items:center;'
            'font-size:%dpx;font-weight:700;color:#dff8ee">%s</div>' % (w, h, radius, fs, inner))


ADV_STAGE = {
    "K22": _paper('<div class="h" style="font-size:96px;line-height:1.35"><span id="sub">线索自动分好</span></div>'),
    "K23": _paper('<div id="box" style="width:900px"><div class="h" id="sub" style="font-size:80px;line-height:1.35">线索自动分好，跟进自动记上</div></div>'),
    "K24": _paper('<div class="h" style="font-size:96px;line-height:1.35"><span id="sub">价格 ¥299 / 月</span></div>'),
    "U30": _svg_stage('<path id="p1" data-anim="subject" fill="none" stroke="#86F0C0" stroke-width="8" stroke-linecap="round" d="M120 1000 C 340 700, 640 1300, 960 900"/>'),
    "U31": _svg_stage('<rect id="p1" data-anim="subject" x="180" y="620" width="720" height="640" rx="40" fill="none" stroke="#86F0C0" stroke-width="8"/>'),
    "U32": _svg_stage('<path id="morph-target" d="M540 600 L 700 900 L 380 900 Z" fill="none"/>'
                      '<path id="shape" data-anim="subject" data-morph-to="#morph-target" fill="rgba(134,240,192,.16)" stroke="#86F0C0" stroke-width="6" d="M540 620 L 680 660 L 720 800 L 680 940 L 540 980 L 400 940 L 360 800 L 400 660 Z"/>'),
    "U33": _svg_stage('<path id="morph-target" d="M540 600 L 700 900 L 380 900 Z" fill="none"/>'
                      '<path id="shape" data-anim="subject" data-morph-to="#morph-target" fill="rgba(134,240,192,.16)" stroke="#86F0C0" stroke-width="6" d="M540 620 L 680 660 L 720 800 L 680 940 L 540 980 L 400 940 L 360 800 L 400 660 Z"/>'),
    "U34": _svg_stage('<circle id="morph-target" cx="540" cy="800" r="200" fill="none"/>'
                      '<path id="shape" data-anim="subject" data-morph-to="#morph-target" fill="rgba(134,240,192,.16)" stroke="#86F0C0" stroke-width="6" d="M540 620 L 680 660 L 720 800 L 680 940 L 540 980 L 400 940 L 360 800 L 400 660 Z"/>'),
    "U35": _svg_stage('<path id="motion-route" fill="none" stroke="rgba(134,240,192,.22)" stroke-width="6" d="M140 1400 C 400 900, 700 1600, 940 1000"/>') + _card("0", 90, 90, 16, 34),
    "U36": _svg_stage('<path id="motion-route" fill="none" stroke="rgba(134,240,192,.22)" stroke-width="6" d="M160 1500 C 420 900, 720 1500, 920 1000"/>') + _card("→", 100, 100, 50, 34),
    "U37": _svg_stage('<path id="motion-route" fill="none" stroke="rgba(134,240,192,.22)" stroke-width="6" d="M140 1300 L 300 900 L 540 1400 L 760 900 L 940 1200"/>') + _card("cubic", 110, 110, 18, 24),
    "T14": _paper('<div class="h" style="font-size:92px;line-height:1.45"><span id="sub">线索自动分好</span></div>'),
    "T15": _paper('<div class="h" style="font-size:92px;line-height:1.45"><span id="sub">快起慢收</span></div>'),
    "T16": _card("缩放", 100, 100, 50, 26),
    "T17": _card("冲过", 110, 110, 20, 26),
    "T18": _card("回位", 110, 110, 50, 26),
    "T19": _card("落地", 120, 120, 20, 26),
    "T20": _card("物理", 110, 110, 50, 26),
    "T21": _card("加速", 110, 110, 20, 26),
    "S16": _paper('<div class="mono" style="font-size:52px;line-height:1.7;color:#C9D3CC" id="sub">线索 128 条 · 待跟进</div>'),
    "S17": _paper('<div class="mono" style="font-size:52px;line-height:1.7;color:#C9D3CC" id="sub">待跟进 12 条</div>'),
    "G05": _grid(6, 3, "gtile", 20),
    "G06": '<div id="grid" style="position:absolute;left:64px;right:64px;top:700px;display:flex;gap:24px;flex-wrap:wrap">'
           + "".join('<div class="gtile" style="width:260px">%s</div>' % t for t in ("A", "B", "C")),
    "S18": _paper('<div class="h" style="font-size:80px;line-height:1.5"><span id="sub">流程整合度</span></div>'),
    "S19": _grid(6, 3, "gtile", 20),
    "UA08": _grid(4, 2, "gtile", 22),
    "G07": _grid(9, 3, "gtile", 22),
}

ADV_SEL = {
    "K22": "#sub", "K23": "#sub", "K24": "#sub",
    "U30": "#p1", "U31": "#p1", "U32": "#shape", "U33": "#shape", "U34": "#shape",
    "U35": "#sub", "U36": "#sub", "U37": "#sub",
    "T14": "#sub", "T15": "#sub", "T16": "#sub", "T17": "#sub", "T18": "#sub",
    "T19": "#sub", "T20": "#sub", "T21": "#sub",
    "S16": "#sub", "S17": "#sub",
    "G05": "#grid", "G06": "#grid", "S18": "#sub", "S19": "#grid", "UA08": "#grid", "G07": "#grid",
}

CAND_STAGE = {
    "W11": '<div class="shotbox"><img id="shot" src="./photo.png" alt=""></div>',
    "W12": '<div class="shotbox"><img id="shot" src="./photo.png" alt=""></div>',
    "W13": '<div class="shotbox"><img id="shot" src="./photo.png" alt=""></div>',
    "W15": '<div class="shotbox"><img id="shot" src="./photo.png" alt=""></div>',
    "W18": '<div class="shotbox"><img id="shot" src="./photo.png" alt=""></div>',
    "W20": '<div class="shotbox"><img id="shot" src="./photo.png" alt=""></div>',
    "K21": '<div class="paper"><div class="kick">逐词逐字</div>'
           '<div class="h" style="font-size:84px;line-height:1.45">搜索 · 触达 · 跟进，<span id="sub">一个后台跑完全程</span></div></div>',
    "T12": '<div class="paper"><div class="kick">手绘落位</div>'
           '<div class="h" style="font-size:92px;line-height:1.45"><span id="sub">线索自动分好</span></div></div>',
    "T13": '<div class="paper" style="display:grid;place-items:center">'
           '<div id="sub" style="padding:26px 44px;border-radius:22px;background:rgba(134,240,192,.16);'
           'border:1px solid rgba(134,240,192,.5);font-size:56px;font-weight:760">¥299 / 月</div></div>',
    "K13": '<div class="paper"><div class="kick">重点</div>'
           '<div class="h" style="font-size:92px;line-height:1.5">这一步<span id="sub">不用换软件</span></div></div>',
    "K14": '<div class="paper"><div class="kick">旁注</div>'
           '<div class="h" style="font-size:92px;line-height:1.5"><span id="sub">搜索 · 触达 · 跟进</span></div></div>',
    "K15": '<div class="paper"><div class="kick">否定</div>'
           '<div class="h" style="font-size:92px;line-height:1.5;color:#9FA9A2"><span id="sub">Excel 里反复搬运</span></div></div>',
    "K16": '<div class="paper"><div class="kick">强调</div>'
           '<div class="h" style="font-size:92px;line-height:1.5"><span id="sub">线索漏掉一半</span></div></div>',
    "U21": '<div class="paper"><div id="plate" style="font-size:78px;font-weight:760;line-height:1.55;'
           'letter-spacing:-.02em;color:#F4F1E9">这一步不用换软件，搜索、触达、跟进都在一个后台里完成</div></div>',
    "G04": '<div class="paper"><div id="fit" style="width:900px;font-size:80px;font-weight:780;line-height:1.32;'
           'letter-spacing:-.02em">线索自动分好，跟进自动记上，一个后台跑完全程</div></div>',
    "S13": '<div class="capbox"><div id="cap" style="font-size:56px;font-weight:760;line-height:1.35;'
           'text-align:center;color:#F4F1E9"></div></div>',
    "S14": '<div class="capbox" style="top:560px;height:700px"><div id="cap" style="font-size:84px;font-weight:790;'
           'line-height:1.5;text-align:center;display:flex;flex-wrap:wrap;gap:14px 12px;justify-content:center"></div></div>',
    "S15": '<div id="spec" style="position:absolute;left:64px;right:64px;top:620px;height:560px"></div>',
    "U23": '<div class="paper"><pre id="code" class="mono" style="font-size:32px;line-height:1.72;color:#C9D3CC;'
           'white-space:pre-wrap">from leadbot import search, crm\nleads = search.run("五金 出口")\nleads.push_to(crm)</pre></div>',
    "U24": '<div class="paper" style="display:grid;place-items:center;text-align:center">'
           '<span id="emo" style="font-size:230px;line-height:1">\U0001F60C</span></div>',
    "Z03": '<div class="paper" style="display:grid;place-items:center">'
           '<div id="big" style="font-size:190px;font-weight:820;line-height:1.1;letter-spacing:.02em">出海</div></div>',
    "U25": '<svg class="stage" viewBox="0 0 1080 1920" style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<path class="line dim" d="M120 1180 C 320 900, 520 1420, 720 1080 S 900 900, 980 1160"/>'
           '<path id="p1" data-anim="subject" fill="none" stroke="#86F0C0" stroke-width="8" stroke-linecap="round"'
           ' d="M120 1180 C 320 900, 520 1420, 720 1080 S 900 900, 980 1160"/></svg>',
    "U26": '<svg class="stage" viewBox="0 0 1080 1920" style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<path data-anim="subject" fill="none" stroke="#86F0C0" stroke-width="8" stroke-linecap="round" d="M140 900 L 940 900"/>'
           '<path data-anim="subject" fill="none" stroke="#86F0C0" stroke-width="8" stroke-linecap="round" d="M140 1060 L 940 1060"/>'
           '<path data-anim="subject" fill="none" stroke="#86F0C0" stroke-width="8" stroke-linecap="round" d="M140 1220 L 940 1220"/></svg>',
    "U27": '<svg class="stage" viewBox="0 0 1080 1920" style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<path id="morph-target" d="M540 560 L593 707 L749 712 L626 808 L669 958 L540 870 L411 958 L454 808 L331 712 L487 707 Z" fill="none"/>'
           '<path id="shape" data-anim="subject" data-morph-to="#morph-target" fill="rgba(134,240,192,.16)" stroke="#86F0C0" stroke-width="6"'
           ' d="M540 580 L681 638 L740 780 L681 922 L540 980 L399 922 L340 780 L399 638 Z"/></svg>',
    "U28": '<svg class="stage" viewBox="0 0 1080 1920" style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<path id="motion-route" fill="none" stroke="rgba(134,240,192,.22)" stroke-width="6"'
           ' d="M140 1500 C 300 900, 780 1700, 900 900"/></svg>'
           '<div id="mover" data-anim="subject" data-motion-path="#motion-route"'
           ' style="position:absolute;left:0;top:0;width:120px;height:120px;border-radius:18px;'
           'background:linear-gradient(140deg,#2f6b5c,#152a26);border:1px solid rgba(134,240,192,.5);'
           'display:grid;place-items:center;font-size:34px;font-weight:700;color:#dff8ee">车</div>',
    "U29": '<svg class="stage" viewBox="0 0 1080 1920" style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<path id="motion-route" fill="none" stroke="rgba(134,240,192,.22)" stroke-width="6"'
           ' d="M140 1400 C 420 800, 700 1600, 940 980"/></svg>'
           '<div id="mover" data-anim="subject" data-motion-path="#motion-route"'
           ' style="position:absolute;left:0;top:0;width:120px;height:120px;border-radius:18px;'
           'background:linear-gradient(140deg,#2f6b5c,#152a26);border:1px solid rgba(134,240,192,.5);'
           'display:grid;place-items:center;font-size:34px;font-weight:700;color:#dff8ee">段</div>',

}

CAND_SEL = {
    "W11": "#shot", "W12": "#shot", "W13": "#shot", "W15": "#shot", "W18": "#shot", "W20": "#shot",
    "K13": "#sub", "K14": "#sub", "K15": "#sub", "K16": "#sub",
    "U21": "#plate", "G04": "#fit", "S13": "#cap", "S14": "#cap", "S15": "#spec",
    "U23": "#code", "U24": "#emo", "Z03": "#big",
    "K21": "#sub", "T12": "#sub", "T13": "#sub",
    "U25": "#p1", "U26": '[data-anim="subject"]', "U27": "#shape", "U28": "#mover", "U29": "#mover",
}

CAND_STAGE.update(ADV_STAGE)
CAND_STAGE.update({
    "X32": '<div class="bd" style="position:absolute;inset:0;background:#05070a;opacity:0;z-index:20"></div>'
           '<div id="sub" data-anim="subject" style="position:absolute;left:140px;top:560px;width:800px;height:700px;'
           'border-radius:28px;background:#101314;border:1px solid rgba(255,255,255,.12);z-index:30;padding:44px">'
           '<div class="kick">跟进详情</div><div style="margin-top:22px;font-size:52px;font-weight:780">宁波 · 五金出口</div></div>',
    "X33": '<div class="bd" style="position:absolute;inset:0;background:#05070a;opacity:0;z-index:20"></div>'
           '<div id="sub" data-anim="subject" style="position:absolute;left:140px;top:560px;width:800px;height:700px;'
           'border-radius:28px;background:#101314;border:1px solid rgba(255,255,255,.12);z-index:30;padding:44px">'
           '<div class="kick">开 → 关 → 再开</div><div style="margin-top:22px;font-size:48px;font-weight:780">被打断的弹层</div></div>',
    "X34": '<div id="pageA" style="position:absolute;inset:0"><div id="sub" data-anim="subject" data-morph-to="520,460,26"'
           ' style="position:absolute;left:64px;top:700px;width:952px;height:300px;border-radius:20px;background:#101314;'
           'border:1px solid rgba(255,255,255,.12);display:flex;align-items:center;gap:26px;padding:0 30px">'
           '<img src="./photo.png" style="width:160px;height:160px;border-radius:14px;object-fit:cover">'
           '<div style="font-size:38px;font-weight:760">客户列表</div></div></div>'
           '<div id="pageB" style="position:absolute;inset:0;opacity:0"><div style="position:absolute;left:64px;top:520px;'
           'width:952px;height:820px;border-radius:26px;background:#101314;border:1px solid rgba(255,255,255,.12);overflow:hidden">'
           '<img src="./photo.png" style="width:100%;height:460px;object-fit:cover">'
           '<div style="padding:36px"><div style="font-size:44px;font-weight:780">客户详情</div></div></div></div>',
    "G10": '<div class="paper" style="padding:0;overflow:hidden"><div id="sub" data-anim="subject" data-morph-to="64,520,952,820,26"'
           ' style="position:absolute;left:300px;top:760px;width:480px;height:400px;border-radius:24px;background:#101314;'
           'border:1px solid rgba(255,255,255,.12)"><div class="swap-a" style="position:absolute;inset:0;display:grid;'
           'place-items:center;font-size:120px;font-weight:800;color:#86F0C0">A</div>'
           '<div class="swap-b" style="position:absolute;inset:0;display:grid;place-items:center;font-size:120px;'
           'font-weight:800;color:#FFD45E;opacity:0">B</div></div></div>',
    "G11": '<div class="paper" style="padding:0;overflow:visible"><div id="sub" data-anim="subject" data-morph-to="64,520,952,520,26"'
           ' style="position:absolute;left:120px;top:760px;width:420px;height:420px;border-radius:22px;background:#101314;'
           'border:1px solid rgba(255,255,255,.12)"><div data-layout-kid style="position:absolute;left:28px;top:28px;'
           'width:90px;height:90px;border-radius:14px;background:#86F0C0;transform-origin:0 0"></div>'
           '<div data-layout-kid style="position:absolute;left:28px;bottom:28px;width:120px;height:40px;border-radius:10px;'
           'background:rgba(255,212,94,.9);transform-origin:0 0"></div></div></div>',
    "G12": '<div class="paper" style="padding:0"><div id="sub" data-anim="subject" data-frame-from="120,800,300,300,20"'
           ' data-morph-to="64,520,952,560,26" style="position:absolute;left:120px;top:800px;width:300px;height:300px;'
           'border-radius:20px;background:#101314;border:1px solid rgba(255,255,255,.12)"></div></div>',
    "G13": "".join('<div data-anim="subject" data-morph-to="64,%d,952,300,22" style="position:absolute;left:%dpx;'
                   'top:820px;width:260px;height:200px;border-radius:18px;background:#101314;'
                   'border:1px solid rgba(255,255,255,.12);display:grid;place-items:center;font-size:38px;'
                   'font-weight:760;color:#86F0C0">0%d</div>' % (520 + i * 380, 90 + i * 320, i + 1) for i in range(3)),
    "G14": '<div class="paper" style="padding:0"><div id="sub" data-anim="subject" style="position:absolute;left:64px;'
           'top:700px;width:952px;height:180px;border-radius:18px;background:#101314;border:1px solid rgba(255,255,255,.12);'
           'display:flex;align-items:center;gap:24px;padding:0 28px;overflow:hidden">'
           '<img src="./photo.png" style="width:120px;height:120px;border-radius:14px;object-fit:cover;flex:0 0 auto">'
           '<div><div style="font-size:36px;font-weight:740">宁波 · 五金出口</div>'
           '<div class="mono" style="margin-top:8px;font-size:22px;color:#9FA9A2">待跟进 · 3 天</div></div></div></div>',
    "G15": '<div class="paper" style="padding:0;overflow:visible"><div id="sub" data-anim="subject" style="position:absolute;'
           'left:180px;top:760px;width:400px;height:400px;border-radius:20px;background:#101314;'
           'border:1px solid rgba(255,255,255,.12);overflow:visible">'
           '<div data-layout-kid style="position:absolute;left:40px;top:40px;width:120px;height:120px;border-radius:12px;'
           'background:#86F0C0;transform-origin:0 0"></div>'
           '<div data-layout-kid style="position:absolute;left:40px;bottom:40px;width:120px;height:40px;border-radius:8px;'
           'background:rgba(255,212,94,.9);transform-origin:0 0"></div></div></div>',
    "G16": '<div id="grid" style="position:absolute;left:64px;right:64px;top:820px;display:grid;'
           'grid-template-columns:repeat(5,1fr);gap:20px">'
           + "".join('<div class="gtile" data-anim="subject" style="text-align:center">0%d</div>' % (i + 1) for i in range(10))
           + '</div>',
    "S20": '<div class="paper" style="padding:0"><div id="sub" data-anim="subject" style="position:absolute;left:120px;'
           'top:900px;width:200px;height:200px;border-radius:24px;background:#101314;border:1px solid rgba(255,255,255,.12);'
           'display:grid;place-items:center;font-size:30px;font-weight:700;color:#86F0C0">同一目标</div></div>',
    "S21": '<div class="paper" style="padding:0"><div id="sub" data-anim="subject" style="position:absolute;left:64px;'
           'top:900px;width:120px;height:120px;border-radius:24px;background:#101314;border:1px solid rgba(255,255,255,.12);'
           'display:grid;place-items:center;font-size:26px;font-weight:700;color:#86F0C0">走</div></div>',
    "S22": '<div class="paper" style="padding:0"><div id="sub" data-anim="subject" style="position:absolute;left:460px;'
           'top:900px;width:160px;height:160px;border-radius:50%;background:rgba(134,240,192,.2);'
           'border:1px solid rgba(134,240,192,.6)"></div></div>',
    "T22": "".join('<div data-anim="subject" style="position:absolute;left:64px;top:%dpx;width:120px;height:120px;'
                   'border-radius:50%%;background:rgba(134,240,192,.18);border:1px solid rgba(134,240,192,.6)"></div>'
                   % (520 + i * 200) for i in range(3)),
})
CAND_STAGE.update({
    "G08": '<div class="paper" style="padding:0;overflow:hidden"><div id="sub" data-anim="subject"'
           ' data-morph-from="64,900,180,180,90" style="position:absolute;left:64px;top:900px;width:180px;'
           'height:180px;border-radius:90px;overflow:hidden;background:#101314;border:1px solid rgba(255,255,255,.12)">'
           '<img src="./photo.png" style="width:100%;height:180px;object-fit:cover;display:block">'
           '<div class="morph-text" style="opacity:0;padding:30px 34px">'
           '<div style="font-size:42px;font-weight:780">李工</div>'
           '<div style="margin-top:10px;font-size:24px;color:#9FA9A2">采购负责人 · 已跟进 3 次</div></div></div></div>',
    "G09": _grid(6, 3, "gtile", 20),
    "X30": '<div id="grid" style="position:absolute;left:64px;right:64px;top:640px;display:grid;'
           'grid-template-columns:repeat(4,1fr);gap:24px">'
           + "".join('<div class="tile" data-anim="subject" style="height:216px;border-radius:18px;'
                     'background:linear-gradient(135deg,%s)"></div>' % c
                     for c in ("#ff512f,#dd2476", "#2193b0,#6dd5ed", "#8e2de2,#4a00e0", "#f7971e,#ffd200",
                               "#00b09b,#96c93d", "#e96443,#904e95", "#11998e,#38ef7d", "#fc466b,#3f5efb"))
           + '</div>',
    "X31": '<div class="paper" style="padding:36px;overflow:hidden;height:520px">'
           '<div class="kick">跟进卡片</div>'
           '<div class="h" style="margin-top:20px;font-size:48px">宁波 · 五金出口</div>'
           '<div id="sub" data-anim="subject" data-escape-to="620,1440" style="position:absolute;left:36px;'
           'bottom:36px;padding:12px 24px;border-radius:999px;background:rgba(134,240,192,.16);'
           'border:1px solid rgba(134,240,192,.5);font-size:24px;font-weight:700;color:#c9f6e5">★ 重点跟进</div></div>',
    "W21": '<div class="paper" style="padding:0;overflow:hidden"><div id="sub" data-anim="subject"'
           ' data-frame-to="64,520,952,536" style="position:absolute;left:340px;top:900px;width:400px;'
           'height:600px;border-radius:22px;overflow:hidden;background:#101314">'
           '<img src="./photo.png" style="width:100%;height:100%;object-fit:cover;'
           'object-position:center 35%;display:block">'
           '<div class="hero-meta" style="position:absolute;left:0;right:0;bottom:0;padding:26px 30px;opacity:0;'
           'background:linear-gradient(180deg,transparent,rgba(6,8,9,.92))">'
           '<div style="font-size:40px;font-weight:780">出海 2026</div>'
           '<div style="margin-top:8px;font-size:22px;color:#9FA9A2">纪录 · 1h 52m</div></div></div></div>',
})
CAND_SEL.update(ADV_SEL)
CAND_SEL.update({"G08": "#sub", "G09": "#grid", "X30": '[data-anim="subject"]', "X31": "#sub", "W21": "#sub"})
CAND_SEL.update({"X32": "#sub", "X33": "#sub", "X34": "#sub", "G10": "#sub", "G11": "#sub", "G12": "#sub",
                 "G13": '[data-anim="subject"]', "G14": "#sub", "G15": "#sub", "G16": '[data-anim="subject"]',
                 "S20": "#sub", "S21": "#sub", "S22": "#sub", "T22": '[data-anim="subject"]'})


def stage_html(kind, card, sc):
    cid = card["id"]
    if cid in CAND_STAGE:
        return CAND_STAGE[cid]
    if kind == "text":
        t = SUBJECT_TEXT.get(cid, ("能力卡", ""))[0]
        return ('<div class="paper"><div class="kick">%s</div>'
                '<div class="h" data-anim="subject">%s</div></div>' % (cid, t or "能力卡"))
    if kind == "media":
        return ('<div class="media" data-anim="subject">'
                '<div class="tag">%s</div></div>' % cid)
    if kind == "ui":
        return ('<div class="panel" data-anim="subject">'
                '<div class="ph">本周线索</div>'
                '<div class="row"><i>A</i><span>宁波 · 五金出口</span><em>待跟进</em></div>'
                '<div class="row"><i>B</i><span>深圳 · 储能方案</span><em>已报价</em></div>'
                '<div class="row"><i>C</i><span>苏州 · 精密件</span><em>已接通</em></div>'
                '<div class="bars"><b style="height:38%"></b><b style="height:62%"></b>'
                '<b style="height:48%"></b><b style="height:86%"></b></div>'
                '<div class="num" data-anim="num">128</div>'
                '</div>')
    if kind == "flip":
        cards = ""
        spec = [(72, 760, 72, 760), (400, 760, 400, 760), (728, 760, 72, 1000), (72, 1000, 400, 1000)]
        for i, (fx, fy, tx, ty) in enumerate(spec):
            cards += ('<div class="fcard" data-anim="f%d" data-flip-from="%d,%d" data-flip-to="%d,%d" '
                      'style="left:%dpx;top:%dpx">0%d</div>' % (i, fx, fy, tx, ty, fx, fy, i + 1))
        return '<div class="fwrap" data-flip-container data-anim="subject">%s</div>' % cards
    if kind == "pointer":
        return ('<div class="panel" data-anim="subject">'
                '<div class="ph">今日线索</div>'
                '<div class="row hit" data-anim="hit"><i>B</i><span>深圳 · 储能方案</span><em>待跟进</em></div>'
                '<div class="row"><i>C</i><span>苏州 · 精密件</span><em>待跟进</em></div>'
                '</div>'
                '<svg class="ptr" data-anim="ptr" data-pointer-to="700,900" width="60" height="60" '
                'viewBox="0 0 32 40" width="72" height="90"><defs><filter id="psh" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="1.2" dy="2.2" stdDeviation="2.4" flood-color="#000" flood-opacity="0.55"/></filter></defs><g filter="url(#psh)"><path d="M2.67 1.78 L2.67 27.30 L9.62 21.24 L13.58 31.40 L18.02 29.46 L14.06 19.36 L23.40 19.36 Z" fill="#ffffff" stroke="#0a0a0a" stroke-width="1.55" stroke-linejoin="round"/></g></svg>')
    if kind == "morph":
        return ('<div class="morph" data-anim="subject" data-morph-to="72,700,936,470,30" '
                'style="left:600px;top:900px;width:300px;height:190px;border-radius:18px">'
                '<div class="mdetail" data-morph-detail>详情层</div></div>')
    if kind == "frame":
        return ('<div class="shot" data-anim="subject" data-frame-to="72,700,936,527" '
                'style="left:180px;top:860px;width:380px;height:380px"></div>')
    if kind == "scroll":
        secs = "".join('<div class="sec" style="top:%dpx">0%d</div>' % (150 + i * 300, i + 1) for i in range(3))
        return ('<div class="view"><div class="page" data-anim="subject">'
                '<div class="sticky">页面标题</div>%s</div></div>' % secs.replace('<div class="sec"', '<div class="sec" data-scroll-hl'))
    if kind == "pointer2":
        return ('<div class="panel"><div class="ph">新建跟进</div>'
                '<div class="row" data-anim="pick"><i>B</i><span>深圳 · 储能方案</span></div>'
                '<div class="field" data-anim="field">客户名称</div>'
                '<div class="submit" data-anim="submit">提交</div></div>'
                '<svg class="ptr" data-anim="ptr" data-pointer-path="pick,field,submit" width="60" height="60" '
                'viewBox="0 0 32 40" width="72" height="90"><defs><filter id="psh" x="-50%" y="-50%" width="200%" height="200%"><feDropShadow dx="1.2" dy="2.2" stdDeviation="2.4" flood-color="#000" flood-opacity="0.55"/></filter></defs><g filter="url(#psh)"><path d="M2.67 1.78 L2.67 27.30 L9.62 21.24 L13.58 31.40 L18.02 29.46 L14.06 19.36 L23.40 19.36 Z" fill="#ffffff" stroke="#0a0a0a" stroke-width="1.55" stroke-linejoin="round"/></g></svg>')
    if kind == "three":
        return '<canvas class="cv" data-anim="subject" width="1080" height="1920"></canvas>'
    if kind == "bg":
        return '<canvas class="cv" data-anim="bg" width="1080" height="1920"></canvas>'
    if kind == "shot":
        return ('<div style="position:absolute;inset:0;overflow:hidden">'
                '<img data-anim="subject" src="./photo.png" alt="" '
                'style="width:100%;height:100%;object-fit:cover;display:block"></div>')
    return ""


NEEDS_THREE = {"Z01"}

# 2026-11-13：插件卡要在样片工程里带上对应插件（生产由 sync_video 自动注入）
PLUGINS_FOR = {
    "G09": ["Flip"],
    "K22": ["SplitText"], "K23": ["SplitText"], "K24": ["SplitText"],
    "U30": ["DrawSVGPlugin"], "U31": ["DrawSVGPlugin"],
    "U32": ["MorphSVGPlugin"], "U33": ["MorphSVGPlugin"], "U34": ["MorphSVGPlugin"],
    "U35": ["MotionPathPlugin"], "U36": ["MotionPathPlugin"], "U37": ["MotionPathPlugin"],
    "T14": ["EasePack"], "T15": ["EasePack"], "T16": ["EasePack"],
    "T17": ["CustomEase"], "T18": ["CustomEase", "CustomBounce"], "T19": ["CustomEase", "CustomBounce"],
    "T20": ["Physics2DPlugin"], "T21": ["Physics2DPlugin"],
    "S16": ["TextPlugin"], "S17": ["TextPlugin"],
    "G05": ["Flip"], "G06": ["Flip"],

    "K21": ["SplitText"],
    "T12": ["EasePack"],
    "T13": ["CustomEase", "CustomBounce"],
    "U25": ["DrawSVGPlugin"],
    "U26": ["DrawSVGPlugin"],
    "U27": ["MorphSVGPlugin"],
    "U28": ["MotionPathPlugin"],
    "U29": ["MotionPathPlugin"],
}
PLUGIN_DIR = VENDOR / "gsap-plugins"


def scene_script(kind, card, sc, sel, sel2, at):
    """返回这段屏要执行的 JS（不含 try/catch，外层包）。"""
    cid = card["id"]
    if kind == "bg":
        return ("var _c=document.querySelector('%s');if(_c){var _o={t:0};"
                "timeline.to(_o,{t:6,duration:%s,ease:'none',onUpdate:function(){"
                "bgkit.draw(_c.getContext('2d'),'%s',1080,1920,_o.t);}},%.2f);}" % (sel, SECONDS - 0.4, cid, at))
    v = default_vars(card, sel, at, sel2)
    return expand(card["code"], v)


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000;font-family:"PingFang SC","Helvetica Neue",sans-serif;-webkit-font-smoothing:antialiased}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:#0a0b0b;color:#F4F1E9}
.scene{position:absolute;inset:0;display:none;overflow:hidden}
.scene.active{display:block}
.hdr{position:absolute;left:64px;top:74px;z-index:20;display:flex;align-items:baseline;gap:20px}
.hdr .id{font-family:"SF Mono",Menlo,monospace;font-size:30px;letter-spacing:.16em;color:#86F0C0}
.hdr .nm{font-size:40px;font-weight:640;letter-spacing:-.01em}
.hdr .fm{font-family:"SF Mono",Menlo,monospace;font-size:22px;color:#7e8a84;letter-spacing:.14em}
.ftr{position:absolute;right:64px;bottom:70px;z-index:20;font-family:"SF Mono",Menlo,monospace;
  font-size:24px;letter-spacing:.12em;color:rgba(244,241,233,.32)}
.paper{position:absolute;left:64px;right:64px;top:420px;bottom:300px;border-radius:20px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);padding:56px}
.paper .kick{font-family:"SF Mono",Menlo,monospace;font-size:22px;letter-spacing:.2em;color:#86F0C0}
.paper .h{margin-top:40px;font-size:96px;line-height:1.14;font-weight:680;letter-spacing:-.03em}
.media{position:absolute;left:64px;right:64px;top:420px;height:820px;border-radius:20px;overflow:hidden;
  background:radial-gradient(520px 420px at 62% 34%,rgba(255,236,206,.24),transparent 62%),
             linear-gradient(150deg,#22323a,#0d1214 62%,#0a0d0e);border:1px solid rgba(255,255,255,.07)}
.media .tag{position:absolute;left:40px;bottom:36px;font-family:"SF Mono",Menlo,monospace;
  font-size:24px;letter-spacing:.14em;color:rgba(244,241,233,.5)}
.panel{position:absolute;left:64px;right:64px;top:420px;border-radius:22px;padding:40px;
  background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.08)}
.panel .ph{font-size:34px;font-weight:640;margin-bottom:26px}
.panel .row{display:flex;align-items:center;gap:24px;padding:24px;border-radius:14px;
  border:1px solid transparent;background:rgba(255,255,255,.03);margin-bottom:12px;font-size:30px}
.panel .row i{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-family:"SF Mono",Menlo,monospace;font-size:20px;font-style:normal;color:#86F0C0;
  background:linear-gradient(140deg,#3c4f5a,#1b2428)}
.panel .row em{margin-left:auto;font-style:normal;font-family:"SF Mono",Menlo,monospace;font-size:20px;
  padding:8px 16px;border-radius:999px;border:1px solid rgba(255,255,255,.18);color:#C9D3CC}
.panel .bars{display:flex;align-items:flex-end;gap:16px;height:220px;margin-top:26px}
.panel .bars b{flex:1;background:rgba(134,240,192,.4);border-radius:6px 6px 0 0}
.panel .num{position:absolute;right:40px;top:26px;font-family:Georgia,serif;font-size:72px;color:#F4F1E9}
.fwrap{position:absolute;inset:0}
.fcard{position:absolute;width:300px;height:200px;border-radius:16px;display:flex;align-items:center;
  justify-content:center;font-family:"SF Mono",Menlo,monospace;font-size:26px;letter-spacing:.12em;
  color:rgba(244,241,233,.7);background:linear-gradient(140deg,#22322e,#101816);
  border:1px solid rgba(255,255,255,.08)}
canvas.cv{position:absolute;inset:0;width:1080px;height:1920px;display:block}
.morph{position:absolute;overflow:hidden;border:1px solid rgba(255,255,255,.1);
  background:linear-gradient(140deg,#20302c,#0e1513)}
.morph .mdetail{position:absolute;inset:0;padding:40px;opacity:0;font-size:30px;color:#9FA9A2}
.shot{position:absolute;border-radius:18px;border:1px solid rgba(255,255,255,.1);overflow:hidden;
  background-image:url("./photo.png");background-size:cover;background-position:52% 40%}
.view{position:absolute;left:64px;right:64px;top:420px;height:1160px;border-radius:22px;overflow:hidden;
  border:1px solid rgba(255,255,255,.09);background:#0d1010}
.page{position:absolute;left:0;right:0;top:0}
.sticky{position:absolute;left:0;right:0;top:0;height:110px;background:rgba(16,20,19,.96);
  border-bottom:1px solid rgba(255,255,255,.08);display:flex;align-items:center;padding:0 36px;font-size:30px}
.sec{position:absolute;left:36px;right:36px;height:260px;border-radius:18px;
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);padding:30px;font-size:30px}
.field{margin:12px 0;padding:24px;border-radius:12px;border:1px solid rgba(255,255,255,.14);
  background:rgba(255,255,255,.02);font-size:28px;color:#B7C1B9}
.submit{display:inline-block;padding:20px 36px;border-radius:999px;background:#86F0C0;color:#0a0b0b;
  font-size:28px;font-weight:640}
.ptr{position:absolute;left:-6px;top:-4px;z-index:60;width:72px;height:90px;pointer-events:none}
.gtile{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.10);
  border-radius:14px;padding:22px 18px;font-size:26px;font-weight:640;color:#E7EFEA}
.line{fill:none;stroke:#86F0C0;stroke-width:8;stroke-linecap:round}
.line.dim{stroke:rgba(134,240,192,.22);stroke-width:6}
.shotbox{position:absolute;left:64px;right:64px;top:420px;height:820px;border-radius:20px;overflow:hidden;
  border:1px solid rgba(255,255,255,.07)}
.shotbox img{width:100%;height:100%;object-fit:cover;display:block}
.capbox{position:absolute;left:64px;right:64px;top:1320px;height:340px;display:flex;align-items:center;justify-content:center}
.err{position:absolute;left:64px;right:64px;bottom:170px;z-index:40;font-family:"SF Mono",Menlo,monospace;
  font-size:26px;line-height:1.5;color:#ffd9d2;background:rgba(226,84,58,.22);
  border:1px solid rgba(226,84,58,.6);border-radius:10px;padding:16px 20px}
"""


def build_one(card, out_root: pathlib.Path):
    """一张卡一个自洽工程，渲染出 3 秒，文件名 <ID>-<名字>.mp4。"""
    cid = card["id"]
    fam = card.get("family", "其他")
    kind = stage_of(card)
    sc = "s01"
    sel = '[data-anim="subject"]'
    if cid in SEL_MAP:
        sel = SEL_MAP[cid]
    if kind == "pointer":
        sel = ".ptr"
    if kind == "flip":
        sel = ".fcard"
    if kind == "bg":
        sel = "canvas"
    if cid in CAND_SEL:
        sel = CAND_SEL[cid]
    sel2 = ".hit"
    try:
        js = scene_script(kind, card, sc, sel, sel2, AT)
    except Exception as e:
        js = ("(function(){var _d=document.createElement('div');_d.className='err';"
              "_d.textContent='%s 参数缺失: %s';document.querySelector('.scene').appendChild(_d);})();"
              % (cid, str(e)[:40].replace("'", "")))

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>%s · %s</title>
<style>%s</style></head><body>
<div id="stage" data-composition-id="card-%s" data-duration="%.1f">
<section class="scene active" data-scene="s01" data-start="0" data-duration="%.1f">
  <div class="hdr"><span class="id">%s</span><span class="nm">%s</span><span class="fm">%s</span></div>
  %s
</section>
</div>
<script src="./gsap.min.js"></script>
<script src="./bg-kit.js"></script>
<script src="./motion-kit.js"></script>
%s
<script>
(function(){
  var tl=gsap.timeline({paused:true});
  window.__timelines=window.__timelines||{};
  window.__timelines['card-%s']=tl;
  var timeline=tl;
  function at(x){return x;}
  %s
  window.addEventListener('hf-seek',function(e){tl.time(e.detail.time);});
})();
</script></body></html>""" % (
        cid, card["name"], CSS, cid.lower(), SECONDS, SECONDS,
        cid, card["name"], fam, stage_html(kind, card, sc),
        ('<script src="./three.global.js"></script>' if cid in NEEDS_THREE else "")
        + ('<script src="./gltrans-kit.js"></script><script src="./glsl.js"></script>'
           if cid.startswith("GT") else "")
        + "".join('<script src="./plugins/%s.min.js"></script>' % _p for _p in PLUGINS_FOR.get(cid, [])),
        cid, js)

    d = out_root / "源" / fam / cid
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(VENDOR / "gsap.min.js", d / "gsap.min.js")
    shutil.copy(VENDOR / "bg-kit.js", d / "bg-kit.js")
    shutil.copy(VENDOR / "motion-kit.js", d / "motion-kit.js")
    if cid in NEEDS_THREE:
        shutil.copy(VENDOR / "three.global.js", d / "three.global.js")
    if cid.startswith("GT"):
        shutil.copy(VENDOR / "gltrans-kit.js", d / "gltrans-kit.js")
        import build_gltrans as _bt
        _bt.build(pathlib.Path.home() / "Downloads" / "gl-transitions-master",
                  [card.get("src", "gltrans:").split(":", 1)[-1]], d / "glsl.js")
    if cid in PLUGINS_FOR:
        (d / "plugins").mkdir(exist_ok=True)
        for _p in PLUGINS_FOR[cid]:
            shutil.copy(PLUGIN_DIR / (_p + ".min.js"), d / "plugins" / (_p + ".min.js"))
    if "photo.png" in html:
        shutil.copy(PHOTO, d / "photo.png")
    (d / "hyperframes.json").write_text(json.dumps({
        "name": "card-" + cid.lower(), "version": 1, "composition": "index.html",
        "width": 1080, "height": 1920, "fps": 30, "duration": SECONDS
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只生成某一张（编号）")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tsv", action="store_true", help="只打印 族/编号/名字/目录，给渲染脚本用")
    args = ap.parse_args()
    cards = [c for c in json.loads(PRESETS.read_text(encoding="utf-8"))["presets"] if c.get("status") == "ready"]
    if args.only:
        cards = [c for c in cards if c["id"] == args.only]
        if not cards:
            raise SystemExit("没有这张卡：" + args.only)
    if args.list:
        for c in cards:
            print(c["id"], c["name"], c.get("family", ""))
        return
    rows = []
    for c in cards:
        d = build_one(c, OUT)
        rows.append("\t".join([c.get("family", "其他"), c["id"], c["name"], str(d)]))
        if args.tsv:
            print("\t".join([c.get("family", "其他"), c["id"], c["name"], str(d)]))
        else:
            print("%s %-10s -> %s" % (c["id"], c["name"], d.relative_to(WORKSPACE)))
    if not args.only:
        (OUT / "渲染清单.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    if not args.tsv:
        print("共 %d 张" % len(cards))


if __name__ == "__main__":
    main()
