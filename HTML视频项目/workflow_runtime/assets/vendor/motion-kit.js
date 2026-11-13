/* motion-kit.js — 视频管线的动效原子能力
 * 只提供「值」和「结构」，不封装 timeline.to()，保证 HTML 里仍有字面量 GSAP 调用
 * （check_html_contract.py 靠静态正则判定「有可寻址时间线」）。
 * 禁止：requestAnimationFrame / performance.now / Math.random
 */
(function (global) {
  "use strict";

  /* ---------- 拆字 / 拆词 / 拆行 ---------- */
  function split(target, unit) {
    var el = typeof target === 'string' ? document.querySelector(target) : target;
    if (!el) return [];
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
      var frag = document.createDocumentFragment();
      var parts = unit === 'words' ? text.split(/(\s+)/) : [].slice.call(text);
      parts.forEach(function (part) {
        if (!part) return;
        if (unit === 'words' && /^\s+$/.test(part)) { frag.appendChild(document.createTextNode(part)); return; }
        var span = document.createElement('span');
        span.className = 'kit-' + (unit === 'words' ? 'word' : 'char');
        span.textContent = part;
        span.style.display = 'inline-block';
        span.style.whiteSpace = 'pre';
        frag.appendChild(span);
        out.push(span);
      });
      el.replaceChild(frag, node);
    });
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
    var s = seed || 7;
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
    drawPath: drawPath
  };
})(window);
