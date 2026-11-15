/* gltrans-kit.js — gl-transitions 运行时（WebGL 1 / GLSL ES 1.00）
 *
 * 契约（和 motion-kit / bg-kit 一致）：
 *   - 只吃 progress（0→1）。每一帧都由时间线 seek 决定，不读时钟、不读指针、不随机。
 *   - 画布属性尺寸固定 1080×1920；CSS 尺寸可以跟目标元素走，不改属性尺寸。
 *   - from / to 可以是 <img>、<canvas> 或 CSS 颜色（底色）；from 缺省 #0a0b0b。
 *
 * 用法（生产片段由 H02SX 按编号展开，模型不写这段）：
 *   glt.mount(imgOrBlockEl, 'BurnThrough', { from: '#0a0b0b', params: { burnColor: [1, .5, 0] } });
 *   var fx = glt.create(canvas, 'BurnThrough', { from: '#000', to: img });
 *   fx.draw(0.5);            // 任意一帧可重复调用，同一 p 永远同一结果
 *
 * 数据文件（shader 源 + 参数默认值）由 能力库/动效库/build_gltrans.py 生成，
 * 必须在它之前加载：<script src="gltrans-kit.js"><script src="gl-transitions.glsl.js">。
 * 来源 gl-transitions（MIT），每个 shader 保留原作者与 License 注释。
 */
(function (global) {
  'use strict';

  var VS = [
    'attribute vec2 _p;',
    'varying vec2 _uv;',
    'void main() { gl_Position = vec4(_p, 0.0, 1.0); _uv = _p * 0.5 + 0.5; }'
  ].join('\n');

  // 固定头部：progress / ratio / 两张贴图；getFromColor、getToColor 按 cover 取样式采样
  var PRELUDE = [
    'precision highp float;',
    'varying vec2 _uv;',
    'uniform sampler2D from, to;',
    'uniform float progress, ratio, _fromR, _toR;',
    'vec4 getFromColor(vec2 uv) {',
    '  return texture2D(from, 0.5 + (uv - 0.5) * vec2(min(ratio / _fromR, 1.0), min(_fromR / ratio, 1.0)));',
    '}',
    'vec4 getToColor(vec2 uv) {',
    '  return texture2D(to, 0.5 + (uv - 0.5) * vec2(min(ratio / _toR, 1.0), min(_toR / ratio, 1.0)));',
    '}'
  ].join('\n');

  var EPILOGUE = 'void main() { gl_FragColor = transition(_uv); }';
  var PLANE = new Float32Array([-1, -1, 3, -1, -1, 3]);

  var REG = {};

  /* ---------------------------------------------------------------- 注册表 */

  function register(name, def) {
    if (!name || !def || !def.src) return;
    REG[name] = def;
  }

  function registerAll(table) {
    if (!table) return;
    for (var k in table) {
      if (Object.prototype.hasOwnProperty.call(table, k)) register(k, table[k]);
    }
  }

  function names() {
    var out = [];
    for (var k in REG) if (Object.prototype.hasOwnProperty.call(REG, k)) out.push(k);
    return out.sort();
  }

  function has(name) {
    return !!REG[name];
  }

  /* ---------------------------------------------------------------- 工具 */

  function clamp01(v) {
    v = Number(v);
    if (!isFinite(v)) return 0;
    return v < 0 ? 0 : (v > 1 ? 1 : v);
  }

  function hexToRgba(css) {
    if (!css || typeof css !== 'string') return null;
    var s = css.trim().replace(/^#/, '');
    if (s.length === 3 || s.length === 4) {
      s = s.split('').map(function (ch) { return ch + ch; }).join('');
    }
    if (!/^[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$/.test(s)) return null;
    var r = parseInt(s.slice(0, 2), 16);
    var g = parseInt(s.slice(2, 4), 16);
    var b = parseInt(s.slice(4, 6), 16);
    var a = s.length === 8 ? parseInt(s.slice(6, 8), 16) : 255;
    return [r, g, b, a];
  }

  function solidSource(rgba) {
    var c = document.createElement('canvas');
    c.width = 1;
    c.height = 1;
    var ctx = c.getContext('2d');
    ctx.fillStyle = 'rgba(' + rgba[0] + ',' + rgba[1] + ',' + rgba[2] + ',' + (rgba[3] / 255) + ')';
    ctx.fillRect(0, 0, 1, 1);
    c.__solid = true;
    return c;
  }

  function context(canvas) {
    var opts = { premultipliedAlpha: false, alpha: true, antialias: false, depth: false, preserveDrawingBuffer: true };
    return canvas.getContext('webgl', opts) || canvas.getContext('experimental-webgl', opts);
  }

  function compile(gl, type, src) {
    var sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
      var log = gl.getShaderInfoLog(sh) || 'shader compile failed';
      gl.deleteShader(sh);
      throw new Error(log);
    }
    return sh;
  }

  function numeric(type, arr) {
    var i, out = [];
    if (/bool|bvec/.test(type)) {
      for (i = 0; i < arr.length; i++) out.push(arr[i] === true || arr[i] === 1 || arr[i] === '1' ? 1 : 0);
      return out;
    }
    if (/int|ivec/.test(type)) {
      for (i = 0; i < arr.length; i++) out.push(Math.round(Number(arr[i]) || 0));
      return out;
    }
    for (i = 0; i < arr.length; i++) out.push(Number(arr[i]) || 0);
    return out;
  }

  /* ---------------------------------------------------------------- 贴图 */

  function upload(gl, source) {
    var tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    var w = source.naturalWidth || source.videoWidth || source.width || 1;
    var h = source.naturalHeight || source.videoHeight || source.height || 1;
    return { tex: tex, w: w, h: h };
  }

  function loaded(source) {
    if (!source) return false;
    if (source.__solid) return true;
    if (source.tagName === 'IMG') return !!(source.complete && source.naturalWidth);
    return !!(source.width && source.height);
  }

  /* ---------------------------------------------------------------- create */

  function create(canvas, name, opts) {
    opts = opts || {};
    var def = REG[name];
    if (!canvas || !def) return null;
    var gl = context(canvas);
    if (!gl) return null;

    var prog;
    try {
      prog = gl.createProgram();
      gl.attachShader(prog, compile(gl, gl.VERTEX_SHADER, VS));
      gl.attachShader(prog, compile(gl, gl.FRAGMENT_SHADER, PRELUDE + '\n' + def.src + '\n' + EPILOGUE));
      gl.bindAttribLocation(prog, 0, '_p');
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(prog) || 'program link failed');
      }
    } catch (err) {
      if (global.console && console.warn) console.warn('[glt] ' + name + ': ' + err.message);
      return null;
    }

    var buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, PLANE, gl.STATIC_DRAW);

    var locCache = {};
    function loc(n) {
      if (!(n in locCache)) locCache[n] = gl.getUniformLocation(prog, n);
      return locCache[n];
    }

    var params = {};
    var defaults = def.params || {};
    for (var k in defaults) {
      if (!Object.prototype.hasOwnProperty.call(defaults, k)) continue;
      var given = opts.params && Object.prototype.hasOwnProperty.call(opts.params, k) ? opts.params[k] : null;
      params[k] = given == null ? defaults[k].default : given;
    }

    var fromSrc = opts.from;
    if (fromSrc == null) fromSrc = '#0a0b0b';
    var fromSolid = typeof fromSrc === 'string' ? hexToRgba(fromSrc) : null;
    var fromImage = fromSolid ? solidSource(fromSolid) : fromSrc;
    var toImage = opts.to || null;

    var texFrom = loaded(fromImage) ? upload(gl, fromImage) : null;
    var texTo = null;

    function ensureTo() {
      if (texTo || !loaded(toImage)) return;
      texTo = upload(gl, toImage);
    }
    if (toImage && toImage.tagName === 'IMG' && !loaded(toImage)) {
      toImage.addEventListener('load', function () { ensureTo(); draw(lastP); });
    }
    ensureTo();

    var lastP = 0;

    function setUniforms() {
      gl.useProgram(prog);
      for (var u in params) {
        if (!Object.prototype.hasOwnProperty.call(params, u)) continue;
        var meta = defaults[u];
        if (!meta) continue;
        var vals = numeric(meta.type, Array.isArray(params[u]) ? params[u] : [params[u]]);
        var n = vals.length;
        var isInt = /int|bool|ivec|bvec/.test(meta.type);
        var name = (isInt ? 'uniform' + n + 'i' : 'uniform' + n + 'f') + 'v';
        var l = loc(u);
        // 注意：WebGL 方法必须带着上下文调用，抽出来直接 fn() 会 Illegal invocation
        if (!gl[name] || l === null) continue;
        gl[name](l, isInt ? new Int32Array(vals) : new Float32Array(vals));
      }
    }

    function draw(p) {
      lastP = clamp01(p);
      ensureTo();
      if (!texFrom || !texTo) return false;
      gl.useProgram(prog);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.enableVertexAttribArray(0);
      gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, texFrom.tex);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, texTo.tex);
      gl.uniform1i(loc('from'), 0);
      gl.uniform1i(loc('to'), 1);
      gl.uniform1f(loc('progress'), lastP);
      gl.uniform1f(loc('ratio'), canvas.width / canvas.height);
      gl.uniform1f(loc('_fromR'), texFrom.w / texFrom.h);
      gl.uniform1f(loc('_toR'), texTo.w / texTo.h);
      setUniforms();
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      return true;
    }

    var api = {
      ok: true,
      name: name,
      meta: def.meta || {},
      params: params,
      canvas: canvas,
      ready: function () { return !!(texFrom && texTo); },
      draw: draw,
      progress: function () { return lastP; }
    };
    api.draw(0);
    return api;
  }

  /* ---------------------------------------------------------------- mount */

  // 把 shader 盖在一个照片元素（<img> 或带 background-image 的块）上。
  // 目标框由 HTML 给，运行时只读一次位置，不参与布局计算。
  function mount(el, name, opts) {
    opts = opts || {};
    if (!el) return null;
    var img = null;
    var host = el;
    if (el.tagName === 'IMG') {
      img = el;
      host = el.parentNode || el;
    } else {
      var bg = (global.getComputedStyle ? getComputedStyle(el).backgroundImage : '') || '';
      var m = bg.match(/url\(["']?(.*?)["']?\)/);
      if (!m) return null;
      img = new Image();
      img.src = m[1];
    }
    var box = null;
    // offset* 不受祖先 transform 缩放影响；拿不到时退回 rect
    if (host && el.offsetParent === host) {
      box = { left: el.offsetLeft, top: el.offsetTop, width: el.offsetWidth, height: el.offsetHeight };
    } else if (el.getBoundingClientRect && host.getBoundingClientRect) {
      var r = el.getBoundingClientRect();
      var hr = host.getBoundingClientRect();
      box = { left: r.left - hr.left, top: r.top - hr.top, width: r.width, height: r.height };
    }
    if (!box || !box.width || !box.height) return null;
    if (host && global.getComputedStyle && getComputedStyle(host).position === 'static') {
      host.style.position = 'relative';
    }
    var cv = document.createElement('canvas');
    cv.width = 1080;
    cv.height = 1920;
    cv.setAttribute('data-gltrans', name);
    cv.style.cssText = 'position:absolute;display:block;pointer-events:none;z-index:3;'
      + 'left:' + box.left + 'px;top:' + box.top + 'px;'
      + 'width:' + box.width + 'px;height:' + box.height + 'px;';
    var fx = create(cv, name, { from: opts.from, to: img, params: opts.params });
    if (!fx) return null;
    host.appendChild(cv);
    fx.el = el;
    return fx;
  }

  global.glt = {
    register: register,
    registerAll: registerAll,
    names: names,
    has: has,
    create: create,
    mount: mount,
    count: function () { return names().length; }
  };
})(window);
