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

  /* ── magicui 批（2026-11-17，MIT）：B49 抖动网点 / B50 透视网格 / B51 流星 ──
   * 全部是 t 的纯函数：同一个 t 画出来永远一样，可 seek、可复现，不用 Math.random。 */
  var BAYER8 = [0,32,8,40,2,34,10,42, 48,16,56,24,50,18,58,26,
                12,44,4,36,14,46,6,38, 60,28,52,20,62,30,54,22,
                3,35,11,43,1,33,9,41, 51,19,59,27,49,17,57,25,
                15,47,7,39,13,45,5,37, 63,31,55,23,61,29,53,21];

  /* B49 抖动网点：低日 + 雾带算出一张明度场，按 8×8 Bayer 阈值排方块点 */
  P.dither = function (c, w, h, t, o) {
    var cell = o.cell || 8, lv = (o.lv == null ? 0.62 : o.lv);
    c.clearRect(0, 0, w, h);
    var cx = w * 0.5, cy = h * 1.06, R = Math.max(w * 0.58, h * 0.5);
    var breathe = 0.86 + 0.14 * (0.5 + 0.5 * Math.sin(t * 0.9));
    for (var j = 0; j * cell < h; j++) {
      for (var i = 0; i * cell < w; i++) {
        var px = i * cell + cell / 2, py = j * cell + cell / 2;
        var dx = (px - cx) / (R * 1.25), dy = (py - cy) / R;
        var d = Math.sqrt(dx * dx + dy * dy);
        var sun = Math.exp(-3.2 * Math.max(d - 0.34, 0));
        var band = 0.5 + 0.5 * Math.sin(py * 0.0125 - t * 1.15);
        var haze = band * Math.exp(-(py / h) * 2.2) * 0.40;
        var L = (sun * 0.92 + haze) * breathe;
        var th = (BAYER8[(j % 8) * 8 + (i % 8)] + 0.5) / 64;
        var v = Math.pow(Math.min(1, L / Math.max(lv, 0.15)), 1.9);
        if (v <= th) continue;
        var k = Math.min(1, (v - th) * 4.5);
        var s = cell * (0.30 + 0.50 * k);
        c.fillStyle = 'rgba(206,244,230,' + (0.10 + 0.52 * Math.min(1, L)).toFixed(3) + ')';
        c.fillRect(i * cell + (cell - s) / 2, j * cell + (cell - s) / 2, s, s);
      }
    }
  };

  /* B50 透视网格：地平线在画面 61%，横线按 z 推进 */
  P.retrogrid = function (c, w, h, t, o) {
    var hz = h * (o.hz || 0.61), vx = w * 0.5, sp = (o.speed == null ? 0.55 : o.speed);
    c.clearRect(0, 0, w, h);
    var lg = c.createLinearGradient(0, hz - h * 0.17, 0, hz + h * 0.05);
    lg.addColorStop(0, 'rgba(255,150,80,0)');
    lg.addColorStop(0.55, 'rgba(255,150,80,.26)');
    lg.addColorStop(1, 'rgba(255,150,80,0)');
    c.fillStyle = lg; c.fillRect(0, hz - h * 0.17, w, h * 0.22);
    c.strokeStyle = 'rgba(134,240,192,.26)'; c.lineWidth = 1.5;
    for (var x = -1440; x <= w + 1440; x += 150) {
      c.beginPath(); c.moveTo(vx + (x - vx) * 0.02, hz); c.lineTo(x, h); c.stroke();
    }
    var f = (t * sp) % 1;
    for (var k = 1; k <= 26; k++) {
      var z = k - f; if (z <= 0.12) continue;
      var y = hz + (h * 0.62) / z;
      if (y > h + 10) continue;
      var a = Math.min(1, 2.9 / z);
      c.strokeStyle = 'rgba(150,246,206,' + (a * 0.85).toFixed(3) + ')';
      c.lineWidth = Math.max(1, 1.3 + 2.2 / z);
      c.beginPath(); c.moveTo(0, y); c.lineTo(w, y); c.stroke();
    }
  };

  /* B51 流星：18 颗错峰斜下，尾部渐隐；星点底按 t 呼吸 */
  P.meteor = function (c, w, h, t, o) {
    var n = o.count || 18, r = rng(o.seed || 77), rs = rng((o.seed || 77) + 32);
    var ANG = Math.PI * 0.155;
    c.clearRect(0, 0, w, h);
    for (var i = 0; i < 110; i++) {
      var sx = rs() * w, sy = rs() * h, ph = rs() * 6.28;
      c.fillStyle = 'rgba(205,228,255,' + (0.10 + 0.20 * (0.5 + 0.5 * Math.sin(t * 2 + ph))).toFixed(3) + ')';
      c.fillRect(sx, sy, 2.4, 2.4);
    }
    var CYC = 1.75, PER = 2.65;
    for (var m = 0; m < n; m++) {
      var x0 = r() * (w * 1.5) - w * 0.3, y0 = r() * (h * 0.46) - h * 0.26;
      var t0 = r() * PER, len = 190 + r() * 300, sp = 880 + r() * 640;
      var lw = 2 + r() * 2.4, a0 = 0.62 + r() * 0.38;
      var dt = (t - t0) % PER; if (dt < 0) dt += PER;
      if (dt > CYC) continue;
      var d = dt * sp;
      var hx = x0 + Math.sin(ANG) * d, hy = y0 + Math.cos(ANG) * d;
      if (hy > h + 40) continue;
      var fade = (dt > 0.8 ? Math.max(0, 1 - (dt - 0.8) / 0.95) : 1) * a0;
      if (fade <= 0.01) continue;
      var tx = hx - Math.sin(ANG) * len, ty = hy - Math.cos(ANG) * len;
      var lg2 = c.createLinearGradient(tx, ty, hx, hy);
      lg2.addColorStop(0, 'rgba(150,220,255,0)');
      lg2.addColorStop(0.62, 'rgba(198,238,255,' + (fade * 0.62).toFixed(3) + ')');
      lg2.addColorStop(1, 'rgba(255,255,255,' + fade.toFixed(3) + ')');
      c.strokeStyle = lg2; c.lineWidth = lw; c.lineCap = 'round';
      c.beginPath(); c.moveTo(tx, ty); c.lineTo(hx, hy); c.stroke();
      c.globalAlpha = fade * 0.95; c.fillStyle = '#f4fcff';
      c.beginPath(); c.arc(hx, hy, lw * 1.05, 0, TAU); c.fill(); c.globalAlpha = 1;
    }
  };


  /* B53 蜂巢网格：六边形点阵，按距中心波形依次亮起；t 的纯函数 */
  P.hexgrid = function (c, w, h, t, o) {
    var R = o.r || 34, lw = o.lw || 1.6;
    var dx = R * 1.732, dy = R * 1.5;
    c.clearRect(0, 0, w, h);
    var cx0 = w * 0.5, cy0 = h * 0.46;
    for (var row = -1; row * dy < h + dy; row++) {
      for (var col = -1; col * dx < w + dx; col++) {
        var x = col * dx + (row % 2 ? dx / 2 : 0);
        var y = row * dy;
        var d = Math.sqrt((x - cx0) * (x - cx0) + (y - cy0) * (y - cy0)) / Math.max(w, h);
        var wave = 0.5 + 0.5 * Math.sin(t * 1.5 - d * 11);
        var a = (0.05 + 0.30 * wave * wave).toFixed(3);
        c.beginPath();
        for (var k = 0; k < 6; k++) {
          var ang = Math.PI / 180 * (60 * k - 30);
          var px = x + R * 0.96 * Math.cos(ang), py = y + R * 0.96 * Math.sin(ang);
          if (k === 0) c.moveTo(px, py); else c.lineTo(px, py);
        }
        c.closePath();
        c.strokeStyle = 'rgba(134,240,192,' + a + ')';
        c.lineWidth = lw;
        c.stroke();
      }
    }
  };

  /* B54 纵深粒子场：伪 3D 点云向观察者漂移，近大远小；z 按周期回绕，可 seek */
  var _depPts = null;
  P.depthdust = function (c, w, h, t, o) {
    var N = o.count || 220, sp = (o.speed == null ? 0.22 : o.speed);
    var F = o.focal || 0.9;
    if (!_depPts || _depPts.length !== N) {
      var r = rng(o.seed || 12);
      _depPts = [];
      for (var i = 0; i < N; i++) {
        _depPts.push([r() * 2 - 1, r() * 2 - 1, 0.12 + r() * 0.88, 0.6 + r() * 0.8]);
      }
    }
    c.clearRect(0, 0, w, h);
    var cx0 = w * 0.5, cy0 = h * 0.5;
    for (var j = 0; j < N; j++) {
      var p = _depPts[j];
      var z = p[2] - (t * sp) % 1;
      if (z <= 0.06) z += 0.92;
      var k = F / z;
      var px = cx0 + p[0] * w * 0.32 * k;
      var py = cy0 + p[1] * h * 0.30 * k;
      if (px < -40 || px > w + 40 || py < -40 || py > h + 40) continue;
      var s = 1.2 + 3.4 * k * 0.34;
      var a = Math.min(0.85, 0.08 + 0.55 * k * 0.34);
      c.fillStyle = 'rgba(180,222,255,' + a.toFixed(3) + ')';
      c.beginPath(); c.arc(px, py, s, 0, TAU); c.fill();
    }
  };

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
    B39: ["drift", { count: 260, seed: 11 }],
    B49: ["dither", { cell: 8, lv: 0.62 }],
    B50: ["retrogrid", { hz: 0.61, speed: 0.55 }],
    B51: ["meteor", { count: 18, seed: 77 }],
    B53: ["hexgrid", { r: 34, lw: 1.6 }],
    B54: ["depthdust", { count: 220, speed: 0.22, focal: 0.9 }]
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
