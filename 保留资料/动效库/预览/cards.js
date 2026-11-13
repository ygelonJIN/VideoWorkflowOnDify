/* 由 build_presets.py 从 presets.json 生成，不要手改 */
window.CARDS = {
 "T01": {
  "id": "T01",
  "name": "逐字上浮",
  "family": "入场",
  "layer": "",
  "params": {
   "unit": "char",
   "y": "0.5em",
   "stagger": 0.05,
   "ease": "power3.out",
   "dur": 0.55
  },
  "code": "var _c = kit.split('{{sel}}', 'chars');\ntimeline.fromTo(_c, {opacity:0, y:'0.5em'},\n  {opacity:1, y:0, duration:{{dur}}, ease:'power3.out', stagger:{{stagger}}}, {{at}});",
  "use": "标题、一句话强调；字数 ≤ 14"
 },
 "T02": {
  "id": "T02",
  "name": "模糊聚焦",
  "family": "入场",
  "layer": "",
  "params": {
   "unit": "word",
   "blur": "10px",
   "y": "50px",
   "stagger": 0.05,
   "dur": 0.35
  },
  "code": "var _w = kit.split('{{sel}}', 'words');\ntimeline.fromTo(_w, {opacity:0, filter:'blur(10px)', y:50},\n  {opacity:1, filter:'blur(0px)', y:0, duration:{{dur}}, ease:'power2.out', stagger:{{stagger}}}, {{at}});",
  "use": "副标题、解释性文字；有照片底时更明显"
 },
 "T03": {
  "id": "T03",
  "name": "折页落字",
  "family": "入场",
  "layer": "",
  "params": {
   "unit": "char",
   "angle": 92,
   "perspective": 700,
   "stagger": 0.045,
   "dur": 0.65
  },
  "code": "var _c = kit.split('{{sel}}', 'chars');\ntimeline.fromTo(_c, {opacity:0, rotationX:92, transformOrigin:'50% 0%', transformPerspective:700},\n  {opacity:1, rotationX:0, duration:{{dur}}, ease:'power3.out', stagger:{{stagger}}}, {{at}});",
  "use": "标题、引句；垂直节奏强的版面"
 },
 "T04": {
  "id": "T04",
  "name": "描边写字",
  "family": "绘制",
  "layer": "",
  "params": {
   "strokeWidth": 1.4,
   "drawDuration": 1.6,
   "fillDelay": 0.2,
   "dur": 0.4,
   "color": "#38d6ff"
  },
  "code": "var _t = document.querySelector('{{sel}}');\n_t.style.webkitTextStroke = '1.4px currentColor';\n_t.style.color = 'transparent';\ntimeline.to(_t, {color:'{{color}}', duration:0.4, ease:'power1.out'}, {{at}}+{{dur}});",
  "use": "关键词强调；一句里只做一个词"
 },
 "T05": {
  "id": "T05",
  "name": "打字机",
  "family": "入场",
  "layer": "",
  "params": {
   "speed": 0.05,
   "hold": 0.8,
   "cursor": true
  },
  "code": "var _t = document.querySelector('{{sel}}');\nvar _txt = _t.textContent; _t.textContent = '';\nfor (var i = 1; i <= _txt.length; i++) {\n  timeline.set(_t, {textContent: _txt.slice(0, i)}, {{at}} + i*0.05);\n}",
  "use": "代码、命令行、对话式文案"
 },
 "T06": {
  "id": "T06",
  "name": "数字递增",
  "family": "状态",
  "layer": "",
  "params": {
   "from": 0,
   "to": 100,
   "dur": 1.2
  },
  "code": "var _n = document.querySelector('{{sel}}');\nvar _o = {'v':{{from}}};\ntimeline.to(_o, {'v':{{to}}, 'duration':{{dur}}, 'ease':'power2.out',\n  'onUpdate':function(){ _n.textContent = Math.round(_o.v); }}, {{at}});",
  "use": "数据、金额、百分比；必须有语义"
 },
 "T07": {
  "id": "T07",
  "name": "字符乱码收敛",
  "family": "入场",
  "layer": "",
  "params": {
   "chars": ":.",
   "stagger": 0.03,
   "seed": 7,
   "dur": 1.2
  },
  "code": "/* 固定种子，渲染可复现 */\nvar _r = kit.seeded(7), _t = document.querySelector('{{sel}}');\nvar _final = _t.textContent, _sp = ':.'; _t.textContent = '';\nfor (var i = 0; i < _final.length; i++) {\n  (function (idx) {\n    timeline.set(_t, {textContent: _final.slice(0, idx) + _sp[(idx + 1) % _sp.length]}, {{at}} + idx * 0.03);\n    timeline.set(_t, {textContent: _final.slice(0, idx + 1)}, {{at}} + idx * 0.03 + 0.09);\n  })(i);\n}\ntimeline.set(_t, {textContent: _final}, {{at}} + _final.length * 0.03);",
  "use": "科技感标题；与代码/数据主题匹配"
 },
 "T08": {
  "id": "T08",
  "name": "解密揭示",
  "family": "入场",
  "layer": "",
  "params": {
   "chars": "ABCDEF0123",
   "seed": 11,
   "dur": 0.9
  },
  "code": "var _r = kit.seeded(11), _t = document.querySelector('{{sel}}');\nvar _final = _t.textContent, _c = 'ABCDEF0123';\nfor (var i = 0; i < _final.length; i++) {\n  (function (idx) {\n    timeline.set(_t, {textContent: _final.slice(0, idx) + _c[Math.floor(_r() * _c.length)]}, {{at}} + idx * 0.04);\n    timeline.set(_t, {textContent: _final.slice(0, idx + 1)}, {{at}} + idx * 0.04 + 0.08);\n  })(i);\n}",
  "use": "关键词、代号、版本号"
 },
 "T09": {
  "id": "T09",
  "name": "翻牌落字",
  "family": "入场",
  "layer": "",
  "params": {
   "flipDuration": 0.12,
   "stagger": 0.06,
   "cycles": 3,
   "dur": 0.5
  },
  "code": "/* 每字上下两片，rotationX 由 -90 收敛到 0，翻 3 次落定 */\nvar _c = kit.split('{{sel}}', 'chars');\n_c.forEach(function (el, i) {\n  el.style.transformStyle = 'preserve-3d';\n  timeline.fromTo(el, {rotationX: -90, opacity: 0},\n    {rotationX: 0, opacity: 1, duration: {{dur}}, ease: 'back.out(1.4)'}, {{at}} + i * 0.06);\n});",
  "use": "短词、价格、倒计时类信息"
 },
 "T10": {
  "id": "T10",
  "name": "环形文字流",
  "family": "空间",
  "layer": "",
  "params": {
   "arc": 120,
   "radius": 420,
   "speed": 0.9,
   "dur": 0.6
  },
  "code": "/* 单次沿弧线摆位，不循环 */\nvar _c = kit.split('{{sel}}', 'chars');\nvar _n = _c.length;\n_c.forEach(function (el, i) {\n  var a = (-60 + (120 / Math.max(1, _n - 1)) * i) * Math.PI / 180;\n  timeline.fromTo(el,\n    {x: 0, y: 0, rotation: a * 57.3, opacity: 0},\n    {x: Math.sin(a) * 420, y: (1 - Math.cos(a)) * 420, opacity: 1,\n     duration: {{dur}}, ease: 'power2.out'}, {{at}} + i * 0.05);\n});",
  "use": "片头 2-3 秒；品牌名重复"
 },
 "T11": {
  "id": "T11",
  "name": "回声拖影",
  "family": "入场",
  "layer": "",
  "params": {
   "echoes": 8,
   "lag": 0.12,
   "offset": 36,
   "fade": 0.72
  },
  "code": "var _c = kit.split('{{sel}}', 'chars');\nfor (var i = 0; i < 8; i++) {\n  timeline.fromTo(_c, {opacity:0, x:i*36, filter:'blur(3px)'},\n    {opacity:0.35*(1-i/8), x:0, filter:'blur(0px)', duration:0.5, ease:'power2.out', stagger:0.03},\n    {{at}} + i*0.04);\n}",
  "use": "速度感标题；配合推镜"
 },
 "P01": {
  "id": "P01",
  "name": "聚光跟随",
  "family": "空间",
  "layer": "",
  "params": {
   "size": "340px",
   "alpha": 0.42,
   "dur": 1.2
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  _b.style.position = _b.style.position || 'relative';\n  var _s = document.createElement('i');\n  _s.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:26;';\n  _b.appendChild(_s);\n  var _o = {'x': 22, 'y': 78};\n  function _paint() {\n    _s.style.background = 'radial-gradient({{size}} {{size}} at ' + _o.x + '% ' + _o.y + '%, rgba(255,240,210,{{alpha}}), transparent 70%)';\n  }\n  _paint();\n  timeline.fromTo(_o, {'x': 22, 'y': 78}, {'x': 64, 'y': 34, 'duration':{{dur}}, 'ease':'power2.inOut', 'onUpdate':_paint}, {{at}});\n})();",
  "use": "聚光点跟着走；暗底、人像特写"
 },
 "P02": {
  "id": "P02",
  "name": "边缘受光",
  "family": "空间",
  "layer": "",
  "params": {
   "radius": 520,
   "alpha": 0.6,
   "dur": 1.0
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  _b.style.position = _b.style.position || 'relative';\n  var _e = document.createElement('i');\n  _e.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:25;opacity:0;background:radial-gradient({{radius}}px {{radius}}px at 78% 28%, rgba(255,240,210,.55), transparent 64%)';\n  _b.appendChild(_e);\n  timeline.to(_e, {'opacity':{{alpha}}, 'duration':{{dur}}, 'ease':'power2.inOut'}, {{at}});\n})();",
  "use": "边缘受光：一层偏侧的暖光，暗底照片上用"
 },
 "P03": {
  "id": "P03",
  "name": "跟随倾斜",
  "family": "空间",
  "layer": "",
  "params": {
   "rx": 5,
   "ry": 7,
   "perspective": 1200,
   "dur": 0.8
  },
  "code": "timeline.fromTo('{{sel}}', {'rotationX': -{{rx}}, 'rotationY': -{{ry}}, 'transformPerspective': {{perspective}}},\n  {'rotationX':0, 'rotationY':0, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});",
  "use": "跟随倾斜：给照片块一点 3D 角度，再落正"
 },
 "W01": {
  "id": "W01",
  "name": "照片包裹",
  "family": "结构",
  "layer": "",
  "params": {
   "r": 26,
   "dur": 0.6
  },
  "code": "timeline.fromTo('{{sel}}', {'borderRadius':'0px', 'scale':1.03, 'overflow':'hidden'},\n  {'borderRadius':'{{r}}px', 'scale':1, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});",
  "use": "给照片块加圆角 + 轻微落定；不新增图形"
 },
 "X01": {
  "id": "X01",
  "name": "擦除切换",
  "family": "结构",
  "layer": "",
  "params": {
   "direction": "up",
   "dur": 0.8
  },
  "code": "timeline.fromTo('{{sel}}', {clipPath:'inset(100% 0% 0% 0%)'},\n  {clipPath:'inset(0% 0% 0% 0%)', duration:{{dur}}, ease:'power3.inOut'}, {{at}});",
  "use": "同屏内容替换：一版换成另一版"
 },
 "B23": {
  "id": "B23",
  "name": "半调网点",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "网点密度随位置变化；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B24": {
  "id": "B24",
  "name": "扫描线",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "细线 + 扫描带；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B25": {
  "id": "B25",
  "name": "点阵辉光",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "密集点阵，中心亮；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B26": {
  "id": "B26",
  "name": "同心环",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "单次扩散的圆环；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B27": {
  "id": "B27",
  "name": "等高线",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "波纹线场；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B28": {
  "id": "B28",
  "name": "横向拉丝",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "细横线掠过；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B29": {
  "id": "B29",
  "name": "雪点",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "漂浮小点；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B30": {
  "id": "B30",
  "name": "雨丝",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "斜向雨丝；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B31": {
  "id": "B31",
  "name": "像素溶解",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "像素块聚散；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B32": {
  "id": "B32",
  "name": "棋盘",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "明暗方格；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B33": {
  "id": "B33",
  "name": "纸纹",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "纤维 + 光带；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B34": {
  "id": "B34",
  "name": "光束",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "锥形光；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B35": {
  "id": "B35",
  "name": "浮尘",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "漂浮颗粒；canvas 背景，由 bgkit 按 t 重绘"
 },
 "B36": {
  "id": "B36",
  "name": "渐变网格",
  "family": "背景",
  "layer": "overlay",
  "params": {},
  "code": "/* canvas 背景：由 H02SX 调 bgkit.bind/ draw，不展开 GSAP */",
  "use": "四色光斑游走；canvas 背景，由 bgkit 按 t 重绘"
 },
 "C01": {
  "id": "C01",
  "name": "缓推",
  "family": "镜头",
  "layer": "media",
  "params": {
   "to": 1.06,
   "dur": 4.0
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':1}, {'scale':{{to}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});",
  "use": "整屏缓推；照片、满屏图层、图块都行"
 },
 "C02": {
  "id": "C02",
  "name": "缓拉",
  "family": "镜头",
  "layer": "media",
  "params": {
   "from": 1.08,
   "dur": 4.0
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':{{from}}}, {'scale':1, 'duration':{{dur}}, 'ease':'none'}, {{at}});",
  "use": "开场收束、结尾释放"
 },
 "C03": {
  "id": "C03",
  "name": "横移",
  "family": "镜头",
  "layer": "media",
  "params": {
   "from": -3,
   "to": 3,
   "dur": 4.0
  },
  "code": "timeline.fromTo('{{sel}}', {'xPercent':{{from}}}, {'xPercent':{{to}}, 'duration':{{dur}}, 'ease':'sine.inOut'}, {{at}});",
  "use": "左右取景，配合文字固定"
 },
 "L01": {
  "id": "L01",
  "name": "双层视差",
  "family": "层",
  "layer": "layer",
  "params": {
   "a": -2,
   "b": 2,
   "a2": 1,
   "b2": -1,
   "dur": 4.0
  },
  "code": "timeline.fromTo('{{sel}}', {'xPercent':{{a}}}, {'xPercent':{{b}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\ntimeline.fromTo('{{sel2}}', {'xPercent':{{a2}}}, {'xPercent':{{b2}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});",
  "use": "前景和背景反向走；字层不动"
 },
 "D01": {
  "id": "D01",
  "name": "呼吸",
  "family": "环境",
  "layer": "media",
  "params": {
   "to": 1.025,
   "dur": 4.0
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':1}, {'scale':{{to}}, 'duration':{{dur}}, 'ease':'sine.inOut'}, {{at}});",
  "use": "停留段保持画面微动；上限 3%"
 },
 "K03": {
  "id": "K03",
  "name": "逐字错位",
  "family": "字形",
  "layer": "element",
  "params": {
   "rot": 4,
   "dur": 0.62,
   "stagger": 0.035,
   "seed": 13
  },
  "code": "var _c = kit.split('{{sel}}', 'chars'), _r = kit.seeded({{seed}});\n_c.forEach(function (el, i) {\n  var _dy = 12 + _r() * 26, _rt = (_r() * 2 - 1) * {{rot}};\n  timeline.fromTo(el, {'yPercent':_dy, 'rotation':_rt, 'opacity':0},\n    {'yPercent':0, 'rotation':0, 'opacity':1, 'duration':{{dur}}, 'ease':'power3.out'}, {{at}} + i * {{stagger}});\n});",
  "use": "大标题、短句；一眼看出是排出来的"
 },
 "K05": {
  "id": "K05",
  "name": "遮罩揭示",
  "family": "字形",
  "layer": "element",
  "params": {
   "dur": 0.7
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'inset(0% 100% 0% 0%)'},\n  {'clipPath':'inset(0% 0% 0% 0%)', 'duration':{{dur}}, 'ease':'power3.inOut'}, {{at}});",
  "use": "标题从一边揭开；比淡入有方向"
 },
 "K06": {
  "id": "K06",
  "name": "荧光笔",
  "family": "字形",
  "layer": "element",
  "params": {
   "color": "#F2C14E",
   "dur": 0.5
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _h = document.createElement('i');\n  _h.style.cssText = 'position:absolute;left:-.06em;right:-.06em;bottom:.04em;height:.44em;background:' + '{{color}}' + ';mix-blend-mode:multiply;transform:scaleX(0);transform-origin:0 50%;z-index:0;';\n  _t.appendChild(_h);\n  timeline.to(_h, {'scaleX':1, 'duration':{{dur}}, 'ease':'power2.inOut'}, {{at}});\n})();",
  "use": "关键词被扫过；浅底专用"
 },
 "G01": {
  "id": "G01",
  "name": "角标",
  "family": "版面",
  "layer": "overlay",
  "params": {
   "len": 26,
   "color": "rgba(255,255,255,.45)",
   "dur": 0.45
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}'), _l = {{len}}, _c = '{{color}}';\n  if (!_b) return;\n  var _css = ['left:0;top:0;border-right:0;border-bottom:0', 'right:0;top:0;border-left:0;border-bottom:0',\n              'left:0;bottom:0;border-right:0;border-top:0', 'right:0;bottom:0;border-left:0;border-top:0'];\n  var _els = _css.map(function (s) {\n    var d = document.createElement('i');\n    d.style.cssText = 'position:absolute;width:' + _l + 'px;height:' + _l + 'px;border:1px solid ' + _c + ';' + s + ';transform:scale(0);';\n    _b.appendChild(d);\n    return d;\n  });\n  timeline.to(_els, {'scale':1, 'duration':{{dur}}, 'ease':'power2.out', 'stagger':0.06}, {{at}});\n})();",
  "use": "杂志框，给画面一个边界"
 },
 "X03": {
  "id": "X03",
  "name": "逐项离场",
  "family": "离场",
  "layer": "element",
  "params": {
   "dist": 40,
   "dur": 0.42,
   "stagger": 0.05
  },
  "code": "timeline.to('{{sel}}', {'opacity':0, 'y':-{{dist}}, 'duration':{{dur}}, 'ease':'power2.in', 'stagger':{{stagger}}}, {{at}});",
  "use": "一切屏的收尾；切点前 0.35–0.5s 走完"
 },
 "X05": {
  "id": "X05",
  "name": "反向飞出",
  "family": "离场",
  "layer": "element",
  "params": {
   "dist": 90,
   "dur": 0.4,
   "stagger": 0.04
  },
  "code": "timeline.to('{{sel}}', {'opacity':0, 'x':{{dist}}, 'duration':{{dur}}, 'ease':'power2.in', 'stagger':{{stagger}}}, {{at}});",
  "use": "横向切镜前的收尾"
 },
 "K01": {
  "id": "K01",
  "name": "超大字落版",
  "family": "字形",
  "layer": "element",
  "params": {
   "from": 1.22,
   "y": 12,
   "dur": 0.8
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':{{from}}, 'yPercent':{{y}}, 'opacity':0, 'transformOrigin':'0% 100%'},\n  {'scale':1, 'yPercent':0, 'opacity':1, 'duration':{{dur}}, 'ease':'power3.out'}, {{at}});",
  "use": "标题字号 ≥ 140px 时用；落定的那一下就是重量"
 },
 "K04": {
  "id": "K04",
  "name": "字距收紧",
  "family": "字形",
  "layer": "element",
  "params": {
   "from": "0.14em",
   "to": "-0.02em",
   "dur": 0.75
  },
  "code": "timeline.fromTo('{{sel}}', {'letterSpacing':'{{from}}', 'opacity':0},\n  {'letterSpacing':'{{to}}', 'opacity':1, 'duration':{{dur}}, 'ease':'power3.out'}, {{at}});",
  "use": "一行字的收束；配合超大字最明显"
 },
 "K07": {
  "id": "K07",
  "name": "手绘下划线",
  "family": "字形",
  "layer": "element",
  "params": {
   "h": 6,
   "color": "#D8452C",
   "dur": 0.6
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _l = document.createElement('i');\n  _l.style.cssText = 'position:absolute;left:0;right:0;bottom:-.08em;height:{{h}}px;background:{{color}};transform:scaleX(0);transform-origin:0 50%;border-radius:2px;z-index:0;';\n  _t.appendChild(_l);\n  timeline.to(_l, {'scaleX':1, 'duration':{{dur}}, 'ease':'power2.inOut'}, {{at}});\n})();",
  "use": "一个词被划上重点；比加粗自然"
 },
 "K08": {
  "id": "K08",
  "name": "手绘圈",
  "family": "字形",
  "layer": "element",
  "params": {
   "w": 3,
   "color": "#D8452C",
   "dur": 0.55
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _c = document.createElement('i');\n  _c.style.cssText = 'position:absolute;left:-.16em;right:-.16em;top:-.12em;bottom:-.16em;border:{{w}}px solid {{color}};border-radius:50%;transform:scale(.6);opacity:0;z-index:0;';\n  _t.appendChild(_c);\n  timeline.to(_c, {'scale':1, 'opacity':1, 'duration':{{dur}}, 'ease':'back.out(1.6)'}, {{at}});\n})();",
  "use": "圈住一个数字或短词"
 },
 "K09": {
  "id": "K09",
  "name": "打字机",
  "family": "字形",
  "layer": "element",
  "params": {
   "speed": 0.05
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  var _txt = _t.textContent; _t.textContent = '';\n  for (var i = 1; i <= _txt.length; i++) {\n    timeline.set(_t, {'textContent': _txt.slice(0, i)}, {{at}} + i * {{speed}});\n  }\n})();",
  "use": "代码、命令行、对话；一行内讲完"
 },
 "K10": {
  "id": "K10",
  "name": "竖排",
  "family": "字形",
  "layer": "element",
  "params": {
   "dur": 0.8
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.writingMode = 'vertical-rl';\n  _t.style.display = 'inline-block';\n  _t.style.letterSpacing = '.1em';\n  timeline.fromTo(_t, {'clipPath':'inset(0% 0% 100% 0%)'},\n    {'clipPath':'inset(0% 0% 0% 0%)', 'duration':{{dur}}, 'ease':'power3.inOut'}, {{at}});\n})();",
  "use": "四到八个字的标题；竖屏天生适合"
 },
 "K12": {
  "id": "K12",
  "name": "删除线",
  "family": "字形",
  "layer": "element",
  "params": {
   "h": 5,
   "color": "#D8452C",
   "dur": 0.45
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _l = document.createElement('i');\n  _l.style.cssText = 'position:absolute;left:-.02em;right:-.02em;top:.54em;height:{{h}}px;background:{{color}};transform:scaleX(0);transform-origin:0 50%;z-index:0;';\n  _t.appendChild(_l);\n  timeline.to(_l, {'scaleX':1, 'duration':{{dur}}, 'ease':'power2.inOut'}, {{at}});\n})();",
  "use": "否定一个旧说法，再给新的"
 },
 "K13": {
  "id": "K13",
  "name": "描边字",
  "family": "字形",
  "layer": "element",
  "params": {
   "w": 1.6,
   "color": "#F2EFE6",
   "dur": 0.7
  },
  "code": "timeline.fromTo('{{sel}}', {'webkitTextStroke':'{{w}}px currentColor', 'color':'transparent'},\n  {'color':'{{color}}', 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});",
  "use": "大字先以线出现，再填实"
 },
 "S02": {
  "id": "S02",
  "name": "进度填充",
  "family": "状态",
  "layer": "element",
  "params": {
   "to": 72,
   "h": 6,
   "color": "#7BE8BE",
   "dur": 1.0
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _b = document.createElement('i');\n  _b.style.cssText = 'position:absolute;left:0;bottom:0;height:{{h}}px;width:0%;background:{{color}};border-radius:2px;';\n  _t.appendChild(_b);\n  timeline.to(_b, {'width':'{{to}}%', 'duration':{{dur}}, 'ease':'power2.inOut'}, {{at}});\n})();",
  "use": "比例、完成度、加载"
 },
 "S04": {
  "id": "S04",
  "name": "勾选",
  "family": "状态",
  "layer": "element",
  "params": {
   "size": 22,
   "color": "#7BE8BE"
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _c = document.createElement('i');\n  _c.style.cssText = 'position:absolute;left:0;top:50%;width:{{size}}px;height:{{size}}px;margin-top:-11px;border:2px solid {{color}};border-radius:50%;transform:scale(0);';\n  var _k = document.createElement('i');\n  _k.style.cssText = 'position:absolute;left:0;top:50%;width:{{size}}px;height:{{size}}px;margin-top:-11px;border-radius:50%;background:{{color}};transform:scale(0);';\n  _t.appendChild(_c); _t.appendChild(_k);\n  timeline.to(_c, {'scale':1, 'duration':.3, 'ease':'back.out(2)'}, {{at}});\n  timeline.to(_k, {'scale':.55, 'duration':.3, 'ease':'power2.out'}, {{at}} + .12);\n})();",
  "use": "清单项被确认"
 },
 "S05": {
  "id": "S05",
  "name": "输入",
  "family": "状态",
  "layer": "element",
  "params": {
   "speed": 0.045,
   "cursor": "#7BE8BE"
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  var _txt = _t.textContent; _t.textContent = '';\n  var _cur = document.createElement('i');\n  _cur.style.cssText = 'display:inline-block;width:.06em;height:1.1em;background:{{cursor}};vertical-align:-.18em;margin-left:.04em;';\n  _t.appendChild(_cur);\n  for (var i = 1; i <= _txt.length; i++) {\n    timeline.set(_t, {'textContent': _txt.slice(0, i)}, {{at}} + i * {{speed}});\n    _t.appendChild(_cur);\n  }\n})();",
  "use": "搜索框、表单、命令"
 },
 "S06": {
  "id": "S06",
  "name": "点击",
  "family": "状态",
  "layer": "element",
  "params": {
   "size": 18,
   "color": "#7BE8BE",
   "dur": 0.7
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _p = document.createElement('i');\n  _p.style.cssText = 'position:absolute;left:50%;top:50%;width:{{size}}px;height:{{size}}px;border-radius:50%;border:2px solid {{color}};transform:translate(-50%,-50%) scale(.2);opacity:0;';\n  _t.appendChild(_p);\n  timeline.fromTo(_p, {'opacity':.9, 'scale':.2},\n    {'opacity':0, 'scale':2.6, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});\n})();",
  "use": "按钮、卡片被按下；证明界面在运行"
 },
 "S07": {
  "id": "S07",
  "name": "悬停高亮",
  "family": "状态",
  "layer": "element",
  "params": {
   "to": 1.03,
   "dur": 0.5
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':1, 'opacity':.72},\n  {'scale':{{to}}, 'opacity':1, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});",
  "use": "指针停在某个选项上"
 },
 "UA01": {
  "id": "UA01",
  "name": "卡片入场",
  "family": "UI",
  "layer": "element",
  "params": {
   "y": 26,
   "dur": 0.55,
   "stagger": 0.07
  },
  "code": "timeline.fromTo('{{sel}}', {'y':{{y}}, 'opacity':0},\n  {'y':0, 'opacity':1, 'duration':{{dur}}, 'ease':'power3.out'}, {{at}});\ntimeline.fromTo('{{sel}} > *', {'y':14, 'opacity':0},\n  {'y':0, 'opacity':1, 'duration':{{dur}}, 'ease':'power2.out', 'stagger':{{stagger}}}, {{at}} + .16);",
  "use": "ui-card / ui-bento 这类块"
 },
 "UA02": {
  "id": "UA02",
  "name": "数据行逐条",
  "family": "UI",
  "layer": "element",
  "params": {
   "x": -18,
   "dur": 0.5,
   "stagger": 0.08
  },
  "code": "timeline.fromTo('{{sel}}', {'x':{{x}}, 'opacity':0},\n  {'x':0, 'opacity':1, 'duration':{{dur}}, 'ease':'power2.out', 'stagger':{{stagger}}}, {{at}});",
  "use": "ui-row / ui-masonry-item 这类列表"
 },
 "UA03": {
  "id": "UA03",
  "name": "标签点亮",
  "family": "UI",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "stagger": 0.1,
   "to": 1
  },
  "code": "timeline.fromTo('{{sel}}', {'opacity':.28, 'scale':.94},\n  {'opacity':{{to}}, 'scale':1, 'duration':{{dur}}, 'ease':'power2.out', 'stagger':{{stagger}}}, {{at}});",
  "use": "ui-chip / ui-step 这类状态标签"
 },
 "M01": {
  "id": "M01",
  "name": "颗粒",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.1,
   "dur": 1.2,
   "z": 26
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-size:180px 180px;';\n  var _svg = \"<svg xmlns='http://www.w3.org/2000/svg' width='180' height='180'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='180' height='180' filter='url(%23n)' opacity='.55'/></svg>\";\n  _d.style.backgroundImage = 'url(\"data:image/svg+xml;utf8,' + _svg + '\")';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n  timeline.to(_d, {'backgroundPosition':'180px 120px', 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "所有暗场；让静止画面也有呼吸"
 },
 "M02": {
  "id": "M02",
  "name": "扫描线",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.55,
   "dur": 1.0,
   "z": 26
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.22) 0 1.5px,transparent 1.5px 4px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "科技、监控、旧屏质感"
 },
 "M03": {
  "id": "M03",
  "name": "半调",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.5,
   "dur": 1.0,
   "z": 26
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-image:radial-gradient(circle at 50% 50%,rgba(10,12,12,.5) 1.1px,transparent 1.6px);background-size:9px 9px;';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "印刷感、报纸感；压在照片上最像"
 },
 "M04": {
  "id": "M04",
  "name": "暗角",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 1,
   "dur": 1.2,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:radial-gradient(120% 92% at 50% 45%,transparent 38%,rgba(0,0,0,.62) 100%);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "每一屏都能加；把注意力压回中心"
 },
 "M05": {
  "id": "M05",
  "name": "辉光",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 1,
   "dur": 1.2,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:radial-gradient(680px 680px at 50% 30%,rgba(255,240,210,.20),transparent 68%);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "片头、片尾、关键结论"
 },
 "M06": {
  "id": "M06",
  "name": "漏光",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 1,
   "dur": 1.6,
   "z": 26
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:linear-gradient(112deg,transparent 38%,rgba(255,170,110,.14) 48%,rgba(255,225,180,.20) 52%,transparent 62%);background-size:260% 260%;background-position:0% 50%;';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':.4, 'ease':'none'}, {{at}});\n  timeline.to(_d, {'backgroundPosition':'100% 50%', 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "换镜、情绪转折；一次就够"
 },
 "M07": {
  "id": "M07",
  "name": "网格线",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.7,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-image:linear-gradient(rgba(255,255,255,.05) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.05) 1px,transparent 1px);background-size:64px 64px;';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "工程感、参数感；压在深色照片上"
 },
 "M08": {
  "id": "M08",
  "name": "点阵",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.8,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-image:radial-gradient(circle,rgba(160,220,255,.16) 1px,transparent 1.4px);background-size:22px 22px;';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "网点底，比网格线轻"
 },
 "M09": {
  "id": "M09",
  "name": "拉丝",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.8,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-image:repeating-linear-gradient(90deg,rgba(255,255,255,.05) 0 1px,transparent 1px 4px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "金属、扫描、速度感"
 },
 "K20": {
  "id": "K20",
  "name": "撑满一行",
  "family": "字形",
  "layer": "element",
  "params": {
   "ratio": 0.98,
   "dur": 0.75
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  var _s = kit.fitScale(_t, {{ratio}});\n  timeline.fromTo(_t, {'scale':_s * 1.16, 'opacity':0, 'transformOrigin':'0% 50%'},\n    {'scale':_s, 'opacity':1, 'duration':{{dur}}, 'ease':'power3.out'}, {{at}});\n})();",
  "use": "一行字要顶到栏宽；靠缩放不用改字号"
 },
 "X11": {
  "id": "X11",
  "name": "左擦除",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.55,
   "ease": "power3.inOut"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'inset(0% 100% 0% 0%)'},\n  {'clipPath':'inset(0% 0% 0% 0%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "从左边揭开这一屏"
 },
 "X12": {
  "id": "X12",
  "name": "右擦除",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.55,
   "ease": "power3.inOut"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'inset(0% 0% 0% 100%)'},\n  {'clipPath':'inset(0% 0% 0% 0%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "从右边揭开"
 },
 "X13": {
  "id": "X13",
  "name": "上擦除",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.55,
   "ease": "power3.inOut"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'inset(0% 0% 100% 0%)'},\n  {'clipPath':'inset(0% 0% 0% 0%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "竖屏最常用：从上往下揭开"
 },
 "X14": {
  "id": "X14",
  "name": "下擦除",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.55,
   "ease": "power3.inOut"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'inset(100% 0% 0% 0%)'},\n  {'clipPath':'inset(0% 0% 0% 0%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "从下往上揭开"
 },
 "X15": {
  "id": "X15",
  "name": "光圈",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.6,
   "ease": "power2.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'circle(0% at 50% 46%)'},\n  {'clipPath':'circle(85% at 50% 46%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "从一个焦点散开；适合人物特写"
 },
 "X17": {
  "id": "X17",
  "name": "翻页",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.7,
   "ease": "power3.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'rotationY':-88, 'transformOrigin':'0% 50%', 'transformPerspective':1200, 'opacity':0},\n  {'rotationY':0, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "纸面、版面的换页"
 },
 "X21": {
  "id": "X21",
  "name": "甩镜",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.5,
   "ease": "power3.out",
   "dist": 14
  },
  "code": "timeline.fromTo('{{sel}}', {'xPercent':{{dist}}, 'skewX':6, 'opacity':0},\n  {'xPercent':0, 'skewX':0, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "加速切镜；配合运动模糊最像"
 },
 "X22": {
  "id": "X22",
  "name": "硬切",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.08
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':1.015}, {'scale':1, 'duration':{{dur}}, 'ease':'none'}, {{at}});",
  "use": "最干脆的一刀；节奏快时用"
 },
 "UA04": {
  "id": "UA04",
  "name": "柱状增长",
  "family": "UI",
  "layer": "element",
  "params": {
   "dur": 0.7,
   "stagger": 0.06
  },
  "code": "timeline.fromTo('{{sel}}', {'scaleY':0, 'opacity':.4},\n  {'scaleY':1, 'opacity':1, 'duration':{{dur}}, 'ease':'power3.out', 'stagger':{{stagger}}}, {{at}});",
  "use": "U13 柱状图：柱子从基线长上来"
 },
 "UA05": {
  "id": "UA05",
  "name": "路径绘制",
  "family": "UI",
  "layer": "element",
  "params": {
   "dur": 0.9
  },
  "code": "(function () {\n  var _p = document.querySelector('{{sel}}');\n  if (!_p) return;\n  kit.drawPath(timeline, _p, {{at}}, {{dur}}, {'ease':'power2.inOut'});\n})();",
  "use": "U14 折线、任何 SVG 线：从起点画到终点"
 },
 "UA06": {
  "id": "UA06",
  "name": "时间轴点亮",
  "family": "UI",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "stagger": 0.16
  },
  "code": "timeline.fromTo('{{sel}}', {'opacity':.35, 'x':-10},\n  {'opacity':1, 'x':0, 'duration':{{dur}}, 'ease':'power2.out', 'stagger':{{stagger}}}, {{at}});",
  "use": "U20 时间轴、步骤条：节点依次亮"
 },
 "X16": {
  "id": "X16",
  "name": "分割擦除",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.6,
   "ease": "power3.inOut"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'polygon(0% 0%, 100% 0%, 100% 42%, 0% 42%, 0% 58%, 100% 58%, 100% 100%, 0% 100%)'},\n  {'clipPath':'polygon(0% 0%, 100% 0%, 100% 50%, 0% 50%, 0% 50%, 100% 50%, 100% 100%, 0% 100%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "上下两半合拢；比单方向擦更有仪式感"
 },
 "X20": {
  "id": "X20",
  "name": "闪白",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.42,
   "op": 0.85
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _w = document.createElement('i');\n  _w.style.cssText = 'position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none;z-index:28;';\n  _b.appendChild(_w);\n  timeline.fromTo(_w, {'opacity':{{op}}}, {'opacity':0, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});\n})();",
  "use": "重音、切点；一屏最多一次"
 },
 "X23": {
  "id": "X23",
  "name": "错位切片",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.55,
   "ease": "power3.out",
   "dist": 10
  },
  "code": "timeline.fromTo('{{sel}}', {'xPercent':{{dist}}, 'skewX':-7, 'opacity':0},\n  {'xPercent':0, 'skewX':0, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "快速换版；有速度但不像甩镜那么猛"
 },
 "X28": {
  "id": "X28",
  "name": "圆角展开",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.7,
   "ease": "power3.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'borderRadius':'42%', 'scale':.8, 'opacity':0},\n  {'borderRadius':'0%', 'scale':1, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "卡片、图块自己张开变成整屏"
 },
 "UA07": {
  "id": "UA07",
  "name": "逐条入场",
  "family": "UI",
  "layer": "element",
  "params": {
   "child": ".b",
   "y": 18,
   "dur": 0.45,
   "stagger": 0.12
  },
  "code": "timeline.fromTo('{{sel}} {{child}}', {'opacity':0, 'y':{{y}}},\n  {'opacity':1, 'y':0, 'duration':{{dur}}, 'ease':'power2.out', 'stagger':{{stagger}}}, {{at}});",
  "use": "组件内部的项目逐条出现：气泡 .b、价格卡 .p、表格行 tr、时间轴 .t"
 },
 "S08": {
  "id": "S08",
  "name": "展开",
  "family": "状态",
  "layer": "element",
  "params": {
   "dur": 0.5,
   "ease": "power3.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'scaleY':0, 'transformOrigin':'50% 0%', 'opacity':.55},\n  {'scaleY':1, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "面板、列表、卡片展开；transform-origin 在顶边"
 },
 "S09": {
  "id": "S09",
  "name": "选中",
  "family": "状态",
  "layer": "element",
  "params": {
   "color": "#7BE8BE",
   "r": 14,
   "dur": 0.35
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  _t.style.position = _t.style.position || 'relative';\n  var _f = document.createElement('i');\n  _f.style.cssText = 'position:absolute;inset:-6px;border:2px solid {{color}};border-radius:{{r}}px;opacity:0;transform:scale(.94);pointer-events:none;';\n  _t.appendChild(_f);\n  timeline.fromTo(_f, {'opacity':0, 'scale':.94}, {'opacity':1, 'scale':1, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});\n})();",
  "use": "选项被选中、输入框被聚焦"
 },
 "S10": {
  "id": "S10",
  "name": "切换",
  "family": "状态",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "ease": "power2.inOut"
  },
  "code": "timeline.fromTo('{{sel}}', {'scaleX':0, 'transformOrigin':'0% 50%'},\n  {'scaleX':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "标签页下的指示条滑到新位置"
 },
 "S11": {
  "id": "S11",
  "name": "拖拽",
  "family": "状态",
  "layer": "element",
  "params": {
   "from": -46,
   "rot": -3,
   "dur": 0.6
  },
  "code": "timeline.fromTo('{{sel}}', {'x':{{from}}, 'rotation':{{rot}}},\n  {'x':0, 'rotation':0, 'duration':{{dur}}, 'ease':'power2.out'}, {{at}});",
  "use": "卡片被拖动后归位；表现“可操作”"
 },
 "X31": {
  "id": "X31",
  "name": "遮罩收走",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "ease": "power2.in"
  },
  "code": "timeline.to('{{sel}}', {'clipPath':'inset(0% 0% 0% 100%)', 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "这一屏被一条竖边收走；比淡出干净"
 },
 "X32": {
  "id": "X32",
  "name": "缩放退出",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "ease": "power2.in"
  },
  "code": "timeline.to('{{sel}}', {'scale':.92, 'opacity':0, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "往画面深处退走"
 },
 "X33": {
  "id": "X33",
  "name": "上抽离场",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "ease": "power2.in"
  },
  "code": "timeline.to('{{sel}}', {'clipPath':'inset(0% 0% 100% 0%)', 'yPercent':-4, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "整屏往上抽走，像翻上一页"
 },
 "M10": {
  "id": "M10",
  "name": "环形",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.7,
   "dur": 1.2,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-radial-gradient(circle at 50% 45%,rgba(160,220,255,.10) 0 1px,transparent 1px 46px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "同心圆纹，做仪表/雷达感"
 },
 "M11": {
  "id": "M11",
  "name": "斜纹",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.6,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-linear-gradient(45deg,rgba(220,235,255,.07) 0 1px,transparent 1px 7px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "45° 细斜纹，做印刷/网点感"
 },
 "M12": {
  "id": "M12",
  "name": "光扫",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 1,
   "dur": 1.4,
   "z": 26
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:linear-gradient(100deg,transparent 42%,rgba(255,255,255,.16) 50%,transparent 58%);background-size:220% 220%;background-position:0% 50%;';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':.3, 'ease':'none'}, {{at}});\n  timeline.to(_d, {'backgroundPosition':'100% 50%', 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "一道高光横着扫过画面；片头片尾"
 },
 "M13": {
  "id": "M13",
  "name": "长影",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.55,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-linear-gradient(45deg,rgba(0,0,0,.42) 0 2px,transparent 2px 5px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "45° 斜向长影，做立体/印刷感"
 },
 "M14": {
  "id": "M14",
  "name": "半调线",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.5,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-linear-gradient(0deg,rgba(205,230,255,.40) 0 1px,transparent 1px 4px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "横向渐变网点，比 M03 更规整"
 },
 "M15": {
  "id": "M15",
  "name": "纸纹B",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.65,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-linear-gradient(90deg,rgba(120,110,95,.18) 0 1px,transparent 1px 3px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "纸面加细纤维；配纸底用"
 },
 "M16": {
  "id": "M16",
  "name": "网点重",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.55,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-image:radial-gradient(circle at 50% 50%,rgba(10,12,12,.68) 1.6px,transparent 2.2px);background-size:14px 14px;';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "粗网点，报章印刷感"
 },
 "M17": {
  "id": "M17",
  "name": "玻璃",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.5,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:linear-gradient(140deg,rgba(200,225,255,.24),rgba(120,160,200,.06) 45%,rgba(255,255,255,.18));';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "一层冷雾，压住杂乱的底"
 },
 "M18": {
  "id": "M18",
  "name": "波纹",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.5,
   "dur": 1.2,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-radial-gradient(circle at 50% 55%,rgba(150,215,255,.26) 0 2px,transparent 2px 54px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "水波/同心纹，做情绪段"
 },
 "M19": {
  "id": "M19",
  "name": "边角压暗",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 1,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:radial-gradient(120% 120% at 50% 50%,transparent 55%,rgba(0,0,0,.72) 100%);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "只压四个角，中间不动"
 },
 "M20": {
  "id": "M20",
  "name": "光晕",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 1,
   "dur": 1.2,
   "z": 26
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:radial-gradient(520px 520px at 50% 26%,rgba(255,226,180,.40),transparent 70%);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "暖光晕，片头片尾"
 },
 "M21": {
  "id": "M21",
  "name": "色带",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.45,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background:repeating-linear-gradient(180deg,rgba(255,255,255,.10) 0 40px,rgba(0,0,0,.16) 40px 80px);';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "横向色阶带，做复古/印刷"
 },
 "M22": {
  "id": "M22",
  "name": "粗噪",
  "family": "材质",
  "layer": "overlay",
  "params": {
   "op": 0.3,
   "dur": 1.0,
   "z": 25
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  var _d = document.createElement('i');\n  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:{{z}};opacity:0;background-size:70px 70px;';\n  var _svg = \"<svg xmlns='http://www.w3.org/2000/svg' width='70' height='70'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='.45' numOctaves='2' stitchTiles='stitch'/></filter><rect width='70' height='70' filter='url(%23n)' opacity='.7'/></svg>\";\n  _d.style.backgroundImage = 'url(\"data:image/svg+xml;utf8,' + _svg + '\")';\n  _b.appendChild(_d);\n  timeline.to(_d, {'opacity':{{op}}, 'duration':{{dur}}, 'ease':'none'}, {{at}});\n})();",
  "use": "比 M01 更粗的噪点，做胶片感"
 },
 "X34": {
  "id": "X34",
  "name": "时钟擦除",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.75
  },
  "code": "(function () {\n  var _b = document.querySelector('{{sel}}');\n  if (!_b) return;\n  _b.style.position = _b.style.position || 'relative';\n  var _m = document.createElement('i');\n  _m.style.cssText = 'position:absolute;inset:0;z-index:27;pointer-events:none;';\n  _b.appendChild(_m);\n  var _o = {'a': 0};\n  timeline.fromTo(_o, {'a': 0}, {'a': 360, 'duration':{{dur}}, 'ease':'none', 'onUpdate': function () {\n    _m.style.background = 'conic-gradient(from 0deg, transparent 0deg ' + _o.a.toFixed(1) + 'deg, rgba(10,11,10,1) ' + _o.a.toFixed(1) + 'deg 360deg)';\n  }}, {{at}});\n  timeline.to(_m, {'opacity':0, 'duration':0.06}, {{at}} + {{dur}});\n})();",
  "use": "像表针扫过一样揭开；开场重音"
 },
 "X35": {
  "id": "X35",
  "name": "立方",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.7,
   "ease": "power3.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'rotationY':-84, 'transformOrigin':'0% 50%', 'transformPerspective':1400, 'opacity':0.25},\n  {'rotationY':0, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "从侧面转进来，有体积感"
 },
 "X36": {
  "id": "X36",
  "name": "交叉扭曲",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.65,
   "ease": "power3.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'xPercent':6, 'skewX':-9, 'scale':1.06, 'opacity':0},\n  {'xPercent':0, 'skewX':0, 'scale':1, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "错位切入，速度感强"
 },
 "X37": {
  "id": "X37",
  "name": "梦幻缩放",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.9,
   "ease": "power2.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'scale':1.3, 'opacity':0, 'rotation':-1.2},\n  {'scale':1, 'opacity':1, 'rotation':0, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "慢慢从远处浮上来，情绪段"
 },
 "X38": {
  "id": "X38",
  "name": "涟漪",
  "family": "离场",
  "layer": "element",
  "params": {
   "dur": 0.75,
   "ease": "power2.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'clipPath':'circle(0% at 50% 52%)', 'scale':1.06},\n  {'clipPath':'circle(92% at 50% 52%)', 'scale':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "从中心荡开，比 X15 光圈更慢更软"
 },
 "DA01": {
  "id": "DA01",
  "name": "数字跳变",
  "family": "状态",
  "layer": "element",
  "params": {
   "from": 128,
   "to": 140,
   "steps": 6,
   "stepdur": 0.09
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  var _from = {{from}}, _to = {{to}}, _n = {{steps}};\n  for (var i = 1; i <= _n; i++) {\n    (function (k) {\n      timeline.set(_t, {'textContent': String(Math.round(_from + (_to - _from) * k / _n))}, {{at}} + k * {{stepdur}});\n    })(i);\n  }\n})();",
  "use": "数值从旧值跳到新值，做对比"
 },
 "DA02": {
  "id": "DA02",
  "name": "条形换值",
  "family": "状态",
  "layer": "element",
  "params": {
   "heights": "24,86,52,100",
   "dur": 0.55,
   "stagger": 0.08
  },
  "code": "(function () {\n  var _els = document.querySelectorAll('{{sel}}');\n  var _hs = '{{heights}}'.split(',');\n  for (var i = 0; i < _els.length; i++) {\n    var _h = (_hs[i % _hs.length] || '50').replace('%','') + '%';\n    timeline.to(_els[i], {'height':_h, 'duration':{{dur}}, 'ease':'power2.inOut'}, {{at}} + i * {{stagger}});\n  }\n})();",
  "use": "柱状图数据刷新：柱子长到新高度"
 },
 "DA03": {
  "id": "DA03",
  "name": "行新增",
  "family": "状态",
  "layer": "element",
  "params": {
   "dur": 0.45,
   "ease": "power3.out"
  },
  "code": "timeline.fromTo('{{sel}}', {'scaleY':0, 'opacity':0, 'transformOrigin':'50% 0%'},\n  {'scaleY':1, 'opacity':1, 'duration':{{dur}}, 'ease':'{{ease}}'}, {{at}});",
  "use": "列表里多出一行；配 S04 勾选"
 },
 "DA04": {
  "id": "DA04",
  "name": "状态翻转",
  "family": "状态",
  "layer": "element",
  "params": {
   "text": "已成交",
   "dur": 0.5
  },
  "code": "(function () {\n  var _t = document.querySelector('{{sel}}');\n  if (!_t) return;\n  timeline.to(_t, {'opacity':0, 'scale':.92, 'duration':{{dur}} * .45, 'ease':'power2.in'}, {{at}});\n  timeline.set(_t, {'textContent':'{{text}}'}, {{at}} + {{dur}} * .45);\n  timeline.to(_t, {'opacity':1, 'scale':1, 'duration':{{dur}} * .55, 'ease':'power2.out'}, {{at}} + {{dur}} * .45);\n})();",
  "use": "标签从“跟进中”变成“已成交”"
 }
};
