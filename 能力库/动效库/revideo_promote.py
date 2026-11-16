#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 revideo 候选里选中的那批写成正式能力卡（presets.json + 能力卡.md + 同步链）。

用法：
    python3 能力库/动效库/revideo_promote.py --dry-run    # 只打印要写什么
    python3 能力库/动效库/revideo_promote.py             # 真写

做四件事：
1. presets.json 追加卡（已存在的编号跳过，可重复跑）
2. 能力卡.md 追加「2026-11-15 revideo 搬运批」一节（按族分表）
3. 候选样片从 待筛/revideo 移到 全卡审阅/<族>/<正式编号>-<名字>.mp4
4. 跑同步链：sync_expander.py → --check

编号分配见下表；`src` 记 `revideo:<源文件>`，可回溯。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
PRESETS = HERE / "presets.json"
CARDS_MD = HERE / "能力卡.md"
REELS = HERE / "样片" / "全卡审阅"
BATCH = HERE / "样片" / "待筛" / "revideo"

# ---------------------------------------------------------------- 共用片段

SPRING = """  function _tbl(m, k, d, v0, tEnd, N) {
    var h = 1 / 600, x = 0, v = v0 || 0, t = 0, out = [0], step = tEnd / (N - 1), next = step;
    while (t < tEnd + h) {
      var a = (-k * (x - 1) - d * v) / m;
      v += a * h; x += v * h; t += h;
      while (t >= next && out.length < N) { out.push(x); next += step; }
    }
    while (out.length < N) out.push(1);
    return out;
  }
  var _tb = _tbl({{mass}}, {{stiffness}}, {{damping}}, 0, {{settle}}, 300);
  function _sp(p) {
    var i = Math.round(Math.max(0, Math.min(1, p)) * (_tb.length - 1));
    return _tb[i];
  }
"""

SVG_PRE = """  var _ns = 'http://www.w3.org/2000/svg';
  function _mk(n) { return document.createElementNS(_ns, n); }
  if (getComputedStyle(_t).position === 'static') _t.style.position = 'relative';
  var _r = _t.getBoundingClientRect();
  var _w = Math.round(_r.width) || 420, _h = Math.round(_r.height) || 420;
  var _s = _mk('svg');
  _s.setAttribute('viewBox', '0 0 ' + _w + ' ' + _h);
  _s.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;overflow:visible;pointer-events:none;';
  _t.appendChild(_s);
"""

C = []          # 卡表
def card(cid, name, family, layer, cap, src, params, use, avoid, code, needs=None):
    C.append(dict(id=cid, name=name, family=family, layer=layer, status="ready", cap=cap,
                  src=src, params=params, use=use, avoid=avoid, code=code,
                  needs=needs or ["text"]))

# ================================================================ 入场（4）

card("T23", "整块滑入", "入场", "element",
     "整块从偏移位置滑到落点，同时淡入",
     "revideo:examples/quickstart",
     {"dx": -260, "dy": -300, "dur": 1.2, "ease": "power3.out"},
     "图标、按钮、单块卡片从画面外滑进来",
     "长段落（整块滑会糊）；已有 C01 缓推同屏",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  timeline.fromTo(_t, {'x': {{dx}}, 'y': {{dy}}, 'opacity': 0},
    {'x': 0, 'y': 0, 'opacity': 1, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""")

card("T24", "弹簧落位", "入场", "element",
     "弹簧显式积分（Plop 预置）：位移+缩放同一条曲线，落定前只回弹一次",
     "revideo:core/tweening/spring.ts#PlopSpring",
     {"from": 150, "scale0": 0.88, "mass": 0.2, "stiffness": 20, "damping": 0.68,
      "settle": 1.5, "dur": 1.5},
     "卡片、面板、价格牌落位；比 power 系更有重量",
     "整段文字（缩放会晃字）；同屏已用 T13 弹跳",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SPRING + """  timeline.fromTo(_t, {'y': {{from}}, 'scale': {{scale0}}, 'opacity': 0, 'transformOrigin': '50% 60%'},
    {'y': 0, 'scale': 1, 'opacity': 1, 'duration': {{dur}}, 'ease': _sp}, {{at}});
})();""")

card("T25", "摇摆归位", "入场", "element",
     "同一套弹簧驱动角度（Swing 预置）：角度来回摆几次后归零",
     "revideo:core/tweening/spring.ts#SwingSpring",
     {"rot": -22, "scale0": 0.82, "mass": 0.39, "stiffness": 19.85, "damping": 2.82,
      "settle": 1.7, "dur": 1.7},
     "角标、印章、小图标、贴纸类小元素归位",
     "大块面板（摆起来像没放稳）；已经用了 T03 折页",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SPRING + """  timeline.fromTo(_t, {'rotation': {{rot}}, 'scale': {{scale0}}, 'opacity': 0, 'transformOrigin': '50% 50%'},
    {'rotation': 0, 'scale': 1, 'opacity': 1, 'duration': {{dur}}, 'ease': _sp}, {{at}});
})();""")

card("T26", "公式落位", "入场", "element",
     "整体从略小缩到原尺寸并淡入，公式/单行结论专用",
     "revideo:examples/tex",
     {"scale0": 0.92, "dur": 1.0, "ease": "power2.out"},
     "公式、单行结论、编号大字",
     "多行段落（整块缩放会让行距跳）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  timeline.fromTo(_t, {'scale': {{scale0}}, 'opacity': 0, 'transformOrigin': '50% 50%'},
    {'scale': 1, 'opacity': 1, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""")

# ================================================================ 结构（2）

card("X39", "推挤换屏", "结构", "camera",
     "出屏层整块移出、入屏层同时从对侧压进来，边是硬的",
     "revideo:core/transitions/slideTransition.ts",
     {"dx": -1080, "dy": 0, "dur": 0.72, "ease": "power3.inOut"},
     "两屏之间的硬切；场景里要同时有入屏层与出屏层",
     "只有一层可动时（那就退化成位移）；与 GT 转场同屏",
     """(function () {
  var _in = document.querySelector('{{sel}}');
  var _out = document.querySelector('{{sel2}}');
  if (!_in) return;
  timeline.fromTo(_in, {'x': {{dx}}, 'y': {{dy}}},
    {'x': 0, 'y': 0, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
  if (_out) {
    timeline.to(_out, {'x': -({{dx}}), 'y': -({{dy}}), 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
  }
})();""", needs=["ui"])

card("X40", "拉远离场", "结构", "camera",
     "入屏层从过近倍率拉回 1 倍，出屏层同时缩进中心并消失",
     "revideo:core/transitions/zoomOutTransition.ts",
     {"scale0": 1.62, "scaleOut": 0.66, "dur": 1.0, "ease": "power2.out"},
     "从细节拉到全景；场景里要同时有入屏层与出屏层",
     "与 C02 缓拉同屏（同一个动作做两遍）",
     """(function () {
  var _in = document.querySelector('{{sel}}');
  var _out = document.querySelector('{{sel2}}');
  if (!_in) return;
  timeline.fromTo(_in, {'scale': {{scale0}}, 'opacity': 0, 'transformOrigin': '50% 46%'},
    {'scale': 1, 'opacity': 1, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
  if (_out) {
    timeline.to(_out, {'scale': {{scaleOut}}, 'opacity': 0, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
  }
})();""", needs=["ui"])

# ================================================================ 照片（2）

card("W25", "图片缩放落定", "照片", "media",
     "图片从略放大收到原尺寸，同时长圆角",
     "revideo:2d/components/Img.ts",
     {"scale0": 1.18, "radius": 28, "dur": 1.4, "ease": "power2.out"},
     "照片刚出现、要「稳住」时；比直接淡入有落定感",
     "已用 W01 包裹（圆角会打架）；满幅照片",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  timeline.fromTo(_t, {'scale': {{scale0}}, 'borderRadius': '0px'},
    {'scale': 1, 'borderRadius': '{{radius}}px', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["img"])

card("W26", "文字镂空照片", "照片", "media",
     "把照片当字色（background-clip:text），字是取景框；照片在字里横移、字不动",
     "revideo:docs/filters-and-effects#masking",
     {"src": "", "bgw": "1200px auto", "pan0": "-260px", "pan1": "340px",
      "dur": 1.9, "ease": "power1.inOut"},
     "大字标题 + 一张真实照片；要「照片长在字里」的封面感",
     "小字号（镂空后看不清字）；同屏再放一张照片",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _src = '{{src}}';
  if (!_src) {
    var _cand = [document.querySelector('{{sel2}}'), document.querySelector('[data-photo]'),
                 document.querySelector('img')];
    for (var _i = 0; _i < _cand.length && !_src; _i++) {
      var _p = _cand[_i];
      if (!_p) continue;
      if (_p.tagName === 'IMG') { _src = _p.getAttribute('src'); continue; }
      var _bg = getComputedStyle(_p).backgroundImage || '';
      var _m = _bg.match(/url\\(["']?(.*?)["']?\\)/);
      if (_m) { _src = _m[1]; }
    }
  }
  if (!_src) return;
  _t.style.backgroundImage = 'url("' + _src + '")';
  _t.style.backgroundSize = '{{bgw}}';
  _t.style.webkitBackgroundClip = 'text';
  _t.style.backgroundClip = 'text';
  _t.style.color = 'transparent';
  timeline.fromTo(_t, {'backgroundPosition': '{{pan0}} 46%'},
    {'backgroundPosition': '{{pan1}} 46%', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["text"])

# ================================================================ 字形（1）

card("K25", "字距收紧", "字形", "element",
     "整段字距从松收到紧，行宽同时变窄",
     "revideo:examples/positioning",
     {"loose": "0.18em", "tight": "-0.03em", "dur": 1.7, "ease": "power2.inOut"},
     "大标题、一句话落版；比 T01 逐字更安静",
     "小字号（收不收看不出）；已经用 K04 收紧过的同一句",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  timeline.fromTo(_t, {'letterSpacing': '{{loose}}'},
    {'letterSpacing': '{{tight}}', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""")

# ================================================================ 状态（1）

card("S23", "节点综合变换", "状态", "element",
     "opacity + scale + rotation 三合一入场，一个元素一次到位",
     "revideo:2d/components/Node.ts",
     {"scale0": 0.6, "rot": 12, "dur": 1.3, "ease": "power3.out"},
     "徽标、图标、小块卡片入场；参数只有一个缩放起点要调",
     "整段文字；同屏已用 T23 弹簧",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  timeline.fromTo(_t, {'opacity': 0, 'scale': {{scale0}}, 'rotation': {{rot}}, 'transformOrigin': '50% 50%'},
    {'opacity': 1, 'scale': 1, 'rotation': 0, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""")

# ================================================================ 绘制（9）

card("U39", "圆形生长", "绘制", "element",
     "注入一个圆，半径从 0 长到目标，描边同时收细",
     "revideo:2d/components/Circle.ts",
     {"pct": 80, "sw": 10, "swEnd": 2, "color": "#86F0C0", "dur": 1.4, "ease": "power3.out"},
     "圈出重点、做「聚焦」的外框；目标元素是空容器时",
     "目标里已经有图形（会叠）；文字节点上（会盖住字）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SVG_PRE + """  var _c = _mk('circle');
  _c.setAttribute('cx', _w / 2);
  _c.setAttribute('cy', _h / 2);
  _c.setAttribute('r', 0);
  _c.setAttribute('fill', 'none');
  _c.setAttribute('stroke', '{{color}}');
  _c.setAttribute('stroke-width', '{{sw}}');
  _s.appendChild(_c);
  var _rad = Math.min(_w, _h) * {{pct}} / 100;
  timeline.to(_c, {'attr': {'r': _rad}, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
  timeline.to(_c, {'attr': {'stroke-width': {{swEnd}}}, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("U40", "矩形生长", "绘制", "element",
     "注入一个矩形，宽高与圆角同时长出来（从中心外扩）",
     "revideo:2d/components/Rect.ts",
     {"pct": 88, "radius": 40, "sw": 4, "color": "#86F0C0", "dur": 1.3, "ease": "power3.out"},
     "给一块内容加框、做「卡片轮廓」先立起来",
     "目标本身是卡片组件（边框重复）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SVG_PRE + """  var _r2 = _mk('rect');
  _r2.setAttribute('x', _w / 2);
  _r2.setAttribute('y', _h / 2);
  _r2.setAttribute('width', 0);
  _r2.setAttribute('height', 0);
  _r2.setAttribute('rx', 0);
  _r2.setAttribute('fill', 'none');
  _r2.setAttribute('stroke', '{{color}}');
  _r2.setAttribute('stroke-width', '{{sw}}');
  _s.appendChild(_r2);
  var _bw = _w * {{pct}} / 100, _bh = _h * {{pct}} / 100;
  timeline.to(_r2, {'attr': {'x': (_w - _bw) / 2, 'y': (_h - _bh) / 2, 'width': _bw, 'height': _bh,
    'rx': {{radius}}, 'stroke-width': {{sw}}}, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("U41", "直线生长", "绘制", "element",
     "一条线从起点画到终点，角度与长度可调",
     "revideo:2d/components/Line.ts",
     {"angle": 52, "len": 92, "sw": 5, "color": "#86F0C0", "dur": 1.2, "ease": "power2.inOut"},
     "趋势线、连接线、指示线；目标元素是空容器",
     "已经有 SVG 路径时（用 U31 描边更准）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SVG_PRE + """  var _ln = _mk('line');
  var _cx = _w / 2, _cy = _h / 2;
  var _L = Math.min(_w, _h) * {{len}} / 100;
  var _a = {{angle}} * Math.PI / 180;
  var _x0 = _cx - Math.cos(_a) * _L / 2, _y0 = _cy + Math.sin(_a) * _L / 2;
  _ln.setAttribute('x1', _x0);
  _ln.setAttribute('y1', _y0);
  _ln.setAttribute('x2', _x0);
  _ln.setAttribute('y2', _y0);
  _ln.setAttribute('stroke', '{{color}}');
  _ln.setAttribute('stroke-width', '{{sw}}');
  _ln.setAttribute('stroke-linecap', 'round');
  _s.appendChild(_ln);
  timeline.to(_ln, {'attr': {'x2': _x0 + Math.cos(_a) * _L, 'y2': _y0 - Math.sin(_a) * _L},
    'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("U42", "射线箭头", "绘制", "element",
     "线 + 箭头，箭头始终贴着线头并跟着切线转向",
     "revideo:2d/components/Ray.ts",
     {"angle": 52, "len": 90, "sw": 5, "head": 26, "color": "#86F0C0", "dur": 1.2,
      "ease": "power2.inOut"},
     "指向、流程箭头、坐标轴；目标元素是空容器",
     "箭头要指着文字（用 I01 指针卡）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SVG_PRE + """  var _cx = _w / 2, _cy = _h / 2;
  var _L = Math.min(_w, _h) * {{len}} / 100;
  var _a = {{angle}} * Math.PI / 180;
  var _x0 = _cx - Math.cos(_a) * _L / 2, _y0 = _cy + Math.sin(_a) * _L / 2;
  var _ln = _mk('line');
  _ln.setAttribute('x1', _x0); _ln.setAttribute('y1', _y0);
  _ln.setAttribute('x2', _x0); _ln.setAttribute('y2', _y0);
  _ln.setAttribute('stroke', '{{color}}'); _ln.setAttribute('stroke-width', {{sw}});
  _ln.setAttribute('stroke-linecap', 'round');
  _s.appendChild(_ln);
  var _hd = _mk('polygon');
  _hd.setAttribute('points', '0,-{{head}} {{head}},0 0,{{head}}');
  _hd.setAttribute('fill', '{{color}}');
  _s.appendChild(_hd);
  var _drv = {p: 0};
  timeline.to(_drv, {'p': 1, 'duration': {{dur}}, 'ease': '{{ease}}', 'onUpdate': function () {
    var px = _x0 + Math.cos(_a) * _L * _drv.p, py = _y0 - Math.sin(_a) * _L * _drv.p;
    _ln.setAttribute('x2', px); _ln.setAttribute('y2', py);
    _hd.setAttribute('transform', 'translate(' + px + ',' + py + ') rotate(' + (-{{angle}}) + ')');
  }}, {{at}});
})();""", needs=["ui"])

card("U43", "网格铺开", "绘制", "element",
     "横竖线从中间往两头长，横竖错开；比整张网格淡入有方向",
     "revideo:2d/components/Grid.ts",
     {"cols": 12, "rows": 20, "color": "rgba(134,240,192,.20)", "stagger": 0.035,
      "dur": 0.75, "ease": "power3.out"},
     "科技感底纹、数据页起手；目标元素是空容器或满屏层",
     "有照片满幅的屏（会被盖住）；同屏已用 B 系 canvas 背景",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') _t.style.position = 'relative';
  var _cols = {{cols}}, _rows = {{rows}}, i;
  var _v = [], _h = [];
  for (i = 0; i <= _cols; i++) {
    var _d = document.createElement('i');
    _d.style.cssText = 'position:absolute;top:0;bottom:0;width:1px;left:' + (i * 100 / _cols) + '%;'
      + 'background:{{color}};transform:scaleY(0);transform-origin:50% 50%;';
    _t.appendChild(_d);
    _v.push(_d);
  }
  for (i = 0; i <= _rows; i++) {
    var _e = document.createElement('i');
    _e.style.cssText = 'position:absolute;left:0;right:0;height:1px;top:' + (i * 100 / _rows) + '%;'
      + 'background:{{color}};transform:scaleX(0);transform-origin:50% 50%;';
    _t.appendChild(_e);
    _h.push(_e);
  }
  timeline.to(_h, {'scaleX': 1, 'duration': {{dur}}, 'ease': '{{ease}}',
    'stagger': {'each': {{stagger}}, 'from': 'center'}}, {{at}});
  timeline.to(_v, {'scaleY': 1, 'duration': {{dur}}, 'ease': '{{ease}}',
    'stagger': {'each': {{stagger}}, 'from': 'center'}}, {{at}} + 0.12);
})();""", needs=["ui"])

card("U44", "公式逐项", "绘制", "element",
     "公式按项依次落位：左边、中间、右边各一段，后一段等前一段站稳",
     "revideo:2d/components/Latex.ts",
     {"stagger": 0.42, "dur": 0.55, "ease": "power2.out", "from": 26},
     "公式、等式、推导步骤；目标元素的子项要拆成 span",
     "整段公式只有一个节点（那就只有一次落位）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _kids = [].slice.call(_t.children);
  if (!_kids.length) _kids = [_t];
  timeline.fromTo(_kids, {'opacity': 0, 'y': {{from}}},
    {'opacity': 1, 'y': 0, 'duration': {{dur}}, 'ease': '{{ease}}', 'stagger': {{stagger}}}, {{at}});
})();""", needs=["text"])

card("U45", "矩形环绕描边", "绘制", "element",
     "沿矩形边框从一角描满一圈（矩形剖面取点，不用手算周长）",
     "revideo:2d/curves/getRectProfile.ts",
     {"inset": 6, "sw": 4, "color": "#86F0C0", "dur": 1.7, "ease": "power1.inOut"},
     "给一块内容「围一圈」；比 U40 更像手画",
     "没有明确边界的文字块",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t || !window.DrawSVGPlugin) return;
""" + SVG_PRE + """  var _i = {{inset}};
  var _p = _mk('path');
  _p.setAttribute('d', 'M' + _i + ',' + _i + ' L' + (_w - _i) + ',' + _i
    + ' L' + (_w - _i) + ',' + (_h - _i) + ' L' + _i + ',' + (_h - _i) + ' Z');
  _p.setAttribute('fill', 'none');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _p.setAttribute('stroke-linejoin', 'round');
  _s.appendChild(_p);
  timeline.fromTo(_p, {'drawSVG': '0%'}, {'drawSVG': '100%', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("U46", "圆周描边", "绘制", "element",
     "沿圆周从一点描满一整圈（圆剖面），收口处不重叠",
     "revideo:2d/curves/getCircleProfile.ts",
     {"pct": 78, "sw": 4, "color": "#86F0C0", "dur": 1.7, "ease": "power1.inOut"},
     "圈重点、做「进度环」的底；目标元素是空容器",
     "同屏已用 U39（两个圆会打架）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t || !window.DrawSVGPlugin) return;
""" + SVG_PRE + """  var _rad = Math.min(_w, _h) * {{pct}} / 200;
  var _p = _mk('path');
  _p.setAttribute('d', 'M' + (_w / 2 - _rad) + ',' + (_h / 2)
    + ' a' + _rad + ',' + _rad + ' 0 1,1 ' + (_rad * 2) + ',0'
    + ' a' + _rad + ',' + _rad + ' 0 1,1 ' + (-_rad * 2) + ',0');
  _p.setAttribute('fill', 'none');
  _p.setAttribute('stroke', '{{color}}');
  _p.setAttribute('stroke-width', '{{sw}}');
  _s.appendChild(_p);
  timeline.fromTo(_p, {'drawSVG': '0%'}, {'drawSVG': '100%', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("U47", "圆点环绕", "绘制", "element",
     "一个圆点沿圆周匀速走一圈，朝向跟着切线",
     "revideo:2d/curves/getPointAtDistance.ts",
     {"pct": 74, "dot": 26, "sw": 3, "color": "#86F0C0", "dur": 1.9},
     "绕行、环绕标注、「第几步」的指示",
     "需要直线路径（用 U28 MotionPath）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
""" + SVG_PRE + """  var _rad = Math.min(_w, _h) * {{pct}} / 200;
  var _trk = _mk('circle');
  _trk.setAttribute('cx', _w / 2); _trk.setAttribute('cy', _h / 2);
  _trk.setAttribute('r', _rad);
  _trk.setAttribute('fill', 'none');
  _trk.setAttribute('stroke', '{{color}}');
  _trk.setAttribute('stroke-width', {{sw}});
  _trk.setAttribute('opacity', '0.18');
  _s.appendChild(_trk);
  var _dot = _mk('circle');
  _dot.setAttribute('r', {{dot}} / 2);
  _dot.setAttribute('fill', '{{color}}');
  _s.appendChild(_dot);
  var _drv = {p: 0};
  timeline.to(_drv, {'p': 1, 'duration': {{dur}}, 'ease': 'none', 'onUpdate': function () {
    var a = -Math.PI / 2 + _drv.p * Math.PI * 2;
    _dot.setAttribute('cx', _w / 2 + Math.cos(a) * _rad);
    _dot.setAttribute('cy', _h / 2 + Math.sin(a) * _rad);
  }}, {{at}});
})();""", needs=["ui"])

# ================================================================ UI（8，代码类）

card("UA09", "代码行级 diff", "UI", "element",
     "行级 diff：旧行划掉压暗、新行就地长出来，行号跟着顺移",
     "revideo:2d/code/CodeSignal.ts#diff",
     {"dur": 0.45, "ease": "power2.out"},
     "讲「改了什么」；代码块要标 data-old / data-new",
     "超过 8 行（观众跟不上）；纯截图型代码",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _old = _t.querySelector('[data-old]');
  var _new = _t.querySelector('[data-new]');
  if (!_old || !_new) return;
  var _lh = _new.getBoundingClientRect().height || 52;
  _new.style.overflow = 'hidden';
  _new.style.opacity = '0';
  _new.style.height = '0px';
  timeline.to(_old, {'opacity': 0.3, 'duration': {{dur}}, 'ease': 'none'}, {{at}});
  timeline.to(_old, {'textDecoration': 'line-through', 'duration': {{dur}}, 'ease': 'none'}, {{at}});
  timeline.to(_new, {'opacity': 1, 'height': _lh, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}} + {{dur}});
})();""", needs=["ui"])

card("UA10", "代码选区扫", "UI", "element",
     "底色块按字符范围从左铺到右，扫完停在原地",
     "revideo:2d/code/CodeSignal.ts#selection",
     {"dur": 0.7, "ease": "power2.inOut", "color": "rgba(134,240,192,.24)"},
     "讲某一句代码时指一下；代码块里要标 data-mark",
     "整行都要高亮（用整行底色，不是选区）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _m = _t.querySelector('[data-mark]') || _t;
  _m.style.backgroundImage = 'linear-gradient({{color}},{{color}})';
  _m.style.backgroundRepeat = 'no-repeat';
  _m.style.backgroundSize = '0% 100%';
  _m.style.borderRadius = '4px';
  var _drv = {w: 0};
  timeline.to(_drv, {'w': 1, 'duration': {{dur}}, 'ease': '{{ease}}', 'onUpdate': function () {
    _m.style.backgroundSize = (_drv.w * 100) + '% 100%';
  }}, {{at}});
})();""", needs=["ui"])

card("UA11", "代码尾部追加", "UI", "element",
     "在代码块末尾接一行，前面的行不动",
     "revideo:2d/code/CodeSignal.ts#append",
     {"text": "    leads.push_to(crm)", "dur": 0.6, "ease": "power2.out"},
     "讲「再加一步」；代码块标 data-code",
     "同时还要删行（会抢注意力）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _d = document.createElement('div');
  _d.setAttribute('data-line', '');
  _d.style.cssText = 'opacity:0;height:0px;overflow:hidden;white-space:pre;';
  _d.textContent = '{{text}}';
  _t.appendChild(_d);
  timeline.to(_d, {'opacity': 1, 'height': 'auto', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("UA12", "代码头部插入", "UI", "element",
     "在最前面塞一行，整块往下让",
     "revideo:2d/code/CodeSignal.ts#prepend",
     {"text": "import search", "dur": 0.6, "ease": "power2.out"},
     "讲「前提是什么」；代码块标 data-code",
     "行数已经顶到屏幕下沿",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _d = document.createElement('div');
  _d.setAttribute('data-line', '');
  _d.style.cssText = 'opacity:0;height:0px;overflow:hidden;white-space:pre;';
  _d.textContent = '{{text}}';
  _t.insertBefore(_d, _t.firstChild);
  timeline.to(_d, {'opacity': 1, 'height': 'auto', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("UA13", "代码中间插入", "UI", "element",
     "在第 N 行后插一行，下面的行顺移",
     "revideo:2d/code/CodeSignal.ts#insert",
     {"after": 1, "text": "    # 校验", "dur": 0.6, "ease": "power2.out"},
     "讲「中间漏了一步」；代码块标 data-code",
     "插在最后一行（用 UA11 更自然）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _ls = [].slice.call(_t.querySelectorAll('[data-line]'));
  var _anchor = _ls[{{after}} - 1] || _t.lastChild;
  var _d = document.createElement('div');
  _d.setAttribute('data-line', '');
  _d.style.cssText = 'opacity:0;height:0px;overflow:hidden;white-space:pre;';
  _d.textContent = '{{text}}';
  if (_anchor && _anchor.parentNode) { _anchor.parentNode.insertBefore(_d, _anchor.nextSibling); }
  else { _t.appendChild(_d); }
  timeline.to(_d, {'opacity': 1, 'height': 'auto', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("UA14", "代码删除一行", "UI", "element",
     "整行收掉，下面的行补上来",
     "revideo:2d/code/CodeSignal.ts#remove",
     {"index": 2, "dur": 0.6, "ease": "power2.in"},
     "讲「这步不需要了」；代码块标 data-code",
     "删完只剩一行（观众还没读完）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _ls = [].slice.call(_t.querySelectorAll('[data-line]'));
  var _d = _ls[{{index}} - 1];
  if (!_d) return;
  _d.style.overflow = 'hidden';
  timeline.to(_d, {'opacity': 0, 'height': 0, 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

card("UA15", "代码编辑态", "UI", "element",
     "光标闪两下，字一个个敲进去，像真在改",
     "revideo:2d/code/CodeSignal.ts#edit",
     {"text": "leads = search.run(q)", "dur": 1.5, "caret": 5},
     "演示「正在写」；目标元素是空的行容器",
     "超过 30 字（敲不完）；已有 T05 打字机同屏",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  var _txt = '{{text}}';
  _t.textContent = '';
  var _cur = document.createElement('i');
  _cur.style.cssText = 'display:inline-block;width:3px;height:1.05em;vertical-align:-.16em;background:#86F0C0;margin-left:2px;';
  _t.appendChild(_cur);
  var _drv = {n: 0};
  timeline.to(_cur, {'opacity': 0, 'duration': 0.14, 'repeat': {{caret}}, 'yoyo': true}, {{at}});
  timeline.to(_drv, {'n': 1, 'duration': {{dur}}, 'ease': 'none', 'onUpdate': function () {
    var k = Math.floor(_drv.n * _txt.length);
    _t.firstChild && _t.firstChild.nodeType === 3 ? (_t.firstChild.nodeValue = _txt.slice(0, k)) : null;
    if (!_t.firstChild || _t.firstChild.nodeType !== 3) {
      _t.insertBefore(document.createTextNode(_txt.slice(0, k)), _cur);
    }
  }}, {{at}} + 0.1);
})();""", needs=["ui"])

card("UA16", "代码块揭示", "UI", "element",
     "整块代码用 clip-path 从左往右揭开，行内颜色保持",
     "revideo:examples/code-block",
     {"dur": 1.2, "ease": "none"},
     "代码块整体出现（不逐字）；比淡入干净",
     "需要逐行讲的时候（用 UA09 / UA10）",
     """(function () {
  var _t = document.querySelector('{{sel}}');
  if (!_t) return;
  _t.style.clipPath = 'inset(0 100% 0 0)';
  timeline.to(_t, {'clipPath': 'inset(0 0% 0 0)', 'duration': {{dur}}, 'ease': '{{ease}}'}, {{at}});
})();""", needs=["ui"])

# ---------------------------------------------------------------- 候选号 → 正式编号

CAND = {
    "T23": "EX01", "T24": "RV01", "T25": "RV03", "T26": "EX07",
    "X39": "RV04", "X40": "RV06",
    "W25": "CP16", "W26": "RV11",
    "K25": "CP17", "S23": "CP23",
    "U39": "CP01", "U40": "CP02", "U41": "CP04", "U42": "CP05",
    "U43": "RV15", "U44": "CP20", "U45": "CV01", "U46": "CV04", "U47": "CV06",
    "UA09": "RV13", "UA10": "RV14", "UA11": "CD02", "UA12": "CD03",
    "UA13": "CD04", "UA14": "CD05", "UA15": "CD07", "UA16": "EX06",
}

# ---------------------------------------------------------------- 写入

BATCH_TITLE = "2026-11-15 revideo 搬运批（27 张，已入表）"
FAM_ORDER = ["入场", "结构", "照片", "字形", "状态", "绘制", "UI"]
SRC_NOTE = ("来源 `~/Downloads/revideo-main`（MIT，Motion Canvas 分支）。只搬机制，不搬引擎；"
            "引擎是 TS 场景图 + canvas 2D，我们跑 HTML+GSAP。候选样片在 `样片/待筛/revideo/`，"
            "对应关系见 `候选评估.md` 的「revideo 批次」。")


def md_section() -> str:
    out = ["", "## " + BATCH_TITLE, "", SRC_NOTE, ""]
    for fam in FAM_ORDER:
        rows = [c for c in C if c["family"] == fam]
        if not rows:
            continue
        out.append("### %s（%d 张）" % (fam, len(rows)))
        out.append("")
        out.append("| 编号 | 名字 | 参数 | 什么时候用 | 别用在哪 |")
        out.append("|---|---|---|---|---|")
        for c in rows:
            ps = " · ".join("%s %s" % (k, v) for k, v in c["params"].items() if k not in ("dur", "ease"))
            ps = (ps + " · " if ps else "") + "dur %s · %s" % (c["params"].get("dur", 0.6),
                                                              c["params"].get("ease", "power2.out"))
            out.append("| %s | %s | %s | %s | %s |" % (c["id"], c["name"], ps, c["use"], c["avoid"]))
        out.append("")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PRESETS.read_text(encoding="utf-8"))
    have = {c["id"] for c in data["presets"]}
    todo = [c for c in C if c["id"] not in have]
    print("待入表 %d 张（已存在 %d 张跳过）" % (len(todo), len(C) - len(todo)))
    for c in todo:
        print("  %-5s %-14s %-4s %s" % (c["id"], c["name"], c["family"], c["src"]))
    if args.dry_run:
        print("\n（dry-run）")
        return

    for c in todo:
        c["cand"] = CAND.get(c["id"], "")
    data["presets"].extend(todo)
    data["updated"] = "2026-11-15"
    PRESETS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("✓ presets.json：+%d" % len(todo))

    md = CARDS_MD.read_text(encoding="utf-8")
    if BATCH_TITLE not in md:
        md = md.rstrip() + "\n" + md_section()
        CARDS_MD.write_text(md, encoding="utf-8")
        print("✓ 能力卡.md：追加一节")

    moved = 0
    for c in todo:
        fam_dir = REELS / c["family"]
        fam_dir.mkdir(parents=True, exist_ok=True)
        dest = fam_dir / ("%s-%s.mp4" % (c["id"], c["name"]))
        if dest.exists():
            continue
        for cand_dir in (BATCH / "out", BATCH / "sweep" / "out"):
            hits = sorted(cand_dir.glob("%s-*.mp4" % c["cand"])) if c.get("cand") else []
            if hits:
                shutil.copy2(hits[0], dest)
                moved += 1
                print("  片 %s ← %s" % (dest.name, hits[0].name))
                break
    print("✓ 确认片：%d 张" % moved)

    print("\n同步链：")
    subprocess.run([sys.executable, str(HERE / "sync_expander.py")], cwd=str(HERE))
    subprocess.run([sys.executable, str(HERE / "sync_expander.py"), "--check"], cwd=str(HERE))


if __name__ == "__main__":
    main()
