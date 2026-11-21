/* motion-kit.js — 视频管线的动效原子能力
 * 只提供「值」和「结构」，不封装 timeline.to()，保证 HTML 里仍有字面量 GSAP 调用
 * （check_html_contract.py 靠静态正则判定「有可寻址时间线」）。
 * 禁止：requestAnimationFrame / performance.now / Math.random
 */
(function (global) {
  "use strict";

  /* ---------- 拆字 / 拆词 / 拆行 ---------- */
  /* 逐字/逐词的目标必须是"文本叶子"。如果传进来的是复合容器（里面还有元素子节点），
   * 单子元素就递归下探；多子元素就取第一个纯文本叶子，其余不动。
   * 2026-11-13 加：T09 打到 .ui-row 容器上时以前会静默返回空数组，整张卡等于没生效。 */
  function leafOf(el) {
    var guard = 0;
    while (el && el.children && el.children.length && guard++ < 6) {
      var kids = [].filter.call(el.children, function (c) {
        return !/^(SCRIPT|STYLE|BR)$/.test(c.tagName);
      });
      if (!kids.length) break;
      if (kids.length === 1) { el = kids[0]; continue; }
      var textish = kids.filter(function (c) {
        return !c.children || !c.children.length;
      })[0];
      if (!textish) return null;
      el = textish;
    }
    return el;
  }

  function split(target, unit) {
    var el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el) return [];
    var leaf = leafOf(el);
    if (!leaf) {
      (window.__splitWarnings = window.__splitWarnings || []).push(
        (el.className || el.tagName) + ' 是复合容器，拆字已跳过');
      return [];
    }
    el = leaf;
    unit = unit || 'chars';
    /* 可重复调用：每次都从原始标记重建，避免二次拆分拿到空数组 */
    if (el.__kitHTML === undefined) el.__kitHTML = el.innerHTML;
    else el.innerHTML = el.__kitHTML;

    if (unit === 'lines') {
      /* 按 <br> 与实际行盒切；这里只处理显式 <br>，自动折行交给版面 */
      var lines = [];
      var buf = [];
      [].slice.call(el.childNodes).forEach(function (node) {
        if (node.nodeName === 'BR') {
          if (buf.length) { lines.push(wrap(buf, 'line')); buf = []; }
          return;
        }
        buf.push(node);
      });
      if (buf.length) lines.push(wrap(buf, 'line'));
      return lines;
    }

    var out = [];
    [].slice.call(el.childNodes).forEach(function (node) {
      if (node.nodeType !== 3) return;
      var text = node.textContent;
      /* 纯空白文本节点（HTML 里的缩进换行）不参与拆字，否则会生成一堆空白 span 把版面撑开 */
      if (!text || !text.replace(/\s/g, '')) return;
      var frag = document.createDocumentFragment();
      var parts = unit === 'words' ? text.split(/(\s+)/) : [].slice.call(text);
      parts.forEach(function (part) {
        if (!part) return;
        if (unit === 'words' && /^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
        var span = document.createElement('span');
        span.className = 'kit-' + (unit === 'words' ? 'word' : 'char');
        span.textContent = part;
        span.style.display = 'inline-block';
        /* 2026-11-16：words 用 pre-wrap 不用 pre。
           中文没有空格，一整行会被拆成一个 span，pre 让它不可断行，
           420px 的栏里 11 个字 60px 就是 660px，直接冲出栏外压到照片上。
           pre-wrap 保留空格、允许内部折行，动画目标仍是一个整体。 */
        span.style.whiteSpace = unit === 'words' ? 'pre-wrap' : 'pre';
        frag.appendChild(span);
        out.push(span);
      });
      el.replaceChild(frag, node);
    });
    /* 拆字后的父元素必须允许自动换行：inline-block 的逐字 span 之间没有空格，
       某些字体会把整行判成不可断，14 个字 124px 就会单行冲出容器。 */
    el.style.whiteSpace = 'normal';
    el.style.wordBreak = 'break-all';
    return out;
  }

  function wrap(nodes, cls) {
    var span = document.createElement('span');
    span.className = 'kit-' + cls;
    span.style.display = 'block';
    nodes.forEach(function (n) { span.appendChild(n); });
    return span;
  }

  /* ---------- 虚拟指针：时间线写 pos，apply 把值落到 CSS 变量 ---------- */
  function pointer(inner, opts) {
    var o = opts || {};
    var pos = { x: o.x == null ? 0.5 : o.x, y: o.y == null ? 0.5 : o.y };
    var box = { w: 0, h: 0 };

    function measure() {
      var r = inner.getBoundingClientRect();
      box.w = r.width || 1;
      box.h = r.height || 1;
    }

    function apply() {
      if (!box.w) measure();
      var px = pos.x * box.w;
      var py = pos.y * box.h;
      inner.style.setProperty('--mx', px.toFixed(1) + 'px');
      inner.style.setProperty('--my', py.toFixed(1) + 'px');
    }

    measure();
    apply();

    /* 深度冻结不需要，直接返回同一对象，时间线 tween 它即可 */
    return { pos: pos, apply: apply, measure: measure };
  }

  /* ---------- 弹簧缓动：返回 0→1 的 ease 函数（可过冲） ----------
   * bounce: 0 = 临界阻尼（不甩尾），0.3 = 轻回弹，-0.2 = 过阻尼
   * visualDuration: 视觉落定时间（秒），实际 tween 时长建议 = 该值 * 1.2
   */
  function spring(bounce, visualDuration) {
    var zeta = bounce < 0 ? 1 / Math.max(1 + bounce, 0.05) : Math.max(1 - bounce, 0.05);
    var dur = Math.max(0.05, visualDuration || 0.4);
    var omega = 2 * Math.PI / dur;

    return function (p) {
      if (p <= 0) return 0;
      if (p >= 1) return 1;
      var t = p * dur;
      var value;
      if (zeta < 1) {
        var wd = omega * Math.sqrt(1 - zeta * zeta);
        value = 1 - Math.exp(-zeta * omega * t) *
          (Math.cos(wd * t) + (zeta * omega / wd) * Math.sin(wd * t));
      } else if (zeta === 1) {
        value = 1 - Math.exp(-omega * t) * (1 + omega * t);
      } else {
        var r = Math.sqrt(zeta * zeta - 1);
        var s1 = -omega * (zeta - r);
        var s2 = -omega * (zeta + r);
        var c2 = s1 / (s1 - s2);
        var c1 = 1 - c2;
        value = 1 - (c1 * Math.exp(s1 * t) + c2 * Math.exp(s2 * t));
      }
      return value;
    };
  }

  /* ---------- 三次贝塞尔缓动（GSAP 核心没有 CustomEase 时的替代） ---------- */
  function cubicBezier(x1, y1, x2, y2) {
    function a(a1, a2) { return 1 - 3 * a2 + 3 * a1; }
    function b(a1, a2) { return 3 * a2 - 6 * a1; }
    function c(a1) { return 3 * a1; }
    function calc(t, a1, a2) { return ((a(a1, a2) * t + b(a1, a2)) * t + c(a1)) * t; }
    function slope(t, a1, a2) { return 3 * a(a1, a2) * t * t + 2 * b(a1, a2) * t + c(a1); }

    return function (x) {
      if (x <= 0) return 0;
      if (x >= 1) return 1;
      var t = x;
      for (var i = 0; i < 8; i++) {
        var d = slope(t, x1, x2);
        if (Math.abs(d) < 1e-6) break;
        t -= (calc(t, x1, x2) - x) / d;
      }
      return calc(t, y1, y2);
    };
  }

  /* ---------- 固定的伪随机（替代 Math.random，渲染可复现） ---------- */
  function seeded(seed) {
    var s = seed, i;
    /* 2026-11-13：支持字符串种子（手绘标注按名字取种子），数字种子行为不变 */
    if (typeof s === 'string') {
      var h = 2166136261;
      for (i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
      s = Math.abs(h) % 233280;
    }
    s = s || 7;
    return function () {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
  }


  /* ---------- 通用底层能力：任何卡、任何手写场景都能直接调 ---------- */

  /* 给定文案和可用宽度，算出能填满的字号（Remotion fitText 的等价实现） */
  function fitText(opts) {
    var o = opts || {};
    var text = String(o.text == null ? '字' : o.text);
    var width = Number(o.withinWidth) || 900;
    var base = 100;
    var cv = document.createElement('canvas').getContext('2d');
    cv.font = (o.fontWeight || 500) + ' ' + base + 'px ' + (o.fontFamily || 'sans-serif');
    var w = cv.measureText(text).width + (Number(o.letterSpacing) || 0) * text.length;
    if (!w) return base;
    return Math.max(8, (width / w) * base);
  }

  /* 量一个元素要放大多少倍才能填满父级宽度（不依赖字体加载） */
  function fitScale(target, ratio) {
    var el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el) return 1;
    var parent = el.parentElement;
    var pw = parent ? parent.getBoundingClientRect().width : 900;
    var ew = el.getBoundingClientRect().width || 1;
    return (pw / ew) * (ratio == null ? 1 : ratio);
  }

  /* 确定性 value noise：seed 固定，同一个 t 永远一样 */
  function noise2(x, y, seed) {
    var s = seed == null ? 7 : seed;
    function h(i, j) {
      var n = i * 374761393 + j * 668265263 + s * 144665;
      n = (n ^ (n >> 13)) * 1274126177;
      return ((n ^ (n >> 16)) >>> 0) / 4294967295;
    }
    var xi = Math.floor(x), yi = Math.floor(y);
    var xf = x - xi, yf = y - yi;
    var u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    var a = h(xi, yi), b = h(xi + 1, yi), c = h(xi, yi + 1), d = h(xi + 1, yi + 1);
    return (a * (1 - u) + b * u) * (1 - v) + (c * (1 - u) + d * u) * v;
  }

  /* SVG 路径：按进度画到 p（0–1）；兼容 <path> 和任意带 getTotalLength 的节点 */
  function pathAt(el, p) {
    if (!el || !el.getTotalLength) return;
    var len = el.getTotalLength() || 0;
    el.style.strokeDasharray = len + ' ' + len;
    el.style.strokeDashoffset = len * (1 - Math.max(0, Math.min(1, p)));
  }

  /* 一条线从 0 画到 1，用时间线驱动 */
  function drawPath(timeline, target, at, dur, opts) {
    var el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el || !timeline) return;
    var len = el.getTotalLength ? (el.getTotalLength() || 0) : 0;
    el.style.strokeDasharray = len + ' ' + len;
    var o = opts || {};
    timeline.fromTo(el, { strokeDashoffset: len },
      { strokeDashoffset: 0, duration: dur || 0.8, ease: o.ease || 'power2.inOut' }, at);
  }


  /* ================= 2026-11-13 新增：从 Remotion 候选移植 ================= */

  /* ---------- macOS 指针（替换旧手绘多边形；热点在 (6,4) 像素，与 I01/I02 的偏移一致） ---------- */
  function cursorSVG() {
    return '<svg class="ptr" viewBox="0 0 32 40" width="72" height="90" aria-hidden="true"'
      + ' style="position:absolute;left:-6px;top:-4px;width:72px;height:90px;pointer-events:none;z-index:60;overflow:visible">'
      + '<defs><filter id="kit-ptr-sh" x="-50%" y="-50%" width="200%" height="200%">'
      + '<feDropShadow dx="1.2" dy="2.2" stdDeviation="2.4" flood-color="#000" flood-opacity="0.55"/>'
      + '</filter></defs>'
      + '<g filter="url(#kit-ptr-sh)">'
      + '<path d="M2.67 1.78 L2.67 27.30 L9.62 21.24 L13.58 31.40 L18.02 29.46 L14.06 19.36 L23.40 19.36 Z"'
      + ' fill="#ffffff" stroke="#0a0a0a" stroke-width="1.55" stroke-linejoin="round"/>'
      + '</g></svg>';
  }

  /* ---------- 手绘标注几何（rough 风格，自研；返回 path 的 d 串） ---------- */
  function _jline(rnd, x1, y1, x2, y2, amp) {
    var mx = (x1 + x2) / 2 + (rnd() - 0.5) * amp;
    var my = (y1 + y2) / 2 + (rnd() - 0.5) * amp;
    return 'M' + x1.toFixed(1) + ' ' + y1.toFixed(1) + 'Q' + mx.toFixed(1) + ' ' + my.toFixed(1)
      + ' ' + x2.toFixed(1) + ' ' + y2.toFixed(1);
  }
  function _closed(pts) {
    var n = pts.length, d = 'M' + pts[0][0].toFixed(1) + ' ' + pts[0][1].toFixed(1);
    for (var i = 0; i < n; i++) {
      var p0 = pts[i], p1 = pts[(i + 1) % n];
      var mx = (p0[0] + p1[0]) / 2, my = (p0[1] + p1[1]) / 2;
      d += 'Q' + p0[0].toFixed(1) + ' ' + p0[1].toFixed(1) + ' ' + mx.toFixed(1) + ' ' + my.toFixed(1);
    }
    return d + 'Z';
  }

  /* type: underline | strike | box | bracket | cross | circle | highlight
   * rect: {x,y,w,h}（相对场景）→ {strokes:[d], fills:[d]} */
  function rough(type, rect, seed, passes) {
    var rnd = seeded(seed == null ? 'rough' : seed);
    passes = passes || 2;
    var x = rect.x, y = rect.y, w = rect.w, h = rect.h;
    var x2 = x + w, y2 = y + h, mx = x + w / 2, my = y + h / 2;
    var strokes = [], fills = [], k;
    function twice(fn) { for (var i = 0; i < passes; i++) strokes.push(fn()); }

    if (type === 'underline') {
      var uy = y2 + h * 0.06;
      twice(function () { return _jline(rnd, x - w * 0.02, uy + (rnd() - 0.5) * 3, x2 + w * 0.02, uy + (rnd() - 0.5) * 3, h * 0.10); });
    } else if (type === 'strike') {
      twice(function () { return _jline(rnd, x - w * 0.01, my + (rnd() - 0.5) * 3, x2 + w * 0.01, my + (rnd() - 0.5) * 3, h * 0.08); });
    } else if (type === 'box') {
      twice(function () { return _jline(rnd, x - 6, y - 5, x2 + 7, y - 7, 7); });
      twice(function () { return _jline(rnd, x2 + 6, y - 4, x2 + 8, y2 + 6, 7); });
      twice(function () { return _jline(rnd, x2 + 5, y2 + 5, x - 7, y2 + 7, 7); });
      twice(function () { return _jline(rnd, x - 5, y2 + 6, x - 8, y - 6, 7); });
    } else if (type === 'bracket') {
      var bx = x - 26;
      for (k = 0; k < 2; k++) {
        var o = k * 3;
        strokes.push(_jline(rnd, bx + 22 - o, y - 8 + o, bx + o, y - 4, 4));
        strokes.push(_jline(rnd, bx + o, y - 4, bx + o, y2 + 4, 6));
        strokes.push(_jline(rnd, bx + o, y2 + 4, bx + 22 - o, y2 + 8 - o, 4));
      }
    } else if (type === 'cross') {
      twice(function () { return _jline(rnd, x, y, x2, y2, 10); });
      twice(function () { return _jline(rnd, x2, y, x, y2, 10); });
    } else if (type === 'circle') {
      for (var t = 0; t < passes; t++) {
        var pts = [], N = 26, rx = w * 0.58 + t * 4, ry = h * 0.78 + t * 4;
        for (var i = 0; i < N; i++) {
          var ang = (i / N) * Math.PI * 2 - 0.35 + t * 0.12;
          var wob = 1 + (rnd() - 0.5) * 0.10;
          pts.push([mx + Math.cos(ang) * rx * wob, my + Math.sin(ang) * ry * wob]);
        }
        strokes.push(_closed(pts));
      }
    } else if (type === 'highlight') {
      fills.push('M' + (x - 10) + ' ' + (y - 4) + 'L' + (x2 + 12) + ' ' + (y - 8)
        + 'L' + (x2 + 8) + ' ' + (y2 + 4) + 'L' + (x - 12) + ' ' + (y2 + 8) + 'Z');
    }
    return { strokes: strokes, fills: fills };
  }


  /* ---------- 手绘标注（rough 风格）：类型几何 + 逐行 + 按长度揭示 ----------
   * 来源：rough-notation@0.5.1 src/render.ts 的类型翻译（MIT），曲线按 roughjs 的
   * bowing / offset 思路重写。与上方旧的 rough(type, rect, seed, passes) 并存，
   * 旧签名不动（K13–K16 仍在用）；新卡一律走 kit.anno。
   *
   * 契约：动画只落在 timeline 的 strokeDashoffset 上，任意帧可 seek；
   * 目标框由 getClientRects / Range 取视觉行，不写死坐标。 */
  function _annoNorm(o) {
    var d = { rgh: 1.5, bow: 1, off: 2, sw: 6, pad: 8 };
    for (var k in (o || {})) if (o[k] != null) d[k] = o[k];
    return d;
  }
  function _annoF(n) { return Math.round(n * 10) / 10; }

  /* 一条手绘直线：两段三次贝塞尔，中段弓形，两端各带随机外扩 */
  function _annoLine(r, x1, y1, x2, y2, o) {
    var sq = (x1 - x2) * (x1 - x2) + (y1 - y2) * (y1 - y2);
    var len = Math.sqrt(sq) || 1;
    var gain = len < 200 ? 1 : (len > 500 ? 0.4 : (-0.0016668 * len + 1.233334));
    var off = o.off;
    if (off * off * 100 > sq) off = len / 10;
    var hv = off / 2;
    function jit(k) { return (r() * 2 - 1) * k * gain * (o.rgh / 1.5); }
    var dp = 0.2 + r() * 0.2;
    var mdx = o.bow * off * (y2 - y1) / 200 + jit(off);
    var mdy = o.bow * off * -(x2 - x1) / 200 + jit(off);
    var sx = x1 + jit(hv), sy = y1 + jit(hv);
    var ex = x2 + jit(hv), ey = y2 + jit(hv);
    var mxp = x1 + (x2 - x1) * dp, myp = y1 + (y2 - y1) * dp;
    return 'M' + _annoF(sx) + ' ' + _annoF(sy)
      + 'C' + _annoF(sx + mdx * 0.6) + ' ' + _annoF(sy + mdy * 0.6)
      + ' ' + _annoF(mxp + mdx) + ' ' + _annoF(myp + mdy)
      + ' ' + _annoF(mxp) + ' ' + _annoF(myp)
      + 'C' + _annoF(mxp + (x2 - x1) * 0.18 + mdx * 0.5) + ' ' + _annoF(myp + (y2 - y1) * 0.18 + mdy * 0.5)
      + ' ' + _annoF(ex - mdx * 0.35) + ' ' + _annoF(ey - mdy * 0.35)
      + ' ' + _annoF(ex) + ' ' + _annoF(ey);
  }
  function _annoPoly(r, pts, o) {
    var d = 'M' + _annoF(pts[0][0]) + ' ' + _annoF(pts[0][1]);
    for (var i = 1; i < pts.length; i++) {
      d += ' ' + _annoLine(r, pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1], o).replace(/^M[^C]*/, '');
    }
    return d;
  }
  /* 开放椭圆：起笔与收笔重叠一小段 */
  function _annoLoop(r, cx, cy, rx, ry, o) {
    var N = 30, pts = [], i, t, a0 = -0.20, a1 = Math.PI * 2 + 0.16;
    for (i = 0; i <= N; i++) {
      t = a0 + (a1 - a0) * (i / N);
      var wob = 1 + (r() - 0.5) * 0.05 * (o.rgh / 1.5);
      pts.push([cx + Math.cos(t) * rx * wob, cy + Math.sin(t) * ry * wob]);
    }
    var d = 'M' + _annoF(pts[0][0]) + ' ' + _annoF(pts[0][1]);
    for (i = 0; i < N; i++) {
      var p0 = pts[i], p1 = pts[i + 1];
      d += 'Q' + _annoF(p0[0]) + ' ' + _annoF(p0[1]) + ' '
        + _annoF((p0[0] + p1[0]) / 2) + ' ' + _annoF((p0[1] + p1[1]) / 2);
    }
    return d;
  }

  /* rect + 类型 → 若干 path 的 d */
  function _annoShapes(type, rc, o, passes) {
    var r = seeded(o.seed == null ? (type || 'anno') : o.seed);
    var pad = o.pad == null ? 8 : o.pad;
    var out = [], i, p;
    var x = rc.x, y = rc.y, w = rc.w, h = rc.h;
    var x2 = x + w, y2 = y + h, my = y + h / 2;

    if (type === 'underline') {
      var uy = y2 + pad * 0.5;
      for (i = 0; i < passes; i++) {
        var oo = _annoNorm(o); oo.off = o.off + i * 1.2;
        if ((i % 2) !== (o.rtl ? 1 : 0)) out.push(_annoLine(r, x2 + 6, uy + i * 5, x - 8, uy - i * 5 + 2, oo));
        else out.push(_annoLine(r, x - 8, uy + i * 5, x2 + 6, uy - i * 5 + 2, oo));
      }
    } else if (type === 'strike') {
      var ang = (o.angle || 0) * Math.PI / 180;
      var dy = Math.tan(ang) * w / 2;
      for (i = 0; i < passes; i++) {
        var o2 = _annoNorm(o); o2.off = o.off + i * 1.2;
        var s5 = i * 5;
        if (i % 2) out.push(_annoLine(r, x2 + 10, my + 2 + s5 - dy, x - 10, my + 4 - s5 + dy, o2));
        else out.push(_annoLine(r, x - 10, my - 3 - s5 - dy, x2 + 10, my - 1 + s5 + dy, o2));
      }
    } else if (type === 'box') {
      var ex = pad * 1.6;
      var X1 = x - ex, Y1 = y - ex, X2 = x2 + ex, Y2 = y2 + ex;
      for (i = 0; i < passes; i++) {
        var b = _annoNorm(o); b.off = o.off + i * 1.4;
        var g = i * 1.8;
        out.push(_annoLine(r, X1 - 4 + g, Y1 - 2 - g, X2 + 5, Y1 + 2 + g, b));
        out.push(_annoLine(r, X2 + 2 + g, Y1 - 4, X2 - 2 - g, Y2 + 5, b));
        out.push(_annoLine(r, X2 + 5 - g, Y2 + 2 + g, X1 - 5, Y2 - 2 - g, b));
        out.push(_annoLine(r, X1 - 2 - g, Y2 + 4, X1 + 2 + g, Y1 - 5, b));
      }
    } else if (type === 'corners') {
      var cl = Math.min(w, h) * (o.armK == null ? 0.34 : o.armK);
      var quad = [[x, y, 1, 1], [x2, y, -1, 1], [x2, y2, -1, -1], [x, y2, 1, -1]];
      for (var q = 0; q < 4; q++) {
        var cq = _annoNorm(o); cq.off = o.off + q * 0.5;
        var P = quad[q];
        out.push(_annoLine(r, P[0], P[1], P[0] + cl * P[2], P[1] + 1, cq));
        out.push(_annoLine(r, P[0], P[1], P[0] + 1, P[1] + cl * P[3], cq));
      }
    } else if (type === 'circle') {
      for (i = 0; i < passes; i++) {
        var c = _annoNorm(o); c.off = o.off + i * 1.6;
        out.push(_annoLoop(r, x + w / 2 + (i ? 1.5 : -1), y + h * 0.5,
          w * (o.rxK == null ? 0.62 : o.rxK) + i * 3,
          h * (o.ryK == null ? 0.60 : o.ryK) + i * 3, c));
      }
    } else if (type === 'cross') {
      var ix = o.inset == null ? 0 : o.inset * w;
      var iy = o.insetY == null ? (o.inset == null ? 0 : o.inset * h) : o.insetY * h;
      var qx1 = x + ix, qy1 = y + iy, qx2 = x2 - ix, qy2 = y2 - iy;
      for (i = 0; i < passes; i++) {
        var cr = _annoNorm(o); cr.off = o.off + i * 1.3;
        if (i % 2) {
          out.push(_annoLine(r, qx2 - 2, qy2 + 3, qx1 - 3, qy1 - 2, cr));
          out.push(_annoLine(r, qx1 + 2, qy2 + 2, qx2 - 3, qy1 - 3, cr));
        } else {
          out.push(_annoLine(r, qx1 - 3, qy1 - 2, qx2 + 2, qy2 + 3, cr));
          out.push(_annoLine(r, qx2 - 2, qy1 - 3, qx1 + 3, qy2 + 2, cr));
        }
      }
    } else if (type === 'bracket') {
      var dirs = [].concat(o.dir || 'right');
      var lx = x - pad * 2, rx = x2 + pad * 2;
      var ty = y - pad * 1.2, by = y2 + pad * 1.2;
      for (var k2 = 0; k2 < dirs.length; k2++) {
        var bb = _annoNorm(o); bb.off = o.off + k2 * 0.8;
        p = null;
        if (dirs[k2] === 'right') p = [[x2, ty], [rx, ty], [rx, by], [x2, by]];
        else if (dirs[k2] === 'left') p = [[x, ty], [lx, ty], [lx, by], [x, by]];
        else if (dirs[k2] === 'top') p = [[lx, y], [lx, ty], [rx, ty], [rx, y]];
        else if (dirs[k2] === 'bottom') p = [[lx, y2], [lx, by], [rx, by], [rx, y2]];
        if (p) out.push(_annoPoly(r, p, bb));
      }
    } else if (type === 'highlight') {
      for (i = 0; i < passes; i++) {
        var hl = _annoNorm(o); hl.off = o.off + i * 1.5; hl.sw = o.sw;
        if (i % 2) out.push(_annoLine(r, x2 + pad * 1.4, my + i * 2.2, x - pad * 1.2, my - i * 2.2, hl));
        else out.push(_annoLine(r, x - pad * 1.2, my - i * 2.2, x2 + pad * 1.4, my + i * 2.2, hl));
      }
    }
    return out;
  }

  var _ANNO_NS = 'http://www.w3.org/2000/svg';

  /* 逐行取框：inline-block 只有一个盒子，靠 Range 拿 line box */
  function _annoRects(host, target) {
    var hb = host.getBoundingClientRect();
    var rs = null;
    try {
      var range = document.createRange();
      range.selectNodeContents(target);
      rs = range.getClientRects();
    } catch (e) { rs = null; }
    if (!rs || !rs.length) rs = target.getClientRects();
    var out = [], r, i;
    if (!rs || !rs.length) {
      r = target.getBoundingClientRect();
      return [{ x: r.left - hb.left, y: r.top - hb.top, w: r.width, h: r.height }];
    }
    for (i = 0; i < rs.length; i++) {
      r = rs[i];
      if (!r.width || !r.height) continue;
      out.push({ x: r.left - hb.left, y: r.top - hb.top, w: r.width, h: r.height });
    }
    if (!out.length) {
      r = target.getBoundingClientRect();
      out.push({ x: r.left - hb.left, y: r.top - hb.top, w: r.width, h: r.height });
    }
    return out;
  }

  function _annoSvg(host, cfg) {
    var svg = document.createElementNS(_ANNO_NS, 'svg');
    svg.setAttribute('viewBox', '0 0 1080 1920');
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;'
      + 'overflow:visible;pointer-events:none;z-index:' + (cfg.z == null ? 6 : cfg.z);
    host.appendChild(svg);
    return svg;
  }

  function _annoBuild(svg, host, target, cfg, tag) {
    var rects = _annoRects(host, target);
    var parts = cfg.parts || [cfg];
    var paths = [], i, m, j, ds, rc, o, part, key;
    for (i = 0; i < rects.length; i++) {
      rc = rects[i];
      for (m = 0; m < parts.length; m++) {
        part = parts[m];
        o = _annoNorm(part);
        for (key in cfg) if (o[key] == null) o[key] = cfg[key];
        o.seed = (part.seed || cfg.seed || 'anno') + ':' + (tag || 0) + ':' + i + ':' + m;
        o.pad = o.pad == null ? 8 : o.pad;
        ds = _annoShapes(part.type, rc, o, o.passes || 2);
        for (j = 0; j < ds.length; j++) {
          var pe = document.createElementNS(_ANNO_NS, 'path');
          pe.setAttribute('d', ds[j]);
          pe.setAttribute('fill', 'none');
          pe.setAttribute('stroke', part.color || cfg.color || '#FFD45E');
          pe.setAttribute('stroke-width', part.sw || cfg.sw || 6);
          pe.setAttribute('stroke-linecap', 'round');
          pe.setAttribute('stroke-linejoin', 'round');
          pe.setAttribute('opacity', (part.op == null ? (cfg.op == null ? 1 : cfg.op) : part.op));
          svg.appendChild(pe);
          paths.push(pe);
        }
      }
    }
    return paths;
  }

  /* 按路径长度分配时长揭示，返回末笔结束时间 */
  function _annoPlay(tl, paths, at, span, cfg) {
    if (!paths.length) return at;
    var lens = [], total = 0, i, L, t = at, dd;
    var ov = cfg.overlap == null ? 0.92 : cfg.overlap;
    for (i = 0; i < paths.length; i++) {
      L = 1;
      try { L = paths[i].getTotalLength() || 1; } catch (e) { L = 1; }
      lens.push(L); total += L;
    }
    for (i = 0; i < paths.length; i++) {
      dd = Math.max(total ? span * lens[i] / total : span / paths.length, 0.10);
      paths[i].style.strokeDasharray = lens[i];
      paths[i].style.strokeDashoffset = lens[i];
      tl.to(paths[i], { strokeDashoffset: 0, duration: dd, ease: cfg.ease || 'power1.inOut' }, t);
      t += dd;
      if (i < paths.length - 1) t -= dd * (1 - ov);
    }
    return t;
  }

  /* 单目标标注：cfg.parts 可给多组（同一目标叠几种类型） */
  function anno(tl, target, cfg) {
    if (!tl || !target) return null;
    cfg = cfg || {};
    var host = target.closest ? (target.closest('.scene') || document.getElementById('stage')) : null;
    host = host || document.getElementById('stage');
    if (!host) return null;
    var svg = _annoSvg(host, cfg);
    var paths = _annoBuild(svg, host, target, cfg, 0);
    _annoPlay(tl, paths, cfg.at == null ? 0.7 : cfg.at, cfg.dur == null ? 0.9 : cfg.dur, cfg);
    return svg;
  }

  /* 多目标依次：items 可以是元素数组或选择器数组 */
  function annoSeq(tl, host, items, opt) {
    if (!tl || !items || !items.length) return null;
    opt = opt || {};
    host = host || document.getElementById('stage');
    if (!host) return null;
    var t = opt.at == null ? 0.5 : opt.at;
    var gap = opt.gap == null ? 0.12 : opt.gap;
    var svg = _annoSvg(host, opt);
    for (var i = 0; i < items.length; i++) {
      var el = typeof items[i] === 'string' ? document.querySelector(items[i]) : items[i];
      if (!el) continue;
      t = _annoPlay(tl, _annoBuild(svg, host, el, opt, i),
        t, opt.dur == null ? 0.7 : opt.dur, opt) + gap;
    }
    return svg;
  }

  /* ---------- 按视觉行量矩形（不改 DOM；相对元素左上角） ---------- */
  function lines(el) {
    if (!el) return [];
    var box = el.getBoundingClientRect(), out = [], cur = null;
    var walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, null);
    var range = document.createRange(), n, i, r, top;
    while ((n = walker.nextNode())) {
      for (i = 0; i < n.length; i++) {
        range.setStart(n, i); range.setEnd(n, i + 1);
        r = range.getBoundingClientRect();
        if (!r.width && !r.height) continue;
        top = Math.round(r.top);
        if (!cur || Math.abs(cur.top - top) > 2) {
          cur = { top: top, left: r.left, right: r.right, h: r.height };
          out.push(cur);
        } else {
          if (r.left < cur.left) cur.left = r.left;
          if (r.right > cur.right) cur.right = r.right;
          if (r.height > cur.h) cur.h = r.height;
        }
      }
    }
    return out.map(function (c) {
      return { x: c.left - box.left, y: c.top - box.top, w: c.right - c.left, h: c.h };
    });
  }

  /* 二分字号，把文本压进 n 行 */
  function fitLines(el, n, opts) {
    if (!el) return 0;
    var o = opts || {}, lo = o.min || 18, hi = o.max || 160, best = lo;
    for (var k = 0; k < 18; k++) {
      var mid = (lo + hi) / 2;
      el.style.fontSize = mid + 'px';
      if (lines(el).length <= n) { best = mid; lo = mid; } else { hi = mid; }
      if (hi - lo < 0.6) break;
    }
    el.style.fontSize = best + 'px';
    return best;
  }

  /* ---------- 词级字幕：按停顿/时长分页 ---------- */
  function captionTokens(items, maxSpan, gap) {
    maxSpan = maxSpan || 1.9; gap = gap || 0.22;
    var pages = [], cur = { tokens: [], from: 0, to: 0 };
    items.forEach(function (it, idx) {
      if (!cur.tokens.length) cur.from = it.from;
      var span = it.to - cur.from;
      var silence = cur.tokens.length ? it.from - cur.to : 0;
      if (cur.tokens.length && (span > maxSpan || silence >= gap)) {
        cur.to = cur.tokens[cur.tokens.length - 1].to;
        pages.push(cur);
        cur = { tokens: [], from: it.from, to: 0 };
      }
      cur.tokens.push({ text: it.text, from: it.from, to: it.to, i: idx });
      cur.to = it.to;
    });
    if (cur.tokens.length) { cur.to = cur.tokens[cur.tokens.length - 1].to; pages.push(cur); }
    return pages;
  }

  /* ---------- 照片形变：WebGL 单 pass，5 个模式（0 波动 1 湍流 2 碎裂 3 球面 4 鱼眼） ---------- */
  var DFM_VS = 'attribute vec2 pos;varying vec2 vUv;void main(){vUv=pos*0.5+0.5;gl_Position=vec4(pos,0.0,1.0);}';
  var DFM_FS = [
    'varying vec2 vUv;',
    'uniform sampler2D uTex; uniform float uT, uP; uniform vec2 uRes; uniform int uMode;',
    'float sn(vec2 p){ return sin(p.x*3.1+p.y*1.7)*0.5+sin(p.x*7.3-p.y*5.1)*0.5; }',
    'float h21(vec2 p){ p=fract(p*vec2(123.34,456.21)); p+=dot(p,p+45.32); return fract(p.x*p.y); }',
    'void main(){',
    '  vec2 uv=vUv; float p=uP; float t=uT; vec2 uv2=uv; float shade=1.0;',
    '  if(uMode==0){',
    '    uv2=uv+vec2(sin(uv.y*14.0+t*3.0)*0.030*p, cos(uv.x*9.0+t*2.2)*0.012*p);',
    '  } else if(uMode==1){',
    '    float a=sn(uv*5.0+t*0.6); float b=sn(uv*5.0+t*0.6+17.0);',
    '    uv2=uv+vec2(a,b)*0.075*p; shade=0.9+0.2*sn(uv*3.0);',
    '  } else if(uMode==2){',
    '    vec2 grid=vec2(6.0,10.0); vec2 gid=floor(uv*grid); vec2 f=fract(uv*grid);',
    '    float r=h21(gid); vec2 dir=normalize(vec2(h21(gid+3.1)-0.5,h21(gid+7.7)-0.5)+1e-5);',
    '    uv2=uv+dir*p*(0.02+0.16*r);',
    '    float gap=step(0.035,f.x)*step(0.035,f.y)*step(f.x,0.965)*step(f.y,0.965);',
    '    shade=mix(0.12,1.0,gap);',
    '  } else if(uMode==3){',
    '    vec2 q=(uv-0.5)*2.0; float r=length(q); float z=sqrt(max(0.0,1.0-r*r));',
    '    float k=mix(1.0,1.0/(0.32+0.68*z),p); uv2=0.5+q*k*0.5;',
    '    float sph=(r<1.0)?(0.30+0.80*z):0.0; shade=mix(1.0,sph,p);',
    '  } else {',
    '    vec2 q=uv-0.5; float r=length(q); float k=1.0+1.15*p;',
    '    uv2=0.5+(q/(r+1e-5))*pow(min(r*1.42,1.0),k)*0.5+(q*0.5);',
    '  }',
    '  vec4 c=texture2D(uTex,clamp(uv2,0.001,0.999));',
    '  gl_FragColor=vec4(c.rgb*shade,1.0);',
    '}'
  ].join('\n');

  function deform(canvas, src, mode) {
    if (!canvas) return null;
    var gl = canvas.getContext('webgl', { premultipliedAlpha: false, alpha: true })
      || canvas.getContext('experimental-webgl');
    if (!gl) return null;
    function sh(type, code) {
      var o = gl.createShader(type);
      gl.shaderSource(o, code); gl.compileShader(o);
      return gl.getShaderParameter(o, gl.COMPILE_STATUS) ? o : null;
    }
    var vs = sh(gl.VERTEX_SHADER, DFM_VS);
    var fs = sh(gl.FRAGMENT_SHADER, 'precision highp float;\n' + DFM_FS);
    if (!vs || !fs) return null;
    var prog = gl.createProgram();
    gl.attachShader(prog, vs); gl.attachShader(prog, fs); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return null;
    gl.useProgram(prog);
    var buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var aPos = gl.getAttribLocation(prog, 'pos');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    var U = {}, tex = null, loaded = false;
    function u(name) { if (!(name in U)) U[name] = gl.getUniformLocation(prog, name); return U[name]; }
    function upload(img) {
      if (!img || !img.naturalWidth) return;
      if (!tex) tex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
      loaded = true;
    }
    if (src) {
      if (src.complete && src.naturalWidth) upload(src);
      else src.addEventListener('load', function () { upload(src); });
    }
    return {
      ok: true,
      ready: function () { return loaded; },
      draw: function (p, t) {
        if (!loaded) return;
        gl.viewport(0, 0, canvas.width, canvas.height);
        gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.uniform1i(u('uTex'), 0);
        gl.uniform1f(u('uT'), t || 0);
        gl.uniform1f(u('uP'), p || 0);
        gl.uniform2f(u('uRes'), canvas.width, canvas.height);
        gl.uniform1i(u('uMode'), mode || 0);
        gl.drawArrays(gl.TRIANGLES, 0, 3);
      }
    };
  }

  global.kit = {
    split: split,
    pointer: pointer,
    spring: spring,
    cubicBezier: cubicBezier,
    seeded: seeded,
    fitText: fitText,
    fitScale: fitScale,
    noise2: noise2,
    pathAt: pathAt,
    drawPath: drawPath,
    cursorSVG: cursorSVG,
    rough: rough,
    anno: anno,
    annoSeq: annoSeq,
    lines: lines,
    fitLines: fitLines,
    captionTokens: captionTokens,
    deform: deform
  };
})(window);
