/* bg-kit.js — 确定性 canvas 背景（B23–B39，Remotion 来源）
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


  /* ---------- B23–B39：Remotion effects 的 t 纯函数 ---------- */
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


  /* ---------- B37–B39：从 Remotion 候选移植（2026-11-13） ---------- */
  /* 值噪声：确定性哈希 + 三线性插值，纯 t 函数 */
  function _h31(x, y, z) {
    var n = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453;
    return n - Math.floor(n);
  }
  function _vnoise(x, y, z) {
    var ix = Math.floor(x), iy = Math.floor(y), iz = Math.floor(z);
    var fx = x - ix, fy = y - iy, fz = z - iz;
    var ux = fx * fx * (3 - 2 * fx), uy = fy * fy * (3 - 2 * fy), uz = fz * fz * (3 - 2 * fz);
    function L(a, b, t) { return a + (b - a) * t; }
    var c000 = _h31(ix, iy, iz), c100 = _h31(ix + 1, iy, iz);
    var c010 = _h31(ix, iy + 1, iz), c110 = _h31(ix + 1, iy + 1, iz);
    var c001 = _h31(ix, iy, iz + 1), c101 = _h31(ix + 1, iy, iz + 1);
    var c011 = _h31(ix, iy + 1, iz + 1), c111 = _h31(ix + 1, iy + 1, iz + 1);
    return L(L(L(c000, c100, ux), L(c010, c110, ux), uy),
             L(L(c001, c101, ux), L(c011, c111, ux), uy), uz);
  }
  function _fbm(x, y, z, oct) {
    var sum = 0, amp = 0.5, norm = 0, f = 1, i;
    for (i = 0; i < (oct || 5); i++) { sum += amp * _vnoise(x * f, y * f, z * f); norm += amp; amp *= 0.5; f *= 2.02; }
    return sum / norm;
  }

  /* 半分辨率画布：噪声在 1/4 像素上算，再放大——观感是柔和的，代价是 1/16 */
  var _halfCache = {};
  function _halfCtx(w, h, scale) {
    var key = w + 'x' + h + ':' + scale;
    var c = _halfCache[key];
    if (!c) {
      c = document.createElement('canvas');
      c.width = Math.max(2, Math.round(w / scale));
      c.height = Math.max(2, Math.round(h / scale));
      _halfCache[key] = c;
    }
    return c;
  }

  var EX = {
    cloudnoise: function (c, w, h, t, o) {
      var sc = o.scale || 4, hw = Math.round(w / sc), hh = Math.round(h / sc);
      var cv = _halfCtx(w, h, sc), hc = cv.getContext('2d');
      var img = hc.createImageData(hw, hh), d = img.data;
      var amp = o.amount == null ? 1 : o.amount;
      var i = 0, px, py, n, r, g, b;
      for (py = 0; py < hh; py++) {
        for (px = 0; px < hw; px++) {
          n = _fbm(px / hw * 3.2, py / hh * 3.2, t * 0.35, 5);
          var k1 = Math.max(0, Math.min(1, (n - 0.30) / 0.58));
          var k2 = Math.max(0, Math.min(1, (n - 0.70) / 0.27));
          r = (0.028 + (0.20 - 0.028) * k1) * 255; r += (0.98 * 255 - r) * k2 * 0.85;
          g = (0.055 + (0.85 - 0.055) * k1) * 255; g += (0.86 * 255 - g) * k2 * 0.85;
          b = (0.095 + (0.72 - 0.095) * k1) * 255; b += (0.42 * 255 - b) * k2 * 0.85;
          var dim = (0.55 + 0.75 * amp) / 1.3;
          d[i++] = r * dim; d[i++] = g * dim; d[i++] = b * dim; d[i++] = 255;
        }
      }
      hc.putImageData(img, 0, 0);
      c.clearRect(0, 0, w, h);
      c.imageSmoothingEnabled = true;
      c.drawImage(cv, 0, 0, w, h);
    },

    warpnoise: function (c, w, h, t, o) {
      var sc = o.scale || 4, hw = Math.round(w / sc), hh = Math.round(h / sc);
      var cv = _halfCtx(w, h, sc), hc = cv.getContext('2d');
      var img = hc.createImageData(hw, hh), d = img.data;
      var amp = o.amount == null ? 1 : o.amount;
      var i = 0, px, py, n, wv, r, g, b;
      for (py = 0; py < hh; py++) {
        for (px = 0; px < hw; px++) {
          var u = px / hw * 2.4, v = py / hh * 2.4;
          wv = _fbm(u, v, t * 0.25, 4);
          n = _fbm(u * 1.25 + 1.7 * wv, v * 1.25 + 1.7 * wv, t * 0.30, 5);
          var k1 = Math.max(0, Math.min(1, (n - 0.28) / 0.60));
          var k2 = Math.max(0, Math.min(1, (n - 0.68) / 0.28));
          r = (0.030 + (0.22 - 0.030) * k1) * 255; r += (0.96 * 255 - r) * k2 * 0.8;
          g = (0.060 + (0.78 - 0.060) * k1) * 255; g += (0.84 * 255 - g) * k2 * 0.8;
          b = (0.100 + (0.68 - 0.100) * k1) * 255; b += (0.46 * 255 - b) * k2 * 0.8;
          var dim = (0.55 + 0.75 * amp) / 1.3;
          d[i++] = r * dim; d[i++] = g * dim; d[i++] = b * dim; d[i++] = 255;
        }
      }
      hc.putImageData(img, 0, 0);
      c.clearRect(0, 0, w, h);
      c.imageSmoothingEnabled = true;
      c.drawImage(cv, 0, 0, w, h);
    },

    drift: function (c, w, h, t, o) {
      var n = o.count || 260, r = rng(o.seed || 11);
      var sim = (c.__kitSimplex || (c.__kitSimplex = _makeSimplex(o.seed || 11)));
      var spr = c.__kitGlow || (c.__kitGlow = [_glow('#86F0C0'), _glow('#FFD45E'), _glow('#5FA8FF')]);
      c.clearRect(0, 0, w, h);
      c.fillStyle = o.bg || '#060809';
      c.fillRect(0, 0, w, h);
      var i, p, nx, ny, a, size;
      var P = c.__kitPts;
      if (!P || P.length !== n) {
        P = []; c.__kitPts = P;
        for (i = 0; i < n; i++) {
          P.push({ x: r() * w, y: r() * h, r: 2.4 + r() * 5.2, sp: 0.55 + r() * 0.9, ph: r() * TAU, c: i % 3 });
        }
      }
      for (i = 0; i < n; i++) {
        p = P[i];
        nx = sim(p.x * 0.0022, p.y * 0.0022 + t * 0.07) * 72;
        ny = sim(p.x * 0.0022 + 31.7, p.y * 0.0022 + t * 0.06) * 72;
        a = 0.22 + 0.78 * Math.pow(0.5 + 0.5 * Math.sin(t * p.sp + p.ph), 2);
        size = p.r * (2.6 + a * 2.2);
        c.globalAlpha = a * 0.9;
        c.drawImage(spr[p.c], p.x + nx - size / 2, p.y + ny - size / 2, size, size);
      }
      c.globalAlpha = 1;
    }
  };

  function _glow(color) {
    var cv = document.createElement('canvas');
    cv.width = cv.height = 64;
    var g = cv.getContext('2d');
    var rg = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    rg.addColorStop(0, 'rgba(255,255,255,1)');
    rg.addColorStop(0.35, 'rgba(255,255,255,0.55)');
    rg.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = rg; g.fillRect(0, 0, 64, 64);
    g.globalCompositeOperation = 'source-in';
    g.fillStyle = color; g.fillRect(0, 0, 64, 64);
    g.globalCompositeOperation = 'source-over';
    return cv;
  }

  var _SIM_F2 = 0.5 * (Math.sqrt(3) - 1), _SIM_G2 = (3 - Math.sqrt(3)) / 6;
  var _SIM_GRAD = [1,1,0,-1,1,0,1,-1,0,-1,-1,0,1,0,1,-1,0,1,1,0,-1,-1,0,-1,0,1,1,0,-1,1,0,1,-1,0,-1,-1];
  function _makeSimplex(seed) {
    var r = rng(seed), p = new Uint8Array(256), i, j, tmp;
    for (i = 0; i < 256; i++) p[i] = i;
    for (i = 255; i > 0; i--) { j = Math.floor(r() * (i + 1)); tmp = p[i]; p[i] = p[j]; p[j] = tmp; }
    var perm = new Uint8Array(512), m12 = new Uint8Array(512);
    for (i = 0; i < 512; i++) { perm[i] = p[i & 255]; m12[i] = perm[i] % 12; }
    return function (xin, yin) {
      var n0 = 0, n1 = 0, n2 = 0;
      var s = (xin + yin) * _SIM_F2;
      var i2 = Math.floor(xin + s), j2 = Math.floor(yin + s);
      var tt = (i2 + j2) * _SIM_G2;
      var x0 = xin - (i2 - tt), y0 = yin - (j2 - tt);
      var i1, j1;
      if (x0 > y0) { i1 = 1; j1 = 0; } else { i1 = 0; j1 = 1; }
      var x1 = x0 - i1 + _SIM_G2, y1 = y0 - j1 + _SIM_G2;
      var x2 = x0 - 1 + 2 * _SIM_G2, y2 = y0 - 1 + 2 * _SIM_G2;
      var ii = i2 & 255, jj = j2 & 255;
      var t0 = 0.5 - x0 * x0 - y0 * y0;
      if (t0 > 0) { var g0 = m12[ii + perm[jj]] * 3; t0 *= t0; n0 = t0 * t0 * (_SIM_GRAD[g0] * x0 + _SIM_GRAD[g0 + 1] * y0); }
      var t1 = 0.5 - x1 * x1 - y1 * y1;
      if (t1 > 0) { var g1 = m12[ii + i1 + perm[jj + j1]] * 3; t1 *= t1; n1 = t1 * t1 * (_SIM_GRAD[g1] * x1 + _SIM_GRAD[g1 + 1] * y1); }
      var t2 = 0.5 - x2 * x2 - y2 * y2;
      if (t2 > 0) { var g2 = m12[ii + 1 + perm[jj + 1]] * 3; t2 *= t2; n2 = t2 * t2 * (_SIM_GRAD[g2] * x2 + _SIM_GRAD[g2 + 1] * y2); }
      return 70 * (n0 + n1 + n2);
    };
  }

  Object.assign(P, EX);

  var NAMES = {
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
    B34: ["beams", { count: 5 }],
    B35: ["dust", { count: 140 }],
    B36: ["gradientmesh", {}],
    B37: ["cloudnoise", { scale: 4 }],
    B38: ["warpnoise", { scale: 4 }],
    B39: ["drift", { count: 260, seed: 11 }]
  };

  /* 直接画：给定编号和 t，画一帧（给单画布轮播用） */
  function draw(ctx, name, w, h, t, opts) {
    var entry = NAMES[name] || NAMES.B23;
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
    var entry = NAMES[name] || NAMES.B23;
    var fn = P[entry[0]];
    if (!fn) return;
    var params = {};
    var k;
    for (k in entry[1]) params[k] = entry[1][k];
    if (opts) for (k in opts) params[k] = opts[k];
    var ctx = canvas.getContext("2d");
    if (!ctx) return;
    canvas.width = 1080; canvas.height = 1920;
    /* 颜色不用改 pattern 本身：整层用 CSS filter 调。
       invert:1  → 白点变黑点（浅底用）
       hue:180   → 换色相（冷青 → 暖橙这类）
       saturate  → 降低或提高饱和度
       这三个都写进 background_params，和 step/count 一样能调。 */
    (function () {
      var f = [];
      if (opts && (opts.invert === 1 || opts.invert === true)) { f.push("invert(1)"); }
      if (opts && opts.hue != null) { f.push("hue-rotate(" + Number(opts.hue) + "deg)"); }
      if (opts && opts.saturate != null) { f.push("saturate(" + Number(opts.saturate) + ")"); }
      if (opts && opts.brightness != null) { f.push("brightness(" + Number(opts.brightness) + ")"); }
      canvas.style.filter = f.length ? f.join(" ") : "";
    })();
    var last = -1;
    var stage = document.getElementById("stage");
    var dur = Number(stage && stage.getAttribute("data-duration")) || 60;
    function paint() {
      var t = timeline.time();
      if (Math.abs(t - last) < 0.02) return;
      last = t;
      fn(ctx, canvas.width, canvas.height, t, params);
    }
    window.addEventListener("hf-seek", function (e) {
      var t = (e && e.detail && e.detail.time);
      if (typeof t === "number") { last = -1; paint(); }
    });
    last = -1;
    paint();
  }

  global.bgkit = { bind: bind, draw: draw, patterns: Object.keys(NAMES), names: NAMES };
})(window);
