#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lottie-web 第二批：文本动画器 / 路径布尔 / 修饰器变体 / 变换与揭示。

输出追加进 样片/待筛/20261117-lottie/本批.json（第一批 8 张几何卡已由 lottie_port.py 写）。

搬的机制对应关系：
  K77 波峰扫字   ← Text Animator range selector（三角/高斯权重）
  K78 范围点亮   ← Animated property range + fill/stroke 权重
  K79 字距呼吸   ← Tracking（ts）随 selector 变化
  K80 逐字斜切   ← Skew（sk）随 selector 变化
  K81 透镜聚焦   ← 多 animator 叠加的不同权重
  T47 逐字旋入   ← 逐字 Rotation + Anchor 加权入场
  T48 逐字弹缩   ← 逐字 Scale 加权入场
  X63 双端描线   ← Trim Paths 的 s/e 两端同时推进
  X64 蚂蚁线     ← DashProperty（dash offset 流动）
  X65 渐变描边   ← GradientStroke 的 stop offset 动画
  X66 圆环挖洞   ← Mask mode = subtract / fill-rule evenodd
  X67 双圆融合   ← Merge Paths（布尔并集）
  X68 阵列多边形 ← Polystar 的 pt 模式 + Repeater 极坐标
  X69 星阵散布   ← 确定性格子散布（seeded，非随机）
  X70 边缘毛刺   ← ZigZag 高频小振幅（尖角模式）
  X71 拖尾点链   ← Repeater 的 so/eo（起止透明度渐变）
  X72 斜切挤压   ← Transform 的 skew + scale 压弹
  X73 纵深视差   ← 3D 图层的 z 分层
  X74 圆孔揭示   ← Mattele / 蒙版揭示（clip 圆孔）
  X75 斜切揭示   ← 蒙版路径扫过

用法：
    python3 能力库/动效库/oneshot/lottie_port2.py
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent
BATCH = "20261117-lottie"
OUT = LIB / "样片" / "待筛" / BATCH

TEXT = '<div data-anim="subject">线索自动分好，跟进自动记上</div>'
EMPTY = '<div data-anim="subject" style="position:absolute;inset:0"></div>'
CONTENT = ('<div data-anim="subject" style="position:absolute;left:100px;right:100px;top:600px;'
           'height:720px;border-radius:24px;background:linear-gradient(150deg,#245349,#10201c);'
           'border:1px solid rgba(134,240,192,.4);padding:56px;color:#dff8ee">'
           '<div style="font-size:44px;font-weight:700;margin-bottom:28px">本周线索</div>'
           '<div style="font-size:30px;line-height:1.9;opacity:.78">128 条新线索<br>'
           '42 条已跟进<br>19 条待回访</div></div>')
BLOCK = ('<div data-anim="subject" style="position:absolute;left:140px;top:740px;width:800px;'
         'height:540px;border-radius:28px;background:linear-gradient(140deg,#2f6b5c,#152a26);'
         'border:1px solid rgba(134,240,192,.45)"></div>')
STACK = ''.join(
    '<div style="height:74px;margin-bottom:26px;border-radius:14px;'
    'background:rgba(134,240,192,%.2f);border:1px solid rgba(134,240,192,.4)"></div>'
    % (0.08 + i * 0.05) for i in range(5))
LAYERS = '<div data-anim="subject" style="position:absolute;left:120px;right:120px;top:560px">%s</div>' % STACK
SVGPATH = ('<svg style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<path data-anim="subject" fill="none" stroke="#86F0C0" stroke-width="12" '
           'stroke-linecap="round" d="M140 1420 C 380 620, 700 1500, 940 780"/></svg>')
SVGCIRC = ('<svg style="position:absolute;inset:0;width:1080px;height:1920px">'
           '<circle data-anim="subject" cx="540" cy="960" r="300" fill="none" '
           'stroke="#86F0C0" stroke-width="12"/></svg>')

PRE = """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var NS = 'http://www.w3.org/2000/svg';
  var CX = 540, CY = 960;
  var _s = document.createElementNS(NS, 'svg');
  _s.setAttribute('class', 'kt-svg');
  _s.setAttribute('viewBox', '0 0 1080 1920');
  _s.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  _s.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;overflow:visible;'
    + 'pointer-events:none;z-index:{{z}}';
"""

POST = """})();"""

CARDS = []


def card(cid, name, role, cap, src, params, use, avoid, note, code,
         stage=None, text=None, sel=None):
    s = {}
    if stage:
        s["stage"] = stage
    if sel:
        s["sel"] = sel
    if text:
        s["text"] = text
    return {
        "id": cid, "name": name, "family": "结构" if cid.startswith("X") else
        ("字形" if cid.startswith("K") else "入场"),
        "role": role, "layer": "element", "status": "ready", "cap": cap, "src": src,
        "params": params, "use": use, "avoid": avoid, "note": note,
        "sample": s, "code": code,
    }


# ════════ 组 A：文本动画器（range selector 的权重型，不是 stagger） ════════

CARDS.append(card(
    "K77", "波峰扫字", "entrance_text", "geometry-t", "lottie-web:TextAnimator-RangeSelector",
    {"amp": 26, "pop": 0.10, "dur": 1.4, "z": 6},
    "一道波从字面扫过：每个字按它离波峰的距离抬升+放大，其余字回位",
    "字数少于 4 个时看不出波，改用 T01",
    "范围权重型：位置由「字在波上的相位」决定，不是按顺序延迟",
    PRE + """  var _c = kit.split('{{sel}}', 'chars');
  if (!_c.length) { return; }
  var _n = _c.length;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, ph, w;
    for (i = 0; i < _n; i++) {
      ph = (i / (_n - 1 || 1)) - (p * 1.6 - 0.34);
      w = Math.exp(-ph * ph * 24);
      _c[i].style.transform = 'translateY(' + (-{{amp}} * w).toFixed(1) + 'px) scale('
        + (1 + {{pop}} * w).toFixed(3) + ')';
      _c[i].style.opacity = (0.84 + 0.16 * w).toFixed(2);
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'none', onUpdate: _draw }, {{at}});
""" + POST, text=TEXT))

CARDS.append(card(
    "K78", "范围点亮", "entrance_text", "geometry-t", "lottie-web:TextAnimator-RangeSelector",
    {"win": 0.34, "pop": 0.16, "glow": 26, "color": "#86F0C0", "dur": 1.5, "z": 6},
    "一道光窗扫过文字：窗口内的字放大并从字面透光，窗外保持原样",
    "深色底才看得出光（浅底只剩放大）",
    "范围权重型：窗口宽度 win 是可调参数，两端用三角权重渐变",
    PRE + """  var _c = kit.split('{{sel}}', 'chars');
  if (!_c.length) { return; }
  var _n = _c.length;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, c, d, w;
    for (i = 0; i < _n; i++) {
      c = i / (_n - 1 || 1);
      d = (c - (p * (1 + {{win}}) - {{win}} / 2)) / ({{win}} / 2);
      w = Math.max(0, 1 - Math.abs(d));
      w = w * w * (3 - 2 * w);
      _c[i].style.transform = 'scale(' + (1 + {{pop}} * w).toFixed(3) + ')';
      _c[i].style.textShadow = w > 0.03
        ? '0 0 ' + ({{glow}} * w).toFixed(0) + 'px {{color}}' : 'none';
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'none', onUpdate: _draw }, {{at}});
""" + POST, text=TEXT))

CARDS.append(card(
    "K79", "字距呼吸", "entrance_text", "geometry-t", "lottie-web:TextAnimator-Tracking",
    {"track": 22, "win": 0.46, "dur": 1.6, "z": 6},
    "字与字之间被一道波推松再收拢，像一口气吸进去又吐出来",
    "已定宽的两端对齐版面（字距变化会推挤换行）",
    "范围权重型：改的是字距（tracking），不是位移，卡片结束字距归零",
    PRE + """  var _c = kit.split('{{sel}}', 'chars');
  if (!_c.length) { return; }
  var _n = _c.length;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, c, d, w;
    for (i = 0; i < _n; i++) {
      c = i / (_n - 1 || 1);
      d = (c - (p * (1 + {{win}}) - {{win}} / 2)) / ({{win}} / 2);
      w = Math.max(0, 1 - d * d);
      _c[i].style.marginRight = ({{track}} * w - {{track}} * 0.5 * w * w).toFixed(2) + 'px';
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'none', onUpdate: _draw }, {{at}});
""" + POST, text=TEXT))

CARDS.append(card(
    "K80", "逐字斜切", "entrance_text", "geometry-t", "lottie-web:TextAnimator-Skew",
    {"skew": 24, "win": 0.38, "dur": 1.3, "z": 6},
    "字被斜着推一下再立正：一道斜切波扫过整行，做“速度感”或“震撼”",
    "书法体、手写体（斜切会破坏笔画重心）",
    "范围权重型：改的是 skew 角度，字本身不移位",
    PRE + """  var _c = kit.split('{{sel}}', 'chars');
  if (!_c.length) { return; }
  var _n = _c.length;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, c, d, w;
    for (i = 0; i < _n; i++) {
      c = i / (_n - 1 || 1);
      d = (c - (p * (1 + {{win}}) - {{win}} / 2)) / ({{win}} / 2);
      w = Math.max(0, 1 - Math.abs(d));
      _c[i].style.transform = 'skewX(' + (-{{skew}} * w).toFixed(2) + 'deg)';
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'none', onUpdate: _draw }, {{at}});
""" + POST, text=TEXT))

CARDS.append(card(
    "K81", "透镜聚焦", "entrance_text", "geometry-t", "lottie-web:TextAnimator-MultiSelector",
    {"zoom": 1.16, "sigma": 1.9, "dur": 1.5, "z": 6},
    "一个放大镜从行首扫到行尾：经过的字被放大抬起，其余字被压小后退",
    "整行只剩 3 个字时（放大后撑出栏外）",
    "范围权重型：放大与缩小同时发生，中心字与两侧形成透镜",
    PRE + """  var _c = kit.split('{{sel}}', 'chars');
  if (!_c.length) { return; }
  var _n = _c.length;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, c, d, w;
    for (i = 0; i < _n; i++) {
      c = i / (_n - 1 || 1);
      d = (c - (p * 1.2 - 0.1)) * {{sigma}};
      w = 1 / (1 + d * d * 6);
      _c[i].style.transform = 'translateY(' + (-14 * w).toFixed(1) + 'px) scale('
        + (1 + ({{zoom}} - 1) * w).toFixed(3) + ')';
      _c[i].style.opacity = (0.62 + 0.38 * w).toFixed(2);
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'sine.inOut', onUpdate: _draw }, {{at}});
""" + POST, text='线索自动分好'))

CARDS.append(card(
    "T47", "逐字旋入", "entrance_text", "stagger", "lottie-web:TextAnimator-Rotation",
    {"rot": -22, "stagger": 0.055, "dur": 0.55, "ease": "back.out(1.6)", "z": 6},
    "每个字绕自己左下角转回正位再落定，标题、人名、关键词",
    "超过 14 个字（拖尾太长）",
    "逐字入场：锚点在字底，rotation 由负回零，和 T01 的纯位移不同",
    """var _c = kit.split('{{sel}}', 'chars');
if (!_c.length) { return; }
_c.forEach(function (el) { el.style.transformOrigin = '40% 100%'; });
timeline.fromTo(_c, { rotation: {{rot}}, opacity: 0, y: 14 },
  { rotation: 0, opacity: 1, y: 0, duration: {{dur}}, ease: '{{ease}}',
    stagger: {{stagger}} }, {{at}});
""", text=TEXT))

CARDS.append(card(
    "T48", "逐字弹缩", "entrance_text", "stagger", "lottie-web:TextAnimator-Scale",
    {"from": 0.2, "stagger": 0.05, "dur": 0.6, "ease": "back.out(2.2)", "z": 6},
    "字从很小弹到原大，每个错开一点，适合数字、口号",
    "正文段落（弹缩会让人读不下去）",
    "逐字入场：scale 从 from 弹到 1，锚点居中",
    """var _c = kit.split('{{sel}}', 'chars');
if (!_c.length) { return; }
_c.forEach(function (el) { el.style.transformOrigin = '50% 60%'; });
timeline.fromTo(_c, { scale: {{from}}, opacity: 0 },
  { scale: 1, opacity: 1, duration: {{dur}}, ease: '{{ease}}',
    stagger: {{stagger}} }, {{at}});
""", text=TEXT))

# ════════ 组 B：路径 / 布尔 / 描边 ════════

CARDS.append(card(
    "X63", "双端描线", "decoration", "geometry-t", "lottie-web:TrimPath",
    {"dur": 1.2, "ease": "power2.inOut", "z": 6},
    "一条线从中段同时向两头生长，或从两头向中间收拢",
    "闭合轮廓（首尾相接时长不满整圈）",
    "作用在已有 svg 路径上：可见段居中，dashoffset 负偏移实现两端同时推进",
    """(function () {
  var _ps = document.querySelectorAll('{{sel}}');
  if (!_ps.length) { return; }
  var _o = { p: 0 };
  function _draw() {
    var i, el, len, vis;
    for (i = 0; i < _ps.length; i++) {
      el = _ps[i];
      len = el.__ktLen || 0;
      if (!len) { try { len = el.getTotalLength(); } catch (e) { len = 0; } el.__ktLen = len; }
      if (!len) { continue; }
      vis = len * Math.max(0.001, _o.p);
      el.style.strokeDasharray = vis.toFixed(1) + ' ' + (len + 2).toFixed(1);
      el.style.strokeDashoffset = (-(len - vis) / 2).toFixed(1);
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
})();
""", stage=SVGPATH))

CARDS.append(card(
    "X64", "蚂蚁线", "decoration", "geometry-t", "lottie-web:DashProperty",
    {"dash": 40, "cycles": 3, "dur": 1.6, "z": 6},
    "虚线沿路径持续向前爬，做流转、进行中、传输中的状态",
    "需要静下来读的图（动线会分心）",
    "作用在已有 svg 路径上：dasharray 固定、dashoffset 匀速推，周期数有限不循环",
    """(function () {
  var _ps = document.querySelectorAll('{{sel}}');
  if (!_ps.length) { return; }
  var _d = {{dash}}, _i;
  Array.prototype.forEach.call(_ps, function (el, k) {
    el.style.strokeDasharray = _d + ' ' + _d;
    timeline.fromTo(el, { strokeDashoffset: 0 },
      { strokeDashoffset: -_d * 2 * {{cycles}}, duration: {{dur}}, ease: 'none' },
      {{at}} + k * 0.04);
  });
})();
""", stage=SVGPATH))

CARDS.append(card(
    "X65", "渐变描边", "decoration", "geometry-t", "lottie-web:GradientStroke",
    {"dur": 1.6, "band": 0.34, "color": "#86F0C0", "sw": 14, "z": 6},
    "一条光带沿着线条从头流到尾，线条本身是亮暗渐变",
    "线条短于 300px（光带看不出移动）",
    "自建 svg + linearGradient：动 stop 的 offset，不是动路径",
    PRE + """  var _n = document.querySelectorAll('svg.kt-svg').length;
  var _id = 'k65g' + _n;
  var _defs = document.createElementNS(NS, 'defs');
  var _lg = document.createElementNS(NS, 'linearGradient');
  _lg.setAttribute('id', _id);
  _lg.setAttribute('x1', '0'); _lg.setAttribute('y1', '1');
  _lg.setAttribute('x2', '1'); _lg.setAttribute('y2', '0');
  var _st = [], _ofs = [-0.4, -0.06, 0.28], _ops = [0, 1, 0];
  var _k;
  for (_k = 0; _k < 3; _k++) {
    var _sp = document.createElementNS(NS, 'stop');
    _sp.setAttribute('offset', _ofs[_k]);
    _sp.setAttribute('stop-color', '{{color}}');
    _sp.setAttribute('stop-opacity', _ops[_k]);
    _lg.appendChild(_sp);
    _st.push(_sp);
  }
  _defs.appendChild(_lg);
  _s.appendChild(_defs);
  var _pth = document.createElementNS(NS, 'path');
  _pth.setAttribute('d', 'M140 1420 C 380 620, 700 1500, 940 780');
  _pth.setAttribute('fill', 'none');
  _pth.setAttribute('stroke', 'url(#' + _id + ')');
  _pth.setAttribute('stroke-width', '{{sw}}');
  _pth.setAttribute('stroke-linecap', 'round');
  _s.appendChild(_pth);
  _t.appendChild(_s);
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, j;
    for (j = 0; j < 3; j++) {
      _st[j].setAttribute('offset', (_ofs[j] + p * 1.4).toFixed(3));
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'none', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

CARDS.append(card(
    "X66", "圆环挖洞", "decoration", "geometry-t", "lottie-web:MaskSubtract",
    {"or": 300, "iratio": 0.62, "sw": 0, "color": "#86F0C0",
     "fill": "rgba(134,240,192,.16)", "dur": 1.1, "ease": "power2.out", "z": 6},
    "实心圆中间开出一个洞并越开越大，做“进入下一层”、“镜头孔”",
    "要把文字压在洞中间（洞会吃掉字）",
    "fill-rule=evenodd 双圆一正一反，洞半径单独一个参数",
    PRE + """  var _R = {{or}}, _IR = {{iratio}};
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill-rule', 'evenodd');
  _p.setAttribute('fill', '{{fill}}');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _s.appendChild(_p);
  _t.appendChild(_s);
  function circle(cx, cy, r) {
    return 'M' + (cx - r).toFixed(1) + ' ' + cy.toFixed(1)
      + ' A' + r.toFixed(1) + ' ' + r.toFixed(1) + ' 0 1 0 ' + (cx + r).toFixed(1) + ' ' + cy.toFixed(1)
      + ' A' + r.toFixed(1) + ' ' + r.toFixed(1) + ' 0 1 0 ' + (cx - r).toFixed(1) + ' ' + cy.toFixed(1) + ' Z';
  }
  var _o = { p: 0 };
  function _draw() {
    var ir = _R * _IR * _o.p;
    _p.setAttribute('d', circle(CX, CY, _R) + (ir > 0.5 ? circle(CX, CY, ir) : ''));
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

CARDS.append(card(
    "X67", "双圆融合", "decoration", "geometry-t", "lottie-web:MergePaths",
    {"r": 175, "from": 520, "waist": 0.95, "fill": "rgba(134,240,192,.20)",
     "color": "#86F0C0", "sw": 0, "dur": 1.2, "ease": "power2.inOut", "z": 6},
    "两个圆相互靠近并融合成一个整体，做“合并”、“聚合”、“连接”",
    "三个以上要融合（这张只处理一对）",
    "并集的视觉等价：两圆之间补一条随距离变高的腰，取同一填充色",
    PRE + """  var _R = {{r}}, _D0 = {{from}}, _W = {{waist}};
  var _g = document.createElementNS(NS, 'g');
  _g.setAttribute('fill', '{{fill}}');
  _g.setAttribute('stroke', '{{color}}');
  _g.setAttribute('stroke-width', '{{sw}}');
  var _c1 = document.createElementNS(NS, 'circle');
  var _c2 = document.createElementNS(NS, 'circle');
  _c1.setAttribute('cy', CY); _c2.setAttribute('cy', CY);
  _c1.setAttribute('r', _R); _c2.setAttribute('r', _R);
  var _bar = document.createElementNS(NS, 'path');
  _g.appendChild(_bar); _g.appendChild(_c1); _g.appendChild(_c2);
  _s.appendChild(_g);
  _t.appendChild(_s);
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p;
    var d = _D0 - (_D0 - _R * 1.1) * p;
    var x1 = CX - d / 2, x2 = CX + d / 2;
    _c1.setAttribute('cx', x1.toFixed(1));
    _c2.setAttribute('cx', x2.toFixed(1));
    var gap = x2 - x1;
    var h = Math.max(0, (_R * 2 - gap) / 2) * _W;
    if (h < 0.6) { _bar.setAttribute('d', ''); return; }
    _bar.setAttribute('d', 'M' + x1.toFixed(1) + ' ' + (CY - h).toFixed(1)
      + ' L' + x2.toFixed(1) + ' ' + (CY - h).toFixed(1)
      + ' L' + x2.toFixed(1) + ' ' + (CY + h).toFixed(1)
      + ' L' + x1.toFixed(1) + ' ' + (CY + h).toFixed(1) + ' Z');
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

# ════════ 组 C：修饰器变体 ════════

CARDS.append(card(
    "X68", "阵列多边形", "decoration", "geometry-t", "lottie-web:PolystarShape+Repeater",
    {"copies": 10, "sides": 6, "radius": 300, "size": 62, "spin": 26,
     "sw": 5, "color": "#86F0C0", "fill": "rgba(134,240,192,.12)",
     "dur": 1.2, "ease": "power2.out", "z": 6},
    "一圈正多边形沿圆周排开并各自转动，做“系统图”、“节点阵”",
    "多边形数超过 16 个（互相压边）",
    "组合机制：polystar 的 pt 模式一个做形，repeater 的极坐标做阵",
    PRE + """  var _N = {{copies}}, _S = {{sides}}, _R = {{radius}}, _SZ = {{size}};
  var els = [], k;
  function poly(r) {
    var out = '', i, a, x, y;
    for (i = 0; i < _S; i++) {
      a = -Math.PI / 2 + i * Math.PI * 2 / _S;
      x = Math.cos(a) * r; y = Math.sin(a) * r;
      out += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    return out + ' Z';
  }
  for (k = 0; k < _N; k++) {
    var _pp = document.createElementNS(NS, 'path');
    _pp.setAttribute('d', poly(_SZ));
    _pp.setAttribute('fill', '{{fill}}');
    _pp.setAttribute('stroke', '{{color}}');
    _pp.setAttribute('stroke-width', '{{sw}}');
    _s.appendChild(_pp);
    els.push(_pp);
  }
  _t.appendChild(_s);
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, ang, kp, e;
    for (i = 0; i < _N; i++) {
      ang = -90 + i * 360 / _N + p * {{spin}};
      kp = Math.max(0, Math.min(1, (p * (_N + 2) - i) / 2));
      e = 1 - Math.pow(1 - kp, 3);
      els[i].setAttribute('transform',
        'translate(' + (CX + Math.cos(ang * Math.PI / 180) * _R).toFixed(1) + ' '
        + (CY + Math.sin(ang * Math.PI / 180) * _R).toFixed(1) + ') rotate('
        + (ang + 90).toFixed(1) + ') scale(' + e.toFixed(3) + ')');
      els[i].setAttribute('opacity', Math.min(1, kp * 1.5).toFixed(3));
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

CARDS.append(card(
    "X69", "星阵散布", "decoration", "geometry-t", "lottie-web:PolystarShape",
    {"iratio": 0.42, "count": 26, "size": 34, "spread": 0.82, "seed": 7,
     "color": "#86F0C0", "fill": "rgba(134,240,192,.18)",
     "dur": 1.0, "ease": "power2.out", "z": 6},
    "一片小星星按固定布局散开并逐个亮起，做“评分”、“精选”、“夜空”",
    "需要严格对齐的版式（散布是故意不齐的）",
    "确定性散布：用 kit.seeded 的 LCG，同参数每次位置完全一致，可 seek",
    PRE + """  var _N = {{count}}, _SZ = {{size}}, _SP = {{spread}};
  var _r = kit.seeded({{seed}});
  var els = [], k, a, rr;
  function star5(r) {
    var out = '', i, an, rad;
    for (i = 0; i < 10; i++) {
      an = -Math.PI / 2 + i * Math.PI / 5;
      rad = (i % 2 === 0) ? r : r * {{iratio}};
      out += (i ? 'L' : 'M') + (Math.cos(an) * rad).toFixed(1) + ' '
        + (Math.sin(an) * rad).toFixed(1);
    }
    return out + ' Z';
  }
  for (k = 0; k < _N; k++) {
    var _pp = document.createElementNS(NS, 'path');
    _pp.setAttribute('d', star5(_SZ * (0.55 + _r() * 0.9)));
    _pp.setAttribute('fill', '{{fill}}');
    _pp.setAttribute('stroke', '{{color}}');
    _pp.setAttribute('stroke-width', 3);
    var _px = CX + (_r() * 2 - 1) * 460 * _SP;
    var _py = CY + (_r() * 2 - 1) * 720 * _SP;
    _pp.setAttribute('data-x', _px.toFixed(1));
    _pp.setAttribute('data-y', _py.toFixed(1));
    _pp.setAttribute('data-rot', ((_r() * 2 - 1) * 40).toFixed(1));
    _s.appendChild(_pp);
    els.push(_pp);
  }
  _t.appendChild(_s);
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, kp, e;
    for (i = 0; i < _N; i++) {
      kp = Math.max(0, Math.min(1, (p * (_N + 4) - i) / 3));
      e = 1 - Math.pow(1 - kp, 2);
      els[i].setAttribute('transform',
        'translate(' + els[i].getAttribute('data-x') + ' ' + els[i].getAttribute('data-y')
        + ') rotate(' + els[i].getAttribute('data-rot') + ') scale(' + e.toFixed(3) + ')');
      els[i].setAttribute('opacity', Math.min(1, kp * 1.5).toFixed(3));
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

CARDS.append(card(
    "X70", "边缘毛刺", "decoration", "geometry-t", "lottie-web:ZigZagHighFreq",
    {"hops": 26, "amp": 12, "w": 840, "h": 840, "sw": 8,
     "color": "#86F0C0", "dur": 1.1, "ease": "power2.out", "z": 6},
    "方框边线长出高频小毛刺，像刚撕开的纸口，做“粗糙”、“原始”",
    "金融/医疗这类要干净的版面",
    "同 ZigZag 但走尖角高频档：hops 大、amp 小，不是波浪",
    PRE + """  var HOPS = {{hops}}, AMP = {{amp}}, W = {{w}}, H = {{h}};
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill', 'none');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'miter');
  _s.appendChild(_p);
  _t.appendChild(_s);
  var x0 = CX - W / 2, y0 = CY - H / 2, x1 = CX + W / 2, y1 = CY + H / 2;
  function edge(ax, ay, bx, by, nx, ny, amp, first) {
    var seg = '', i, t, mx, my, sg;
    for (i = 0; i < HOPS; i++) {
      if (i === 0 && first) { seg += 'M' + ax.toFixed(1) + ' ' + ay.toFixed(1); }
      t = (i + 0.5) / HOPS;
      mx = ax + (bx - ax) * t; my = ay + (by - ay) * t;
      sg = (i % 2 === 0) ? 1 : -1;
      seg += 'L' + (mx + nx * amp * sg).toFixed(1) + ' ' + (my + ny * amp * sg).toFixed(1);
    }
    return seg;
  }
  var _o = { p: 0 };
  function _draw() {
    var amp = AMP * _o.p, d = '';
    d += edge(x0, y0, x1, y0, 0, -1, amp, true);
    d += edge(x1, y0, x1, y1, 1, 0, amp, false);
    d += edge(x1, y1, x0, y1, 0, 1, amp, false);
    d += edge(x0, y1, x0, y0, -1, 0, amp, false);
    _p.setAttribute('d', d + ' Z');
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

CARDS.append(card(
    "X71", "拖尾点链", "decoration", "geometry-t", "lottie-web:Repeater-eo",
    {"copies": 9, "size": 32, "span": 560, "fade": 0.86, "sw": 0,
     "color": "#86F0C0", "fill": "#86F0C0", "dur": 1.0, "ease": "power3.out", "z": 6},
    "一串圆点从一点甩出并逐渐变小变淡，做“拖尾”、“速度线”、“数据流”",
    "要看清每个点的位置（拖尾本身就糊）",
    "Repeater 的 so/eo 段：透明度按副本序号指数衰减，不是统一淡出",
    PRE + """  var _N = {{copies}}, _SZ = {{size}}, _SP = {{span}}, _FD = {{fade}};
  var els = [], k, o = { p: 0 };
  for (k = 0; k < _N; k++) {
    var _c = document.createElementNS(NS, 'circle');
    _c.setAttribute('r', (_SZ * Math.pow(_FD, k)).toFixed(2));
    _c.setAttribute('fill', '{{fill}}');
    _c.setAttribute('stroke', '{{color}}');
    _c.setAttribute('stroke-width', '{{sw}}');
    _s.appendChild(_c);
    els.push(_c);
  }
  _t.appendChild(_s);
  function _draw() {
    var p = o.p, i, kp, e, x;
    for (i = 0; i < _N; i++) {
      kp = Math.max(0, Math.min(1, (p * (_N + 3) - i) / 2.2));
      e = 1 - Math.pow(1 - kp, 3);
      x = CX - _SP / 2 + (i / (_N - 1 || 1)) * _SP * e;
      els[i].setAttribute('cx', x.toFixed(1));
      els[i].setAttribute('cy', CY.toFixed(1));
      els[i].setAttribute('opacity', (Math.pow(_FD, i) * Math.min(1, kp * 1.6)).toFixed(3));
    }
  }
  _draw();
  timeline.to(o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST, stage=EMPTY))

# ════════ 组 D：变换与揭示 ════════

CARDS.append(card(
    "X72", "斜切挤压", "decoration", "geometry-t", "lottie-web:Transform-skew",
    {"skew": 20, "squash": 0.66, "dur": 1.15, "z": 6},
    "元素被斜着压扁再弹回原状，做“被推了一下”的受力反馈",
    "元素里正在读的小字（挤压会短暂变形）",
    "作用于宿主本身：transform-origin 落在底边，skew 与 scaleY 同时压",
    """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) { return; }
  _t.style.transformOrigin = '50% 100%';
  _t.style.zIndex = '{{z}}';
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, sk, sy, u, v, e;
    if (p < 0.3) {
      u = p / 0.3;
      sk = -{{skew}} * u * u;
      sy = 1 - (1 - {{squash}}) * u * u;
    } else {
      v = (p - 0.3) / 0.7;
      e = Math.exp(-4.2 * v) * Math.cos(v * 9.5);
      sk = -{{skew}} * e;
      sy = 1 - (1 - {{squash}}) * e;
    }
    _t.style.transform = 'skewX(' + sk.toFixed(2) + 'deg) scaleY(' + sy.toFixed(3) + ')';
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: 'none', onUpdate: _draw }, {{at}});
})();
""", stage=BLOCK))

CARDS.append(card(
    "X73", "纵深视差", "decoration", "geometry-t", "lottie-web:Layer3D",
    {"depth": 90, "shift": 190, "dur": 1.2, "ease": "power2.inOut", "z": 6},
    "把子元素按前后分层，逐层错开移动，做出纵深与视差",
    "只有一个子元素（分层不成立）",
    "给宿主 perspective，子元素按序号分配 z 深度，位移量按深度递增",
    """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) { return; }
  _t.style.perspective = '1600px';
  _t.style.zIndex = '{{z}}';
  var _k = [].slice.call(_t.children);
  if (!_k.length) { return; }
  var i, n = _k.length;
  for (i = 0; i < n; i++) {
    _k[i].style.transformStyle = 'preserve-3d';
    _k[i].style.transform = 'translateZ(' + (-{{depth}} * i).toFixed(1) + 'px)';
  }
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, j, k2;
    for (j = 0; j < n; j++) {
      k2 = 1 - j / (n - 1 || 1);
      _k[j].style.transform = 'translateZ(' + (-{{depth}} * j).toFixed(1)
        + 'px) translateX(' + ({{shift}} * (p - 0.5) * 2 * k2).toFixed(1) + 'px)';
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
})();
""", stage=LAYERS))

CARDS.append(card(
    "X74", "圆孔揭示", "decoration", "geometry-t", "lottie-web:MatteCircle",
    {"r": 92, "cx": 50, "cy": 50, "dur": 1.0, "ease": "power2.inOut", "z": 6},
    "从一个圆孔往外揭示画面内容，做“进入”、“聚焦到局部”",
    "内容边缘本来就是圆（揭示边界会重叠）",
    "作用于宿主本身：clip-path 圆半径逐帧重算，可 seek",
    """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) { return; }
  _t.style.zIndex = '{{z}}';
  var _o = { p: 0 };
  function _draw() {
    var r = _o.p * {{r}};
    _t.style.clipPath = 'circle(' + r.toFixed(2) + '% at {{cx}}% {{cy}}%)';
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
})();
""", stage=CONTENT))

CARDS.append(card(
    "X75", "斜切揭示", "decoration", "geometry-t", "lottie-web:MatteSlant",
    {"skew": 26, "dur": 1.0, "ease": "power2.inOut", "z": 6},
    "一条斜边扫过内容把它揭开，做“翻篇”、“换一屏”",
    "内容左右贯通必须完整（斜边会先吃掉一角）",
    "作用于宿主本身：clip-path 多边形，斜边角度由 skew 控制",
    """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) { return; }
  _t.style.zIndex = '{{z}}';
  var _k = {{skew}} / 100;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, x = p * (100 + _k * 100);
    _t.style.clipPath = 'polygon(0% 0%, ' + Math.min(100, x).toFixed(2) + '% 0%, '
      + Math.max(0, x - _k * 100).toFixed(2) + '% 100%, 0% 100%)';
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
})();
""", stage=CONTENT))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "本批.json"
    old = []
    if f.is_file():
        old = [c for c in json.loads(f.read_text(encoding="utf-8"))
               if c["id"] not in {c2["id"] for c2 in CARDS}]
    allc = old + CARDS
    f.write_text(json.dumps(allc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("本批.json 现共 %d 张（新增 %d）" % (len(allc), len(CARDS)))
    for c in CARDS:
        print("  %s %s  %s" % (c["id"], c["name"], c["src"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
