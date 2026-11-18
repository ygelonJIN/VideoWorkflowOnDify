#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lottie-web 形状修饰器 → 几何卡：候选批次 20261117-lottie。

只写 样片/待筛/20261117-lottie/本批.json，不碰 presets.json、不渲染。
渲染交给 render_candidates.sh；转正交给 add_card.py --batch。

搬的是机制不是代码：lottie 的 7 个 shape modifier 全部重写成
"svg 内按 onUpdate 每帧重算 d" 的形态，不引入 lottie 运行时。
坐标固定 1080×1920 并靠 viewBox 缩放，不测布局、不用随机数、不循环。

用法：
    python3 能力库/动效库/oneshot/lottie_port.py
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE.parent
BATCH = "20261117-lottie"
OUT = LIB / "样片" / "待筛" / BATCH

STAGE = '<div data-anim="subject" style="position:absolute;inset:0"></div>'

# 卡片共用的 svg 建板骨架（不测布局：viewBox 固定 1080×1920，靠 100% 填充宿主）
PRE = """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var NS = 'http://www.w3.org/2000/svg';
  var CX = 540, CY = 960;
  var _s = document.createElementNS(NS, 'svg');
  _s.setAttribute('viewBox', '0 0 1080 1920');
  _s.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  _s.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;overflow:visible;'
    + 'pointer-events:none;z-index:{{z}}';
"""

POST = """})();"""


def card(cid, name, cap, src, params, use, avoid, note, code):
    return {
        "id": cid, "name": name, "family": "结构", "role": "decoration",
        "layer": "element", "status": "ready", "cap": cap, "src": src,
        "params": params, "use": use, "avoid": avoid, "note": note,
        "sample": {"stage": STAGE, "sel": '[data-anim="subject"]'},
        "code": code,
    }


CARDS = []

# ── X55 星形生长：PolystarShape（docs/json/shapes/star.json 的 pt/or/os/ir/is/d）
CARDS.append(card(
    "X55", "星形生长", "geometry-t", "lottie-web:PolystarShape",
    {"pts": 5, "or": 300, "iratio": 0.42, "rot": -90, "spin": 0,
     "sw": 10, "color": "#86F0C0", "fill": "rgba(134,240,192,.10)",
     "z": 6, "dur": 1.1, "ease": "power2.out"},
    "把一块空处生成几何星形：从正圆收成 N 角星，角数/内外径/描边可调",
    "要塞很密的图标区域（星尖会互相压）",
    "几何生成卡：宿主内自建 svg，viewBox 固定 1080×1920，每帧按参数重算 d",
    PRE + """  var N = {{pts}}, RO = {{or}}, IR = {{iratio}};
  var ROT = {{rot}} * Math.PI / 180, SPIN = {{spin}} * Math.PI / 180;
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill', '{{fill}}');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'round');
  _s.appendChild(_p);
  _t.appendChild(_s);
  function dstar(ro, ri, sp) {
    var out = '', i, a, r, x, y;
    for (i = 0; i < N * 2; i++) {
      a = ROT + sp + i * Math.PI / N;
      r = (i % 2 === 0) ? ro : ri;
      x = CX + Math.cos(a) * r;
      y = CY + Math.sin(a) * r;
      out += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    return out + 'Z';
  }
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, ro = RO * (0.35 + 0.65 * p);
    _p.setAttribute('d', dstar(ro, ro * (1 - p * (1 - IR)), SPIN * p));
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X56 阵列累乘：RepeaterModifier（c/o/tr + so/eo 的变换累乘）
CARDS.append(card(
    "X56", "阵列累乘", "geometry-t", "lottie-web:RepeaterModifier",
    {"copies": 8, "size": 140, "gap": 0.95, "rotStep": -12, "scaleStep": 0.88,
     "opStep": 0.86, "sw": 8, "color": "#86F0C0",
     "fill": "rgba(134,240,192,.14)", "z": 6, "dur": 1.0, "ease": "power3.out"},
    "同一元素复制成一串：每个副本在前一个基础上位移+旋转+缩放，逐个甩出",
    "需要精确等距排布时（累乘会越走越密）",
    "几何生成卡：副本变换逐级累乘（Repeater 的 tr 累加），不是 stagger 补间",
    PRE + """  var N = {{copies}}, SZ = {{size}};
  var SS = {{scaleStep}}, RS = {{rotStep}}, OPS = {{opStep}}, GAP = {{gap}};
  var els = [], k;
  for (k = 0; k < N; k++) {
    var _r = document.createElementNS(NS, 'rect');
    _r.setAttribute('x', (-SZ / 2).toFixed(1));
    _r.setAttribute('y', (-SZ / 2).toFixed(1));
    _r.setAttribute('width', SZ);
    _r.setAttribute('height', SZ);
    _r.setAttribute('rx', (SZ * 0.12).toFixed(1));
    _r.setAttribute('fill', '{{fill}}');
    _r.setAttribute('stroke', '{{color}}');
    _r.setAttribute('stroke-width', '{{sw}}');
    _s.appendChild(_r);
    els.push(_r);
  }
  _t.appendChild(_s);
  var TOT = 0, _ss = 1, _j;
  for (_j = 0; _j < N - 1; _j++) { TOT += GAP * SZ * _ss; _ss *= SS; }
  var X0 = CX - TOT / 2;
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, x = 0, sc = 1, a = 0, i, kp, e;
    for (i = 0; i < N; i++) {
      kp = Math.max(0, Math.min(1, (p * (N + 2) - i) / 2));
      e = 1 - Math.pow(1 - kp, 2);
      els[i].setAttribute('transform',
        'translate(' + (X0 + x).toFixed(1) + ' ' + CY.toFixed(1) + ') rotate(' + a.toFixed(1)
        + ') scale(' + (sc * e).toFixed(3) + ')');
      els[i].setAttribute('opacity', (Math.pow(OPS, i) * Math.min(1, kp * 1.6)).toFixed(3));
      x += GAP * SZ * sc;
      sc *= SS;
      a += RS;
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X57 环形扇开：Repeater 的极坐标变体
CARDS.append(card(
    "X57", "环形扇开", "geometry-t", "lottie-web:RepeaterModifier",
    {"copies": 14, "radius": 330, "size": 62, "sw": 6, "color": "#86F0C0",
     "fill": "rgba(134,240,192,.16)", "z": 6, "dur": 1.2, "ease": "power2.out"},
    "沿圆周复制一圈元素并逐个亮起，做刻度盘、环阵、放射状结构",
    "元素要压文字的地方（环会围住正文）",
    "几何生成卡：极坐标复制，副本自转对齐半径方向",
    PRE + """  var N = {{copies}}, R = {{radius}}, SZ = {{size}};
  var els = [], k;
  for (k = 0; k < N; k++) {
    var _r = document.createElementNS(NS, 'rect');
    _r.setAttribute('x', (-SZ / 2).toFixed(1));
    _r.setAttribute('y', (-SZ / 2).toFixed(1));
    _r.setAttribute('width', SZ);
    _r.setAttribute('height', SZ * 2.6);
    _r.setAttribute('rx', (SZ * 0.3).toFixed(1));
    _r.setAttribute('fill', '{{fill}}');
    _r.setAttribute('stroke', '{{color}}');
    _r.setAttribute('stroke-width', '{{sw}}');
    _s.appendChild(_r);
    els.push(_r);
  }
  _t.appendChild(_s);
  var _o = { p: 0 };
  function _draw() {
    var p = _o.p, i, ang, kp, e;
    for (i = 0; i < N; i++) {
      ang = -90 + i * 360 / N;
      kp = Math.max(0, Math.min(1, (p * (N + 2) - i) / 2));
      e = 1 - Math.pow(1 - kp, 3);
      els[i].setAttribute('transform',
        'translate(' + (CX + Math.cos(ang * Math.PI / 180) * R).toFixed(1) + ' '
        + (CY + Math.sin(ang * Math.PI / 180) * R).toFixed(1) + ') rotate('
        + (ang + 90).toFixed(1) + ') scale(' + e.toFixed(3) + ')');
      els[i].setAttribute('opacity', Math.min(1, kp * 1.4).toFixed(3));
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X58 圆角变形：RoundCornersModifier（rd）
CARDS.append(card(
    "X58", "星角磨圆", "geometry-t", "lottie-web:RoundCornersModifier",
    {"pts": 8, "or": 330, "iratio": 0.52, "rd": 96, "sw": 10,
     "color": "#86F0C0", "fill": "rgba(134,240,192,.10)",
     "z": 6, "dur": 1.1, "ease": "power2.inOut"},
    "给尖角做真几何倒圆：多角星边角半径从 0 长到 rd，尖→圆润",
    "需要锐利锐角的时候（磨圆后就没有攻击性）",
    "几何生成卡：顶点处插二次贝塞尔，半径按相邻边长自动限幅",
    PRE + """  var N = {{pts}}, RO = {{or}}, IR = {{iratio}}, RD = {{rd}};
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill', '{{fill}}');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'round');
  _s.appendChild(_p);
  _t.appendChild(_s);
  var V = [], i, a, r;
  for (i = 0; i < N * 2; i++) {
    a = -Math.PI / 2 + i * Math.PI / N;
    r = (i % 2 === 0) ? RO : RO * IR;
    V.push([CX + Math.cos(a) * r, CY + Math.sin(a) * r]);
  }
  function roundAll(v, rr) {
    var n = v.length, out = '', j, c, pv, nx, d1, d2, ax, ay, bx, by, rd;
    for (j = 0; j < n; j++) {
      c = v[j]; pv = v[(j - 1 + n) % n]; nx = v[(j + 1) % n];
      d1 = Math.hypot(pv[0] - c[0], pv[1] - c[1]) || 1;
      d2 = Math.hypot(nx[0] - c[0], nx[1] - c[1]) || 1;
      rd = Math.min(rr, d1 * 0.45, d2 * 0.45);
      ax = c[0] + (pv[0] - c[0]) / d1 * rd;
      ay = c[1] + (pv[1] - c[1]) / d1 * rd;
      bx = c[0] + (nx[0] - c[0]) / d2 * rd;
      by = c[1] + (nx[1] - c[1]) / d2 * rd;
      out += (j ? 'L' : 'M') + ax.toFixed(1) + ' ' + ay.toFixed(1);
      out += ' Q' + c[0].toFixed(1) + ' ' + c[1].toFixed(1) + ' '
        + bx.toFixed(1) + ' ' + by.toFixed(1);
    }
    return out + ' Z';
  }
  var _o = { p: 0 };
  function _draw() {
    _p.setAttribute('d', roundAll(V, RD * _o.p));
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X59 边线锯齿：ZigZagModifier（s/r/pt）
CARDS.append(card(
    "X59", "边线锯齿", "geometry-t", "lottie-web:ZigZagModifier",
    {"hops": 9, "amp": 34, "w": 840, "h": 840, "smooth": 1, "sw": 9,
     "color": "#86F0C0", "z": 6, "dur": 1.0, "ease": "power2.out"},
    "方框边线长成锯齿/波浪：口径、毛边、信号感的结构框",
    "要干净直线的版式（锯齿会抢版面秩序）",
    "几何生成卡：每条边按 hops 等分，中点沿法线偏移 amp，smooth=1 走二次贝塞尔",
    PRE + """  var HOPS = {{hops}}, AMP = {{amp}}, W = {{w}}, H = {{h}}, SM = {{smooth}};
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill', 'none');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'round');
  _s.appendChild(_p);
  _t.appendChild(_s);
  var x0 = CX - W / 2, y0 = CY - H / 2, x1 = CX + W / 2, y1 = CY + H / 2;
  function edge(ax, ay, bx, by, nx, ny, amp) {
    var seg = '', i, t, mx, my, px, py, sg, ex, ey;
    for (i = 0; i < HOPS; i++) {
      if (i === 0) { seg += 'M' + ax.toFixed(1) + ' ' + ay.toFixed(1); }
      t = (i + 0.5) / HOPS;
      mx = ax + (bx - ax) * t; my = ay + (by - ay) * t;
      sg = (i % 2 === 0) ? 1 : -1;
      px = mx + nx * amp * sg; py = my + ny * amp * sg;
      ex = ax + (bx - ax) * (i + 1) / HOPS; ey = ay + (by - ay) * (i + 1) / HOPS;
      if (SM) { seg += 'Q' + px.toFixed(1) + ' ' + py.toFixed(1) + ' ' + ex.toFixed(1) + ' ' + ey.toFixed(1); }
      else { seg += 'L' + px.toFixed(1) + ' ' + py.toFixed(1); }
    }
    return seg;
  }
  var _o = { p: 0 };
  function _draw() {
    var amp = AMP * _o.p, d = '';
    d += edge(x0, y0, x1, y0, 0, -1, amp);
    d += edge(x1, y0, x1, y1, 1, 0, amp);
    d += edge(x1, y1, x0, y1, 0, 1, amp);
    d += edge(x0, y1, x0, y0, -1, 0, amp);
    _p.setAttribute('d', d + ' Z');
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X60 内凹外扩：PuckerAndBloatModifier（a）
CARDS.append(card(
    "X60", "内凹外扩", "geometry-t", "lottie-web:PuckerAndBloatModifier",
    {"pts": 6, "or": 340, "amt": 0.55, "sw": 10, "color": "#86F0C0",
     "fill": "rgba(134,240,192,.10)", "z": 6, "dur": 1.0, "ease": "power2.inOut"},
    "同一条轮廓在「圆胖」和「内凹成星」之间连续变形，一个参数控方向",
    "amt 接近 1 时轮廓会自交（视觉打结）",
    "几何生成卡：边中点沿外法线偏移，amt>0 内凹成星、amt<0 外扩",
    PRE + """  var N = {{pts}}, RO = {{or}}, AMT = {{amt}};
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill', '{{fill}}');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'round');
  _s.appendChild(_p);
  _t.appendChild(_s);
  var V = [], i, a;
  for (i = 0; i < N; i++) {
    a = -Math.PI / 2 + i * Math.PI * 2 / N;
    V.push([CX + Math.cos(a) * RO, CY + Math.sin(a) * RO]);
  }
  var EDGE = 2 * RO * Math.sin(Math.PI / N);
  function shape(amt) {
    var out = 'M' + V[0][0].toFixed(1) + ' ' + V[0][1].toFixed(1), j, c, n2, mx, my, dx, dy, len;
    for (j = 0; j < N; j++) {
      c = V[j]; n2 = V[(j + 1) % N];
      mx = (c[0] + n2[0]) / 2; my = (c[1] + n2[1]) / 2;
      dx = mx - CX; dy = my - CY;
      len = Math.hypot(dx, dy) || 1;
      out += ' Q' + (mx + dx / len * amt * EDGE * 0.5).toFixed(1) + ' '
        + (my + dy / len * amt * EDGE * 0.5).toFixed(1) + ' '
        + n2[0].toFixed(1) + ' ' + n2[1].toFixed(1);
    }
    return out + ' Z';
  }
  var _o = { p: 0 };
  function _draw() {
    _p.setAttribute('d', shape(-AMT * _o.p));
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X61 多环描边：OffsetPathModifier（amount）
CARDS.append(card(
    "X61", "等距多环", "geometry-t", "lottie-web:OffsetPathModifier",
    {"pts": 6, "or": 250, "rings": 4, "gap": 52, "sw": 7,
     "color": "#86F0C0", "z": 6, "dur": 1.2, "ease": "power2.out"},
    "一个轮廓按固定间距外推出多层同心环，由内到外逐层浮现",
    "ring 数超过 6 时外环会顶出安全区",
    "几何生成卡：正多边形等距偏移 = 半径加 gap/cos(π/N)，不是缩放复制",
    PRE + """  var N = {{pts}}, RO = {{or}}, RG = {{rings}}, GAP = {{gap}};
  var els = [], k;
  for (k = 0; k < RG; k++) {
    var _r = document.createElementNS(NS, 'path');
    _r.setAttribute('fill', 'none');
    _r.setAttribute('stroke', '{{color}}');
    _r.setAttribute('stroke-width', '{{sw}}');
    _r.setAttribute('stroke-linejoin', 'round');
    _r.setAttribute('opacity', (1 - k * 0.16).toFixed(2));
    _s.appendChild(_r);
    els.push(_r);
  }
  _t.appendChild(_s);
  var COS = Math.cos(Math.PI / N);
  function ring(rr) {
    var out = '', i, a, x, y;
    for (i = 0; i < N; i++) {
      a = -Math.PI / 2 + i * Math.PI * 2 / N;
      x = CX + Math.cos(a) * rr;
      y = CY + Math.sin(a) * rr;
      out += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    return out + ' Z';
  }
  var _o = { p: 0 };
  function _draw() {
    var i, kp;
    for (i = 0; i < RG; i++) {
      kp = Math.max(0, Math.min(1, (_o.p * (RG + 1) - i)));
      els[i].setAttribute('d', ring(RO + i * GAP / COS));
      els[i].setAttribute('opacity', ((1 - i * 0.16) * kp).toFixed(3));
    }
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))

# ── X62 形状形变：ShapeProperty.interpolateShape 的重采样插值
CARDS.append(card(
    "X62", "形状互变", "geometry-t", "lottie-web:ShapeProperty",
    {"N": 96, "from": "circle", "to": "star", "size": 330, "inner": 0.38,
     "sw": 9, "color": "#86F0C0", "fill": "rgba(134,240,192,.10)",
     "z": 6, "dur": 1.3, "ease": "power2.inOut"},
    "两个轮廓互变：圆/方/三角/星之间按弧长等分重采样后逐点插值，尖角保留",
    "from 与 to 尖角数差太多时会有一点「揉」的过程（那是形变本身，不是坏帧）",
    "几何生成卡：顶点→等弧长重采样 N 点→顶点朝上对齐→线a插值，不靠极坐标半径函数",
    PRE + """  var N = {{N}}, SZ = {{size}}, INNER = {{inner}};
  var FA = '{{from}}', FB = '{{to}}';
  var _p = document.createElementNS(NS, 'path');
  _p.setAttribute('fill', '{{fill}}');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'round');
  _s.appendChild(_p);
  _t.appendChild(_s);
  function verts(kind) {
    var v = [], i, a, r;
    if (kind === 'square') { return [[-0.86, -0.86], [0.86, -0.86], [0.86, 0.86], [-0.86, 0.86]]; }
    if (kind === 'triangle') {
      for (i = 0; i < 3; i++) { a = -Math.PI / 2 + i * Math.PI * 2 / 3; v.push([Math.cos(a), Math.sin(a)]); }
      return v;
    }
    if (kind === 'star') {
      for (i = 0; i < 10; i++) {
        a = -Math.PI / 2 + i * Math.PI / 5;
        r = (i % 2 === 0) ? 1 : INNER;
        v.push([Math.cos(a) * r, Math.sin(a) * r]);
      }
      return v;
    }
    for (i = 0; i < 48; i++) { a = -Math.PI / 2 + i * Math.PI * 2 / 48; v.push([Math.cos(a), Math.sin(a)]); }
    return v;
  }
  function resample(v, n) {
    var segs = [], i, a, b, d, len = 0;
    for (i = 0; i < v.length; i++) {
      a = v[i]; b = v[(i + 1) % v.length];
      d = Math.hypot(b[0] - a[0], b[1] - a[1]);
      if (d < 1e-9) { continue; }
      segs.push({ a: a, b: b, d: d });
      len += d;
    }
    var step = len / n, out = [], j = 0, acc = 0, s0 = segs[0], k, t, tg;
    for (k = 0; k < n; k++) {
      tg = k * step;
      while (acc + s0.d < tg && j < segs.length - 1) { acc += s0.d; j += 1; s0 = segs[j]; }
      t = (tg - acc) / s0.d;
      out.push([s0.a[0] + (s0.b[0] - s0.a[0]) * t, s0.a[1] + (s0.b[1] - s0.a[1]) * t]);
    }
    return out;
  }
  function alignTop(pts) {
    var mi = 0, i;
    for (i = 1; i < pts.length; i++) { if (pts[i][1] < pts[mi][1]) { mi = i; } }
    return pts.slice(mi).concat(pts.slice(0, mi));
  }
  var PA = alignTop(resample(verts(FA), N));
  var PB = alignTop(resample(verts(FB), N));
  function shape(p) {
    var out = '', i, x, y;
    for (i = 0; i < N; i++) {
      x = CX + (PA[i][0] + (PB[i][0] - PA[i][0]) * p) * SZ;
      y = CY + (PA[i][1] + (PB[i][1] - PA[i][1]) * p) * SZ;
      out += (i ? 'L' : 'M') + x.toFixed(1) + ' ' + y.toFixed(1);
    }
    return out + ' Z';
  }
  var _o = { p: 0 };
  function _draw() {
    _p.setAttribute('d', shape(_o.p));
  }
  _draw();
  timeline.to(_o, { p: 1, duration: {{dur}}, ease: '{{ease}}', onUpdate: _draw }, {{at}});
""" + POST))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / "本批.json"
    f.write_text(json.dumps(CARDS, ensure_ascii=False, indent=1), encoding="utf-8")
    print("写出 %s（%d 张）" % (f.relative_to(LIB.parent.parent), len(CARDS)))
    for c in CARDS:
        print("  %s %s  %s" % (c["id"], c["name"], c["src"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
