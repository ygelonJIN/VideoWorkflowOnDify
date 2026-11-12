/* bg-kit.js — 确定性 canvas 背景（B08–B21）
 * 每条背景都是 t 的纯函数：同一个 t 画出来永远一样，可 seek、可复现。
 * 由场景脚本调用 bgkit.bind(timeline, canvas, name, params)，用一条覆盖全场的
 * 哑 tween 驱动重绘（不占 eventCallback，不和场景显隐抢 onUpdate）。
 */
(function (global) {
  "use strict";

  var TAU = Math.PI * 2;

  function rng(seed) {
    var s = seed || 1;
    return function () { s = (s * 9301 + 49297) % 233280; return s / 233280; };
  }

  var P = {
    particles: function (c, w, h, t, o) {
      var n = o.count || 70, r = rng(o.seed || 7), pad = 20;
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var x0 = r(), y0 = r(), sp = 0.02 + r() * 0.05, sz = 1 + r() * 2.4;
        var x = ((x0 + t * sp) % 1) * w;
        var y = ((y0 - t * sp * 0.6 + 1) % 1) * h;
        c.beginPath();
        c.arc(x, y, sz, 0, TAU);
        c.fillStyle = "rgba(180,225,255," + (0.12 + r() * 0.4) + ")";
        c.fill();
      }
      c.globalAlpha = 1;
    },

    dots: function (c, w, h, t, o) {
      var step = o.step || 28, r = 1.6;
      c.clearRect(0, 0, w, h);
      for (var y = step / 2; y < h; y += step) {
        for (var x = step / 2; x < w; x += step) {
          var d = Math.hypot(x - w / 2, y - h * 0.4) / Math.hypot(w, h);
          var a = 0.10 + 0.30 * (0.5 + 0.5 * Math.sin(t * 1.1 - d * 9));
          c.beginPath(); c.arc(x, y, r, 0, TAU);
          c.fillStyle = "rgba(170,215,255," + a.toFixed(3) + ")";
          c.fill();
        }
      }
    },

    grid: function (c, w, h, t, o) {
      var step = o.step || 64;
      c.clearRect(0, 0, w, h);
      c.strokeStyle = "rgba(255,255,255,.07)";
      c.lineWidth = 1;
      for (var x = 0; x <= w; x += step) { c.beginPath(); c.moveTo(x, 0); c.lineTo(x, h); c.stroke(); }
      for (var y = 0; y <= h; y += step) { c.beginPath(); c.moveTo(0, y); c.lineTo(w, y); c.stroke(); }
      var by = ((t * 0.18) % 1) * h, bh = 260;
      var g = c.createLinearGradient(0, by - bh / 2, 0, by + bh / 2);
      g.addColorStop(0, "rgba(56,214,255,0)");
      g.addColorStop(0.5, "rgba(56,214,255,.16)");
      g.addColorStop(1, "rgba(56,214,255,0)");
      c.fillStyle = g; c.fillRect(0, by - bh / 2, w, bh);
    },

    rays: function (c, w, h, t, o) {
      var n = o.count || 9, cx = w * (o.cx == null ? 0.5 : o.cx), cy = h * (o.cy == null ? 1.05 : o.cy);
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var a = (i / n) * Math.PI + Math.sin(t * 0.15 + i) * 0.06;
        var spread = 0.06 + 0.03 * Math.sin(t * 0.3 + i * 1.7);
        var len = h * 1.6;
        c.beginPath(); c.moveTo(cx, cy);
        c.lineTo(cx + Math.cos(a - spread) * len, cy - Math.sin(a - spread) * len);
        c.lineTo(cx + Math.cos(a + spread) * len, cy - Math.sin(a + spread) * len);
        c.closePath();
        c.fillStyle = "rgba(120,200,255," + (0.05 + 0.06 * Math.abs(Math.sin(t * 0.4 + i))).toFixed(3) + ")";
        c.fill();
      }
    },

    ripples: function (c, w, h, t, o) {
      var cx = w * 0.5, cy = h * 0.42;
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < 5; i++) {
        var p = ((t * 0.22 + i * 0.2) % 1);
        var r = p * Math.hypot(w, h) * 0.6;
        c.beginPath(); c.arc(cx, cy, r, 0, TAU);
        c.strokeStyle = "rgba(150,215,255," + (0.22 * (1 - p)).toFixed(3) + ")";
        c.lineWidth = 3; c.stroke();
      }
    },

    ribbons: function (c, w, h, t, o) {
      var n = o.count || 5;
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var amp = 40 + i * 18, base = h * (0.25 + i * 0.13);
        c.beginPath();
        for (var x = 0; x <= w; x += 12) {
          var y = base + Math.sin(x / 180 + t * (0.4 + i * 0.08) + i) * amp;
          if (x === 0) c.moveTo(x, y); else c.lineTo(x, y);
        }
        c.strokeStyle = "rgba(" + (i % 2 ? "120,170,255" : "150,230,255") + ",.10)";
        c.lineWidth = 26 - i * 3; c.stroke();
      }
    },

    blobs: function (c, w, h, t, o) {
      var r = rng(o.seed || 3);
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < 4; i++) {
        var bx = w * (0.2 + 0.6 * r()) + Math.sin(t * 0.2 + i) * 90;
        var by = h * (0.2 + 0.6 * r()) + Math.cos(t * 0.17 + i) * 120;
        var rad = 220 + i * 60;
        var g = c.createRadialGradient(bx, by, 0, bx, by, rad);
        g.addColorStop(0, "rgba(110,180,255,.16)");
        g.addColorStop(1, "rgba(110,180,255,0)");
        c.fillStyle = g; c.fillRect(bx - rad, by - rad, rad * 2, rad * 2);
      }
    },

    pixels: function (c, w, h, t, o) {
      var size = o.size || 48, r = rng(o.seed || 11);
      c.clearRect(0, 0, w, h);
      for (var y = 0; y < h; y += size) {
        for (var x = 0; x < w; x += size) {
          var v = Math.sin((x + y) / 420 + t * 0.8) * 0.5 + 0.5;
          if (v < 0.62) continue;
          c.fillStyle = "rgba(120,205,255," + ((v - 0.62) * 0.55).toFixed(3) + ")";
          c.fillRect(x + 2, y + 2, size - 4, size - 4);
        }
      }
    }
  };

  var NAMES = {
    B08: ["particles", { count: 70 }],
    B09: ["dots", { step: 28 }],
    B10: ["grid", { step: 64 }],
    B11: ["grid", { step: 44 }],
    B12: ["rays", { count: 11, cy: 1.06 }],
    B13: ["rays", { count: 7, cx: 0.18, cy: 0.5 }],
    B14: ["ripples", {}],
    B15: ["ribbons", { count: 5 }],
    B16: ["ribbons", { count: 8 }],
    B17: ["blobs", { seed: 3 }],
    B18: ["pixels", { size: 52, seed: 5 }],
    B19: ["dots", { step: 18 }],
    B20: ["pixels", { size: 34, seed: 9 }],
    B21: ["pixels", { size: 24, seed: 13 }]
  };

  function bind(timeline, canvas, name, opts) {
    if (!timeline || !canvas) return;
    var entry = NAMES[name] || NAMES.B08;
    var fn = P[entry[0]];
    if (!fn) return;
    var params = {};
    var k;
    for (k in entry[1]) params[k] = entry[1][k];
    if (opts) for (k in opts) params[k] = opts[k];
    var ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = 1080; canvas.height = 1920;
    var last = -1;
    var stage = document.getElementById("stage");
    var dur = Number(stage && stage.getAttribute("data-duration")) || 60;
    function paint() {
      var t = timeline.time();
      if (Math.abs(t - last) < 0.02) return;
      last = t;
      fn(ctx, canvas.width, canvas.height, t, params);
    }
    /* 用一条与片长等长的哑 tween 驱动重绘：不延长总时长，seek 到哪一帧都成立 */
    timeline.to({}, { duration: dur, ease: "none", onUpdate: paint }, 0);
    window.addEventListener("hf-seek", function (e) {
      var t = (e && e.detail && e.detail.time);
      if (typeof t === "number") { last = -1; fn(ctx, canvas.width, canvas.height, t, params); }
    });
    fn(ctx, canvas.width, canvas.height, 0, params);
  }

  global.bgkit = { bind: bind, patterns: Object.keys(NAMES), names: NAMES };
})(window);
