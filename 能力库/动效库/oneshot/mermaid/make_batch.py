#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 mermaid 搬出来的东西写成一批待审卡（本批.json）。

输入：同目录 shapes.json（extract.mjs 的产物，几何是 mermaid 自己算的）
输出：本批.json —— 只用来出候选样片，不写 presets.json。

三类东西：
  1) 形状卡 MG01..   每个形状一张，走 DrawSVG 描边 + 淡入
  2) 图示卡 MD01..   流程图 / 时序图 / 泳道 / 时间轴 / 四象限 / 桑基 / 树 / 鱼骨
  3) 动效卡 MX01..   逐边画出 / 光点沿路径 / 跨线跳桥 / 步骤徽章，加一张换行卡 MT01
"""
from __future__ import annotations

import json
import pathlib
import re

HERE = pathlib.Path(__file__).resolve().parent
SHAPES = json.loads((HERE / "shapes.json").read_text(encoding="utf-8"))["shapes"]

STROKE = "#86F0C0"
FILL = "rgba(134,240,192,.14)"
TEXT = "#F4F1E9"
MUTED = "#9FA9A2"
ACCENT = "#FFD45E"

NAMES = {
    "anchor": "锚点", "bang": "感叹符", "blockArrow": "块箭头", "bowTieRect": "领结框",
    "bpmnActivity": "BPMN 任务", "bpmnAnnotation": "BPMN 注释", "bpmnBoundary": "BPMN 边界事件",
    "bpmnDataObject": "BPMN 数据对象", "bpmnDataStore": "BPMN 数据存储", "bpmnEnd": "BPMN 结束",
    "bpmnEvent": "BPMN 事件", "bpmnGateway": "BPMN 网关", "bpmnIntermediate": "BPMN 中间事件",
    "bpmnStart": "BPMN 开始", "browser": "浏览器窗", "bucket": "桶", "card": "卡片形",
    "choice": "菱形判断", "circle": "圆", "cloud": "云", "collapsedGroup": "折叠组",
    "composite": "组合框", "console": "命令行窗", "crossedCircle": "叉圆",
    "curlyBraceLeft": "左花括号", "curlyBraceRight": "右花括号", "curlyBraces": "花括号",
    "curvedTrapezoid": "曲边梯形", "cylinder": "圆柱", "datastore": "数据存储",
    "defaultMindmapNode": "脑图节点", "dividedRect": "分隔框", "document": "文档形",
    "doubleCircle": "双圆", "erBox": "实体框", "filledCircle": "实心圆",
    "flippedTriangle": "倒三角", "folder": "文件夹", "forkJoin": "分叉汇合",
    "halfRoundedRectangle": "半圆角框", "hexagon": "六边形", "hourglass": "沙漏",
    "icon": "图标框", "iconCircle": "圆形图标框", "iconRounded": "圆角图标框",
    "iconSquare": "方形图标框", "imageSquare": "图片框", "invertedTrapezoid": "倒梯形",
    "kanbanItem": "看板项", "labelRect": "标签框", "leanLeft": "左倾框", "leanRight": "右倾框",
    "lightningBolt": "闪电", "linedCylinder": "线纹圆柱", "linedWaveEdgedRect": "线纹波浪框",
    "mindmapCircle": "脑图圆", "multiRect": "多段框", "multiWaveEdgedRectangle": "多段波浪框",
    "note": "便签", "person": "人形", "question": "问号", "rectLeftInvArrow": "左反箭头框",
    "rectWithTitle": "带标题框", "requirementBox": "需求框", "roundedRect": "圆角框",
    "shadedProcess": "阴影流程框", "slopedRect": "斜切框", "squareRect": "方框",
    "stadium": "药丸框", "state": "状态框", "stateEnd": "结束态", "stateStart": "起始态",
    "subroutine": "子程序框", "taggedRect": "带标签框", "taggedWaveEdgedRectangle": "带标签波浪框",
    "text": "纯文字", "tiltedCylinder": "斜置圆柱", "trapezoid": "梯形",
    "trapezoidalPentagon": "五边形", "triangle": "三角", "usecaseActor": "用例角色",
    "usecaseActorAwesome": "用例角色·实", "usecaseActorHollow": "用例角色·空",
    "usecaseActorIcon": "用例角色·图", "usecaseBusiness": "业务用例", "usecaseEllipse": "椭圆用例",
    "usecaseJsonTable": "JSON 表", "waveEdgedRectangle": "波浪框", "waveRectangle": "波浪矩形",
    "windowPane": "窗格",
}

# classBox 的导出是给类图用的多行布局，构造函数不在提取白名单里；按同样的版式补一张。
CLASSBOX_SVG = (
    '<svg viewBox="-230 -170 460 340" xmlns="http://www.w3.org/2000/svg" data-shape="classBox">'
    f'<rect x="-230" y="-170" width="460" height="110" fill="{FILL}" stroke="{STROKE}" stroke-width="4"/>'
    f'<rect x="-230" y="-60" width="460" height="230" fill="rgba(134,240,192,.06)" stroke="{STROKE}" stroke-width="4"/>'
    f'<line x1="-230" y1="-60" x2="230" y2="-60" stroke="{STROKE}" stroke-width="3"/>'
    f'<text x="0" y="-105" text-anchor="middle" font-size="34" font-weight="700" fill="{TEXT}">类名</text>'
    f'<text x="-200" y="-16" font-size="26" fill="{MUTED}">+ 字段: 类型</text>'
    f'<text x="-200" y="30" font-size="26" fill="{MUTED}">+ 方法(): 返回</text>'
    '</svg>'
)


# mermaid 的描边多半靠 CSS 类，不在属性上；这里补一份最小样式表，让线框在暗底上立住。
SHAPE_STYLE = (
    "<style>svg{overflow:visible}"
    "*{stroke:" + STROKE + ";stroke-width:3;stroke-linejoin:round;stroke-linecap:round}"
    "text{stroke:none;fill:" + TEXT + "}"
    "line,path{fill:none}"
    "rect,polygon,circle,ellipse{fill:rgba(134,240,192,.12)}"
    "rect[opacity='0'],.bpmn-bounds{fill:none;stroke:none}"
    ".bpmn-bounds,[opacity='0']{stroke:none;fill:none}"
    "</style>"
)


def recolor(svg: str) -> str:
    """把 mermaid 主题色统一成本库的线色；形状本身不动。"""
    svg = re.sub(r'stroke="#(?!none)[0-9a-fA-F]{3,8}"', f'stroke="{STROKE}"', svg)
    svg = re.sub(r'fill="#(?!none)[0-9a-fA-F]{3,8}"', f'fill="{FILL}"', svg)
    return svg.replace(">", ">" + SHAPE_STYLE, 1)


def shape_stage(svg: str) -> str:
    w = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+) ([\d.]+)"', svg)
    vw = float(w.group(1)) if w else 400.0
    vh = float(w.group(2)) if w else 400.0
    # 长边统一到 560px：小形状不至于被放大成糊，长条形状也不至于撑爆
    scale = 480.0 / max(vw, vh, 1.0)
    scale = min(max(scale, 0.35), 9.0)
    width = int(vw * scale)
    return (
        '<div data-anim="subject" style="position:absolute;left:0;right:0;top:560px;display:flex;justify-content:center">'
        '%s</div>' % svg.replace('<svg ', '<svg style="width:%dpx;height:auto;display:block" ' % width)
    )


SHAPE_JS = (
    "var _s=document.querySelector('%s svg');"
    "var _p=_s?_s.querySelectorAll('path,rect,circle,ellipse,polygon,line,polyline'):[];"
    "timeline.fromTo(_p,{opacity:0},{opacity:1,duration:0.22,stagger:0.03},0.30);"
    "if(window.DrawSVGPlugin&&_p.length){"
    "timeline.fromTo(_p,{drawSVG:'0%%'},{drawSVG:'100%%',duration:1.05,ease:'power2.inOut',stagger:0.04},0.42);}"
    "if(_s){timeline.fromTo(_s,{scale:0.985},{scale:1,duration:1.1,ease:'power2.out'},0.36);}"
)

SEL = '[data-anim="subject"]'


# 这两个在 mermaid 里不是"形状"：anchor 只是一个点标记，labelRect 只画标签、矩形是 0.1×0.1。
DEGENERATE = {"anchor", "labelRect"}


def shape_cards():
    cards = []
    items = [{"name": s["name"], "svg": s["svg"]} for s in SHAPES if s["name"] not in DEGENERATE]
    items.append({"name": "classBox", "svg": CLASSBOX_SVG})
    for i, it in enumerate(items, start=1):
        name_cn = NAMES.get(it["name"], it["name"])
        svg = recolor(it["svg"])
        code = svg.replace(STROKE, "{{stroke}}").replace(FILL, "{{fill}}")
        cards.append({
            "id": "MG%02d" % i,
            "name": name_cn,
            "family": "图示",
            "role": "component",
            "status": "ready",
            "cap": "component-html",
            "src": "mermaid:shapes/%s.ts" % it["name"],
            "params": {"w": 640, "fill": FILL, "stroke": STROKE},
            "use": "图示里当节点/容器底板：%s；只换文案与配色" % name_cn,
            "avoid": "不要单形状铺满整屏，也不要同时上三种以上形状",
            "code": code,
            "sample": {
                "stage": shape_stage(svg),
                "sel": SEL,
                "plugins": ["DrawSVGPlugin"],
                "js": SHAPE_JS % SEL,
            },
        })
    return cards


# ---------------- 图示卡的手摆版面（1080×1920） ----------------

def _node(cx, cy, w, h, label, r=20, fill=None, cls="dn"):
    fill = fill or "rgba(255,255,255,.05)"
    return (f'<g class="{cls}"><rect x="{cx - w / 2}" y="{cy - h / 2}" width="{w}" height="{h}" rx="{r}" '
            f'fill="{fill}" stroke="{STROKE}" stroke-width="4"/>'
            f'<text x="{cx}" y="{cy + 12}" text-anchor="middle" font-size="34" font-weight="650" '
            f'fill="{TEXT}">{label}</text></g>')


def _edge(d, cls="de", arrow=True, dash=None):
    extra = ' stroke-dasharray="%s"' % dash if dash else ""
    mk = ' marker-end="url(#arw)"' if arrow else ""
    return f'<path class="{cls}" d="{d}" fill="none" stroke="{STROKE}" stroke-width="5"{mk}{extra}/>'


DEFS = (
    '<defs><marker id="arw" viewBox="0 0 12 12" refX="10" refY="6" markerWidth="7" markerHeight="7" '
    f'orient="auto"><path d="M1 1 L11 6 L1 11" fill="none" stroke="{STROKE}" stroke-width="2"/></marker></defs>'
)

SVG_OPEN = ('<svg class="dsvg" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg" '
            'style="position:absolute;inset:0;width:1080px;height:1920px">')


def _wrap(inner):
    return SVG_OPEN + DEFS + inner + '</svg>'


def diagram_flow():
    inner = (
        _node(540, 560, 420, 150, "拿到线索")
        + _node(280, 860, 360, 150, "自动筛选")
        + _node(800, 860, 360, 150, "自动分级")
        + _node(540, 1160, 420, 150, "按级跟进")
        + _node(540, 1440, 420, 150, "成交归档")
        + _edge("M540 635 V710 H280 V785")
        + _edge("M540 635 V710 H800 V785")
        + _edge("M280 935 V1010 H540 V1085")
        + _edge("M800 935 V1010 H540 V1085")
        + _edge("M540 1235 V1365")
    )
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn rect',{opacity:0,scale:.94,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.5,ease:'power2.out',stagger:.12},0.30);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn text',{opacity:0},{opacity:1,duration:.4,stagger:.12},0.45);"
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},"
        "{drawSVG:'100%',duration:.55,ease:'power2.inOut',stagger:.18},0.9);"
    )
    return _wrap(inner), js


def diagram_sequence():
    xs = [250, 540, 830]
    names = ["客户", "系统", "后台"]
    inner = ""
    for x, n in zip(xs, names):
        inner += (f'<g class="dn"><rect x="{x - 110}" y="520" width="220" height="90" rx="16" '
                  f'fill="rgba(255,255,255,.06)" stroke="{STROKE}" stroke-width="4"/>'
                  f'<text x="{x}" y="576" text-anchor="middle" font-size="34" font-weight="650" '
                  f'fill="{TEXT}">{n}</text></g>')
        inner += (f'<line class="de" x1="{x}" y1="610" x2="{x}" y2="1420" stroke="{STROKE}" '
                  f'stroke-width="3" stroke-dasharray="10 12"/>')
    msgs = [(0, 1, 760, "提交需求"), (1, 2, 930, "校验参数"), (2, 1, 1100, "返回结果"), (1, 0, 1270, "给出方案")]
    for a, b, y, label in msgs:
        x1, x2 = xs[a], xs[b]
        d = f"M{x1} {y} H{x2}"
        inner += _edge(d)
        inner += (f'<text class="dl" x="{(x1 + x2) / 2}" y="{y - 18}" text-anchor="middle" font-size="28" '
                  f'fill="{MUTED}">{label}</text>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0,y:-18},{opacity:1,y:0,duration:.45,"
        "ease:'power2.out',stagger:.12},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},"
        "{drawSVG:'100%',duration:.5,ease:'power2.inOut',stagger:.2},0.8);"
        "timeline.fromTo('[data-anim=\"subject\"] .dl',{opacity:0},{opacity:1,duration:.3,stagger:.2},1.0);"
    )
    return _wrap(inner), js


def diagram_swimlane():
    lanes = [(560, 380, "获客"), (980, 380, "跟进")]
    inner = ""
    for y, h, label in lanes:
        inner += (f'<g class="dlane"><rect x="100" y="{y}" width="880" height="{h}" rx="24" '
                  f'fill="rgba(255,255,255,.03)" stroke="rgba(255,255,255,.12)" stroke-width="3"/>'
                  f'<rect x="100" y="{y}" width="180" height="{h}" rx="24" fill="rgba(134,240,192,.10)"/>'
                  f'<text x="190" y="{y + h / 2 + 12}" text-anchor="middle" font-size="32" '
                  f'font-weight="700" fill="{STROKE}">{label}</text></g>')
    steps = [(500, 700, "搜索"), (820, 700, "去重"), (500, 1120, "外呼"), (820, 1120, "记录")]
    for cx, cy, label in steps:
        inner += _node(cx, cy, 240, 140, label, r=16)
    inner += _edge("M620 700 H700")
    inner += _edge("M820 770 V915 H500 V1050")
    inner += _edge("M620 1120 H700")
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dlane',{opacity:0},{opacity:1,duration:.5,stagger:.15},0.25);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn rect',{opacity:0,scale:.9,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.45,ease:'back.out(1.4)',stagger:.14},0.6);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn text',{opacity:0},{opacity:1,duration:.3,stagger:.14},0.75);"
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},{drawSVG:'100%',duration:.4,stagger:.12},1.35);"
    )
    return _wrap(inner), js


def diagram_timeline():
    inner = (f'<path class="de" d="M140 980 H940" fill="none" stroke="{STROKE}" stroke-width="5" '
             f'marker-end="url(#arw)"/>')
    pts = [(230, "立项", 1), (450, "试点", -1), (670, "铺开", 1), (890, "复盘", -1)]
    for x, label, up in pts:
        inner += (f'<g class="dn"><circle cx="{x}" cy="980" r="20" fill="{FILL}" stroke="{STROKE}" stroke-width="4"/>'
                  f'<line x1="{x}" y1="980" x2="{x}" y2="{920 if up > 0 else 1040}" stroke="{STROKE}" '
                  f'stroke-width="3"/>'
                  f'<text x="{x}" y="{880 if up > 0 else 1090}" text-anchor="middle" font-size="34" '
                  f'font-weight="650" fill="{TEXT}">{label}</text></g>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},{drawSVG:'100%',duration:1.0,"
        "ease:'power2.inOut'},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0,y:14},{opacity:1,y:0,duration:.45,"
        "ease:'power2.out',stagger:.16},0.85);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn circle',{scale:0,transformOrigin:'50% 50%'},"
        "{scale:1,duration:.4,ease:'back.out(2)',stagger:.16},0.8);"
    )
    return _wrap(inner), js


def diagram_quadrant():
    inner = (
        f'<line class="de" x1="540" y1="560" x2="540" y2="1400" stroke="{STROKE}" stroke-width="4"/>'
        f'<line class="de" x1="140" y1="980" x2="940" y2="980" stroke="{STROKE}" stroke-width="4"/>'
        f'<text x="540" y="530" text-anchor="middle" font-size="28" fill="{MUTED}">高价值</text>'
        f'<text x="540" y="1440" text-anchor="middle" font-size="28" fill="{MUTED}">低价值</text>'
        f'<text x="120" y="985" text-anchor="start" font-size="28" fill="{MUTED}">难</text>'
        f'<text x="960" y="985" text-anchor="end" font-size="28" fill="{MUTED}">易</text>'
    )
    bubbles = [(390, 800, 86, "重点"), (700, 810, 74, "快赢"), (380, 1160, 70, "观察"), (710, 1150, 60, "放弃")]
    for cx, cy, r, label in bubbles:
        inner += (f'<g class="dn"><circle cx="{cx}" cy="{cy}" r="{r}" fill="{FILL}" stroke="{STROKE}" stroke-width="4"/>'
                  f'<text x="{cx}" y="{cy + 11}" text-anchor="middle" font-size="30" font-weight="650" '
                  f'fill="{TEXT}">{label}</text></g>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},{drawSVG:'100%',duration:.7,"
        "ease:'power2.inOut',stagger:.2},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0,scale:.4,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.55,ease:'back.out(1.6)',stagger:.14},0.9);"
    )
    return _wrap(inner), js


def diagram_sankey():
    cols = {
        0: [(620, 150), (860, 190)],
        1: [(700, 300)],
        2: [(640, 160), (860, 240)],
    }
    xs = {0: 200, 1: 540, 2: 880}
    inner = ""
    for c, blocks in cols.items():
        for y, h in blocks:
            inner += (f'<g class="dn"><rect x="{xs[c] - 55}" y="{y}" width="110" height="{h}" rx="14" '
                      f'fill="{FILL}" stroke="{STROKE}" stroke-width="4"/></g>')
    ribbons = [
        (256, 620, 150, 485, 700, 120),
        (256, 860, 190, 485, 860, 140),
        (596, 700, 150, 824, 640, 90),
        (596, 850, 150, 824, 860, 150),
    ]
    for x1, y1, h1, x2, y2, h2 in ribbons:
        d = (f"M{x1} {y1 + h1 * 0.3} C {(x1 + x2) / 2} {y1 + h1 * 0.3}, {(x1 + x2) / 2} {y2 + h2 * 0.3}, {x2} {y2 + h2 * 0.3} "
             f"L{x2} {y2 + h2 * 0.7} C {(x1 + x2) / 2} {y2 + h2 * 0.7}, {(x1 + x2) / 2} {y1 + h1 * 0.7}, {x1} {y1 + h1 * 0.7} Z")
        inner += f'<path class="dr" d="{d}" fill="{FILL}" stroke="none"/>'
    inner += (f'<text x="200" y="1120" text-anchor="middle" font-size="30" fill="{MUTED}">来源</text>'
              f'<text x="540" y="1120" text-anchor="middle" font-size="30" fill="{MUTED}">处置</text>'
              f'<text x="880" y="1120" text-anchor="middle" font-size="30" fill="{MUTED}">结果</text>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0,x:-20},{opacity:1,x:0,duration:.45,"
        "ease:'power2.out',stagger:.1},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .dr',{opacity:0,scaleY:.3,transformOrigin:'0% 50%'},"
        "{opacity:1,scaleY:1,duration:.6,ease:'power2.out',stagger:.14},0.75);"
    )
    return _wrap(inner), js


def diagram_tree():
    inner = _node(540, 600, 340, 130, "主问题", r=26)
    kids = [(250, "分支一"), (540, "分支二"), (830, "分支三")]
    for cx, label in kids:
        inner += _node(cx, 880, 250, 120, label, r=20)
        inner += _edge(f"M540 665 C 540 760, {cx} 780, {cx} 820")
        for dx, leaf in ((-115, "细项"), (115, "细项")):
            inner += _node(cx + dx, 1140, 200, 100, leaf, r=14, fill="rgba(255,255,255,.04)")
            inner += _edge(f"M{cx} 940 V1030 H{cx + dx} V1090")
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0,y:16},{opacity:1,y:0,duration:.4,"
        "ease:'power2.out',stagger:.07},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},{drawSVG:'100%',duration:.4,"
        "ease:'power2.inOut',stagger:.06},0.55);"
    )
    return _wrap(inner), js


def diagram_fishbone():
    inner = (f'<path class="de" d="M130 1080 H920" fill="none" stroke="{STROKE}" stroke-width="6" '
             f'marker-end="url(#arw)"/>'
             f'<g class="dn"><rect x="920" y="1010" width="130" height="140" rx="16" fill="{FILL}" '
             f'stroke="{STROKE}" stroke-width="4"/>'
             f'<text x="985" y="1090" text-anchor="middle" font-size="30" font-weight="650" fill="{TEXT}">问题</text></g>')
    bones = [(300, "人"), (480, "机"), (660, "料"), (840, "法")]
    for i, (x, label) in enumerate(bones):
        up = i % 2 == 0
        y2 = 880 if up else 1280
        inner += (f'<g class="dn"><path class="de" d="M{x} 1080 L{x - 60} {y2}" fill="none" '
                  f'stroke="{STROKE}" stroke-width="4"/>'
                  f'<text x="{x - 70}" y="{y2 - 16 if up else y2 + 44}" text-anchor="middle" font-size="32" '
                  f'font-weight="650" fill="{TEXT}">{label}</text>'
                  f'<text class="sub" x="{x - 30}" y="{(1080 + y2) / 2 + (14 if up else -8)}" '
                  f'text-anchor="start" font-size="24" fill="{MUTED}">{label}因一</text>'
                  f'<text class="sub" x="{x - 52}" y="{(1080 + y2) / 2 + (56 if up else 34)}" '
                  f'text-anchor="start" font-size="24" fill="{MUTED}">{label}因二</text></g>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},{drawSVG:'100%',duration:.6,"
        "ease:'power2.inOut',stagger:.18},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn text',{opacity:0},{opacity:1,duration:.35,stagger:.16},0.9);"
    )
    return _wrap(inner), js


DIAGRAMS = [
    ("MD01", "流程图·三段推进", diagram_flow,
     "把'先做什么、再做什么'摊开；节点 4–6 个", "节点超过 8 个就别用这张，改成分屏"),
    ("MD02", "时序图·三方往返", diagram_sequence,
     "客户、系统、后台之间来回；讲交互过程", "角色超过 4 条线会挤，改用泳道"),
    ("MD03", "泳道图·两条线并行", diagram_swimlane,
     "两个角色的动作并排推进；讲分工", "步骤超过 6 个会太密"),
    ("MD04", "时间轴·四个节点", diagram_timeline,
     "讲发展过程、版本迭代、里程碑", "节点超过 6 个就拆屏"),
    ("MD05", "四象限·两类分选", diagram_quadrant,
     "把事情按两个维度分开：价值/难度、紧急/重要", "四块之外不要再加标签"),
    ("MD06", "桑基流向·三段归集", diagram_sankey,
     "讲流量、线索、预算怎么被分流与归集", "每段超过 4 个块会看不清流向"),
    ("MD07", "树状图·一主三分支", diagram_tree,
     "把一个大问题拆成三条线；讲结构", "叶子超过三层就换脑图分屏"),
    ("MD08", "鱼骨图·四个方向找原因", diagram_fishbone,
     "讲'为什么出问题'，人机料法四路", "骨上不要再挂子骨，屏会糊"),
]

DIAGRAM_JS_TAIL = (
    "if(!window.DrawSVGPlugin){timeline.set('[data-anim=\"subject\"] .de',{opacity:1},0);}"
)


def diagram_cards():
    cards = []
    for cid, name, fn, use, avoid in DIAGRAMS:
        stage, js = fn()
        cards.append({
            "id": cid, "name": name, "family": "图示", "role": "component", "status": "ready",
            "cap": "component-html", "src": "mermaid:diagrams",
            "params": {"dur": 0.6, "stagger": 0.15},
            "use": use, "avoid": avoid,
            "code": '<div class="dsfig">%s</div>' % stage.replace('style="position:absolute;inset:0;width:1080px;height:1920px"', ''),
            "sample": {"stage": '<div data-anim="subject">%s</div>' % stage, "sel": SEL,
                       "plugins": ["DrawSVGPlugin"], "js": js + DIAGRAM_JS_TAIL},
        })
    return cards


# ---------------- 动效卡 ----------------

def motion_step_edges():
    inner = ""
    pts = [(540, 600, "接到线索"), (540, 860, "自动分级"), (540, 1120, "分配跟进"), (540, 1380, "回写记录")]
    for cx, cy, label in pts:
        inner += _node(cx, cy, 420, 150, label)
    for i in range(3):
        y1 = pts[i][1] + 75
        y2 = pts[i + 1][1] - 75
        inner += (f'<path class="e{i + 1}" data-step="{i + 1}" d="M540 {y1} V{y2}" fill="none" '
                  f'stroke="{STROKE}" stroke-width="5" marker-end="url(#arw)"/>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn rect',{opacity:0},{opacity:1,duration:.35,stagger:.1},0.25);"
        "timeline.fromTo('[data-anim=\"subject\"] .dn text',{opacity:0},{opacity:1,duration:.3,stagger:.1},0.35);"
        "for(var i=1;i<=3;i++){timeline.fromTo('[data-anim=\"subject\"] .e'+i+'',{drawSVG:'0%'},"
        "{drawSVG:'100%',duration:.42,ease:'power2.inOut'},0.6+(i-1)*0.28);}"
    )
    return _wrap(inner), js


def motion_dot_path():
    d = "M200 1420 C 200 900, 660 1180, 660 760 S 900 620, 900 900"
    inner = (f'<path class="de" d="{d}" fill="none" stroke="rgba(134,240,192,.25)" stroke-width="6"/>'
             f'<circle class="dot" cx="0" cy="0" r="26" fill="{STROKE}"/>'
             f'<g class="badge"><circle cx="0" cy="0" r="34" fill="#0a0b0b" stroke="{STROKE}" stroke-width="4"/>'
             f'<text x="0" y="11" text-anchor="middle" font-size="28" font-weight="700" fill="{TEXT}">1</text></g>')
    js = (
        "var _p=document.querySelector('[data-anim=\"subject\"] .de');"
        "timeline.fromTo('[data-anim=\"subject\"] .de',{drawSVG:'0%'},{drawSVG:'100%',duration:1.1,"
        "ease:'power1.inOut'},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .dot',{motionPath:{path:_p,align:_p,alignOrigin:[0.5,0.5],"
        "start:0,end:1},opacity:0},{opacity:1,duration:.2},0.55);"
        "timeline.to('[data-anim=\"subject\"] .dot',{motionPath:{path:_p,align:_p,alignOrigin:[0.5,0.5],"
        "start:0,end:1},duration:1.5,ease:'none'},0.55);"
        "timeline.fromTo('[data-anim=\"subject\"] .badge',{opacity:0,scale:0,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.3,ease:'back.out(2)'},0.95);"
    )
    return _wrap(inner), js


def motion_line_jump():
    inner = (
        f'<path class="a" d="M160 900 C 380 900, 420 860, 640 860 S 860 900, 920 900" fill="none" '
        f'stroke="{STROKE}" stroke-width="5"/>'
        f'<path class="b1" d="M540 620 V1060" fill="none" stroke="{STROKE}" stroke-width="5"/>'
        f'<path class="b2" d="M540 1140 V1560" fill="none" stroke="{STROKE}" stroke-width="5"/>'
        f'<path class="bridge" d="M470 860 C 490 800, 590 800, 610 860" fill="none" '
        f'stroke="{STROKE}" stroke-width="5" stroke-linecap="round"/>'
    )
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .a',{drawSVG:'0%'},{drawSVG:'100%',duration:.9,"
        "ease:'power2.inOut'},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .b1,[data-anim=\"subject\"] .b2',{drawSVG:'0%'},"
        "{drawSVG:'100%',duration:.7,ease:'power2.inOut',stagger:.15},0.45);"
        "timeline.fromTo('[data-anim=\"subject\"] .bridge',{drawSVG:'0%'},{drawSVG:'100%',duration:.4,"
        "ease:'power2.out'},1.15);"
    )
    return _wrap(inner), js


def motion_step_badge():
    inner = (_node(540, 620, 420, 150, "提交申请", r=18)
             + _node(540, 1000, 420, 150, "系统校验", r=18)
             + _node(540, 1380, 420, 150, "结果回传", r=18))
    inner += (f'<path class="e1" d="M540 695 V925" fill="none" stroke="{STROKE}" stroke-width="5" '
              f'marker-end="url(#arw)"/>')
    inner += (f'<path class="e2" d="M540 1075 V1305" fill="none" stroke="{STROKE}" stroke-width="5" '
              f'marker-end="url(#arw)"/>')
    inner += (f'<g class="bd1"><circle cx="540" cy="778" r="30" fill="#0a0b0b" stroke="{STROKE}" '
              f'stroke-width="4"/><text x="540" y="789" text-anchor="middle" font-size="26" '
              f'font-weight="700" fill="{TEXT}">1</text></g>')
    inner += (f'<g class="bd2"><circle cx="540" cy="1158" r="30" fill="#0a0b0b" stroke="{STROKE}" '
              f'stroke-width="4"/><text x="540" y="1169" text-anchor="middle" font-size="26" '
              f'font-weight="700" fill="{TEXT}">2</text></g>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0,scale:.92,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.45,ease:'power2.out',stagger:.14},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .e1',{drawSVG:'0%'},{drawSVG:'100%',duration:.5,"
        "ease:'power2.inOut'},0.7);"
        "timeline.fromTo('[data-anim=\"subject\"] .e2',{drawSVG:'0%'},{drawSVG:'100%',duration:.5,"
        "ease:'power2.inOut'},1.35);"
        "timeline.fromTo('[data-anim=\"subject\"] .bd1',{opacity:0,scale:0,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.3,ease:'back.out(2)'},1.0);"
        "timeline.fromTo('[data-anim=\"subject\"] .bd2',{opacity:0,scale:0,transformOrigin:'50% 50%'},"
        "{opacity:1,scale:1,duration:.3,ease:'back.out(2)'},1.35);"
    )
    return _wrap(inner), js


def motion_wrap_label():
    label = "线索自动分级之后，跟进提醒会直接落到负责人手上"
    lines = ["线索自动分级之后，", "跟进提醒会直接", "落到负责人手上"]
    inner = (f'<g class="dn"><rect x="140" y="820" width="800" height="300" rx="26" fill="{FILL}" '
             f'stroke="{STROKE}" stroke-width="4"/></g>')
    for i, line in enumerate(lines):
        inner += (f'<text class="ln" x="190" y="{900 + i * 76}" font-size="52" font-weight="700" '
                  f'fill="{TEXT}">{line}</text>')
    js = (
        "timeline.fromTo('[data-anim=\"subject\"] .dn',{opacity:0},{opacity:1,duration:.4},0.3);"
        "timeline.fromTo('[data-anim=\"subject\"] .ln',{opacity:0,y:18},{opacity:1,y:0,duration:.4,"
        "ease:'power2.out',stagger:.16},0.7);"
    )
    return _wrap(inner), js, label


MOTIONS = [
    ("MX01", "逐边推进·一条接一条", motion_step_edges, "component_motion",
     "流程图一步步走：每条边走完才走下一条", "边超过 5 条就太快，拆两屏"),
    ("MX02", "光点沿路径走", motion_dot_path, "component_motion",
     "沿一条线交代'经过哪几步'", "路径自己不要同时抖动，会晕"),
    ("MX03", "跨线跳桥", motion_line_jump, "component_motion",
     "两条线交叉时拱一下，说明'不相交、只是穿过'", "交叉点超过三个就别画桥"),
    ("MX04", "步骤徽章挂边", motion_step_badge, "component_motion",
     "在边上标 1、2，讲先后顺序", "边上文字已经很多时不要再挂徽章"),
]


def motion_cards():
    cards = []
    for cid, name, fn, role, use, avoid in MOTIONS:
        stage, js = fn()
        cards.append({
            "id": cid, "name": name, "family": "图示", "role": role, "status": "ready",
            "cap": "gsap-draw", "src": "mermaid:rendering-elements/edgeStepAnimation.ts",
            "params": {"dur": 0.45, "stagger": 0.18},
            "use": use, "avoid": avoid,
            "code": "timeline.fromTo('{{sel}} .de',{drawSVG:'0%'},{drawSVG:'100%',duration:{{dur}},"
                    "ease:'power2.inOut',stagger:{{stagger}}},{{at}});",
            "sample": {"stage": '<div data-anim="subject">%s</div>' % stage, "sel": SEL,
                       "plugins": ["DrawSVGPlugin", "MotionPathPlugin"], "js": js},
        })
    # 换行卡：只讲断行，不做图示
    stage, js, label = motion_wrap_label()
    cards.append({
        "id": "MT01", "name": "标签自动换行", "family": "图示", "role": "component", "status": "ready",
        "cap": "component-html", "src": "mermaid:rendering-util/splitText.ts",
        "params": {"w": 800, "size": 52},
        "use": "长标签按宽度断成 2–3 行，行高固定；讲一句话塞不进盒子时",
        "avoid": "已经是短标签还硬断行，读起来会顿",
        "code": '<div class="wraplabel" style="width:640px">%s</div>' % label,
        "sample": {"stage": '<div data-anim="subject">%s</div>' % stage, "sel": SEL, "js": js},
    })
    return cards


def main():
    cards = shape_cards() + diagram_cards() + motion_cards()
    out = HERE / "本批.json"
    out.write_text(json.dumps(cards, ensure_ascii=False, indent=1), encoding="utf-8")
    fam = {}
    for c in cards:
        fam[c["family"]] = fam.get(c["family"], 0) + 1
    print("写出 %s：%d 张" % (out, len(cards)))
    print("  形状 MG %d / 图示 MD %d / 动效 MX %d + 换行 MT 1" % (
        len(shape_cards()), len(DIAGRAMS), len(MOTIONS)))
    print("  族分布：%s" % fam)


if __name__ == "__main__":
    main()
