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
    if budget and isinstance(motions, list) and motions:
        motions = [item for item in motions if isinstance(item, dict)][:2]
        entrance = str(budget.get("entrance") or "").strip().upper()
        state = str(budget.get("state") or "").strip().upper()
        if motions and entrance:
            motions[0]["preset"] = entrance
        if state:
            if len(motions) >= 2:
                motions[1]["preset"] = state
            elif motions:
                clone = dict(motions[0])
                clone["preset"] = state
                clone["reason"] = "补状态变化"
                motions.append(clone)

    # 每个编号 = 一段可复制的代码模板；%(x)s 由这里填。
    TPL = {
        "T01": """var _c%(k)s = kit.split('%(sel)s', 'chars');
timeline.fromTo(_c%(k)s, {'opacity':0, 'y':'0.5em'},
  {'opacity':1, 'y':0, 'duration':%(dur)s, 'ease':'power3.out', 'stagger':%(stagger)s}, %(at)s);""",
        "T02": """var _w%(k)s = kit.split('%(sel)s', 'words');
timeline.fromTo(_w%(k)s, {'opacity':0, 'filter':'blur(10px)', 'y':50},
  {'opacity':1, 'filter':'blur(0px)', 'y':0, 'duration':%(dur)s, 'ease':'power2.out', 'stagger':%(stagger)s}, %(at)s);""",
        "T03": """var _f%(k)s = kit.split('%(sel)s', 'chars');
timeline.fromTo(_f%(k)s, {'opacity':0, 'rotationX':92, 'transformOrigin':'50%% 0%%', 'transformPerspective':700},
  {'opacity':1, 'rotationX':0, 'duration':%(dur)s, 'ease':'power3.out', 'stagger':%(stagger)s}, %(at)s);""",
        "T04": """timeline.set('%(sel)s', {'webkitTextStroke':'1.4px currentColor', 'color':'transparent'}, 0);
timeline.to('%(sel)s', {'color':'%(color)s', 'duration':%(dur)s, 'ease':'power1.out'}, %(at)s);""",
        "T05": """var _t%(k)s = document.querySelector('%(sel)s');
(function(el){ var txt = el.textContent; el.textContent = ''; for (var i = 1; i <= txt.length; i++) {
  timeline.set(el, {'textContent': txt.slice(0, i)}, %(at)s + i * 0.05); } })(_t%(k)s);""",
        "T06": """var _n%(k)s = document.querySelector('%(sel)s');
var _o%(k)s = {'v':%(from)s};
timeline.to(_o%(k)s, {'v':%(to)s, 'duration':%(dur)s, 'ease':'power2.out',
  'onUpdate':function(){ _n%(k)s.textContent = Math.round(_o%(k)s.v); }}, %(at)s);""",
        "T07": """var _s%(k)s = kit.seeded(%(seed)s), _x%(k)s = document.querySelector('%(sel)s');
var _final%(k)s = _x%(k)s.textContent, _junk%(k)s = ':.';
for (var i = 0; i < _final%(k)s.length; i++) {
  timeline.set(_x%(k)s, {'textContent': _final%(k)s.slice(0, i) + _junk%(k)s[i %% 2]}, %(at)s + i * 0.03);
  timeline.set(_x%(k)s, {'textContent': _final%(k)s.slice(0, i + 1)}, %(at)s + i * 0.03 + 0.09);
}""",
        "T08": """var _d%(k)s = kit.seeded(11), _y%(k)s = document.querySelector('%(sel)s');
var _fin%(k)s = _y%(k)s.textContent, _cs%(k)s = 'ABCDEF0123';
for (var i = 0; i < _fin%(k)s.length; i++) {
  timeline.set(_y%(k)s, {'textContent': _fin%(k)s.slice(0, i) + _cs%(k)s[i %% 10]}, %(at)s + i * 0.04);
  timeline.set(_y%(k)s, {'textContent': _fin%(k)s.slice(0, i + 1)}, %(at)s + i * 0.04 + 0.08);
}""",
        "T09": """var _q%(k)s = kit.split('%(sel)s', 'chars');
_q%(k)s.forEach(function(el, i){ el.style.transformStyle = 'preserve-3d';
  timeline.fromTo(el, {'rotationX':-90, 'opacity':0},
    {'rotationX':0, 'opacity':1, 'duration':%(dur)s, 'ease':'back.out(1.4)'}, %(at)s + i * 0.06); });""",
        "T10": """var _r%(k)s = kit.split('%(sel)s', 'chars');
_r%(k)s.forEach(function(el, i){ var a = (-60 + 120 * i / Math.max(1, _r%(k)s.length - 1)) * Math.PI / 180;
  timeline.fromTo(el, {'x':0, 'y':0, 'opacity':0},
    {'x':Math.sin(a) * 420, 'y':(1 - Math.cos(a)) * 420, 'opacity':1,
     'duration':%(dur)s, 'ease':'power2.out'}, %(at)s + i * 0.05); });""",
        "T11": """var _e%(k)s = kit.split('%(sel)s', 'chars');
for (var i = 0; i < 8; i++) {
  timeline.fromTo(_e%(k)s, {'opacity':0, 'x':i * 36, 'filter':'blur(3px)'},
    {'opacity':0.35 * (1 - i / 8), 'x':0, 'filter':'blur(0px)', 'duration':0.5,
     'ease':'power2.out', 'stagger':0.03}, %(at)s + i * 0.04);
}""",
        "X01": """timeline.fromTo('%(sel)s', {'clipPath':'inset(0 100%% 0 0)'},
  {'clipPath':'inset(0 0%% 0 0)', 'duration':%(dur)s, 'ease':'power3.inOut'}, %(at)s);""",
        "X02": """timeline.fromTo('%(sel)s', {'opacity':0, 'y':24},
  {'opacity':1, 'y':0, 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);""",
        "P01": """timeline.fromTo('%(sel)s', {'--mx':'20%%', '--my':'80%%'},
  {'--mx':'62%%', '--my':'34%%', 'duration':%(dur)s, 'ease':'power2.inOut'}, %(at)s);""",
        "P02": """timeline.fromTo('%(sel)s', {'opacity':0.2}, {'opacity':1, 'duration':%(dur)s, 'ease':'power2.inOut'}, %(at)s);""",
        "P03": """timeline.fromTo('%(sel)s', {'--ry':'-6deg', '--rx':'4deg'},
  {'--ry':'0deg', '--rx':'0deg', 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);""",
        "W01": """timeline.fromTo('%(sel)s', {'opacity':0, 'scale':0.96},
  {'opacity':1, 'scale':1, 'duration':%(dur)s, 'ease':'power3.out'}, %(at)s);""",
        "U01": """timeline.fromTo('%(sel)s', {'opacity':0, 'y':26},
  {'opacity':1, 'y':0, 'duration':%(dur)s, 'ease':'power2.out'}, %(at)s);""",
        "U02": """timeline.to('%(sel)s .ui-step', {'duration':0.01}, %(at)s);
timeline.fromTo('%(sel)s .ui-step', {'--ui-progress':0}, {'--ui-progress':1, 'duration':%(dur)s, 'ease':'none', 'stagger':0.12}, %(at)s);""",
    }
    DEFAULTS = {
        "T01": {"dur": 0.55, "stagger": 0.05}, "T02": {"dur": 0.35, "stagger": 0.05},
        "T03": {"dur": 0.65, "stagger": 0.045}, "T04": {"dur": 0.4, "color": "#38d6ff"},
        "T05": {"dur": 0.05}, "T06": {"dur": 1.2, "from": 0, "to": 100},
        "T07": {"dur": 1.2, "seed": 7}, "T08": {"dur": 0.9, "seed": 11},
        "T09": {"dur": 0.12}, "T10": {"dur": 0.6}, "T11": {"dur": 0.5},
        "X01": {"dur": 0.8}, "X02": {"dur": 0.6},
        "P01": {"dur": 1.2}, "P02": {"dur": 0.6}, "P03": {"dur": 0.8},
        "W01": {"dur": 0.9}, "U01": {"dur": 0.6}, "U02": {"dur": 1.0},
    }

    parts = []
    # 背景编号：B08–B21 由这里建 canvas；B01–B07 由场景组直接加类名
    visual = scene_data.get("visual_budget") if isinstance(scene_data.get("visual_budget"), dict) else {}
    bg_id = str(visual.get("background") or "").strip().upper()
    if re.fullmatch(r"B(0[8-9]|1[0-9]|2[01])", bg_id):
        bg_js = ("(function(){var box=document.querySelector('[data-scene=\"%s\"] [data-anim=\"bg\"]');"
                 "if(!box)return;var cv=box.querySelector('canvas');"
                 "if(!cv){cv=document.createElement('canvas');cv.style.cssText="
                 "'position:absolute;inset:0;width:100%%;height:100%%;';box.appendChild(cv);}"
                 "bgkit.bind(timeline,cv,'%s');})();" % (sid, bg_id))
        parts.append("/* preset: %s */\n" % bg_id + bg_js)
    used = []
    skipped = []
    for idx, item in enumerate(motions):
        if not isinstance(item, dict):
            continue
        preset = str(item.get("preset") or "").strip().upper()
        if preset.startswith("B") and preset[1:].isdigit():
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
        if not target:
            skipped.append(preset + "(no target)")
            continue
        # target 允许直接给 data-anim 名，也允许给完整选择器
        sel = target if target.startswith(("[", ".", "#")) else '[data-anim="%s"]' % target
        if sid and not sel.startswith('[data-scene='):
            sel = '[data-scene="%s"] %s' % (sid, sel)

        trigger = str(item.get("trigger") or "sentence_start").strip()
        fallback = item.get("fallback")
        try:
            fallback = float(fallback)
        except Exception:
            fallback = 0.1
        # 入场窗口：本机强制不超过 1.2s，避免模型把动作写到屏后段，前几秒是死画面
        fallback = max(0.0, min(fallback, 1.2))
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
    head = ""
    if sid:
        # 第一帧只有背景：本屏所有 data-anim（bg / scrim 除外）先归零
        head += ("timeline.set('[data-scene=\"%s\"] [data-anim]:not([data-anim=\"bg\"]):not([data-anim=\"scrim\"])',"
                 " {'opacity':0}, 0);\n" % sid)
        # 照片默认从无到有（没有被 P01/W01 接管时也要出现）
        head += ("timeline.fromTo('[data-scene=\"%s\"] [data-anim=\"media\"]',"
                 " {'opacity':0, 'scale':1.04},"
                 " {'opacity':1, 'scale':1, 'duration':0.9, 'ease':'power2.out'}, at(0.25));\n" % sid)
    body = head + body
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
