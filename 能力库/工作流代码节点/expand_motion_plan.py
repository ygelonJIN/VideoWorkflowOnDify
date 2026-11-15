def main(motion_json: str, scene_json: str = "") -> dict:
    """把动效判断（JSON）展开成本屏的 <script>；编号由 H00 统一分配，模型只选目标与时机。"""
    import json
    import re

    raw = str(motion_json or "").strip()
    data = {}
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            start, end = raw.find("{"), raw.rfind("}")
            if 0 <= start < end:
                try:
                    data = json.loads(raw[start:end + 1])
                except Exception:
                    data = {}

    motions = data.get("motions") if isinstance(data, dict) else None
    if not isinstance(motions, list):
        motions = []
    scene_data = {}
    try:
        scene_data = json.loads(str(scene_json or "{}"))
    except Exception:
        scene_data = {}
    if not isinstance(scene_data, dict):
        scene_data = {}
    sid = str(data.get("scene_id") or scene_data.get("scene_id") or "").strip()

    # 全片编号由 H00 统一分配：这里只把编号套到模型选的目标/时机上。
    budget = scene_data.get("motion_budget") if isinstance(scene_data.get("motion_budget"), dict) else {}
    if isinstance(motions, list):
        motions = [item for item in motions if isinstance(item, dict)]
    # 每屏条数不设上限：模型选多少展开多少。预算只在模型一条都没选时兜底。
    if budget and isinstance(motions, list) and not motions:
        entrance = str(budget.get("entrance") or "").strip().upper()
        state = str(budget.get("state") or "").strip().upper()
        if entrance:
            motions.append({"preset": entrance, "target": "title", "trigger": "sentence_start",
                            "fallback": 0.2, "reason": "预算兜底：入场"})
        if state:
            motions.append({"preset": state, "target": "stat", "trigger": "sentence_start",
                            "fallback": 0.9, "reason": "预算兜底：状态变化"})

    # 每个编号 = 一段可复制的代码模板；%(x)s 由这里填。





    TPL = {
        "T01": """var _c = kit.split('%(sel)s', '%(unit)ss');
timeline.fromTo(_c, {opacity:0, y:'%(y)s'},
  {opacity:1, y:0, duration:%(dur)s, ease:'%(ease)s', stagger:%(stagger)s}, %(at)s);""",
        "T02": """var _w = kit.split('%(sel)s', '%(unit)ss');
timeline.fromTo(_w, {opacity:0, filter:'blur(%(blur)s)', y:'%(y)s'},
  {opacity:1, filter:'blur(0px)', y:0, duration:%(dur)s, ease:'power2.out', stagger:%(stagger)s}, %(at)s);""",
        "T03": """var _c = kit.split('%(sel)s', '%(unit)ss');
timeline.fromTo(_c, {opacity:0, rotationX:%(angle)s, transformOrigin:'50%% 0%%', transformPerspective:%(perspective)s},
  {opacity:1, rotationX:0, duration:%(dur)s, ease:'power3.out', stagger:%(stagger)s}, %(at)s);""",
        "T04": """var _t = document.querySelector('%(sel)s');
_t.style.webkitTextStroke = '%(strokeWidth)spx currentColor';
_t.style.color = 'transparent';
timeline.to(_t, {color:'%(color)s', duration:%(dur)s, ease:'power1.out'}, %(at)s + %(fillDelay)s);""",
        "T05": """var _t = document.querySelector('%(sel)s');
if (_t) {
  var _txt = _t.textContent;
  _t.textContent = '';
  timeline.set(_t, {'opacity': 1}, %(at)s);
  for (var _i = 1; _i <= _txt.length; _i++) {
    (function (k) {
      timeline.call(function () { _t.textContent = _txt.slice(0, k); }, null, %(at)s + k * %(speed)s);
    })(_i);
  }
}""",
        "T06": """var _n = document.querySelector('%(sel)s');
var _o = {'v':%(from)s};
timeline.to(_o, {'v':%(to)s, 'duration':%(dur)s, 'ease':'power2.out',
  'onUpdate':function(){ _n.textContent = Math.round(_o.v); }}, %(at)s);""",
        "T09": """var _c = kit.split('%(sel)s', 'chars');
_c.forEach(function (el, i) {
  el.style.transformStyle = 'preserve-3d';
  timeline.fromTo(el, {rotationX: -90, opacity: 0},
    {rotationX: 0, opacity: 1, duration: %(dur)s, ease: 'back.out'}, %(at)s + i * %(stagger)s);
});""",
        "W01": """timeline.fromTo('%(sel)s', {'borderRadius':'0px', 'scale':1.03, 'overflow':'hidden'},
  {'borderRadius':'%(r)spx', 'scale':1, 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);""",
        "X01": """var _dir = '%(direction)s';
var _inset = _dir === 'down' ? 'inset(-100%% 0%% 0%% 0%%)'
  : _dir === 'left' ? 'inset(0%% 100%% 0%% 0%%)'
  : _dir === 'right' ? 'inset(0%% 0%% 0%% 100%%)'
  : 'inset(100%% 0%% 0%% 0%%)';
timeline.fromTo('%(sel)s', {clipPath: _inset},
  {clipPath:'inset(0%% 0%% 0%% 0%%)', duration:%(dur)s, ease:'power3.inOut'}, %(at)s);""",
        "C01": """timeline.fromTo('%(sel)s', {'scale':1}, {'scale':%(to)s, 'duration':%(dur)s, 'ease':'none'}, %(at)s);""",
        "C02": """timeline.fromTo('%(sel)s', {'scale':%(from)s}, {'scale':1, 'duration':%(dur)s, 'ease':'none'}, %(at)s);""",
        "C03": """timeline.fromTo('%(sel)s', {'xPercent':%(from)s}, {'xPercent':%(to)s, 'duration':%(dur)s, 'ease':'sine.inOut'}, %(at)s);""",
        "K03": """var _c = kit.split('%(sel)s', 'chars'), _r = kit.seeded(%(seed)s);
_c.forEach(function (el, i) {
  var _dy = 12 + _r() * 26, _rt = (_r() * 2 - 1) * %(rot)s;
  timeline.fromTo(el, {'yPercent':_dy, 'rotation':_rt, 'opacity':0},
    {'yPercent':0, 'rotation':0, 'opacity':1, 'duration':%(dur)s, 'ease':'power3.out'}, %(at)s + i * %(stagger)s);
});""",
        "G02": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  var _boxes = [];
  _els.forEach(function (n, i) {
    var _f = (n.getAttribute('data-flip-from') || '').split(',');
    var _t = (n.getAttribute('data-flip-to') || '').split(',');
    if (_f.length < 2 || _t.length < 2) return;
    var _dx = parseFloat(_t[0]) - parseFloat(_f[0]);
    var _dy = parseFloat(_t[1]) - parseFloat(_f[1]);
    timeline.fromTo(n, {'x':0, 'y':0},
      {'x':_dx, 'y':_dy, 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s + i * %(stagger)s);
    var _b = n.parentElement;
    while (_b && !_b.hasAttribute('data-flip-container')) _b = _b.parentElement;
    if (_b && _boxes.indexOf(_b) < 0) _boxes.push(_b);
  });
  _boxes.forEach(function (_b) {
    var _o = _b.querySelectorAll('[data-flip-out]');
    if (!_o.length) return;
    timeline.to(_o, {'opacity':%(outOp)s, 'duration':%(dur)s * 0.7, 'ease':'power2.out'}, %(at)s);
  });
})();""",
        "X03": """timeline.to('%(sel)s', {'opacity':0, 'y':-%(dist)s, 'duration':%(dur)s, 'ease':'power2.in', 'stagger':%(stagger)s}, %(at)s);""",
        "X05": """timeline.to('%(sel)s', {'opacity':0, 'x':%(dist)s, 'duration':%(dur)s, 'ease':'power2.in', 'stagger':%(stagger)s}, %(at)s);""",
        "K01": """timeline.fromTo('%(sel)s', {'scale':%(from)s, 'yPercent':%(y)s, 'opacity':0, 'transformOrigin':'0%% 100%%'},
  {'scale':1, 'yPercent':0, 'opacity':1, 'duration':%(dur)s, 'ease':'power3.out'}, %(at)s);""",
        "K04": """timeline.fromTo('%(sel)s', {'letterSpacing':'%(from)s', 'opacity':0},
  {'letterSpacing':'%(to)s', 'opacity':1, 'duration':%(dur)s, 'ease':'power3.out'}, %(at)s);""",
        "K07": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _l = document.createElement('i');
  _l.style.cssText = 'position:absolute;left:0;right:0;bottom:-.08em;height:%(h)spx;background:%(color)s;transform:scaleX(0);transform-origin:0 50%%;border-radius:2px;z-index:0;';
  _t.appendChild(_l);
  timeline.to(_l, {'scaleX':1, 'duration':%(dur)s, 'ease':'power2.inOut'}, %(at)s);
})();""",
        "K08": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _c = document.createElement('i');
  _c.style.cssText = 'position:absolute;left:-.16em;right:-.16em;top:-.12em;bottom:-.16em;border:%(w)spx solid %(color)s;border-radius:50%%;transform:scale(.6);opacity:0;z-index:0;';
  _t.appendChild(_c);
  timeline.to(_c, {'scale':1, 'opacity':1, 'duration':%(dur)s, 'ease':'back.out'}, %(at)s);
})();""",
        "K10": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  _t.style.writingMode = 'vertical-rl';
  _t.style.display = 'inline-block';
  _t.style.letterSpacing = '.1em';
  timeline.fromTo(_t, {'clipPath':'inset(0%% 0%% 100%% 0%%)'},
    {'clipPath':'inset(0%% 0%% 0%% 0%%)', 'duration':%(dur)s, 'ease':'power3.inOut'}, %(at)s);
})();""",
        "K12": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _l = document.createElement('i');
  _l.style.cssText = 'position:absolute;left:-.02em;right:-.02em;top:.54em;height:%(h)spx;background:%(color)s;transform:scaleX(0);transform-origin:0 50%%;z-index:0;';
  _t.appendChild(_l);
  timeline.to(_l, {'scaleX':1, 'duration':%(dur)s, 'ease':'power2.inOut'}, %(at)s);
})();""",
        "S02": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  // 下划线必须和"被划的那行字"等长。以前直接给整块元素画 0→72%% 的条，
  // 多行标题时条比末行长、单行时又比字短（2026-11-15 实测）。这里把末行
  // 包进一个 inline-block 的板子，条画板子上、宽度 100%%，长度就跟着字走。
  var _bar = '<i class="k-underline" style="position:absolute;left:0;bottom:-.12em;height:%(h)spx;width:0;background:%(color)s;border-radius:2px;"></i>';
  var _plate = document.createElement('span');
  _plate.style.cssText = 'display:inline-block;position:relative;white-space:nowrap;';
  if (!_t.querySelector('*')) {
    var _parts = String(_t.innerHTML).split(/<br\\s*\\/?>/i);
    var _tail = _parts.pop();
    _parts.push('<span style="display:inline-block;position:relative;white-space:nowrap">' + _tail + _bar + '</span>');
    _t.innerHTML = _parts.length > 1 ? _parts.join('<br>') : _parts[0];
  } else {
    var _anchor = _t.lastChild;
    if (!_anchor) { return; }
    _t.insertBefore(_plate, _anchor);
    _plate.appendChild(_anchor);
    _plate.insertAdjacentHTML('beforeend', _bar);
  }
  var _b = _t.querySelector('.k-underline');
  timeline.to(_b, {'width':'100%%', 'duration':%(dur)s, 'ease':'power2.inOut'}, %(at)s);
})();""",
        "S04": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _c = document.createElement('i');
  _c.style.cssText = 'position:absolute;left:0;top:50%%;width:%(size)spx;height:%(size)spx;margin-top:-11px;border:2px solid %(color)s;border-radius:50%%;transform:scale(0);';
  var _k = document.createElement('i');
  _k.style.cssText = 'position:absolute;left:0;top:50%%;width:%(size)spx;height:%(size)spx;margin-top:-11px;border-radius:50%%;background:%(color)s;transform:scale(0);';
  _t.appendChild(_c); _t.appendChild(_k);
  timeline.to(_c, {'scale':1, 'duration':.3, 'ease':'back.out'}, %(at)s);
  timeline.to(_k, {'scale':.55, 'duration':.3, 'ease':'power2.out'}, %(at)s + .12);
})();""",
        "S05": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _txt = _t.textContent; _t.textContent = '';
  var _cur = document.createElement('i');
  _cur.style.cssText = 'display:inline-block;width:.06em;height:1.1em;background:%(cursor)s;vertical-align:-.18em;margin-left:.04em;';
  _t.appendChild(_cur);
  for (var i = 1; i <= _txt.length; i++) {
    timeline.set(_t, {'textContent': _txt.slice(0, i)}, %(at)s + i * %(speed)s);
    _t.appendChild(_cur);
  }
})();""",
        "S06": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _p = document.createElement('i');
  _p.style.cssText = 'position:absolute;left:50%%;top:50%%;width:%(size)spx;height:%(size)spx;border-radius:50%%;border:2px solid %(color)s;transform:translate(-50%%,-50%%) scale(.2);opacity:0;';
  _t.appendChild(_p);
  timeline.fromTo(_p, {'opacity':.9, 'scale':.2},
    {'opacity':0, 'scale':2.6, 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);
})();""",
        "S07": """timeline.fromTo('%(sel)s', {'scale':1, 'opacity':.72},
  {'scale':%(to)s, 'opacity':1, 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);""",
        "UA01": """timeline.fromTo('%(sel)s', {'y':%(y)s, 'opacity':0},
  {'y':0, 'opacity':1, 'duration':%(dur)s, 'ease':'power3.out'}, %(at)s);
timeline.fromTo('%(sel)s > *', {'y':14, 'opacity':0},
  {'y':0, 'opacity':1, 'duration':%(dur)s, 'ease':'power2.out', 'stagger':%(stagger)s}, %(at)s + .16);""",
        "UA02": """timeline.fromTo('%(sel)s', {'x':%(x)s, 'opacity':0},
  {'x':0, 'opacity':1, 'duration':%(dur)s, 'ease':'power2.out', 'stagger':%(stagger)s}, %(at)s);""",
        "UA03": """timeline.fromTo('%(sel)s', {'opacity':0, 'scale':.94},
  {'opacity':%(to)s, 'scale':1, 'duration':%(dur)s, 'ease':'power2.out', 'stagger':%(stagger)s}, %(at)s);""",
        "M04": """(function () {
  var _b = document.querySelector('%(sel)s');
  if (!_b) return;
  var _d = document.createElement('i');
  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:%(z)s;opacity:0;background:radial-gradient(120%% 92%% at 50%% 45%%,transparent 38%%,rgba(0,0,0,.62) 100%%);';
  _b.appendChild(_d);
  timeline.to(_d, {'opacity':%(op)s, 'duration':%(dur)s, 'ease':'none'}, %(at)s);
})();""",
        "M05": """(function () {
  var _b = document.querySelector('%(sel)s');
  if (!_b) return;
  var _d = document.createElement('i');
  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:%(z)s;opacity:0;background:radial-gradient(680px 680px at 50%% 30%%,rgba(255,240,210,.20),transparent 68%%);';
  _b.appendChild(_d);
  timeline.to(_d, {'opacity':%(op)s, 'duration':%(dur)s, 'ease':'none'}, %(at)s);
})();""",
        "X11": """timeline.fromTo('%(sel)s', {'clipPath':'inset(0%% 100%% 0%% 0%%)'},
  {'clipPath':'inset(0%% 0%% 0%% 0%%)', 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s);""",
        "X14": """timeline.fromTo('%(sel)s', {'clipPath':'inset(100%% 0%% 0%% 0%%)'},
  {'clipPath':'inset(0%% 0%% 0%% 0%%)', 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s);""",
        "X21": """timeline.fromTo('%(sel)s', {'xPercent':%(dist)s, 'skewX':6, 'opacity':0},
  {'xPercent':0, 'skewX':0, 'opacity':1, 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s);""",
        "UA04": """timeline.fromTo('%(sel)s', {'scaleY':0, 'opacity':.4},
  {'scaleY':1, 'opacity':1, 'duration':%(dur)s, 'ease':'power3.out', 'stagger':%(stagger)s}, %(at)s);""",
        "UA06": """timeline.fromTo('%(sel)s', {'opacity':.35, 'x':-10},
  {'opacity':1, 'x':0, 'duration':%(dur)s, 'ease':'power2.out', 'stagger':%(stagger)s}, %(at)s);""",
        "S08": """timeline.fromTo('%(sel)s', {'scaleY':0, 'transformOrigin':'50%% 0%%', 'opacity':.55},
  {'scaleY':1, 'opacity':1, 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s);""",
        "S10": """timeline.fromTo('%(sel)s', {'scaleX':0, 'transformOrigin':'0%% 50%%'},
  {'scaleX':1, 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s);""",
        "S11": """timeline.fromTo('%(sel)s', {'x':%(from)s, 'rotation':%(rot)s},
  {'x':0, 'rotation':0, 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);""",
        "M12": """(function () {
  var _b = document.querySelector('%(sel)s');
  if (!_b) return;
  var _d = document.createElement('i');
  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:%(z)s;opacity:0;background:linear-gradient(100deg,transparent 42%%,rgba(255,255,255,.16) 50%%,transparent 58%%);background-size:220%% 220%%;background-position:0%% 50%%;';
  _b.appendChild(_d);
  timeline.to(_d, {'opacity':%(op)s, 'duration':.3, 'ease':'none'}, %(at)s);
  timeline.to(_d, {'backgroundPosition':'100%% 50%%', 'duration':%(dur)s, 'ease':'none'}, %(at)s);
})();""",
        "M16": """(function () {
  var _b = document.querySelector('%(sel)s');
  if (!_b) return;
  var _d = document.createElement('i');
  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:%(z)s;opacity:0;background-image:radial-gradient(circle at 50%% 50%%,rgba(10,12,12,.68) 1.6px,transparent 2.2px);background-size:14px 14px;';
  _b.appendChild(_d);
  timeline.to(_d, {'opacity':%(op)s, 'duration':%(dur)s, 'ease':'none'}, %(at)s);
})();""",
        "M20": """(function () {
  var _b = document.querySelector('%(sel)s');
  if (!_b) return;
  var _d = document.createElement('i');
  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:%(z)s;opacity:0;background:radial-gradient(520px 520px at 50%% 26%%,rgba(255,226,180,.40),transparent 70%%);';
  _b.appendChild(_d);
  timeline.to(_d, {'opacity':%(op)s, 'duration':%(dur)s, 'ease':'none'}, %(at)s);
})();""",
        "M21": """(function () {
  var _b = document.querySelector('%(sel)s');
  if (!_b) return;
  var _d = document.createElement('i');
  _d.style.cssText = 'position:absolute;inset:0;pointer-events:none;z-index:%(z)s;opacity:0;background:repeating-linear-gradient(180deg,rgba(255,255,255,.10) 0 40px,rgba(0,0,0,.16) 40px 80px);';
  _b.appendChild(_d);
  timeline.to(_d, {'opacity':%(op)s, 'duration':%(dur)s, 'ease':'none'}, %(at)s);
})();""",
        "DA02": """(function () {
  var _els = document.querySelectorAll('%(sel)s');
  var _hs = '%(heights)s'.split(',');
  for (var i = 0; i < _els.length; i++) {
    var _h = (_hs[i %% _hs.length] || '50').replace('%%','') + '%%';
    timeline.to(_els[i], {'height':_h, 'duration':%(dur)s, 'ease':'power2.inOut'}, %(at)s + i * %(stagger)s);
  }
})();""",
        "DA03": """timeline.fromTo('%(sel)s', {'scaleY':0, 'opacity':0, 'transformOrigin':'50%% 0%%'},
  {'scaleY':1, 'opacity':1, 'duration':%(dur)s, 'ease':'%(ease)s'}, %(at)s);""",
        "DA04": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  timeline.to(_t, {'opacity':0, 'scale':.92, 'duration':%(dur)s * .45, 'ease':'power2.in'}, %(at)s);
  timeline.set(_t, {'textContent':'%(text)s'}, %(at)s + %(dur)s * .45);
  timeline.to(_t, {'opacity':1, 'scale':1, 'duration':%(dur)s * .55, 'ease':'power2.out'}, %(at)s + %(dur)s * .45);
})();""",
        "I01": """(function () {
  var _p = document.querySelector('%(sel)s'), _t = document.querySelector('%(sel2)s');
  if (!_p || !_t) return;
  var _sc = _p.closest('.scene');
  var _st = _sc ? _sc.getAttribute('style') : null;
  if (_sc && getComputedStyle(_sc).display === 'none') {
    _sc.style.display = 'block';
    _sc.style.visibility = 'hidden';
  }
  var _pr = _p.getBoundingClientRect(), _tr = _t.getBoundingClientRect();
  if (_st !== null) _sc.setAttribute('style', _st || '');
  var _dx = (_tr.left + _tr.width / 2) - (_pr.left + 6);
  var _dy = (_tr.top + _tr.height / 2) - (_pr.top + 4);
  timeline.to(_p, {'x':_dx, 'y':_dy, 'duration':%(move)s, 'ease':'power2.inOut'}, %(at)s);
  timeline.call(function () { _p.classList.add('is-hand'); }, null, %(at)s + %(move)s);
  timeline.to(_t, {'borderColor':'%(hit)s', 'backgroundColor':'rgba(134,240,192,.10)', 'duration':%(hold)s, 'ease':'power2.out'}, %(at)s + %(move)s);
  timeline.fromTo(_p, {'scale':1}, {'scale':0.86, 'duration':0.1, 'ease':'power2.in'}, %(at)s + %(move)s + %(hold)s);
  timeline.to(_p, {'scale':1, 'duration':%(press)s, 'ease':'back.out'}, %(at)s + %(move)s + %(hold)s + 0.12);
})();""",
        "Z01": """(function () {
  var _cv = document.querySelector('%(sel)s');
  if (!_cv || !window.THREE) return;
  var _w = _cv.width || 1080, _h = _cv.height || 1920;
  var _r = new THREE.WebGLRenderer({canvas:_cv, antialias:true});
  _r.setSize(_w, _h, false);
  _r.setPixelRatio(1);
  var _s = new THREE.Scene();
  _s.background = new THREE.Color(0x0a0b0b);
  _s.fog = new THREE.Fog(0x0a0b0b, %(fogNear)s, %(fogFar)s);
  var _c = new THREE.PerspectiveCamera(38, _w / _h, 0.1, 120);
  _c.position.set(0, 0, %(camZ)s);
  var _g = new THREE.Group();
  _s.add(_g);
  var _geo = new THREE.PlaneGeometry(1.2, 0.76);
  var _pal = [0x2f4a44,0x33425a,0x1f6f5c,0x46586b,0x1b5d52,0x3c4a6b,0x2b3a44,0x2a5548,0x35405a];
  var _ps = [];
  for (var i = 0; i < 9; i++) {
    var m = new THREE.Mesh(_geo, new THREE.MeshBasicMaterial({color:_pal[i], transparent:true, opacity:0.92, side:THREE.DoubleSide}));
    m.position.set(((i %% 3) - 1) * 1.35, (Math.floor(i / 3) - 1) * 1.02, 0);
    _g.add(m);
    _ps.push(m);
  }
  var _o = {'p': 0};
  timeline.to(_o, {'p': 1, 'duration':%(dur)s, 'ease':'none', 'onUpdate': function () {
    var p = _o.p;
    _g.rotation.y = -0.3 + p * 0.6;
    _g.rotation.x = 0.18 - p * 0.32;
    _c.position.z = %(camZ)s - p * 1.6;
    for (var k = 0; k < _ps.length; k++) {
      _ps[k].position.z = Math.sin(p * Math.PI * 2 + k * 0.5) * 0.34;
      _ps[k].rotation.z = Math.sin(p * 3 + k) * 0.05;
    }
    _r.render(_s, _c);
  }}, %(at)s);
})();""",
        "G03": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  _els.forEach(function (n, i) {
    var _to = (n.getAttribute('data-morph-to') || '').split(',');
    if (_to.length < 4) return;
    timeline.to(n, {
      'left': parseFloat(_to[0]), 'top': parseFloat(_to[1]),
      'width': parseFloat(_to[2]), 'height': parseFloat(_to[3]),
      'borderRadius': _to[4] ? parseFloat(_to[4]) : 22,
      'duration': %(dur)s, 'ease': '%(ease)s'
    }, %(at)s + i * %(stagger)s);
    var _d = n.querySelector('[data-morph-detail]');
    if (_d) timeline.to(_d, {'opacity': 1, 'duration': %(fade)s, 'ease': 'power2.out'}, %(at)s + %(dur)s * 0.55);
  });
})();""",
        "I02": """(function () {
  var _p = document.querySelector('%(sel)s');
  if (!_p) return;
  var _sc = _p.closest('.scene');
  var _st = _sc ? _sc.getAttribute('style') : null;
  if (_sc && getComputedStyle(_sc).display === 'none') {
    _sc.style.display = 'block';
    _sc.style.visibility = 'hidden';
  }
  var _pr = _p.getBoundingClientRect();
  var _path = (_p.getAttribute('data-pointer-path') || '').split(',');
  var _t = %(at)s;
  _path.forEach(function (name) {
    name = (name || '').trim();
    if (!name) return;
    var _el = document.querySelector('[data-anim="' + name + '"]') || document.querySelector(name);
    if (!_el) return;
    var _r = _el.getBoundingClientRect();
    timeline.to(_p, {'x': (_r.left + _r.width / 2) - (_pr.left + 6),
                     'y': (_r.top + _r.height / 2) - (_pr.top + 4),
                     'duration': %(move)s, 'ease': 'power2.inOut'}, _t);
    timeline.to(_el, {'borderColor': '%(hit)s', 'backgroundColor': 'rgba(134,240,192,.10)',
                      'duration': %(hold)s, 'ease': 'power2.out'}, _t + %(move)s);
    timeline.fromTo(_p, {'scale': 1}, {'scale': 0.86, 'duration': 0.1, 'ease': 'power2.in'}, _t + %(move)s + %(hold)s);
    timeline.to(_p, {'scale': 1, 'duration': %(press)s, 'ease': 'back.out'}, _t + %(move)s + %(hold)s + 0.12);
    _t = _t + %(move)s + %(hold)s + %(gap)s;
  });
  if (_st !== null) _sc.setAttribute('style', _st || '');
})();""",
        "Z02": """(function () {
  var _cv = document.querySelector('%(sel)s');
  if (!_cv || !window.THREE) return;
  var _w = _cv.width || 1080, _h = _cv.height || 1920;
  var _r = new THREE.WebGLRenderer({canvas: _cv, antialias: true});
  _r.setSize(_w, _h, false);
  _r.setPixelRatio(1);
  var _s = new THREE.Scene();
  _s.background = new THREE.Color(0x0a0b0b);
  _s.fog = new THREE.Fog(0x0a0b0b, %(fogNear)s, %(fogFar)s);
  var _c = new THREE.PerspectiveCamera(46, _w / _h, 0.1, 120);
  _c.position.set(0, %(camY)s, %(camZ)s);
  _c.lookAt(0, 0, 0);
  var N = %(grid)s;
  var _g = new THREE.BufferGeometry();
  var _pos = new Float32Array(N * N * 3);
  var _base = [];
  for (var i = 0; i < N; i++) {
    for (var j = 0; j < N; j++) {
      var k = (i * N + j) * 3;
      var bx = (i / (N - 1) - 0.5) * 13;
      var bz = (j / (N - 1) - 0.5) * 13;
      _pos[k] = bx; _pos[k + 1] = 0; _pos[k + 2] = bz;
      _base.push([bx, bz]);
    }
  }
  _g.setAttribute('position', new THREE.BufferAttribute(_pos, 3));
  var _m = new THREE.PointsMaterial({color: 0x86f0c0, size: %(size)s, transparent: true, opacity: 0.8});
  var _pts = new THREE.Points(_g, _m);
  _pts.position.y = -1.4;
  _s.add(_pts);
  var _o = {'p': 0};
  timeline.to(_o, {'p': 1, 'duration': %(dur)s, 'ease': 'none', 'onUpdate': function () {
    var p = _o.p, arr = _g.attributes.position.array;
    for (var idx = 0; idx < _base.length; idx++) {
      var bx = _base[idx][0], bz = _base[idx][1];
      arr[idx * 3 + 1] = Math.sin(bx * 0.5 + p * 5.4) * 0.55 + Math.cos(bz * 0.44 - p * 3.6) * 0.45;
    }
    _g.attributes.position.needsUpdate = true;
    _pts.rotation.y = -0.18 + p * 0.3;
    _r.render(_s, _c);
  }}, %(at)s);
})();""",
        "S12": """(function () {
  var _page = document.querySelector('%(sel)s');
  if (!_page) return;
  timeline.to(_page, {'y': %(dist)s, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
  var _hl = [].slice.call(document.querySelectorAll('[data-scroll-hl]'));
  _hl.forEach(function (el, i) {
    timeline.to(el, {'backgroundColor': 'rgba(134,240,192,.10)', 'duration': %(hold)s,
                     'ease': 'power2.out'}, %(at)s + %(dur)s * (0.15 + i * 0.25));
  });
})();""",
        "W02": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  _els.forEach(function (n, i) {
    var _to = (n.getAttribute('data-frame-to') || '').split(',');
    if (_to.length < 4) return;
    timeline.to(n, {
      'left': parseFloat(_to[0]), 'top': parseFloat(_to[1]),
      'width': parseFloat(_to[2]), 'height': parseFloat(_to[3]),
      'duration': %(dur)s, 'ease': '%(ease)s'
    }, %(at)s + i * %(stagger)s);
  });
})();""",
        "W11": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.kit || !kit.deform) return;
  var _img = null;
  if (_el.tagName === 'IMG') { _img = _el; }
  else {
    var _bg = getComputedStyle(_el).backgroundImage || '';
    var _m = _bg.match(/url\(["']?(.*?)["']?\)/);
    if (_m) { _img = new Image(); _img.src = _m[1]; }
  }
  if (!_img) return;
  var _host = _el.tagName === 'IMG' ? _el.parentNode : _el;
  if (!_host) return;
  if (getComputedStyle(_host).position === 'static') _host.style.position = 'relative';
  var _r = _el.getBoundingClientRect(), _hr = _host.getBoundingClientRect();
  var _cv = document.createElement('canvas');
  _cv.width = 1080; _cv.height = 1920;
  _cv.style.cssText = 'position:absolute;pointer-events:none;display:block;z-index:3;'
    + 'left:' + (_r.left - _hr.left) + 'px;top:' + (_r.top - _hr.top) + 'px;'
    + 'width:' + _r.width + 'px;height:' + _r.height + 'px;';
  var _fx = kit.deform(_cv, _img, %(mode)s);
  if (!_fx) return;
  _host.appendChild(_cv);
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': %(amount)s, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _fx.draw(_drv.p, timeline.time());
  } }, %(at)s);
})();""",
        "W12": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.kit || !kit.deform) return;
  var _img = null;
  if (_el.tagName === 'IMG') { _img = _el; }
  else {
    var _bg = getComputedStyle(_el).backgroundImage || '';
    var _m = _bg.match(/url\(["']?(.*?)["']?\)/);
    if (_m) { _img = new Image(); _img.src = _m[1]; }
  }
  if (!_img) return;
  var _host = _el.tagName === 'IMG' ? _el.parentNode : _el;
  if (!_host) return;
  if (getComputedStyle(_host).position === 'static') _host.style.position = 'relative';
  var _r = _el.getBoundingClientRect(), _hr = _host.getBoundingClientRect();
  var _cv = document.createElement('canvas');
  _cv.width = 1080; _cv.height = 1920;
  _cv.style.cssText = 'position:absolute;pointer-events:none;display:block;z-index:3;'
    + 'left:' + (_r.left - _hr.left) + 'px;top:' + (_r.top - _hr.top) + 'px;'
    + 'width:' + _r.width + 'px;height:' + _r.height + 'px;';
  var _fx = kit.deform(_cv, _img, %(mode)s);
  if (!_fx) return;
  _host.appendChild(_cv);
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': %(amount)s, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _fx.draw(_drv.p, timeline.time());
  } }, %(at)s);
})();""",
        "W13": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.kit || !kit.deform) return;
  var _img = null;
  if (_el.tagName === 'IMG') { _img = _el; }
  else {
    var _bg = getComputedStyle(_el).backgroundImage || '';
    var _m = _bg.match(/url\(["']?(.*?)["']?\)/);
    if (_m) { _img = new Image(); _img.src = _m[1]; }
  }
  if (!_img) return;
  var _host = _el.tagName === 'IMG' ? _el.parentNode : _el;
  if (!_host) return;
  if (getComputedStyle(_host).position === 'static') _host.style.position = 'relative';
  var _r = _el.getBoundingClientRect(), _hr = _host.getBoundingClientRect();
  var _cv = document.createElement('canvas');
  _cv.width = 1080; _cv.height = 1920;
  _cv.style.cssText = 'position:absolute;pointer-events:none;display:block;z-index:3;'
    + 'left:' + (_r.left - _hr.left) + 'px;top:' + (_r.top - _hr.top) + 'px;'
    + 'width:' + _r.width + 'px;height:' + _r.height + 'px;';
  var _fx = kit.deform(_cv, _img, %(mode)s);
  if (!_fx) return;
  _host.appendChild(_cv);
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': %(amount)s, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _fx.draw(_drv.p, timeline.time());
  } }, %(at)s);
})();""",
        "W15": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.kit || !kit.deform) return;
  var _img = null;
  if (_el.tagName === 'IMG') { _img = _el; }
  else {
    var _bg = getComputedStyle(_el).backgroundImage || '';
    var _m = _bg.match(/url\(["']?(.*?)["']?\)/);
    if (_m) { _img = new Image(); _img.src = _m[1]; }
  }
  if (!_img) return;
  var _host = _el.tagName === 'IMG' ? _el.parentNode : _el;
  if (!_host) return;
  if (getComputedStyle(_host).position === 'static') _host.style.position = 'relative';
  var _r = _el.getBoundingClientRect(), _hr = _host.getBoundingClientRect();
  var _cv = document.createElement('canvas');
  _cv.width = 1080; _cv.height = 1920;
  _cv.style.cssText = 'position:absolute;pointer-events:none;display:block;z-index:3;'
    + 'left:' + (_r.left - _hr.left) + 'px;top:' + (_r.top - _hr.top) + 'px;'
    + 'width:' + _r.width + 'px;height:' + _r.height + 'px;';
  var _fx = kit.deform(_cv, _img, %(mode)s);
  if (!_fx) return;
  _host.appendChild(_cv);
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': %(amount)s, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _fx.draw(_drv.p, timeline.time());
  } }, %(at)s);
})();""",
        "W18": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.kit || !kit.deform) return;
  var _img = null;
  if (_el.tagName === 'IMG') { _img = _el; }
  else {
    var _bg = getComputedStyle(_el).backgroundImage || '';
    var _m = _bg.match(/url\(["']?(.*?)["']?\)/);
    if (_m) { _img = new Image(); _img.src = _m[1]; }
  }
  if (!_img) return;
  var _host = _el.tagName === 'IMG' ? _el.parentNode : _el;
  if (!_host) return;
  if (getComputedStyle(_host).position === 'static') _host.style.position = 'relative';
  var _r = _el.getBoundingClientRect(), _hr = _host.getBoundingClientRect();
  var _cv = document.createElement('canvas');
  _cv.width = 1080; _cv.height = 1920;
  _cv.style.cssText = 'position:absolute;pointer-events:none;display:block;z-index:3;'
    + 'left:' + (_r.left - _hr.left) + 'px;top:' + (_r.top - _hr.top) + 'px;'
    + 'width:' + _r.width + 'px;height:' + _r.height + 'px;';
  var _fx = kit.deform(_cv, _img, %(mode)s);
  if (!_fx) return;
  _host.appendChild(_cv);
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': %(amount)s, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _fx.draw(_drv.p, timeline.time());
  } }, %(at)s);
})();""",
        "W20": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _p = _t.parentNode;
  if (getComputedStyle(_p).position === 'static') _p.style.position = 'relative';
  var _r = _t.getBoundingClientRect(), _pr = _p.getBoundingClientRect();
  var _L = _r.left - _pr.left, _T = _r.top - _pr.top;
  var _ang = %(angle)s * Math.PI / 180, _ux = Math.cos(_ang), _uy = Math.sin(_ang);
  var _n = %(copies)s, _g = [], _i;
  for (_i = _n; _i >= 1; _i--) {
    var _c = _t.cloneNode(true);
    _c.removeAttribute('data-anim');
    _c.setAttribute('aria-hidden', 'true');
    _c.style.cssText = 'position:absolute;pointer-events:none;opacity:0;left:' + _L + 'px;top:' + _T
      + 'px;width:' + _r.width + 'px;height:' + _r.height + 'px;';
    _p.appendChild(_c);
    _g.push({ el: _c, k: _i });
  }
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': 1, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    for (var j = 0; j < _g.length; j++) {
      var g = _g[j], o = Math.pow(%(fade)s, g.k) * 0.55 * _drv.p;
      var d = %(dist)s * _drv.p * g.k / _n;
      g.el.style.opacity = o.toFixed(3);
      g.el.style.transform = 'translate(' + (_ux * d).toFixed(2) + 'px,' + (_uy * d).toFixed(2) + 'px)';
    }
  } }, %(at)s);
})();""",
        "K13": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.rough) return;
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _b = _sc.getBoundingClientRect(), _r = _t.getBoundingClientRect();
  var _svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  _svg.setAttribute('viewBox', '0 0 ' + Math.round(_b.width) + ' ' + Math.round(_b.height));
  _svg.style.cssText = 'position:absolute;left:0;top:0;width:100%%;height:100%%;pointer-events:none;overflow:visible;z-index:%(z)s;';
  _sc.appendChild(_svg);
  var _g = kit.rough('%(type)s', { x: _r.left - _b.left, y: _r.top - _b.top, w: _r.width, h: _r.height }, '%(seed)s', %(passes)s);
  var _i, _p, _len;
  for (_i = 0; _i < _g.strokes.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.strokes[_i]);
    _p.setAttribute('fill', 'none');
    _p.setAttribute('stroke', '%(color)s');
    _p.setAttribute('stroke-width', %(w)s);
    _p.setAttribute('stroke-linecap', 'round');
    _len = _p.getTotalLength ? (_p.getTotalLength() || 1) : 1;
    _p.style.strokeDasharray = _len + ' ' + _len;
    _svg.appendChild(_p);
    timeline.fromTo(_p, { 'strokeDashoffset': _len }, { 'strokeDashoffset': 0, 'duration': %(dur)s, 'ease': 'power1.inOut' }, %(at)s + _i * %(stagger)s);
  }
  for (_i = 0; _i < _g.fills.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.fills[_i]);
    _p.setAttribute('fill', '%(color)s');
    _p.setAttribute('opacity', '0');
    _svg.appendChild(_p);
    timeline.to(_p, { 'opacity': %(fillOpacity)s, 'duration': %(dur)s, 'ease': 'none' }, %(at)s);
  }
})();""",
        "K14": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.rough) return;
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _b = _sc.getBoundingClientRect(), _r = _t.getBoundingClientRect();
  var _svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  _svg.setAttribute('viewBox', '0 0 ' + Math.round(_b.width) + ' ' + Math.round(_b.height));
  _svg.style.cssText = 'position:absolute;left:0;top:0;width:100%%;height:100%%;pointer-events:none;overflow:visible;z-index:%(z)s;';
  _sc.appendChild(_svg);
  var _g = kit.rough('%(type)s', { x: _r.left - _b.left, y: _r.top - _b.top, w: _r.width, h: _r.height }, '%(seed)s', %(passes)s);
  var _i, _p, _len;
  for (_i = 0; _i < _g.strokes.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.strokes[_i]);
    _p.setAttribute('fill', 'none');
    _p.setAttribute('stroke', '%(color)s');
    _p.setAttribute('stroke-width', %(w)s);
    _p.setAttribute('stroke-linecap', 'round');
    _len = _p.getTotalLength ? (_p.getTotalLength() || 1) : 1;
    _p.style.strokeDasharray = _len + ' ' + _len;
    _svg.appendChild(_p);
    timeline.fromTo(_p, { 'strokeDashoffset': _len }, { 'strokeDashoffset': 0, 'duration': %(dur)s, 'ease': 'power1.inOut' }, %(at)s + _i * %(stagger)s);
  }
  for (_i = 0; _i < _g.fills.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.fills[_i]);
    _p.setAttribute('fill', '%(color)s');
    _p.setAttribute('opacity', '0');
    _svg.appendChild(_p);
    timeline.to(_p, { 'opacity': %(fillOpacity)s, 'duration': %(dur)s, 'ease': 'none' }, %(at)s);
  }
})();""",
        "K15": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.rough) return;
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _b = _sc.getBoundingClientRect(), _r = _t.getBoundingClientRect();
  var _svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  _svg.setAttribute('viewBox', '0 0 ' + Math.round(_b.width) + ' ' + Math.round(_b.height));
  _svg.style.cssText = 'position:absolute;left:0;top:0;width:100%%;height:100%%;pointer-events:none;overflow:visible;z-index:%(z)s;';
  _sc.appendChild(_svg);
  var _g = kit.rough('%(type)s', { x: _r.left - _b.left, y: _r.top - _b.top, w: _r.width, h: _r.height }, '%(seed)s', %(passes)s);
  var _i, _p, _len;
  for (_i = 0; _i < _g.strokes.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.strokes[_i]);
    _p.setAttribute('fill', 'none');
    _p.setAttribute('stroke', '%(color)s');
    _p.setAttribute('stroke-width', %(w)s);
    _p.setAttribute('stroke-linecap', 'round');
    _len = _p.getTotalLength ? (_p.getTotalLength() || 1) : 1;
    _p.style.strokeDasharray = _len + ' ' + _len;
    _svg.appendChild(_p);
    timeline.fromTo(_p, { 'strokeDashoffset': _len }, { 'strokeDashoffset': 0, 'duration': %(dur)s, 'ease': 'power1.inOut' }, %(at)s + _i * %(stagger)s);
  }
  for (_i = 0; _i < _g.fills.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.fills[_i]);
    _p.setAttribute('fill', '%(color)s');
    _p.setAttribute('opacity', '0');
    _svg.appendChild(_p);
    timeline.to(_p, { 'opacity': %(fillOpacity)s, 'duration': %(dur)s, 'ease': 'none' }, %(at)s);
  }
})();""",
        "K16": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.rough) return;
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _b = _sc.getBoundingClientRect(), _r = _t.getBoundingClientRect();
  var _svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  _svg.setAttribute('viewBox', '0 0 ' + Math.round(_b.width) + ' ' + Math.round(_b.height));
  _svg.style.cssText = 'position:absolute;left:0;top:0;width:100%%;height:100%%;pointer-events:none;overflow:visible;z-index:%(z)s;';
  _sc.appendChild(_svg);
  var _g = kit.rough('%(type)s', { x: _r.left - _b.left, y: _r.top - _b.top, w: _r.width, h: _r.height }, '%(seed)s', %(passes)s);
  var _i, _p, _len;
  for (_i = 0; _i < _g.strokes.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.strokes[_i]);
    _p.setAttribute('fill', 'none');
    _p.setAttribute('stroke', '%(color)s');
    _p.setAttribute('stroke-width', %(w)s);
    _p.setAttribute('stroke-linecap', 'round');
    _len = _p.getTotalLength ? (_p.getTotalLength() || 1) : 1;
    _p.style.strokeDasharray = _len + ' ' + _len;
    _svg.appendChild(_p);
    timeline.fromTo(_p, { 'strokeDashoffset': _len }, { 'strokeDashoffset': 0, 'duration': %(dur)s, 'ease': 'power1.inOut' }, %(at)s + _i * %(stagger)s);
  }
  for (_i = 0; _i < _g.fills.length; _i++) {
    _p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    _p.setAttribute('d', _g.fills[_i]);
    _p.setAttribute('fill', '%(color)s');
    _p.setAttribute('opacity', '0');
    _svg.appendChild(_p);
    timeline.to(_p, { 'opacity': %(fillOpacity)s, 'duration': %(dur)s, 'ease': 'none' }, %(at)s);
  }
})();""",
        "U21": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.lines) return;
  var _ls = kit.lines(_t);
  var _host = _t.parentNode;
  if (!_host) return;
  if (getComputedStyle(_host).position === 'static') _host.style.position = 'relative';
  _t.style.position = 'relative';
  _t.style.zIndex = '1';
  var _ox = _t.offsetLeft, _oy = _t.offsetTop;
  var _i, _d;
  for (_i = 0; _i < _ls.length; _i++) {
    _d = document.createElement('i');
    _d.style.cssText = 'position:absolute;pointer-events:none;z-index:0;background:%(color)s;border-radius:%(radius)spx;'
      + 'transform:scaleX(0);transform-origin:0 50%%;'
      + 'left:' + (_ox + _ls[_i].x - %(padX)s) + 'px;top:' + (_oy + _ls[_i].y - %(padY)s) + 'px;'
      + 'width:' + (_ls[_i].w + %(padX)s * 2) + 'px;height:' + (_ls[_i].h + %(padY)s * 2) + 'px;';
    _host.appendChild(_d);
    timeline.to(_d, { 'scaleX': 1, 'duration': %(dur)s, 'ease': 'power2.out' }, %(at)s + _i * %(stagger)s);
  }
  timeline.to(_t, { 'color': '%(ink)s', 'duration': %(dur)s, 'ease': 'none' }, %(at)s + %(dur)s * 0.5);
})();""",
        "G04": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.fitLines) return;
  var _drv = { w: %(fromW)s };
  timeline.to(_drv, { 'w': %(toW)s, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _t.style.width = _drv.w + 'px';
    kit.fitLines(_t, %(lines)s, { min: %(minFs)s, max: %(maxFs)s });
  } }, %(at)s);
})();""",
        "S13": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit || !kit.captionTokens) return;
  var _raw = '%(text)s', _chunk = %(chunk)s, _step = %(span)s / Math.max(1, Math.ceil(_raw.length / _chunk));
  var _items = [], _i;
  for (_i = 0; _i * _chunk < _raw.length; _i++) {
    _items.push({ text: _raw.substr(_i * _chunk, _chunk), from: %(at)s + _i * _step, to: %(at)s + (_i + 1) * _step });
  }
  _t.innerHTML = '';
  var _sp = [];
  for (_i = 0; _i < _items.length; _i++) {
    var _s = document.createElement('span');
    _s.textContent = _items[_i].text;
    _s.style.cssText = 'display:inline-block;padding:0 .12em;border-radius:.18em;';
    _t.appendChild(_s);
    _sp.push({ el: _s, from: _items[_i].from, to: _items[_i].to });
  }
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': 1, 'duration': %(span)s + 0.3, 'ease': 'none', 'onUpdate': function () {
    var now = timeline.time(), j;
    for (j = 0; j < _sp.length; j++) {
      var on = now >= _sp[j].from && now < _sp[j].to;
      _sp[j].el.style.color = on ? '%(ink)s' : '%(color)s';
      _sp[j].el.style.background = on ? '%(hl)s' : 'transparent';
      _sp[j].el.style.transform = on ? 'scale(1.08)' : 'scale(1)';
    }
  } }, %(at)s);
})();""",
        "S14": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit) return;
  var _raw = '%(text)s', _chunk = %(chunk)s;
  var _n = Math.ceil(_raw.length / _chunk), _step = %(span)s / Math.max(1, _n);
  _t.innerHTML = '';
  var _sp = [], _i;
  for (_i = 0; _i < _n; _i++) {
    var _s = document.createElement('span');
    _s.textContent = _raw.substr(_i * _chunk, _chunk);
    _s.style.cssText = 'display:inline-block;padding:.06em .22em;border-radius:.22em;opacity:0;'
      + 'background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.10);';
    _t.appendChild(_s);
    _sp.push({ el: _s, from: %(at)s + _i * _step, to: %(at)s + (_i + 1) * _step });
  }
  for (_i = 0; _i < _sp.length; _i++) {
    timeline.fromTo(_sp[_i].el, { 'opacity': 0, 'scale': 0.82 }, { 'opacity': 1, 'scale': 1, 'duration': %(dur)s, 'ease': 'back.out' }, %(at)s + _i * _step * 0.85);
  }
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': 1, 'duration': %(span)s + 0.3, 'ease': 'none', 'onUpdate': function () {
    var now = timeline.time(), j;
    for (j = 0; j < _sp.length; j++) {
      var on = now >= _sp[j].from && now < _sp[j].to;
      _sp[j].el.style.background = on ? '%(hl)s' : 'rgba(255,255,255,.06)';
      _sp[j].el.style.color = on ? '%(ink)s' : '%(color)s';
      _sp[j].el.style.borderColor = on ? '%(hl)s' : 'rgba(255,255,255,.10)';
      _sp[j].el.style.transform = on ? 'scale(1.12)' : 'scale(1)';
    }
  } }, %(at)s);
})();""",
        "S15": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.kit) return;
  var _b = _t.getBoundingClientRect();
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _cv = document.createElement('canvas');
  _cv.width = Math.max(2, Math.round(_b.width));
  _cv.height = Math.max(2, Math.round(_b.height));
  _cv.style.cssText = 'position:absolute;left:0;top:0;width:100%%;height:100%%;pointer-events:none;display:block;';
  _t.appendChild(_cv);
  var _c = _cv.getContext('2d');
  var _bars = %(bars)s, _base = [], _r = kit.seeded('%(seed)s'), _i;
  for (_i = 0; _i < _bars; _i++) _base.push(0.15 + _r() * 0.85);
  var _drv = { p: 0 };
  timeline.to(_drv, { 'p': 1, 'duration': %(dur)s, 'ease': 'none', 'onUpdate': function () {
    var t = timeline.time(), W = _cv.width, H = _cv.height, bw = W / _bars, i, drive, hh;
    _c.clearRect(0, 0, W, H);
    for (i = 0; i < _bars; i++) {
      drive = 0.42 + 0.58 * Math.pow(0.5 + 0.5 * Math.sin(t * (2.2 + _base[i] * 4) + i * 0.55), 1.7);
      hh = Math.max(4, _base[i] * drive * H * %(height)s);
      _c.fillStyle = i === %(bars)s - 1 ? '%(hl)s' : '%(color)s';
      _c.fillRect(i * bw + bw * 0.16, H - hh, bw * 0.68, hh);
    }
  } }, %(at)s);
})();""",
        "U23": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _txt = _t.textContent || '';
  _t.textContent = '';
  var _ch = [], _i;
  for (_i = 0; _i < _txt.length; _i++) {
    var _s = document.createElement('span');
    _s.textContent = _txt.charAt(_i);
    _s.style.opacity = '0';
    _t.appendChild(_s);
    _ch.push(_s);
  }
  var _drv = { n: 0 };
  timeline.to(_drv, { 'n': 1, 'duration': %(dur)s, 'ease': 'none', 'onUpdate': function () {
    var k = Math.floor(_drv.n * _ch.length), j;
    for (j = 0; j < _ch.length; j++) _ch[j].style.opacity = j < k ? '1' : '0';
  } }, %(at)s);
})();""",
        "U24": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  _t.style.display = 'inline-block';
  _t.style.opacity = '0';
  timeline.fromTo(_t, { 'opacity': 0, 'scale': %(fromScale)s, 'y': 26 },
    { 'opacity': 1, 'scale': 1, 'y': 0, 'duration': %(dur)s, 'ease': 'back.out' }, %(at)s);
  timeline.to(_t, { 'scale': 1.1, 'duration': 0.18, 'ease': 'sine.inOut' }, %(at)s + %(dur)s);
  timeline.to(_t, { 'scale': 1, 'duration': 0.24, 'ease': 'sine.out' }, %(at)s + %(dur)s + 0.18);
})();""",
        "Z03": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _NS = 'http://www.w3.org/2000/svg';
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _b = _sc.getBoundingClientRect(), _r = _t.getBoundingClientRect();
  var _txt = _t.textContent || '';
  _t.style.color = 'transparent';
  var _svg = document.createElementNS(_NS, 'svg');
  _svg.setAttribute('viewBox', '0 0 ' + Math.round(_b.width) + ' ' + Math.round(_b.height));
  _svg.style.cssText = 'position:absolute;left:0;top:0;width:100%%;height:100%%;pointer-events:none;z-index:%(z)s;';
  _sc.appendChild(_svg);
  var _x = _r.left - _b.left, _y = _r.top - _b.top + _r.height * 0.76;
  var _g = document.createElementNS(_NS, 'g');
  _svg.appendChild(_g);
  var _drv = { d: 0 };
  timeline.to(_drv, { 'd': 1, 'duration': %(dur)s, 'ease': 'power2.out', 'onUpdate': function () {
    while (_g.firstChild) _g.removeChild(_g.firstChild);
    var steps = Math.max(1, Math.round(%(layers)s * _drv.d)), i, el;
    for (i = steps; i >= 1; i--) {
      el = document.createElementNS(_NS, 'text');
      el.setAttribute('x', _x + i * %(step)s);
      el.setAttribute('y', _y + i * %(step)s * 1.12);
      el.setAttribute('font-size', _r.height * 0.92);
      el.setAttribute('font-weight', '820');
      el.setAttribute('fill', '%(side)s');
      el.textContent = _txt;
      _g.appendChild(el);
    }
    el = document.createElementNS(_NS, 'text');
    el.setAttribute('x', _x);
    el.setAttribute('y', _y);
    el.setAttribute('font-size', _r.height * 0.92);
    el.setAttribute('font-weight', '820');
    el.setAttribute('fill', '%(color)s');
    el.textContent = _txt;
    _g.appendChild(el);
  } }, %(at)s);
})();""",
        "K21": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.SplitText) return;
  var _sp = new SplitText(_t, {type: 'words,chars'});
  timeline.from(_sp.words, {'opacity': 0, 'y': %(y)s, 'duration': %(dur)s, 'stagger': %(stagger)s, 'ease': 'power2.out'}, %(at)s);
  timeline.from(_sp.chars, {'rotationX': -70, 'opacity': 0, 'duration': %(dur)s, 'stagger': %(charStagger)s, 'ease': 'back.out'}, %(at)s + %(wordDelay)s);
})();""",
        "T12": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  timeline.fromTo(_t, {'x': -%(dist)s, 'opacity': 0},
    {'x': 0, 'opacity': 1, 'duration': %(dur)s, 'ease': 'power2.out'}, %(at)s);
})();""",
        "T13": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.CustomBounce) return;
  CustomBounce.create('kit-bounce', {'strength': %(strength)s, 'squash': %(squash)s});
  timeline.fromTo(_t, {'y': -%(drop)s, 'opacity': 0},
    {'y': 0, 'opacity': 1, 'duration': %(dur)s, 'ease': 'kit-bounce'}, %(at)s);
  timeline.to(_t, {'scaleY': %(squashY)s, 'scaleX': %(squashX)s, 'duration': %(dur)s, 'ease': 'kit-bounce-squash'}, %(at)s);
})();""",
        "U25": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.DrawSVGPlugin) return;
  timeline.fromTo(_t, {'drawSVG': '0%% %(a)s%%'}, {'drawSVG': '%(b)s%% 100%%', 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U26": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  if (!_els.length || !window.DrawSVGPlugin) return;
  var _from = ['0%% 0%%', '100%% 100%%', '50%% 50%%'];
  _els.forEach(function (el, i) {
    timeline.fromTo(el, {'drawSVG': _from[i %% 3]}, {'drawSVG': '0%% 100%%', 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s + i * %(stagger)s);
  });
})();""",
        "U27": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MorphSVGPlugin) return;
  var _to = _t.getAttribute('data-morph-to') || '%(to)s';
  if (!_to || !document.querySelector(_to)) return;
  timeline.to(_t, {'morphSVG': _to, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U28": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MotionPathPlugin) return;
  var _p = _t.getAttribute('data-motion-path') || '%(path)s';
  if (!_p || !document.querySelector(_p)) return;
  timeline.to(_t, {'motionPath': {'path': _p, 'align': _p, 'alignOrigin': [0.5, 0.5],
    'autoRotate': %(rotate)s, 'start': %(start)s, 'end': %(end)s},
    'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U29": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MotionPathPlugin) return;
  var _p = _t.getAttribute('data-motion-path') || '%(path)s';
  if (!_p || !document.querySelector(_p)) return;
  timeline.to(_t, {'motionPath': {'path': _p, 'align': _p, 'alignOrigin': [0.5, 0.5],
    'autoRotate': %(rotate)s, 'start': %(start)s, 'end': %(end)s},
    'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "K22": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.SplitText) return;
  var _sp = new SplitText(_t, {'type': '%(unit)s', 'mask': '%(unit)s'});
  timeline.from(_sp['%(unit)s'], {'yPercent': %(y)s, 'opacity': 0, 'duration': %(dur)s, 'stagger': %(stagger)s, 'ease': 'power3.out'}, %(at)s);
})();""",
        "K23": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.SplitText) return;
  var _box = _t.parentNode;
  var _sp = new SplitText(_t, {'type': 'lines', 'mask': 'lines'});
  timeline.from(_sp.lines, {'yPercent': 110, 'opacity': 0, 'duration': %(dur)s, 'stagger': %(stagger)s, 'ease': 'power3.out'}, %(at)s);
  var _done = false;
  timeline.call(function () {
    if (_done) return;
    _done = true;
    if (_box) _box.style.width = '%(toW)spx';
    _sp.revert();
    _sp = new SplitText(_t, {'type': 'lines', 'mask': 'lines'});
  }, null, %(at)s + %(resplitAt)s);
})();""",
        "K24": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.SplitText) return;
  var _sp = new SplitText(_t, {'type': 'chars', 'specialChars': ['%(keep)s']});
  timeline.from(_sp.chars, {'opacity': 0, 'y': %(y)s, 'duration': %(dur)s, 'stagger': %(stagger)s, 'ease': 'power2.out'}, %(at)s);
})();""",
        "U30": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.DrawSVGPlugin) return;
  timeline.fromTo(_t, {'drawSVG': '0%%'}, {'drawSVG': '100%%', 'duration': %(dur)s, 'ease': 'power2.inOut'}, %(at)s);
  if (%(back)s) timeline.to(_t, {'drawSVG': '100%% 100%%', 'duration': %(backDur)s, 'ease': 'power2.inOut'}, %(at)s + %(dur)s);
})();""",
        "U31": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.DrawSVGPlugin) return;
  timeline.fromTo(_t, {'drawSVG': '0%%'}, {'drawSVG': '100%%', 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U32": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MorphSVGPlugin) return;
  var _to = _t.getAttribute('data-morph-to') || '%(to)s';
  if (!_to || !document.querySelector(_to)) return;
  timeline.to(_t, {'morphSVG': {'shape': _to, 'shapeIndex': %(shapeIndex)s}, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U33": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MorphSVGPlugin) return;
  var _to = _t.getAttribute('data-morph-to') || '%(to)s';
  if (!_to || !document.querySelector(_to)) return;
  timeline.to(_t, {'morphSVG': {'shape': _to, 'type': 'rotational'}, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U34": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MorphSVGPlugin) return;
  var _to = _t.getAttribute('data-morph-to') || '%(to)s';
  if (!_to || !document.querySelector(_to)) return;
  timeline.to(_t, {'morphSVG': _to, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U35": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MotionPathPlugin) return;
  var _p = _t.getAttribute('data-motion-path') || '%(path)s';
  if (!_p || !document.querySelector(_p)) return;
  timeline.to(_t, {'motionPath': {'path': _p, 'align': _p, 'alignOrigin': [0.5, 0.5], 'curviness': %(curviness)s},
    'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U36": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MotionPathPlugin) return;
  var _p = _t.getAttribute('data-motion-path') || '%(path)s';
  if (!_p || !document.querySelector(_p)) return;
  timeline.to(_t, {'motionPath': {'path': _p, 'align': _p, 'alignOrigin': [%(ox)s, %(oy)s],
    'autoRotate': %(rotate)s, 'offsetX': %(offX)s, 'offsetY': %(offY)s},
    'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "U37": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.MotionPathPlugin) return;
  var _p = _t.getAttribute('data-motion-path') || '%(path)s';
  if (!_p || !document.querySelector(_p)) return;
  timeline.to(_t, {'motionPath': {'path': _p, 'align': _p, 'alignOrigin': [0.5, 0.5],
    'type': 'cubic', 'curviness': %(curviness)s, 'resolution': %(resolution)s},
    'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
})();""",
        "T14": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.RoughEase) return;
  var _e = RoughEase({'strength': %(strength)s, 'points': %(points)s, 'taper': 'both', 'randomize': false, 'clamp': true});
  timeline.fromTo(_t, {'x': -%(dist)s, 'opacity': 0},
    {'x': 0, 'opacity': 1, 'duration': %(dur)s, 'ease': _e, 'stagger': %(stagger)s}, %(at)s);
})();""",
        "T15": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.SlowMo) return;
  var _e = SlowMo(%(linear)s, %(power)s);
  timeline.fromTo(_t, {'x': -%(dist)s, 'opacity': 0}, {'x': 0, 'opacity': 1, 'duration': %(dur)s, 'ease': _e}, %(at)s);
})();""",
        "T16": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.ExpoScaleEase) return;
  var _e = ExpoScaleEase(%(from)s, %(to)s);
  timeline.to(_t, {'scale': %(to)s, 'duration': %(dur)s, 'ease': _e, 'transformOrigin': '50%% 50%%'}, %(at)s);
})();""",
        "T17": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.CustomEase) return;
  CustomEase.create('kit-twice', '%(curve)s');
  timeline.to(_t, {'x': %(dist)s, 'duration': %(dur)s, 'ease': 'kit-twice'}, %(at)s);
})();""",
        "T18": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.CustomBounce) return;
  CustomBounce.create('kit-back', {'strength': %(strength)s, 'endAtStart': true});
  timeline.to(_t, {'x': %(dist)s, 'duration': %(dur)s, 'ease': 'kit-back'}, %(at)s);
})();""",
        "T19": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.CustomBounce) return;
  CustomBounce.create('kit-sq', {'strength': %(strength)s, 'squash': %(squash)s});
  timeline.fromTo(_t, {'y': -%(drop)s, 'opacity': 0}, {'y': 0, 'opacity': 1, 'duration': %(dur)s, 'ease': 'kit-sq'}, %(at)s);
  if (%(squash)s) timeline.to(_t, {'scaleY': %(squashY)s, 'scaleX': %(squashX)s, 'duration': %(dur)s, 'ease': 'kit-sq-squash'}, %(at)s);
})();""",
        "T20": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.Physics2DPlugin) return;
  timeline.to(_t, {'duration': %(dur)s, 'ease': 'none',
    'physics2D': {'velocity': %(velocity)s, 'angle': %(angle)s, 'gravity': %(gravity)s,
      'xProp': 'left', 'yProp': 'top'}}, %(at)s);
})();""",
        "T21": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.Physics2DPlugin) return;
  timeline.to(_t, {'duration': %(dur)s, 'ease': 'none',
    'physics2D': {'velocity': %(velocity)s, 'angle': 0, 'gravity': 0,
      'acceleration': %(accel)s, 'accelerationAngle': 0}}, %(at)s);
})();""",
        "S16": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.TextPlugin) return;
  timeline.to(_t, {'duration': %(dur)s, 'text': {'value': '%(text)s', 'type': 'diff'}, 'ease': 'none'}, %(at)s);
})();""",
        "S17": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.TextPlugin) return;
  timeline.to(_t, {'duration': %(dur)s,
    'text': {'value': '%(text)s', 'oldClass': '%(oldClass)s', 'newClass': '%(newClass)s'}, 'ease': 'none'}, %(at)s);
})();""",
        "G05": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.Flip) return;
  var _items = _t.children;
  if (!_items.length) return;
  var _st = Flip.getState(_items);
  _t.style.gridTemplateColumns = '%(columns)s';
  _t.style.gap = '%(gap)s';
  var _f = Flip.from(_st, {'duration': %(dur)s, 'ease': '%(ease)s', 'absolute': true, 'stagger': %(stagger)s});
  _f.pause(0);
  var _dv = {p: 0};
  timeline.to(_dv, {'p': 1, 'duration': %(dur)s, 'ease': 'none', 'onUpdate': function () { _f.progress(_dv.p); }}, %(at)s);
})();""",
        "G06": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.Flip) return;
  var _items = _t.children;
  if (!_items.length) return;
  var _st = Flip.getState(_items);
  _t.style.flexDirection = '%(direction)s';
  var _f = Flip.from(_st, {'duration': %(dur)s, 'ease': '%(ease)s', 'absolute': true, 'spin': %(spin)s, 'simple': true});
  _f.pause(0);
  var _dv = {p: 0};
  timeline.to(_dv, {'p': 1, 'duration': %(dur)s, 'ease': 'none', 'onUpdate': function () { _f.progress(_dv.p); }}, %(at)s);
})();""",
        "S18": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.gsap) return;
  if (getComputedStyle(_t).position === 'static') { _t.style.position = 'relative'; }
  var _bar = document.createElement('i');
  _bar.style.cssText = 'position:absolute;left:0;bottom:-%(h)spx;height:%(h)spx;width:0;background:%(color)s;border-radius:%(h)spx;display:block;';
  _t.appendChild(_bar);
  var _map = gsap.utils.mapRange(0, 1, 0, %(maxWidth)s);
  var _clamp = gsap.utils.clamp(0, %(maxWidth)s);
  var _dv = {p: 0};
  timeline.to(_dv, {'p': 1, 'duration': %(dur)s, 'ease': '%(ease)s', 'onUpdate': function () {
    _bar.style.width = _clamp(_map(_dv.p)).toFixed(1) + 'px';
  }}, %(at)s);
})();""",
        "S19": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.gsap) return;
  var _els = [].slice.call(_t.children);
  if (!_els.length) return;
  var _r = gsap.utils.random(0, 1, true);
  var _sc = gsap.utils.random(%(minScale)s, %(maxScale)s, true);
  var _rt = gsap.utils.random(-%(maxRot)s, %(maxRot)s, true);
  var _from = _els.map(function () {
    return {x: (_r() * 2 - 1) * %(dist)s, y: (_r() * 2 - 1) * %(dist)s, rotation: _rt(), scale: _sc(), opacity: 0};
  });
  _els.forEach(function (el, i) {
    timeline.fromTo(el, _from[i], {'x': 0, 'y': 0, 'rotation': 0, 'scale': 1, 'opacity': 1,
      'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s + i * %(stagger)s);
  });
})();""",
        "UA08": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.gsap || !gsap.registerEffect) return;
  gsap.registerEffect({
    name: 'kitCardIn',
    effect: function (targets, cfg) {
      return gsap.timeline().from(targets, {'opacity': 0, 'y': cfg.y, 'scale': cfg.scale,
        'duration': cfg.dur, 'stagger': cfg.stagger, 'ease': 'power3.out'});
    },
    defaults: {'y': %(y)s, 'scale': 0.94, 'dur': %(dur)s, 'stagger': %(stagger)s}
  });
  var _tw = gsap.effects.kitCardIn(_t.children.length ? _t.children : _t);
  if (!_tw || !_tw.pause) return;
  _tw.pause(0);
  var _dv = {p: 0};
  timeline.to(_dv, {'p': 1, 'duration': %(dur)s * 1.6, 'ease': 'none', 'onUpdate': function () { _tw.progress(_dv.p); }}, %(at)s);
})();""",
        "G07": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.gsap) return;
  var _els = [].slice.call(_t.children);
  if (!_els.length) return;
  timeline.from(_els, {'opacity': 0, 'scale': %(fromScale)s, 'duration': %(dur)s,
    'stagger': {'grid': [%(cols)s, %(rows)s], 'from': '%(from)s', 'each': %(each)s, 'ease': 'power2.out'}}, %(at)s);
})();""",
        "G08": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _from = (_t.getAttribute('data-morph-from') || '%(from)s').split(',');
  if (_from.length < 5) return;
  var _img = _t.querySelector('%(child)s');
  var _txt = _t.querySelector('%(textChild)s');
  var _startH = _img ? _img.getBoundingClientRect().height : 0;
  timeline.fromTo(_t,
    {'left': parseFloat(_from[0]), 'top': parseFloat(_from[1]),
     'width': parseFloat(_from[2]), 'height': parseFloat(_from[3]),
     'borderRadius': parseFloat(_from[4])},
    {'left': %(toX)s, 'top': %(toY)s, 'width': %(toW)s, 'height': %(toH)s,
     'borderRadius': %(toR)s, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
  if (_img && %(imgH)s) {
    timeline.fromTo(_img, {'height': _startH}, {'height': %(imgH)s, 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
  }
  if (_txt) timeline.to(_txt, {'opacity': 1, 'duration': %(fadeDur)s, 'ease': 'power2.out'}, %(at)s + %(dur)s * %(fadeAt)s);
})();""",
        "G09": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t || !window.Flip) return;
  var _items = [].slice.call(_t.children);
  if (!_items.length) return;
  timeline.from(_items, {'opacity': 0, 'y': %(y)s, 'scale': %(fromScale)s, 'duration': %(dur)s,
    'stagger': %(stagger)s, 'ease': 'power2.out'}, %(at)s);
  var _st = Flip.getState(_items);
  _t.style.gridTemplateColumns = '%(columns)s';
  var _f = Flip.from(_st, {'duration': %(flipDur)s, 'ease': '%(ease)s', 'absolute': true, 'stagger': %(flipStagger)s});
  _f.pause(0);
  var _dv = {p: 0};
  timeline.to(_dv, {'p': 1, 'duration': %(flipDur)s, 'ease': 'none',
    'onUpdate': function () { _f.progress(_dv.p); }}, %(at)s + %(flipAt)s);
})();""",
        "X30": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  if (!_els.length) return;
  _els.forEach(function (el) {
    el.style.clipPath = 'circle(0%% at 50%% 50%%)';
  });
  timeline.to(_els, {'clipPath': 'circle(%(pct)s%% at 50%% 50%%)', 'duration': %(dur)s,
    'ease': '%(ease)s', 'stagger': %(stagger)s}, %(at)s);
})();""",
        "X31": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _st = _sc.getBoundingClientRect(), _r = _t.getBoundingClientRect();
  var _to = (_t.getAttribute('data-escape-to') || '%(to)s').split(',');
  if (_to.length < 2) return;
  var _g = _t.cloneNode(true);
  _g.removeAttribute('data-anim');
  _g.removeAttribute('id');
  _g.setAttribute('aria-hidden', 'true');
  _g.style.cssText = 'position:absolute;pointer-events:none;z-index:%(z)s;display:grid;place-items:center;'
    + 'left:' + (_r.left - _st.left) + 'px;top:' + (_r.top - _st.top) + 'px;'
    + 'width:' + _r.width + 'px;height:' + _r.height + 'px;';
  _sc.appendChild(_g);
  timeline.to(_t, {'opacity': 0, 'duration': %(hideDur)s, 'ease': 'none'}, %(at)s);
  timeline.to(_g, {'opacity': 1, 'duration': %(hideDur)s, 'ease': 'none'}, %(at)s);
  timeline.fromTo(_g, {'left': _r.left - _st.left, 'top': _r.top - _st.top, 'scale': 1},
    {'left': parseFloat(_to[0]), 'top': parseFloat(_to[1]), 'scale': %(scale)s,
     'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s + %(hideDur)s);
})();""",
        "W21": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _to = (_t.getAttribute('data-frame-to') || '%(frameTo)s').split(',');
  if (_to.length < 4) return;
  var _img = _t.querySelector('%(child)s');
  timeline.to(_t, {'left': parseFloat(_to[0]), 'top': parseFloat(_to[1]),
    'width': parseFloat(_to[2]), 'height': parseFloat(_to[3]),
    'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
  if (_img) timeline.fromTo(_img, {'objectPosition': '%(focusFrom)s'},
    {'objectPosition': '%(focusTo)s', 'duration': %(dur)s, 'ease': '%(ease)s'}, %(at)s);
  var _txt = _t.querySelector('%(textChild)s');
  if (_txt) timeline.to(_txt, {'opacity': 1, 'duration': %(fadeDur)s, 'ease': 'power2.out'}, %(at)s + %(dur)s * %(fadeAt)s);
})();""",
        "X32": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _sc = _t.closest('.scene') || document.getElementById('stage');
  var _bd = _sc.querySelector('%(backdrop)s');
  if (_bd) timeline.to(_bd, {'opacity': %(dim)s, 'duration': %(dimDur)s, 'ease': 'power2.out'}, %(at)s);
  timeline.fromTo(_t, {'scale': %(fromScale)s, 'y': %(fromY)s, 'opacity': 0},
    {'scale': 1, 'y': 0, 'opacity': 1, 'duration': %(dur)s, 'ease': 'power3.out'}, %(at)s);
})();""",
        "G12": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _a = (_t.getAttribute('data-frame-from') || '%(from)s').split(',');
  var _b = (_t.getAttribute('data-morph-to') || '%(to)s').split(',');
  if (_a.length < 5 || _b.length < 5) return;
  var _rect = function (v) { return {'left': parseFloat(v[0]), 'top': parseFloat(v[1]),
    'width': parseFloat(v[2]), 'height': parseFloat(v[3]), 'borderRadius': parseFloat(v[4])}; };
  timeline.to(_t, Object.assign(_rect(_b), {'duration': %(dur)s, 'ease': 'power3.inOut'}), %(at)s);
  timeline.to(_t, Object.assign(_rect(_a), {'duration': %(dur)s, 'ease': 'power3.inOut'}), %(at)s + %(backAt)s);
})();""",
        "G13": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  if (!_els.length) return;
  _els.forEach(function (el, i) {
    var _to = (el.getAttribute('data-morph-to') || '%(to)s').split(',');
    if (_to.length < 4) return;
    timeline.to(el, {'left': parseFloat(_to[0]), 'top': parseFloat(_to[1]),
      'width': parseFloat(_to[2]), 'height': parseFloat(_to[3]),
      'borderRadius': parseFloat(_to[4] || 22),
      'duration': %(dur)s, 'ease': 'power3.inOut'}, %(at)s + i * %(stagger)s);
  });
})();""",
        "G14": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _img = _t.querySelector('%(img)s');
  timeline.to(_t, {'top': %(openTop)s, 'height': %(openH)s, 'borderRadius': %(openR)s,
    'duration': %(dur)s, 'ease': 'power3.inOut'}, %(at)s);
  if (_img) timeline.to(_img, {'width': %(imgW)s, 'height': %(imgH)s, 'borderRadius': %(imgR)s,
    'duration': %(dur)s, 'ease': 'power3.inOut'}, %(at)s);
  timeline.to(_t, {'top': %(listTop)s, 'height': %(listH)s, 'borderRadius': %(listR)s,
    'duration': %(backDur)s, 'ease': 'power3.inOut'}, %(at)s + %(backAt)s);
  if (_img) timeline.to(_img, {'width': %(imgSmall)s, 'height': %(imgSmall)s, 'borderRadius': 14,
    'duration': %(backDur)s, 'ease': 'power3.inOut'}, %(at)s + %(backAt)s);
})();""",
        "G16": """(function () {
  var _els = [].slice.call(document.querySelectorAll('%(sel)s'));
  if (!_els.length) return;
  var _n = _els.length;
  _els.forEach(function (el, i) {
    var _lin = _n > 1 ? i / (_n - 1) : 0;
    var _curve = Math.pow(_lin, %(power)s);
    timeline.fromTo(el, {'opacity': 0, 'y': %(y)s},
      {'opacity': 1, 'y': 0, 'duration': %(dur)s, 'ease': 'power2.out'}, %(at)s + _curve * %(span)s);
  });
})();""",
        "S20": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  timeline.to(_t, {'x': %(dx)s, 'duration': %(dur)s, 'ease': 'power2.out'}, %(at)s);
  timeline.to(_t, {'y': %(dy)s, 'duration': %(dur)s, 'ease': 'power2.inOut'}, %(at)s + %(gap)s);
  timeline.to(_t, {'rotation': %(rot)s, 'duration': %(dur)s * 0.8, 'ease': 'power2.out'}, %(at)s + %(gap)s * 2);
})();""",
        "S21": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  timeline.to(_t, {'x': %(dist)s, 'duration': %(dur)s, 'ease': 'power1.inOut'}, %(at)s);
  timeline.to(_t, {'x': %(backX)s, 'duration': %(backDur)s, 'ease': 'power2.inOut'}, %(at)s + %(interruptAt)s);
})();""",
        "S22": """(function () {
  var _t = document.querySelector('%(sel)s');
  if (!_t) return;
  var _peak = %(peak)s, _decay = %(decay)s, _t0 = %(at)s;
  for (var i = 0; i < %(times)s; i++) {
    var _amp = 1 + (_peak - 1) * Math.pow(_decay, i);
    timeline.to(_t, {'scale': _amp, 'duration': %(upDur)s, 'ease': 'power2.out'}, _t0 + i * %(cycle)s);
    timeline.to(_t, {'scale': 1, 'duration': %(downDur)s, 'ease': 'power2.inOut'}, _t0 + i * %(cycle)s + %(upDur)s);
  }
})();""",
        "GT01": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ApertureWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ApertureWipe', { from: '%(from)s', params: {"blades": %(blades)s, "rotation": %(rotation)s, "shadow": %(shadow)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT02": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ArrowWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ArrowWipe', { from: '%(from)s', params: {"direction": _n(%(direction)s, 2), "notch": %(notch)s, "width": %(width)s, "count": %(count)s, "origin": _b(%(origin)s), "smoothness": %(smoothness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT03": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('BlockCover')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'BlockCover', { from: '%(from)s', params: {"blocks": %(blocks)s, "color": _n(%(color)s, 4), "pop": %(pop)s, "smoothness": %(smoothness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT04": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('BlockSlide')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'BlockSlide', { from: '%(from)s', params: {"grid": _n(%(grid)s, 2), "direction": _n(%(direction)s, 2), "stagger": %(stagger)s, "zoom": %(zoom)s, "background": _n(%(background)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT05": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('BloomDissolve')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'BloomDissolve', { from: '%(from)s', params: {"spread": %(spread)s, "threshold": %(threshold)s, "intensity": %(intensity)s, "tint": _n(%(tint)s, 3)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT06": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('BrushWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'BrushWipe', { from: '%(from)s', params: {"strokes": %(strokes)s, "angle": %(angle)s, "roughness": %(roughness)s, "waviness": %(waviness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT07": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ButterflyWaveScrawler')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ButterflyWaveScrawler', { from: '%(from)s', params: {"amplitude": %(amplitude)s, "waves": %(waves)s, "colorSeparation": %(colorSeparation)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT08": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CameraShake')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CameraShake', { from: '%(from)s', params: {"strength": %(strength)s, "jolts": %(jolts)s, "blur": %(blur)s, "split": %(split)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT09": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CardDeal')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CardDeal', { from: '%(from)s', params: {"grid": _n(%(grid)s, 2), "deck": _n(%(deck)s, 2), "spin": %(spin)s, "shadow": %(shadow)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT10": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CardSwipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CardSwipe', { from: '%(from)s', params: {"direction": _n(%(direction)s, 2), "rotation": %(rotation)s, "depth": %(depth)s, "backColor": _n(%(backColor)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT11": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CellDissolve')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CellDissolve', { from: '%(from)s', params: {"cells": %(cells)s, "smoothness": %(smoothness)s, "border": %(border)s, "borderColor": _n(%(borderColor)s, 4), "seed": %(seed)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT12": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CircleBurst')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CircleBurst', { from: '%(from)s', params: {"center": _n(%(center)s, 2), "color1": _n(%(color1)s, 4), "color2": _n(%(color2)s, 4), "color3": _n(%(color3)s, 4), "stagger": %(stagger)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT13": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CircleOpen')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CircleOpen', { from: '%(from)s', params: {"smoothness": %(smoothness)s, "opening": _b(%(opening)s)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT14": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Clothesline')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Clothesline', { from: '%(from)s', params: {"direction": %(direction)s, "sway": %(sway)s, "size": %(size)s, "background": _n(%(background)s, 4), "lineColor": _n(%(lineColor)s, 4), "pinColor": _n(%(pinColor)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT15": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CodeRain')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CodeRain', { from: '%(from)s', params: {"cellSize": %(cellSize)s, "trail": %(trail)s, "tint": %(tint)s, "glow": _n(%(glow)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT16": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ColorCoords')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ColorCoords', { from: '%(from)s', params: {} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT17": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ColorDistance')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ColorDistance', { from: '%(from)s', params: {"power": %(power)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT18": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ComicPanels')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ComicPanels', { from: '%(from)s', params: {"gutter": %(gutter)s, "gutterColor": _n(%(gutterColor)s, 4), "borderColor": _n(%(borderColor)s, 4), "seed": %(seed)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT19": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CrossWarp')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CrossWarp', { from: '%(from)s', params: {} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT20": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CrossZoom')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CrossZoom', { from: '%(from)s', params: {"strength": %(strength)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT21": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Crosshatch')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Crosshatch', { from: '%(from)s', params: {"center": _n(%(center)s, 2), "threshold": %(threshold)s, "fadeEdge": %(fadeEdge)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT22": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CurvedWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CurvedWipe', { from: '%(from)s', params: {"direction": _n(%(direction)s, 2), "curvature": %(curvature)s, "smoothness": %(smoothness)s, "shadow": _n(%(shadow)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT23": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('CylinderRoll')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'CylinderRoll', { from: '%(from)s', params: {"curvature": %(curvature)s, "blur": %(blur)s, "shading": %(shading)s, "chroma": %(chroma)s, "downward": _b(%(downward)s)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT24": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('DefocusBlur')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'DefocusBlur', { from: '%(from)s', params: {"blurSize": %(blurSize)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT25": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('DirectionalWarp')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'DirectionalWarp', { from: '%(from)s', params: {"smoothness": %(smoothness)s, "direction": _n(%(direction)s, 2)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT26": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('DirectionalWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'DirectionalWipe', { from: '%(from)s', params: {"direction": _n(%(direction)s, 2), "smoothness": %(smoothness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT27": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Disintegrate')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Disintegrate', { from: '%(from)s', params: {"particleSize": %(particleSize)s, "direction": _n(%(direction)s, 2), "spread": %(spread)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT28": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('DominoFall')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'DominoFall', { from: '%(from)s', params: {"count": %(count)s, "reverse": _b(%(reverse)s), "knock": %(knock)s, "lean": %(lean)s, "perspective": %(perspective)s, "shading": %(shading)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT29": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('DoomMelt')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'DoomMelt', { from: '%(from)s', params: {"bars": %(bars)s, "amplitude": %(amplitude)s, "noise": %(noise)s, "frequency": %(frequency)s, "dripScale": %(dripScale)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT30": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('FacetedGlass')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'FacetedGlass', { from: '%(from)s', params: {"facets": %(facets)s, "refraction": %(refraction)s, "bevel": %(bevel)s, "highlight": _n(%(highlight)s, 4), "seed": %(seed)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT31": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('FilmStrip')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'FilmStrip', { from: '%(from)s', params: {"frames": %(frames)s, "shrink": %(shrink)s, "blur": %(blur)s, "weave": %(weave)s, "filmColor": _n(%(filmColor)s, 4), "holeColor": _n(%(holeColor)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT32": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Fisheye')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Fisheye', { from: '%(from)s', params: {"strength": %(strength)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT33": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('GeometricCollage')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'GeometricCollage', { from: '%(from)s', params: {"cells": %(cells)s, "stagger": %(stagger)s, "plates": _b(%(plates)s), "color1": _n(%(color1)s, 4), "color2": _n(%(color2)s, 4), "color3": _n(%(color3)s, 4), "shadow": %(shadow)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT34": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('GlitchDisplace')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'GlitchDisplace', { from: '%(from)s', params: {} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT35": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('GooeyWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'GooeyWipe', { from: '%(from)s', params: {"blobs": %(blobs)s, "smoothness": %(smoothness)s, "highlight": _n(%(highlight)s, 4), "shadow": _n(%(shadow)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT36": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Halftone')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Halftone', { from: '%(from)s', params: {"dots": %(dots)s, "angle": %(angle)s, "paper": _n(%(paper)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT37": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('HeartWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'HeartWipe', { from: '%(from)s', params: {"center": _n(%(center)s, 2), "smoothness": %(smoothness)s, "pulse": %(pulse)s, "glowColor": _n(%(glowColor)s, 3), "glow": %(glow)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT38": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Hexagonalize')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Hexagonalize', { from: '%(from)s', params: {"steps": %(steps)s, "horizontalHexagons": %(horizontalHexagons)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT39": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Hologram')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Hologram', { from: '%(from)s', params: {"tint": _n(%(tint)s, 3), "background": _n(%(background)s, 4), "scanlines": %(scanlines)s, "jitter": %(jitter)s, "flicker": %(flicker)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT40": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Honeycomb')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Honeycomb', { from: '%(from)s', params: {"size": %(size)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT41": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('HorizontalClose')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'HorizontalClose', { from: '%(from)s', params: {} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT42": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('HorizontalOpen')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'HorizontalOpen', { from: '%(from)s', params: {} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT43": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('LayoutGrid')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'LayoutGrid', { from: '%(from)s', params: {"gutter": %(gutter)s, "overlap": %(overlap)s, "band": %(band)s, "shadow": %(shadow)s, "paper": _n(%(paper)s, 4), "accent": _n(%(accent)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT44": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('LedWall')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'LedWall', { from: '%(from)s', params: {"cells": %(cells)s, "glow": %(glow)s, "flash": %(flash)s, "zoom": %(zoom)s, "triads": _b(%(triads)s), "direction": _n(%(direction)s, 2), "panel": _n(%(panel)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT45": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('LensFlare')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'LensFlare', { from: '%(from)s', params: {"angle": %(angle)s, "height": %(height)s, "intensity": %(intensity)s, "color": _n(%(color)s, 3)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT46": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('LightStreaks')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'LightStreaks', { from: '%(from)s', params: {"reach": %(reach)s, "threshold": %(threshold)s, "intensity": %(intensity)s, "tint": _n(%(tint)s, 3), "blur": %(blur)s, "vertical": _b(%(vertical)s)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT47": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Morph')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Morph', { from: '%(from)s', params: {"strength": %(strength)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT48": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('PaperTear')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'PaperTear', { from: '%(from)s', params: {"roughness": %(roughness)s, "tilt": %(tilt)s, "rim": %(rim)s, "paper": _n(%(paper)s, 4), "shadow": _n(%(shadow)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT49": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('PerlinDissolve')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'PerlinDissolve', { from: '%(from)s', params: {"scale": %(scale)s, "smoothness": %(smoothness)s, "seed": %(seed)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT50": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ProjectorThrow')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ProjectorThrow', { from: '%(from)s', params: {"darkness": %(darkness)s, "keystone": %(keystone)s, "blur": %(blur)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT51": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Reassemble')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Reassemble', { from: '%(from)s', params: {"rows": %(rows)s, "depth": %(depth)s, "spread": %(spread)s, "backColor": _n(%(backColor)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT52": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Refraction')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Refraction', { from: '%(from)s', params: {"strength": %(strength)s, "scale": %(scale)s, "dispersion": %(dispersion)s, "brightness": %(brightness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT53": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('RingSpin')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'RingSpin', { from: '%(from)s', params: {"rings": %(rings)s, "square": _b(%(square)s), "turns": %(turns)s, "stagger": %(stagger)s, "blur": %(blur)s, "settle": %(settle)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT54": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('RingsWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'RingsWipe', { from: '%(from)s', params: {"count": %(count)s, "center": _n(%(center)s, 2), "stagger": %(stagger)s, "radial": _b(%(radial)s), "borderWidth": %(borderWidth)s, "borderColor": _n(%(borderColor)s, 4), "smoothness": %(smoothness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT55": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Shatter')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Shatter', { from: '%(from)s', params: {"center": _n(%(center)s, 2), "shards": %(shards)s, "gravity": %(gravity)s, "seed": %(seed)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT56": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Shockwave')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Shockwave', { from: '%(from)s', params: {"tileSize": %(tileSize)s, "scatter": %(scatter)s, "diagonal": %(diagonal)s, "prism": %(prism)s, "glow": %(glow)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT57": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('ShutterWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'ShutterWipe', { from: '%(from)s', params: {"blades": %(blades)s, "tilt": %(tilt)s, "gate": %(gate)s, "color": _n(%(color)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT58": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('SimpleZoomOut')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'SimpleZoomOut', { from: '%(from)s', params: {"zoom_quickness": %(zoom_quickness)s, "fade": _b(%(fade)s)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT59": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('SketchDissolve')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'SketchDissolve', { from: '%(from)s', params: {"lineWidth": %(lineWidth)s, "edges": %(edges)s, "hatching": %(hatching)s, "paper": _n(%(paper)s, 4), "ink": _n(%(ink)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT60": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('SlotReels')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'SlotReels', { from: '%(from)s', params: {"reels": %(reels)s, "blur": %(blur)s, "stagger": %(stagger)s, "bounce": %(bounce)s, "separator": _n(%(separator)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT61": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Snapshot')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Snapshot', { from: '%(from)s', params: {"tilt": %(tilt)s, "border": %(border)s, "flash": %(flash)s, "shadow": %(shadow)s, "borderColor": _n(%(borderColor)s, 4)} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT62": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('SplatterWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'SplatterWipe', { from: '%(from)s', params: {"splats": %(splats)s, "spikiness": %(spikiness)s, "droplets": %(droplets)s, "drips": %(drips)s, "rim": %(rim)s, "seed": %(seed)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT63": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('StaticFade')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'StaticFade', { from: '%(from)s', params: {"n_noise_pixels": %(n_noise_pixels)s, "static_luminosity": %(static_luminosity)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT64": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('StripDatamoshGlitch')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'StripDatamoshGlitch', { from: '%(from)s', params: {"strength": %(strength)s, "horizontalBars": %(horizontalBars)s, "verticalSlits": %(verticalSlits)s, "tear": %(tear)s, "chroma": %(chroma)s, "residue": %(residue)s, "noiseAmount": %(noiseAmount)s, "scanAmount": %(scanAmount)s, "flashAmount": %(flashAmount)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT65": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('TruchetWipe')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'TruchetWipe', { from: '%(from)s', params: {"cells": %(cells)s, "outline": %(outline)s, "spread": %(spread)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT66": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('TvLostSignal')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'TvLostSignal', { from: '%(from)s', params: {} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT67": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('Vortex')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'Vortex', { from: '%(from)s', params: {"grid": %(grid)s, "center": _n(%(center)s, 2), "spin": %(spin)s, "randomness": %(randomness)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
        "GT68": """(function () {
  var _el = document.querySelector('%(sel)s');
  if (!_el || !window.glt || !glt.has('WhipPan')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, 'WhipPan', { from: '%(from)s', params: {"direction": _n(%(direction)s, 2), "blur": %(blur)s} });
  if (!_fx) return;
  var _p0 = %(p0)s, _p1 = %(p1)s, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: %(dur)s, ease: '%(ease)s',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, %(at)s);
})();""",
    }

    DEFAULTS = {
        "T01": {'unit': 'char', 'y': '0.5em', 'stagger': 0.05, 'ease': 'power3.out', 'dur': 0.55},
        "T02": {'unit': 'word', 'blur': '10px', 'y': '50px', 'stagger': 0.05, 'dur': 0.35},
        "T03": {'unit': 'char', 'angle': 92, 'perspective': 700, 'stagger': 0.045, 'dur': 0.65},
        "T04": {'strokeWidth': 1.4, 'color': '#38d6ff', 'fillDelay': 0.4, 'dur': 0.4, 'stagger': 0.05},
        "T05": {'speed': 0.05, 'dur': 0.6, 'stagger': 0.05},
        "T06": {'from': 0, 'to': 100, 'dur': 1.2, 'stagger': 0.05},
        "T09": {'stagger': 0.06, 'dur': 0.5},
        "W01": {'r': 26, 'dur': 0.6, 'stagger': 0.05},
        "X01": {'direction': 'up', 'dur': 0.8, 'stagger': 0.05},
        "C01": {'to': 1.06, 'dur': 4.0, 'stagger': 0.05},
        "C02": {'from': 1.08, 'dur': 4.0, 'stagger': 0.05},
        "C03": {'from': -3, 'to': 3, 'dur': 4.0, 'stagger': 0.05},
        "K03": {'rot': 4, 'dur': 0.62, 'stagger': 0.035, 'seed': 13},
        "G02": {'dur': 0.85, 'ease': 'power3.inOut', 'stagger': 0.03, 'outOp': 0.12},
        "X03": {'dist': 40, 'dur': 0.42, 'stagger': 0.05},
        "X05": {'dist': 90, 'dur': 0.4, 'stagger': 0.04},
        "K01": {'from': 1.22, 'y': 12, 'dur': 0.8, 'stagger': 0.05},
        "K04": {'from': '0.14em', 'to': '-0.02em', 'dur': 0.75, 'stagger': 0.05},
        "K07": {'h': 6, 'color': '#D8452C', 'dur': 0.6, 'stagger': 0.05},
        "K08": {'w': 3, 'color': '#D8452C', 'dur': 0.55, 'stagger': 0.05},
        "K10": {'dur': 0.8, 'stagger': 0.05},
        "K12": {'h': 5, 'color': '#D8452C', 'dur': 0.45, 'stagger': 0.05},
        "S02": {'to': 72, 'h': 6, 'color': '#7BE8BE', 'dur': 1.0, 'stagger': 0.05},
        "S04": {'size': 22, 'color': '#7BE8BE', 'dur': 0.6, 'stagger': 0.05},
        "S05": {'speed': 0.045, 'cursor': '#7BE8BE', 'dur': 0.6, 'stagger': 0.05},
        "S06": {'size': 18, 'color': '#7BE8BE', 'dur': 0.7, 'stagger': 0.05},
        "S07": {'to': 1.03, 'dur': 0.5, 'stagger': 0.05},
        "UA01": {'y': 26, 'dur': 0.55, 'stagger': 0.07},
        "UA02": {'x': -18, 'dur': 0.5, 'stagger': 0.08},
        "UA03": {'dur': 0.45, 'stagger': 0.1, 'to': 1},
        "M04": {'op': 1, 'dur': 1.2, 'z': 25, 'stagger': 0.05},
        "M05": {'op': 1, 'dur': 1.2, 'z': 25, 'stagger': 0.05},
        "X11": {'dur': 0.55, 'ease': 'power3.inOut', 'stagger': 0.05},
        "X14": {'dur': 0.55, 'ease': 'power3.inOut', 'stagger': 0.05},
        "X21": {'dur': 0.5, 'ease': 'power3.out', 'dist': 14, 'stagger': 0.05},
        "UA04": {'dur': 0.7, 'stagger': 0.06},
        "UA06": {'dur': 0.45, 'stagger': 0.16},
        "S08": {'dur': 0.5, 'ease': 'power3.out', 'stagger': 0.05},
        "S10": {'dur': 0.45, 'ease': 'power2.inOut', 'stagger': 0.05},
        "S11": {'from': -46, 'rot': -3, 'dur': 0.6, 'stagger': 0.05},
        "M12": {'op': 1, 'dur': 1.4, 'z': 26, 'stagger': 0.05},
        "M16": {'op': 0.55, 'dur': 1.0, 'z': 25, 'stagger': 0.05},
        "M20": {'op': 1, 'dur': 1.2, 'z': 26, 'stagger': 0.05},
        "M21": {'op': 0.45, 'dur': 1.0, 'z': 25, 'stagger': 0.05},
        "DA02": {'heights': '24,86,52,100', 'dur': 0.55, 'stagger': 0.08},
        "DA03": {'dur': 0.45, 'ease': 'power3.out', 'stagger': 0.05},
        "DA04": {'text': '已成交', 'dur': 0.5, 'stagger': 0.05},
        "I01": {'move': 0.8, 'hold': 0.3, 'press': 0.42, 'hit': 'rgba(134,240,192,.42)', 'dur': 0.6, 'stagger': 0.05},
        "Z01": {'dur': 4.2, 'camZ': 8.6, 'fogNear': 12, 'fogFar': 30, 'stagger': 0.05},
        "G03": {'dur': 0.95, 'ease': 'power3.inOut', 'stagger': 0.04, 'fade': 0.5},
        "I02": {'move': 0.55, 'hold': 0.28, 'press': 0.4, 'gap': 0.28, 'hit': 'rgba(134,240,192,.42)', 'dur': 0.6, 'stagger': 0.05},
        "Z02": {'dur': 3.4, 'grid': 38, 'size': 0.06, 'camY': 3.4, 'camZ': 11.5, 'fogNear': 14, 'fogFar': 34, 'stagger': 0.05},
        "S12": {'dist': -780, 'dur': 2.2, 'ease': 'power2.inOut', 'hold': 0.3, 'stagger': 0.05},
        "W02": {'dur': 0.9, 'ease': 'power3.inOut', 'stagger': 0.05},
        "W11": {'mode': 0, 'amount': 1, 'dur': 1.2, 'ease': 'power2.inOut', 'stagger': 0.05},
        "W12": {'mode': 1, 'amount': 1, 'dur': 1.2, 'ease': 'power2.inOut', 'stagger': 0.05},
        "W13": {'mode': 2, 'amount': 1, 'dur': 1.0, 'ease': 'power2.out', 'stagger': 0.05},
        "W15": {'mode': 3, 'amount': 1, 'dur': 1.3, 'ease': 'power2.inOut', 'stagger': 0.05},
        "W18": {'mode': 4, 'amount': 1, 'dur': 1.2, 'ease': 'power2.inOut', 'stagger': 0.05},
        "W20": {'copies': 8, 'dist': 120, 'fade': 0.82, 'angle': 200, 'dur': 1.2, 'ease': 'power2.out', 'stagger': 0.05},
        "K13": {'type': 'box', 'color': '#FFD45E', 'w': 6, 'dur': 0.8, 'stagger': 0.05, 'passes': 2, 'fillOpacity': 0.34, 'seed': 'box', 'z': 8},
        "K14": {'type': 'bracket', 'color': '#FFD45E', 'w': 6, 'dur': 0.7, 'stagger': 0.05, 'passes': 2, 'fillOpacity': 0.34, 'seed': 'bracket', 'z': 8},
        "K15": {'type': 'cross', 'color': '#FF5D6C', 'w': 6, 'dur': 0.6, 'stagger': 0.06, 'passes': 2, 'fillOpacity': 0.34, 'seed': 'cross', 'z': 8},
        "K16": {'type': 'highlight', 'color': '#FFD45E', 'w': 6, 'dur': 0.55, 'stagger': 0.05, 'passes': 2, 'fillOpacity': 0.42, 'seed': 'hl', 'z': 0},
        "U21": {'color': 'rgba(255,212,94,.92)', 'ink': '#101314', 'radius': 18, 'padX': 18, 'padY': 8, 'dur': 0.55, 'stagger': 0.22},
        "G04": {'fromW': 900, 'toW': 560, 'lines': 2, 'minFs': 26, 'maxFs': 96, 'dur': 1.6, 'ease': 'power2.inOut', 'stagger': 0.05},
        "S13": {'text': '线索自动分好跟进自动记上', 'chunk': 2, 'span': 2.4, 'color': '#F4F1E9', 'ink': '#0d1010', 'hl': '#FFD45E', 'dur': 0.6, 'stagger': 0.05},
        "S14": {'text': '线索自动分好跟进自动记上', 'chunk': 2, 'span': 2.4, 'dur': 0.4, 'color': '#F4F1E9', 'ink': '#0d1010', 'hl': '#FFD45E', 'stagger': 0.05},
        "S15": {'bars': 24, 'height': 0.86, 'color': 'rgba(134,240,192,.92)', 'hl': '#FFD45E', 'seed': 'spec', 'dur': 2.4, 'stagger': 0.05},
        "U23": {'dur': 1.4, 'stagger': 0.05},
        "U24": {'fromScale': 0.35, 'dur': 0.6, 'stagger': 0.05},
        "Z03": {'layers': 24, 'step': 3.2, 'color': '#F4F1E9', 'side': '#16262a', 'dur': 1.4, 'z': 12, 'stagger': 0.05},
        "K21": {'y': 24, 'dur': 0.5, 'stagger': 0.12, 'charStagger': 0.02, 'wordDelay': 0.55},
        "T12": {'dist': 90, 'strength': 2.2, 'points': 22, 'dur': 1.1, 'stagger': 0.22},
        "T13": {'drop': 320, 'strength': 0.65, 'squash': 2, 'dur': 1.4, 'squashY': 0.86, 'squashX': 1.08, 'stagger': 0.05},
        "U25": {'a': 18, 'b': 82, 'dur': 2.0, 'ease': 'power2.inOut', 'stagger': 0.05},
        "U26": {'dur': 0.9, 'ease': 'power2.out', 'stagger': 0.15},
        "U27": {'to': '#morph-target', 'dur': 1.0, 'ease': 'power2.inOut', 'stagger': 0.05},
        "U28": {'path': '#motion-route', 'rotate': 1, 'start': 0, 'end': 1, 'dur': 2.2, 'ease': 'power1.inOut', 'stagger': 0.05},
        "U29": {'path': '#motion-route', 'rotate': 0, 'start': 0.35, 'end': 0.75, 'dur': 2.0, 'ease': 'power2.inOut', 'stagger': 0.05},
        "K22": {'unit': 'chars', 'y': 118, 'dur': 0.55, 'stagger': 0.05},
        "K23": {'toW': 520, 'resplitAt': 0.9, 'dur': 0.6, 'stagger': 0.1},
        "K24": {'keep': '¥299', 'y': 30, 'dur': 0.5, 'stagger': 0.04},
        "U30": {'dur': 1.3, 'back': 1, 'backDur': 0.8, 'stagger': 0.05},
        "U31": {'dur': 1.8, 'ease': 'none', 'stagger': 0.05},
        "U32": {'to': '#morph-target', 'shapeIndex': 1, 'dur': 1.2, 'ease': 'power2.inOut', 'stagger': 0.05},
        "U33": {'to': '#morph-target', 'dur': 1.3, 'ease': 'power2.inOut', 'stagger': 0.05},
        "U34": {'to': '#morph-target', 'dur': 1.2, 'ease': 'power2.inOut', 'stagger': 0.05},
        "U35": {'path': '#motion-route', 'curviness': 1, 'dur': 2.0, 'ease': 'power1.inOut', 'stagger': 0.05},
        "U36": {'path': '#motion-route', 'ox': 0.9, 'oy': 0.5, 'rotate': 1, 'offX': 12, 'offY': -8, 'dur': 2.1, 'ease': 'power1.inOut', 'stagger': 0.05},
        "U37": {'path': '#motion-route', 'curviness': 1.6, 'resolution': 12, 'dur': 2.2, 'ease': 'power1.inOut', 'stagger': 0.05},
        "T14": {'dist': 90, 'strength': 2.2, 'points': 22, 'dur': 1.1, 'stagger': 0.22},
        "T15": {'dist': 260, 'linear': 0.7, 'power': 0.7, 'dur': 1.6, 'stagger': 0.05},
        "T16": {'from': 1, 'to': 4, 'dur': 1.6, 'stagger': 0.05},
        "T17": {'dist': 780, 'curve': 'M0,0 C0.3,1.6 0.55,-0.6 1,1', 'dur': 1.8, 'stagger': 0.05},
        "T18": {'dist': 700, 'strength': 0.8, 'dur': 1.9, 'stagger': 0.05},
        "T19": {'drop': 320, 'strength': 0.6, 'squash': 2, 'squashY': 0.9, 'squashX': 1.06, 'dur': 1.4, 'stagger': 0.05},
        "T20": {'velocity': 520, 'angle': -58, 'gravity': 1100, 'dur': 1.9, 'stagger': 0.05},
        "T21": {'velocity': 180, 'accel': 600, 'dur': 1.8, 'stagger': 0.05},
        "S16": {'text': '线索 128 条 · 已成交', 'dur': 1.4, 'stagger': 0.05},
        "S17": {'text': '已成交 12 条', 'oldClass': 'old-chunk', 'newClass': 'new-chunk', 'dur': 1.5, 'stagger': 0.05},
        "G05": {'columns': 'repeat(2,1fr)', 'gap': '28px', 'dur': 1.4, 'ease': 'power3.inOut', 'stagger': 0.05},
        "G06": {'direction': 'column', 'spin': 1, 'dur': 1.3, 'ease': 'power2.inOut', 'stagger': 0.05},
        "S18": {'maxWidth': 720, 'h': 24, 'color': '#86F0C0', 'dur': 2.0, 'ease': 'power2.inOut', 'stagger': 0.05},
        "S19": {'dist': 220, 'minScale': 0.7, 'maxScale': 1.15, 'maxRot': 12, 'dur': 0.6, 'stagger': 0.06, 'ease': 'power2.out'},
        "UA08": {'y': 44, 'dur': 0.6, 'stagger': 0.16},
        "G07": {'cols': 3, 'rows': 3, 'from': 'center', 'each': 0.09, 'fromScale': 0.6, 'dur': 0.6, 'stagger': 0.05},
        "G08": {'from': '64,900,180,180,90', 'toX': 64, 'toY': 520, 'toW': 952, 'toH': 820, 'toR': 26, 'imgH': 340, 'child': 'img', 'textChild': '.morph-text', 'dur': 1.1, 'ease': 'power3.inOut', 'fadeDur': 0.45, 'fadeAt': 0.55, 'stagger': 0.05},
        "G09": {'columns': 'repeat(2,1fr)', 'y': 40, 'fromScale': 0.9, 'dur': 0.5, 'stagger': 0.08, 'flipAt': 0.75, 'flipDur': 1.0, 'flipStagger': 0.04, 'ease': 'power3.inOut'},
        "X30": {'pct': 75, 'dur': 0.6, 'stagger': 0.09, 'ease': 'power2.out'},
        "X31": {'to': '620,1440', 'z': 30, 'scale': 1.2, 'dur': 1.0, 'hideDur': 0.12, 'ease': 'power3.inOut', 'stagger': 0.05},
        "W21": {'frameTo': '64,520,952,536', 'child': 'img', 'textChild': '.hero-meta', 'focusFrom': 'center 35%', 'focusTo': 'center 55%', 'dur': 1.15, 'ease': 'power3.inOut', 'fadeDur': 0.45, 'fadeAt': 0.95, 'stagger': 0.05},
        "X32": {'backdrop': '.bd', 'dim': 0.66, 'dimDur': 0.35, 'fromScale': 0.82, 'fromY': 80, 'dur': 0.6, 'stagger': 0.05},
        "G12": {'from': '120,800,300,300,20', 'to': '64,520,952,560,26', 'dur': 0.85, 'backAt': 1.25, 'stagger': 0.05},
        "G13": {'to': '64,0,952,300,22', 'dur': 1.0, 'stagger': 0.1},
        "G14": {'img': 'img', 'openTop': 520, 'openH': 700, 'openR': 26, 'imgW': 952, 'imgH': 420, 'imgR': 0, 'listTop': 700, 'listH': 180, 'listR': 18, 'imgSmall': 120, 'dur': 0.85, 'backAt': 1.4, 'backDur': 0.8, 'stagger': 0.05},
        "G16": {'y': 60, 'dur': 0.5, 'span': 1.2, 'power': 1.9, 'stagger': 0.05},
        "S20": {'dx': 600, 'dy': -320, 'rot': 90, 'dur': 1.0, 'gap': 0.5, 'stagger': 0.05},
        "S21": {'dist': 840, 'dur': 1.6, 'backX': 120, 'backDur': 0.9, 'interruptAt': 1.0, 'stagger': 0.05},
        "S22": {'peak': 1.35, 'decay': 0.72, 'times': 3, 'cycle': 0.6, 'upDur': 0.26, 'downDur': 0.32, 'dur': 0.6, 'stagger': 0.05},
        "GT01": {'dur': 2.2, 'p0': 0.14, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'blades': 6, 'rotation': 60.0, 'shadow': 0.5, 'stagger': 0.05},
        "GT02": {'dur': 2.2, 'p0': 0.14, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'direction': [1.0, 0.0], 'notch': 0.4, 'width': 80.0, 'count': 1, 'origin': 0, 'smoothness': 0.004, 'stagger': 0.05},
        "GT03": {'dur': 2.2, 'p0': 0.09, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'blocks': 16, 'color': [0.95, 0.32, 0.26, 1.0], 'pop': 0.5, 'smoothness': 0.03, 'stagger': 0.05},
        "GT04": {'dur': 2.2, 'p0': 0.29, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'grid': [5, 4], 'direction': [1.0, 0.0], 'stagger': 0.6, 'zoom': 0.35, 'background': [0.0, 0.0, 0.0, 1.0]},
        "GT05": {'dur': 2.2, 'p0': 0.45, 'p1': 0.88, 'ease': 'none', 'from': '#0a0b0b', 'spread': 0.25, 'threshold': 0.6, 'intensity': 1.5, 'tint': [1.0, 0.9, 0.75], 'stagger': 0.05},
        "GT06": {'dur': 2.2, 'p0': 0.12, 'p1': 0.85, 'ease': 'none', 'from': '#0a0b0b', 'strokes': 4.0, 'angle': -7.0, 'roughness': 0.6, 'waviness': 0.5, 'stagger': 0.05},
        "GT07": {'dur': 2.2, 'p0': 0.09, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'amplitude': 1.0, 'waves': 30.0, 'colorSeparation': 0.3, 'stagger': 0.05},
        "GT08": {'dur': 2.2, 'p0': 0.46, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'strength': 0.5, 'jolts': 12.0, 'blur': 0.5, 'split': 0.5, 'stagger': 0.05},
        "GT09": {'dur': 2.2, 'p0': 0.09, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'grid': [4, 3], 'deck': [0.5, -0.4], 'spin': 0.6, 'shadow': 0.5, 'stagger': 0.05},
        "GT10": {'dur': 2.2, 'p0': 0.11, 'p1': 0.88, 'ease': 'none', 'from': '#0a0b0b', 'direction': [1.0, 0.25], 'rotation': 0.5, 'depth': 0.15, 'backColor': [0.06, 0.06, 0.07, 1.0], 'stagger': 0.05},
        "GT11": {'dur': 2.2, 'p0': 0.09, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'cells': 8.0, 'smoothness': 0.1, 'border': 0.006, 'borderColor': [1.0, 0.95, 0.8, 1.0], 'seed': 0.0, 'stagger': 0.05},
        "GT12": {'dur': 2.2, 'p0': 0.09, 'p1': 0.75, 'ease': 'none', 'from': '#0a0b0b', 'center': [0.5, 0.5], 'color1': [0.99, 0.79, 0.29, 1.0], 'color2': [0.95, 0.38, 0.33, 1.0], 'color3': [0.13, 0.15, 0.3, 1.0], 'stagger': 0.3},
        "GT13": {'dur': 2.2, 'p0': 0.21, 'p1': 0.8, 'ease': 'none', 'from': '#0a0b0b', 'smoothness': 0.3, 'opening': 1, 'stagger': 0.05},
        "GT14": {'dur': 2.2, 'p0': 0.11, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'direction': 1.0, 'sway': 0.5, 'size': 0.72, 'background': [0.86, 0.84, 0.8, 1.0], 'lineColor': [0.42, 0.34, 0.26, 1.0], 'pinColor': [0.84, 0.68, 0.47, 1.0], 'stagger': 0.05},
        "GT15": {'dur': 2.2, 'p0': 0.19, 'p1': 0.62, 'ease': 'none', 'from': '#0a0b0b', 'cellSize': 0.045, 'trail': 0.5, 'tint': 0.5, 'glow': [0.2, 1.0, 0.4, 1.0], 'stagger': 0.05},
        "GT16": {'dur': 2.2, 'p0': 0.21, 'p1': 0.95, 'ease': 'none', 'from': '#0a0b0b', 'stagger': 0.05},
        "GT17": {'dur': 2.2, 'p0': 0.28, 'p1': 0.95, 'ease': 'none', 'from': '#0a0b0b', 'power': 5.0, 'stagger': 0.05},
        "GT18": {'dur': 2.2, 'p0': 0.09, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'gutter': 0.03, 'gutterColor': [1.0, 1.0, 1.0, 1.0], 'borderColor': [0.0, 0.0, 0.0, 1.0], 'seed': 0.0, 'stagger': 0.05},
        "GT19": {'dur': 2.2, 'p0': 0.17, 'p1': 0.83, 'ease': 'none', 'from': '#0a0b0b', 'stagger': 0.05},
        "GT20": {'dur': 2.2, 'p0': 0.37, 'p1': 0.9, 'ease': 'none', 'from': '#0a0b0b', 'strength': 0.4, 'stagger': 0.05},
        "GT21": {'dur': 2.2, 'p0': 0.11, 'p1': 0.89, 'ease': 'none', 'from': '#0a0b0b', 'center': [0.5, 0.5], 'threshold': 3.0, 'fadeEdge': 0.1, 'stagger': 0.05},
        "GT22": {'dur': 2.2, 'p0': 0.09, 'p1': 0.89, 'ease': 'none', 'from': '#0a0b0b', 'direction': [0.0, 1.0], 'curvature': 0.6, 'smoothness': 0.02, 'shadow': [0.0, 0.0, 0.0, 0.4], 'stagger': 0.05},
        "GT23": {'dur': 2.2, 'p0': 0.35, 'p1': 0.91, 'ease': 'none', 'from': '#0a0b0b', 'curvature': 0.8, 'blur': 0.5, 'shading': 0.6, 'chroma': 0.5, 'downward': 0, 'stagger': 0.05},
        "GT24": {'dur': 2.2, 'p0': 0.09, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'blurSize': 0.03, 'stagger': 0.05},
        "GT25": {'dur': 2.2, 'p0': 0.17, 'p1': 0.84, 'ease': 'none', 'from': '#0a0b0b', 'smoothness': 0.1, 'direction': [-1.0, 1.0], 'stagger': 0.05},
        "GT26": {'dur': 2.2, 'p0': 0.21, 'p1': 0.78, 'ease': 'none', 'from': '#0a0b0b', 'direction': [1.0, -1.0], 'smoothness': 0.5, 'stagger': 0.05},
        "GT27": {'dur': 2.2, 'p0': 0.13, 'p1': 0.63, 'ease': 'none', 'from': '#0a0b0b', 'particleSize': 0.01, 'direction': [1.0, -0.2], 'spread': 0.8, 'stagger': 0.05},
        "GT28": {'dur': 2.2, 'p0': 0.11, 'p1': 0.89, 'ease': 'none', 'from': '#0a0b0b', 'count': 12, 'reverse': 0, 'knock': 0.2, 'lean': 0.8, 'perspective': 0.8, 'shading': 0.6, 'stagger': 0.05},
        "GT29": {'dur': 2.2, 'p0': 0.09, 'p1': 0.41, 'ease': 'none', 'from': '#0a0b0b', 'bars': 30, 'amplitude': 2.0, 'noise': 0.1, 'frequency': 0.5, 'dripScale': 0.5, 'stagger': 0.05},
        "GT30": {'dur': 2.2, 'p0': 0.25, 'p1': 0.91, 'ease': 'none', 'from': '#0a0b0b', 'facets': 5.0, 'refraction': 0.1, 'bevel': 0.6, 'highlight': [1.0, 0.98, 0.92, 1.0], 'seed': 0.0, 'stagger': 0.05},
        "GT31": {'dur': 2.2, 'p0': 0.36, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'frames': 2, 'shrink': 0.2, 'blur': 0.5, 'weave': 0.5, 'filmColor': [0.06, 0.05, 0.05, 1.0], 'holeColor': [0.96, 0.93, 0.85, 1.0], 'stagger': 0.05},
        "GT32": {'dur': 2.2, 'p0': 0.38, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'strength': 0.8, 'stagger': 0.05},
        "GT33": {'dur': 2.2, 'p0': 0.16, 'p1': 0.74, 'ease': 'none', 'from': '#0a0b0b', 'cells': 2, 'stagger': 1.0, 'plates': 1, 'color1': [0.89, 0.22, 0.17, 1.0], 'color2': [0.97, 0.77, 0.15, 1.0], 'color3': [0.14, 0.32, 0.66, 1.0], 'shadow': 0.6},
        "GT34": {'dur': 2.2, 'p0': 0.36, 'p1': 0.71, 'ease': 'none', 'from': '#0a0b0b', 'stagger': 0.05},
        "GT35": {'dur': 2.2, 'p0': 0.17, 'p1': 0.67, 'ease': 'none', 'from': '#0a0b0b', 'blobs': 5.0, 'smoothness': 0.5, 'highlight': [1.0, 1.0, 1.0, 0.7], 'shadow': [0.0, 0.0, 0.0, 0.3], 'stagger': 0.05},
        "GT36": {'dur': 2.2, 'p0': 0.36, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'dots': 26.0, 'angle': 45.0, 'paper': [0.05, 0.06, 0.06, 1.0], 'stagger': 0.05},
        "GT37": {'dur': 2.2, 'p0': 0.2, 'p1': 0.81, 'ease': 'none', 'from': '#0a0b0b', 'center': [0.5, 0.5], 'smoothness': 0.006, 'pulse': 0.5, 'glowColor': [1.0, 0.85, 0.9], 'glow': 0.3, 'stagger': 0.05},
        "GT38": {'dur': 2.2, 'p0': 0.09, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'steps': 40, 'horizontalHexagons': 14.0, 'stagger': 0.05},
        "GT39": {'dur': 2.2, 'p0': 0.24, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'tint': [0.2, 0.75, 1.0], 'background': [0.0, 0.02, 0.05, 1.0], 'scanlines': 150.0, 'jitter': 0.04, 'flicker': 0.6, 'stagger': 0.05},
        "GT40": {'dur': 2.2, 'p0': 0.25, 'p1': 0.78, 'ease': 'none', 'from': '#0a0b0b', 'size': 6.0, 'stagger': 0.05},
        "GT41": {'dur': 2.2, 'p0': 0.4, 'p1': 0.84, 'ease': 'none', 'from': '#0a0b0b', 'stagger': 0.05},
        "GT42": {'dur': 2.2, 'p0': 0.17, 'p1': 0.6, 'ease': 'none', 'from': '#0a0b0b', 'stagger': 0.05},
        "GT43": {'dur': 2.2, 'p0': 0.14, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'gutter': 0.04, 'overlap': 0.55, 'band': 0.22, 'shadow': 0.4, 'paper': [0.96, 0.95, 0.91, 1.0], 'accent': [0.93, 0.27, 0.2, 1.0], 'stagger': 0.05},
        "GT44": {'dur': 2.2, 'p0': 0.28, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'cells': 24.0, 'glow': 0.6, 'flash': 0.7, 'zoom': 0.15, 'triads': 0, 'direction': [1.0, 0.0], 'panel': [0.02, 0.02, 0.025, 1.0], 'stagger': 0.05},
        "GT45": {'dur': 2.2, 'p0': 0.17, 'p1': 0.79, 'ease': 'none', 'from': '#0a0b0b', 'angle': -12.0, 'height': 0.18, 'intensity': 1.0, 'color': [0.35, 0.6, 1.0], 'stagger': 0.05},
        "GT46": {'dur': 2.2, 'p0': 0.45, 'p1': 0.67, 'ease': 'none', 'from': '#0a0b0b', 'reach': 0.9, 'threshold': 0.45, 'intensity': 2.4, 'tint': [0.53, 0.94, 0.75], 'blur': 0.06, 'vertical': 0, 'stagger': 0.05},
        "GT47": {'dur': 2.2, 'p0': 0.09, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'strength': 0.1, 'stagger': 0.05},
        "GT48": {'dur': 2.2, 'p0': 0.12, 'p1': 0.72, 'ease': 'none', 'from': '#0a0b0b', 'roughness': 0.12, 'tilt': 0.1, 'rim': 0.012, 'paper': [1.0, 0.98, 0.94, 1.0], 'shadow': [0.0, 0.0, 0.0, 0.35], 'stagger': 0.05},
        "GT49": {'dur': 2.2, 'p0': 0.13, 'p1': 0.9, 'ease': 'none', 'from': '#0a0b0b', 'scale': 4.0, 'smoothness': 0.01, 'seed': 12.9898, 'stagger': 0.05},
        "GT50": {'dur': 2.2, 'p0': 0.21, 'p1': 0.93, 'ease': 'none', 'from': '#0a0b0b', 'darkness': 0.8, 'keystone': 0.45, 'blur': 0.015, 'stagger': 0.05},
        "GT51": {'dur': 2.2, 'p0': 0.16, 'p1': 0.91, 'ease': 'none', 'from': '#0a0b0b', 'rows': 4, 'depth': 0.8, 'spread': 0.05, 'backColor': [0.04, 0.04, 0.05, 1.0], 'stagger': 0.05},
        "GT52": {'dur': 2.2, 'p0': 0.46, 'p1': 0.88, 'ease': 'none', 'from': '#0a0b0b', 'strength': 0.15, 'scale': 2.5, 'dispersion': 0.5, 'brightness': 1.0, 'stagger': 0.05},
        "GT53": {'dur': 2.2, 'p0': 0.23, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'rings': 6, 'square': 0, 'turns': 1, 'stagger': 0.5, 'blur': 0.6, 'settle': 0.5},
        "GT54": {'dur': 2.2, 'p0': 0.16, 'p1': 0.86, 'ease': 'none', 'from': '#0a0b0b', 'count': 6, 'center': [0.5, 0.5], 'stagger': 0.5, 'radial': 0, 'borderWidth': 0.008, 'borderColor': [1.0, 1.0, 1.0, 1.0], 'smoothness': 0.004},
        "GT55": {'dur': 2.2, 'p0': 0.12, 'p1': 0.76, 'ease': 'none', 'from': '#0a0b0b', 'center': [0.5, 0.5], 'shards': 6.0, 'gravity': 1.0, 'seed': 0.0, 'stagger': 0.05},
        "GT56": {'dur': 2.2, 'p0': 0.2, 'p1': 0.73, 'ease': 'none', 'from': '#0a0b0b', 'tileSize': 0.035, 'scatter': 0.85, 'diagonal': 0.9, 'prism': 0.65, 'glow': 0.75, 'stagger': 0.05},
        "GT57": {'dur': 2.2, 'p0': 0.16, 'p1': 0.92, 'ease': 'none', 'from': '#0a0b0b', 'blades': 5, 'tilt': 0.06, 'gate': 0.035, 'color': [0.09, 0.09, 0.1, 1.0], 'stagger': 0.05},
        "GT58": {'dur': 2.2, 'p0': 0.35, 'p1': 0.92, 'ease': 'none', 'from': '#0a0b0b', 'zoom_quickness': 0.8, 'fade': 1, 'stagger': 0.05},
        "GT59": {'dur': 2.2, 'p0': 0.09, 'p1': 0.86, 'ease': 'none', 'from': '#0a0b0b', 'lineWidth': 1.5, 'edges': 1.0, 'hatching': 0.6, 'paper': [0.96, 0.94, 0.89, 1.0], 'ink': [0.16, 0.16, 0.2, 1.0], 'stagger': 0.05},
        "GT60": {'dur': 2.2, 'p0': 0.09, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'reels': 5, 'blur': 0.6, 'stagger': 0.45, 'bounce': 0.5, 'separator': [0.04, 0.04, 0.05, 1.0]},
        "GT61": {'dur': 2.2, 'p0': 0.09, 'p1': 0.85, 'ease': 'none', 'from': '#0a0b0b', 'tilt': 0.35, 'border': 0.04, 'flash': 0.85, 'shadow': 0.45, 'borderColor': [0.96, 0.94, 0.89, 1.0], 'stagger': 0.05},
        "GT62": {'dur': 2.2, 'p0': 0.12, 'p1': 0.75, 'ease': 'none', 'from': '#0a0b0b', 'splats': 4.0, 'spikiness': 0.6, 'droplets': 0.6, 'drips': 0.5, 'rim': 0.5, 'seed': 3.0, 'stagger': 0.05},
        "GT63": {'dur': 2.2, 'p0': 0.1, 'p1': 0.88, 'ease': 'none', 'from': '#0a0b0b', 'n_noise_pixels': 200.0, 'static_luminosity': 0.8, 'stagger': 0.05},
        "GT64": {'dur': 2.2, 'p0': 0.09, 'p1': 0.87, 'ease': 'none', 'from': '#0a0b0b', 'strength': 1.0, 'horizontalBars': 42.0, 'verticalSlits': 18.0, 'tear': 0.18, 'chroma': 0.032, 'residue': 0.62, 'noiseAmount': 0.16, 'scanAmount': 0.13, 'flashAmount': 0.2, 'stagger': 0.05},
        "GT65": {'dur': 2.2, 'p0': 0.24, 'p1': 0.79, 'ease': 'none', 'from': '#0a0b0b', 'cells': 8.0, 'outline': 0.6, 'spread': 0.75, 'stagger': 0.05},
        "GT66": {'dur': 2.2, 'p0': 0.09, 'p1': 0.94, 'ease': 'none', 'from': '#0a0b0b', 'stagger': 0.05},
        "GT67": {'dur': 2.2, 'p0': 0.18, 'p1': 0.79, 'ease': 'none', 'from': '#0a0b0b', 'grid': 24, 'center': [0.5, 0.5], 'spin': 1.0, 'randomness': 0.2, 'stagger': 0.05},
        "GT68": {'dur': 2.2, 'p0': 0.28, 'p1': 0.9, 'ease': 'none', 'from': '#0a0b0b', 'direction': [-1.0, 0.0], 'blur': 0.4, 'stagger': 0.05},
    }


    parts = []
    # 背景编号：只有 B08–B39 是 canvas 卡；B01–B07 和 B41–B48 是 CSS 类卡，
    # 场景组已经写好了类名，这里一个 canvas 都不能建。
    # 2026-11-14 踩过：B41 用旧正则 r"B(0[8-9]|[1-9][0-9])" 命中，被当成 canvas，
    # bgkit 没有这个 pattern 就回落到 B08，深色粒子盖住了浅色 CSS 卡。
    TEXT_PRESETS = {"T01", "T02", "T03", "T05", "T09", "T12", "T15", "T21",
                    "K01", "K03", "K04", "K21", "K22", "K23"}
    CAMERA_PRESETS = {"C01", "C02", "C03", "W01", "W02", "W11", "W12", "W13",
                      "W15", "W18", "W20", "W21"}
    STATE_PRESETS = {"S02", "S04", "S05", "S06", "S07", "S08", "S10",
                     "S11", "S12", "S13", "S14", "S15", "S16", "S17",
                     "S18", "S19", "S20", "S21", "S22", "X01", "X02"}
    CANVAS_BG = set("B%02d" % i for i in range(23, 40)) - {"B22", "B33"}
    visual = scene_data.get("visual_budget") if isinstance(scene_data.get("visual_budget"), dict) else {}
    bg_id = str(visual.get("background") or "").strip().upper()
    # 背景参数：motion_plan 里的 background_params 覆盖卡片默认值。
    # 以前 bind 只传编号，模型改了也没处放，"选了卡不能写参数"。
    bg_opts = {}
    if isinstance(data, dict):
        raw_opts = data.get("background_params")
        if isinstance(raw_opts, dict):
            for k, v in raw_opts.items():
                if isinstance(v, (int, float, str)) and not isinstance(v, bool):
                    bg_opts[str(k)] = v
    scene_vb = scene_data.get("visual_budget") if isinstance(scene_data.get("visual_budget"), dict) else {}
    if isinstance(scene_vb.get("background_params"), dict):
        for k, v in scene_vb["background_params"].items():
            if isinstance(v, (int, float, str)) and not isinstance(v, bool):
                bg_opts[str(k)] = v
    import json as _json
    bg_opt_lit = _json.dumps(bg_opts, ensure_ascii=False) if bg_opts else ""
    if bg_id in CANVAS_BG:
        bg_js = ("(function(){var box=document.querySelector('[data-scene=\"%s\"] [data-anim=\"bg\"]');"
                 "if(!box)return;var cv=box.querySelector('canvas');"
                 "if(!cv){cv=document.createElement('canvas');cv.style.cssText="
                 "'position:absolute;inset:0;width:100%%;height:100%%;';box.appendChild(cv);}"
                 "bgkit.bind(timeline,cv,'%s'%s);})();" % (
                     sid, bg_id, ("," + bg_opt_lit) if bg_opt_lit else ""))
        parts.append("/* preset: %s */\n" % bg_id + bg_js)
    used = []
    skipped = []
    used_targets = set()
    for idx, item in enumerate(motions):
        if not isinstance(item, dict):
            continue
        preset = str(item.get("preset") or "").strip().upper()
        if preset.startswith("B") and preset[1:].isdigit() and preset in CANVAS_BG:
            bg = ("(function(){var box=document.querySelector('[data-scene=\"%s\"] [data-anim=\"bg\"]');"
                  "if(!box)return;var cv=box.querySelector('canvas');"
                  "if(!cv){cv=document.createElement('canvas');cv.style.cssText="
                  "'position:absolute;inset:0;width:100%%;height:100%%;';box.appendChild(cv);}"
                  "bgkit.bind(timeline,cv,'%s');})();" % (sid, preset))
            parts.append("/* preset: %s */\n" % preset + bg)
            used.append(preset)
            continue
        if preset not in TPL:
            skipped.append(preset or "?")
            continue
        target = str(item.get("target") or "").strip()
        # 拆字/拆词类卡只作用在文字节点上。指到 copy / card-1 这类容器，
        # kit.split 会把整块文本一起拆，观感是整片字糊成一团、一起浮。
        # 这里直接把目标归一到文字 role，不靠模型每次都选对。
        TEXT_ROLES = {"title", "lead", "body", "note", "num", "label", "accent"}
        if preset in TEXT_PRESETS and target not in TEXT_ROLES:
            target = "title"
        # 照片层归转场节点：屏内动效再给 media 写 opacity/clip，会和转场的覆盖抢同一个属性，
        # 结果是照片整屏停在 0（2026-11-15 实测 s07）。这里直接跳过。
        if target == "media" and preset not in CAMERA_PRESETS:
            skipped.append(preset + "(media 归转场)")
            continue
        if not target:
            skipped.append(preset + "(no target)")
            continue
        # target 允许直接给 data-anim 名，也允许给完整选择器
        sel = target if target.startswith(("[", ".", "#")) else '[data-anim="%s"]' % target
        if sid and not sel.startswith('[data-scene='):
            sel = '[data-scene="%s"] %s' % (sid, sel)

        # 同一屏的两个动效不许落在同一个目标上。
        # 2026-11-14 踩过：s05 的入场 T02 和状态 X01 都指向 card-1，
        # X01 是"从裁切到揭示"，immediateRender 把整张卡从屏头藏到 cue 时刻，
        # 3.5 秒的屏有 2.3 秒是空的。状态类重复目标直接跳过。
        if preset in STATE_PRESETS and target in used_targets:
            skipped.append(preset + "(target 与入场重复)")
            continue
        used_targets.add(target)

        trigger = str(item.get("trigger") or "sentence_start").strip()
        fallback = item.get("fallback")
        try:
            fallback = float(fallback)
        except Exception:
            fallback = 0.1
        # 入场窗口：上限 2.2s。原来夹在 1.2s，长屏（7-8s）的动作全挤在开头，
        # 中后段五六秒完全静止；屏尾留白改由 cue 层的 __cueHold（默认 1.2s）保证。
        fallback = max(0.0, min(fallback, 2.2))
        if trigger.startswith("word:"):
            word = trigger[5:].strip().replace("'", "")
            at_expr = "at(cue('%s', '%s', %s))" % (sid, word, fallback)
        else:
            at_expr = "at(%s)" % fallback

        values = dict(DEFAULTS.get(preset, {}))
        params = item.get("params")
        if isinstance(params, dict):
            for key, value in params.items():
                values[str(key)] = value
        values.setdefault("sel2", sel)
        values.update({"sel": sel, "at": at_expr, "k": "%d" % idx})
        values.setdefault("dur", 0.6)
        values.setdefault("stagger", 0.05)
        values.setdefault("from", 0)
        values.setdefault("to", 100)
        values.setdefault("seed", 7)
        values.setdefault("color", "#38d6ff")
        values["dur"] = float(values["dur"])
        values["stagger"] = float(values["stagger"])

        try:
            block = TPL[preset] % values
            # 统一把目标在它自己的时刻显示出来（首帧被整体隐藏过）
            block = "timeline.set('%s', {'opacity':1}, %s);\n" % (sel.replace("'", ""), at_expr) + block
            parts.append("/* preset: %s */\n" % preset + block)
            used.append(preset)
        except Exception:
            skipped.append(preset + "(模板参数不匹配)")

    body = "\n\n".join(parts)
    script = (
        "<script>\nwindow.__sceneBuilders.push(function(timeline, at){\n"
        "  var cue = function(s, w, f){ return window.__cue ? window.__cue(s, w, f) : f; };\n"
        "  /* 本屏动效由判断节点出力，本地按编号展开 */\n"
        + body + "\n});\n</script>"
    ) if body else "<script>\n/* 本屏没有可用动效编号：跳过 */\n</script>"

    return {
        "script": script,
        "motion_used_json": json.dumps({"scene_id": sid, "used": used, "skipped": skipped}, ensure_ascii=False),
    }
