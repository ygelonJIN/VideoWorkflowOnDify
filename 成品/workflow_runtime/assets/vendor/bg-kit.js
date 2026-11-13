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


  /* ---------- B23–B36：从 Remotion effects 的观感改写成的 t 纯函数 ---------- */
  Object.assign(P, {
    halftone: function (c, w, h, t, o) {
      var step = o.step || 13, r0 = step * 0.60;
      c.clearRect(0, 0, w, h);
      c.fillStyle = o.color || "rgba(205,230,255,.32)";
      for (var y = step / 2; y < h; y += step) {
        for (var x = step / 2; x < w; x += step) {
          var v = 0.5 + 0.30 * Math.sin(x * 0.0100 + t * 0.45)
                      + 0.22 * Math.sin(y * 0.0155 - t * 0.35)
                      + 0.12 * Math.sin((x + y) * 0.0060 + t * 0.60);
          v = Math.max(0, Math.min(1, v));
          var r = r0 * (0.12 + 0.88 * v);
          if (r < 0.35) continue;
          c.beginPath(); c.arc(x, y, r, 0, TAU); c.fill();
        }
      }
    },

    scanlines: function (c, w, h, t, o) {
      var gap = o.gap || 4;
      c.clearRect(0, 0, w, h);
      c.fillStyle = o.line || "rgba(200,226,255,.16)";
      var off = (t * (o.speed || 20)) % gap;
      for (var y = -gap; y < h + gap; y += gap) c.fillRect(0, y + off, w, 1.4);
      var by = ((t * 0.16) % 1) * (h + 260) - 130;
      var g = c.createLinearGradient(0, by - 130, 0, by + 130);
      g.addColorStop(0, "rgba(120,240,200,0)");
      g.addColorStop(.5, "rgba(120,240,200,.05)");
      g.addColorStop(1, "rgba(120,240,200,0)");
      c.fillStyle = g; c.fillRect(0, by - 130, w, 260);
    },

    dotglow: function (c, w, h, t, o) {
      var step = o.step || 30, cx = w * .5, cy = h * .42;
      c.clearRect(0, 0, w, h);
      for (var y = step / 2; y < h; y += step) {
        for (var x = step / 2; x < w; x += step) {
          var d = Math.hypot(x - cx, y - cy) / Math.hypot(w, h);
          var a = Math.max(0, .55 - d * .7) * (0.7 + 0.3 * Math.sin(t * 1.4 - d * 10));
          if (a <= 0.01) continue;
          c.beginPath(); c.arc(x, y, 1.5, 0, TAU);
          c.fillStyle = "rgba(170,225,255," + a.toFixed(3) + ")"; c.fill();
        }
      }
    },

    rings: function (c, w, h, t, o) {
      var cx = w * .5, cy = h * .44, n = o.count || 7;
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var p = ((t * .16 + i / n) % 1);
        c.beginPath(); c.arc(cx, cy, p * Math.hypot(w, h) * .55, 0, TAU);
        c.strokeStyle = "rgba(150,215,255," + (0.34 * (1 - p)).toFixed(3) + ")";
        c.lineWidth = 2; c.stroke();
      }
    },

    contour: function (c, w, h, t, o) {
      var n = o.count || 16;
      c.clearRect(0, 0, w, h);
      c.strokeStyle = o.color || "rgba(150,210,255,.26)";
      c.lineWidth = 1;
      for (var i = 0; i < n; i++) {
        var base = (i / n) * h;
        c.beginPath();
        for (var x = 0; x <= w; x += 14) {
          var y = base + Math.sin(x / 210 + t * .5 + i * .5) * 34 + Math.sin(x / 90 - t * .3) * 10;
          if (x === 0) c.moveTo(x, y); else c.lineTo(x, y);
        }
        c.stroke();
      }
    },

    streaks: function (c, w, h, t, o) {
      var n = o.count || 60, r = rng(o.seed || 21);
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var y0 = r() * h, len = 120 + r() * 420, a = .09 + r() * .12;
        var x = ((t * (40 + r() * 90)) % (w + len)) - len;
        c.fillStyle = "rgba(200,230,255," + a.toFixed(3) + ")";
        c.fillRect(x, y0, len, 1.2);
      }
    },

    speckle: function (c, w, h, t, o) {
      var n = o.count || 220, r = rng(o.seed || 31);
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var x0 = r(), y0 = r(), sp = .004 + r() * .012, sz = .8 + r() * 1.8;
        var x = ((x0 + t * sp) % 1) * w;
        var y = ((y0 + t * sp * .4) % 1) * h;
        c.beginPath(); c.arc(x, y, sz, 0, TAU);
        c.fillStyle = "rgba(230,240,255," + (0.22 + r() * .45).toFixed(3) + ")"; c.fill();
      }
    },

    rain: function (c, w, h, t, o) {
      var n = o.count || 90, r = rng(o.seed || 41), len = o.len || 90;
      c.clearRect(0, 0, w, h);
      c.strokeStyle = "rgba(195,228,255,.30)"; c.lineWidth = 1;
      for (var i = 0; i < n; i++) {
        var x0 = r() * w, sp = .55 + r() * .5, ph = r();
        var y = (((ph + t * sp) % 1.2) - .2) * h;
        c.beginPath(); c.moveTo(x0, y); c.lineTo(x0 - 6, y + len); c.stroke();
      }
    },

    pixelate: function (c, w, h, t, o) {
      var size = o.size || 22, r = rng(o.seed || 51);
      c.clearRect(0, 0, w, h);
      for (var y = 0; y < h; y += size) {
        for (var x = 0; x < w; x += size) {
          var k = r() * .5 + .5 * Math.sin((x * .7 + y) / 300 + t * 1.2);
          if (k < .84) continue;
          c.fillStyle = "rgba(150,215,255," + ((k - .84) * 1.2).toFixed(3) + ")";
          c.fillRect(x + 1, y + 1, size - 2, size - 2);
        }
      }
    },

    checker: function (c, w, h, t, o) {
      var size = o.size || 132, off = (t * 6) % (size * 2);
      c.clearRect(0, 0, w, h);
      c.fillStyle = o.color || "rgba(220,235,255,.055)";
      for (var y = -size * 2; y < h + size * 2; y += size) {
        for (var x = -size * 2; x < w + size * 2; x += size) {
          var cx = Math.round(x / size), cy = Math.round(y / size);
          if ((cx + cy) % 2) continue;
          c.fillRect(x + off, y + off, size, size);
        }
      }
    },

    paper: function (c, w, h, t, o) {
      var r = rng(o.seed || 61);
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < 700; i++) {
        var x = r() * w, y = r() * h, len = 4 + r() * 22;
        c.strokeStyle = "rgba(235,228,210," + (0.05 + r() * .10).toFixed(3) + ")";
        c.lineWidth = 1;
        c.beginPath(); c.moveTo(x, y); c.lineTo(x + len, y + (r() - .5) * 2); c.stroke();
      }
      var g = c.createRadialGradient(w * .5, h * .42, 0, w * .5, h * .42, h * .55);
      g.addColorStop(0, "rgba(255,250,235,.075)");
      g.addColorStop(1, "rgba(255,250,235,0)");
      c.fillStyle = g; c.fillRect(0, 0, w, h);
    },

    beams: function (c, w, h, t, o) {
      var n = o.count || 4, cx = w * (o.cx == null ? .5 : o.cx), cy = h * 1.02;
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var a = -Math.PI / 2 + (i - (n - 1) / 2) * .16 + Math.sin(t * .2 + i) * .015;
        var spread = .055 + .02 * Math.sin(t * .4 + i);
        var x1 = cx + Math.cos(a - spread) * h * 1.7, y1 = cy + Math.sin(a - spread) * h * 1.7;
        var x2 = cx + Math.cos(a + spread) * h * 1.7, y2 = cy + Math.sin(a + spread) * h * 1.7;
        var g = c.createLinearGradient(cx, cy, (x1 + x2) / 2, (y1 + y2) / 2);
        var amp = (0.10 + .07 * Math.abs(Math.sin(t * .4 + i))).toFixed(3);
        g.addColorStop(0, "rgba(160,215,255," + amp + ")");
        g.addColorStop(.55, "rgba(160,215,255," + (amp * 0.45).toFixed(3) + ")");
        g.addColorStop(1, "rgba(160,215,255,0)");
        c.beginPath(); c.moveTo(x1, y1); c.lineTo(x2, y2); c.lineTo(cx, cy); c.closePath();
        c.fillStyle = g; c.fill();
      }
    },

    dust: function (c, w, h, t, o) {
      var n = o.count || 140, r = rng(o.seed || 71);
      c.clearRect(0, 0, w, h);
      for (var i = 0; i < n; i++) {
        var x0 = r() * w, y0 = r() * h, sp = .01 + r() * .03, sz = .6 + r() * 1.6;
        var x = x0 + Math.sin(t * sp * 6 + i) * 18;
        var y = ((y0 - t * sp * 40) % h + h) % h;
        c.beginPath(); c.arc(x, y, sz, 0, TAU);
        c.fillStyle = "rgba(255,246,220," + (0.18 + r() * .40).toFixed(3) + ")"; c.fill();
      }
    },

    gradientmesh: function (c, w, h, t, o) {
      c.clearRect(0, 0, w, h);
      var cols = ["rgba(120,200,255,.24)", "rgba(150,120,255,.21)", "rgba(90,230,200,.18)", "rgba(255,170,120,.17)"];
      for (var i = 0; i < 4; i++) {
        var bx = w * (.5 + .34 * Math.sin(t * .18 + i * 1.7));
        var by = h * (.5 + .30 * Math.cos(t * .13 + i * 2.1));
        var rad = 320 + i * 60;
        var g = c.createRadialGradient(bx, by, 0, bx, by, rad);
        g.addColorStop(0, cols[i]);
        g.addColorStop(1, "rgba(0,0,0,0)");
        c.fillStyle = g; c.fillRect(bx - rad, by - rad, rad * 2, rad * 2);
      }
    }
  });

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
    B21: ["pixels", { size: 24, seed: 13 }],
    B23: ["halftone", { step: 13 }],
    B24: ["scanlines", { gap: 4 }],
    B25: ["dotglow", { step: 30 }],
    B26: ["rings", { count: 7 }],
    B27: ["contour", { count: 16 }],
    B28: ["streaks", { count: 60 }],
    B29: ["speckle", { count: 220 }],
    B30: ["rain", { count: 90 }],
    B31: ["pixelate", { size: 22 }],
    B32: ["checker", { size: 64 }],
    B33: ["paper", {}],
    B34: ["beams", { count: 5 }],
    B35: ["dust", { count: 140 }],
    B36: ["gradientmesh", {}]
  };

  /* 直接画：给定编号和 t，画一帧（给单画布轮播用） */
  function draw(ctx, name, w, h, t, opts) {
    var entry = NAMES[name] || NAMES.B08;
    var fn = P[entry[0]];
    if (!fn) return false;
    var params = {};
    var k;
    for (k in entry[1]) params[k] = entry[1][k];
    if (opts) for (k in opts) params[k] = opts[k];
    fn(ctx, w, h, t, params);
    return true;
  }

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

  global.bgkit = { bind: bind, draw: draw, patterns: Object.keys(NAMES), names: NAMES };
})(window);
