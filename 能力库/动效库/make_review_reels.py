#!/usr/bin/env python3
"""把 presets.json 里的卡逐张做成 1080×1920 的审阅样片（真合成，不是格子）。

用法：
    python3 make_review_reels.py            # 生成 HTML 工程到 样片/全卡审阅/
    python3 make_review_reels.py --list     # 只打印分批

产物：能力库/动效库/样片/全卡审阅/reel-NN/index.html
每张卡 3 秒，左上角标编号 + 名字 + 族，右下角是「第几张 / 共几张」。
卡片的 code 原样展开（{{sel}}/{{at}}/参数），和管线里产出的代码是同一份。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parent
WORKSPACE = ROOT.parent.parent
PRESETS = ROOT / "presets.json"
OUT = WORKSPACE / "能力库" / "动效库" / "样片" / "全卡审阅"
VENDOR = WORKSPACE / "成品" / "workflow_runtime" / "assets" / "vendor"
PHOTO = WORKSPACE / "能力库" / "动效库" / "样片" / "镜头与排版" / "demo1-相机层" / "photo.png"

SECONDS = 3.0          # 每张卡时长
AT = 0.7               # 卡开始的时间点（屏内）
MAX_DUR = 2.0

# 分批：族 -> reel
BATCHES = [
    ("reel-01", "入场 + 字形", ["入场", "字形"]),
    ("reel-02", "状态与数据", ["状态"]),
    ("reel-03", "UI 组件", ["UI"]),
    ("reel-04", "离场与转场", ["离场", "结构"]),
    ("reel-05", "材质", ["材质"]),
    ("reel-06", "背景", ["背景"]),
    ("reel-07", "镜头 · 版面 · 照片", ["镜头", "版面", "绘制", "照片"]),
    ("reel-08", "交互 · 三维 · 候选", ["交互", "三维"]),
]

# 舞台类型：default=文字，ui=卡片行，media=图块，bg=canvas，three=canvas+three
STAGE = {}


SEL_MAP = {
    "T06": ".num", "DA01": ".num", "DA04": ".num", "DA02": ".bars b",
    "DA03": ".row", "S04": ".row", "S05": ".ph",
    "S06": ".row", "S07": ".row", "S09": ".row",
    "S11": ".row", "S08": ".panel", "S10": ".bars",
    "UA01": ".panel", "UA02": ".row", "UA03": ".row em", "UA04": ".bars b",
    "UA05": ".bars", "UA06": ".row", "UA07": ".row span",
    "I01": ".ptr", "I02": ".ptr", "G03": ".morph", "W02": ".shot", "S12": ".page", "Z02": "canvas",
}


def stage_of(card):
    cid, fam = card["id"], card.get("family", "")
    if cid in ("G02",):
        return "flip"
    if cid in ("G03",):
        return "morph"
    if cid in ("W02",):
        return "frame"
    if cid == "S12":
        return "scroll"
    if cid == "I02":
        return "pointer2"
    if cid == "Z02":
        return "three"
    if cid == "I01":
        return "pointer"
    if cid == "Z01":
        return "three"
    if fam == "背景":
        return "bg"
    if fam in ("材质", "镜头"):
        return "media"
    if fam in ("状态", "UI") or cid in ("T06",):
        return "ui"
    return "text"


SUBJECT_TEXT = {
    "T01": ("还在手动复制", ""), "T02": ("外贸老板的效率困境", ""), "T03": ("线索在一个平台", ""),
    "T04": ("报价单", ""), "T05": ("$ npx build", ""), "T07": ("SYNC ENGINE", ""),
    "T08": ("V2.4", ""), "T09": ("128", ""), "T11": ("效率", ""),
    "K01": ("爆发式增长", ""), "K03": ("字自己落下", ""), "K04": ("把字收紧", ""),
    "K05": ("从一边揭开", ""), "K06": ("关键的一步", ""), "K07": ("画一条下划线", ""),
    "K08": ("32%", ""), "K09": ("正在同步", ""), "K10": ("纵横四海", ""),
    "K12": ("不靠加班", ""), "K13": ("先有线", ""), "K20": ("撑满这一行", ""),
    "W01": ("", ""), "G01": ("", ""), "X01": ("换一版", ""),
    "X03": ("切点前的收尾", ""), "X05": ("横向飞出去", ""), "X11": ("左擦除", ""),
    "X14": ("下擦除", ""), "X21": ("甩镜", ""),
}


def default_vars(card, sel, at, sel2):
    v = {"dur": 0.6, "stagger": 0.05, "from": 0, "to": 100, "seed": 7,
         "color": "#38d6ff", "child": ".b", "ratio": 0.98, "r": 26, "len": 26,
         "size": "340px", "radius": 520, "alpha": 0.6, "rx": 5, "ry": 7,
         "perspective": 1200, "h": 6, "w": 3, "op": 0.6, "z": 25, "speed": 0.05,
         "cursor": "#7BE8BE", "heights": "24,86,52,100", "text": "已成交",
         "steps": 6, "stepdur": 0.09, "ease": "power3.out", "dist": 40,
         "move": 0.8, "hold": 0.3, "press": 0.42, "hit": "rgba(134,240,192,.42)",
         "camZ": 8.6, "fogNear": 12, "fogFar": 30, "outOp": 0.12,
         "sel": sel, "sel2": sel2, "at": "at(%.2f)" % at}
    for k, val in (card.get("params") or {}).items():
        v[k] = val
    if "dur" in v:
        try:
            v["dur"] = min(float(v["dur"]), MAX_DUR)
        except Exception:
            v["dur"] = 0.6
    return v


def expand(code: str, v: dict) -> str:
    def rep(m):
        k = m.group(1)
        if k not in v:
            raise KeyError(k)
        return str(v[k])
    return re.sub(r"\{\{(\w+)\}\}", rep, code)


def stage_html(kind, card, sc):
    cid = card["id"]
    if kind == "text":
        t = SUBJECT_TEXT.get(cid, ("能力卡", ""))[0]
        return ('<div class="paper"><div class="kick">%s</div>'
                '<div class="h" data-anim="subject">%s</div></div>' % (cid, t or "能力卡"))
    if kind == "media":
        return ('<div class="media" data-anim="subject">'
                '<div class="tag">%s</div></div>' % cid)
    if kind == "ui":
        return ('<div class="panel" data-anim="subject">'
                '<div class="ph">本周线索</div>'
                '<div class="row"><i>A</i><span>宁波 · 五金出口</span><em>待跟进</em></div>'
                '<div class="row"><i>B</i><span>深圳 · 储能方案</span><em>已报价</em></div>'
                '<div class="row"><i>C</i><span>苏州 · 精密件</span><em>已接通</em></div>'
                '<div class="bars"><b style="height:38%"></b><b style="height:62%"></b>'
                '<b style="height:48%"></b><b style="height:86%"></b></div>'
                '<div class="num" data-anim="num">128</div>'
                '</div>')
    if kind == "flip":
        cards = ""
        spec = [(72, 760, 72, 760), (400, 760, 400, 760), (728, 760, 72, 1000), (72, 1000, 400, 1000)]
        for i, (fx, fy, tx, ty) in enumerate(spec):
            cards += ('<div class="fcard" data-anim="f%d" data-flip-from="%d,%d" data-flip-to="%d,%d" '
                      'style="left:%dpx;top:%dpx">0%d</div>' % (i, fx, fy, tx, ty, fx, fy, i + 1))
        return '<div class="fwrap" data-flip-container data-anim="subject">%s</div>' % cards
    if kind == "pointer":
        return ('<div class="panel" data-anim="subject">'
                '<div class="ph">今日线索</div>'
                '<div class="row hit" data-anim="hit"><i>B</i><span>深圳 · 储能方案</span><em>待跟进</em></div>'
                '<div class="row"><i>C</i><span>苏州 · 精密件</span><em>待跟进</em></div>'
                '</div>'
                '<svg class="ptr" data-anim="ptr" data-pointer-to="700,900" width="60" height="60" '
                'viewBox="0 0 28 28"><path d="M4.2 1.2 L4.2 21.6 L9.5 16.5 L12.9 24.5 L16.7 22.8 '
                'L13.3 15.1 L20.7 15.1 Z" fill="#ffffff" stroke="#101010" stroke-width="1.7" '
                'stroke-linejoin="round"/></svg>')
    if kind == "morph":
        return ('<div class="morph" data-anim="subject" data-morph-to="72,700,936,470,30" '
                'style="left:600px;top:900px;width:300px;height:190px;border-radius:18px">'
                '<div class="mdetail" data-morph-detail>详情层</div></div>')
    if kind == "frame":
        return ('<div class="shot" data-anim="subject" data-frame-to="72,700,936,527" '
                'style="left:180px;top:860px;width:380px;height:380px"></div>')
    if kind == "scroll":
        secs = "".join('<div class="sec" style="top:%dpx">0%d</div>' % (150 + i * 300, i + 1) for i in range(3))
        return ('<div class="view"><div class="page" data-anim="subject">'
                '<div class="sticky">页面标题</div>%s</div></div>' % secs.replace('<div class="sec"', '<div class="sec" data-scroll-hl'))
    if kind == "pointer2":
        return ('<div class="panel"><div class="ph">新建跟进</div>'
                '<div class="row" data-anim="pick"><i>B</i><span>深圳 · 储能方案</span></div>'
                '<div class="field" data-anim="field">客户名称</div>'
                '<div class="submit" data-anim="submit">提交</div></div>'
                '<svg class="ptr" data-anim="ptr" data-pointer-path="pick,field,submit" width="60" height="60" '
                'viewBox="0 0 28 28"><path d="M4.2 1.2 L4.2 21.6 L9.5 16.5 L12.9 24.5 L16.7 22.8 '
                'L13.3 15.1 L20.7 15.1 Z" fill="#ffffff" stroke="#101010" stroke-width="1.7" '
                'stroke-linejoin="round"/></svg>')
    if kind == "three":
        return '<canvas class="cv" data-anim="subject" width="1080" height="1920"></canvas>'
    if kind == "bg":
        return '<canvas class="cv" data-anim="bg" width="1080" height="1920"></canvas>'
    return ""


NEEDS_THREE = {"Z01"}


def scene_script(kind, card, sc, sel, sel2, at):
    """返回这段屏要执行的 JS（不含 try/catch，外层包）。"""
    cid = card["id"]
    if kind == "bg":
        return ("var _c=document.querySelector('%s');if(_c){var _o={t:0};"
                "timeline.to(_o,{t:6,duration:%s,ease:'none',onUpdate:function(){"
                "bgkit.draw(_c.getContext('2d'),'%s',1080,1920,_o.t);}},%.2f);}" % (sel, SECONDS - 0.4, cid, at))
    v = default_vars(card, sel, at, sel2)
    return expand(card["code"], v)


CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000;font-family:"PingFang SC","Helvetica Neue",sans-serif;-webkit-font-smoothing:antialiased}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:#0a0b0b;color:#F4F1E9}
.scene{position:absolute;inset:0;display:none;overflow:hidden}
.scene.active{display:block}
.hdr{position:absolute;left:64px;top:74px;z-index:20;display:flex;align-items:baseline;gap:20px}
.hdr .id{font-family:"SF Mono",Menlo,monospace;font-size:30px;letter-spacing:.16em;color:#86F0C0}
.hdr .nm{font-size:40px;font-weight:640;letter-spacing:-.01em}
.hdr .fm{font-family:"SF Mono",Menlo,monospace;font-size:22px;color:#7e8a84;letter-spacing:.14em}
.ftr{position:absolute;right:64px;bottom:70px;z-index:20;font-family:"SF Mono",Menlo,monospace;
  font-size:24px;letter-spacing:.12em;color:rgba(244,241,233,.32)}
.paper{position:absolute;left:64px;right:64px;top:420px;bottom:300px;border-radius:20px;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);padding:56px}
.paper .kick{font-family:"SF Mono",Menlo,monospace;font-size:22px;letter-spacing:.2em;color:#86F0C0}
.paper .h{margin-top:40px;font-size:96px;line-height:1.14;font-weight:680;letter-spacing:-.03em}
.media{position:absolute;left:64px;right:64px;top:420px;height:820px;border-radius:20px;overflow:hidden;
  background:radial-gradient(520px 420px at 62% 34%,rgba(255,236,206,.24),transparent 62%),
             linear-gradient(150deg,#22323a,#0d1214 62%,#0a0d0e);border:1px solid rgba(255,255,255,.07)}
.media .tag{position:absolute;left:40px;bottom:36px;font-family:"SF Mono",Menlo,monospace;
  font-size:24px;letter-spacing:.14em;color:rgba(244,241,233,.5)}
.panel{position:absolute;left:64px;right:64px;top:420px;border-radius:22px;padding:40px;
  background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.08)}
.panel .ph{font-size:34px;font-weight:640;margin-bottom:26px}
.panel .row{display:flex;align-items:center;gap:24px;padding:24px;border-radius:14px;
  border:1px solid transparent;background:rgba(255,255,255,.03);margin-bottom:12px;font-size:30px}
.panel .row i{width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-family:"SF Mono",Menlo,monospace;font-size:20px;font-style:normal;color:#86F0C0;
  background:linear-gradient(140deg,#3c4f5a,#1b2428)}
.panel .row em{margin-left:auto;font-style:normal;font-family:"SF Mono",Menlo,monospace;font-size:20px;
  padding:8px 16px;border-radius:999px;border:1px solid rgba(255,255,255,.18);color:#C9D3CC}
.panel .bars{display:flex;align-items:flex-end;gap:16px;height:220px;margin-top:26px}
.panel .bars b{flex:1;background:rgba(134,240,192,.4);border-radius:6px 6px 0 0}
.panel .num{position:absolute;right:40px;top:26px;font-family:Georgia,serif;font-size:72px;color:#F4F1E9}
.fwrap{position:absolute;inset:0}
.fcard{position:absolute;width:300px;height:200px;border-radius:16px;display:flex;align-items:center;
  justify-content:center;font-family:"SF Mono",Menlo,monospace;font-size:26px;letter-spacing:.12em;
  color:rgba(244,241,233,.7);background:linear-gradient(140deg,#22322e,#101816);
  border:1px solid rgba(255,255,255,.08)}
canvas.cv{position:absolute;inset:0;width:1080px;height:1920px;display:block}
.morph{position:absolute;overflow:hidden;border:1px solid rgba(255,255,255,.1);
  background:linear-gradient(140deg,#20302c,#0e1513)}
.morph .mdetail{position:absolute;inset:0;padding:40px;opacity:0;font-size:30px;color:#9FA9A2}
.shot{position:absolute;border-radius:18px;border:1px solid rgba(255,255,255,.1);overflow:hidden;
  background-image:url("./photo.png");background-size:cover;background-position:52% 40%}
.view{position:absolute;left:64px;right:64px;top:420px;height:1160px;border-radius:22px;overflow:hidden;
  border:1px solid rgba(255,255,255,.09);background:#0d1010}
.page{position:absolute;left:0;right:0;top:0}
.sticky{position:absolute;left:0;right:0;top:0;height:110px;background:rgba(16,20,19,.96);
  border-bottom:1px solid rgba(255,255,255,.08);display:flex;align-items:center;padding:0 36px;font-size:30px}
.sec{position:absolute;left:36px;right:36px;height:260px;border-radius:18px;
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.07);padding:30px;font-size:30px}
.field{margin:12px 0;padding:24px;border-radius:12px;border:1px solid rgba(255,255,255,.14);
  background:rgba(255,255,255,.02);font-size:28px;color:#B7C1B9}
.submit{display:inline-block;padding:20px 36px;border-radius:999px;background:#86F0C0;color:#0a0b0b;
  font-size:28px;font-weight:640}
.ptr{position:absolute;left:-9px;top:-3px;z-index:30;width:60px;height:60px;pointer-events:none}
.ptr{position:absolute;left:-9px;top:-3px;z-index:30;width:60px;height:60px;pointer-events:none}
.err{position:absolute;left:64px;right:64px;bottom:170px;z-index:40;font-family:"SF Mono",Menlo,monospace;
  font-size:26px;line-height:1.5;color:#ffd9d2;background:rgba(226,84,58,.22);
  border:1px solid rgba(226,84,58,.6);border-radius:10px;padding:16px 20px}
"""


def build_one(card, out_root: pathlib.Path):
    """一张卡一个自洽工程，渲染出 3 秒，文件名 <ID>-<名字>.mp4。"""
    cid = card["id"]
    fam = card.get("family", "其他")
    kind = stage_of(card)
    sc = "s01"
    sel = '[data-anim="subject"]'
    if cid in SEL_MAP:
        sel = SEL_MAP[cid]
    if kind == "pointer":
        sel = ".ptr"
    if kind == "flip":
        sel = ".fcard"
    if kind == "bg":
        sel = "canvas"
    sel2 = ".hit"
    try:
        js = scene_script(kind, card, sc, sel, sel2, AT)
    except Exception as e:
        js = ("(function(){var _d=document.createElement('div');_d.className='err';"
              "_d.textContent='%s 参数缺失: %s';document.querySelector('.scene').appendChild(_d);})();"
              % (cid, str(e)[:40].replace("'", "")))

    html = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>%s · %s</title>
<style>%s</style></head><body>
<div id="stage" data-composition-id="card-%s" data-duration="%.1f">
<section class="scene active" data-scene="s01" data-start="0" data-duration="%.1f">
  <div class="hdr"><span class="id">%s</span><span class="nm">%s</span><span class="fm">%s</span></div>
  %s
</section>
</div>
<script src="./gsap.min.js"></script>
<script src="./bg-kit.js"></script>
<script src="./motion-kit.js"></script>
%s
<script>
(function(){
  var tl=gsap.timeline({paused:true});
  window.__timelines=window.__timelines||{};
  window.__timelines['card-%s']=tl;
  var timeline=tl;
  function at(x){return x;}
  %s
  window.addEventListener('hf-seek',function(e){tl.time(e.detail.time);});
})();
</script></body></html>""" % (
        cid, card["name"], CSS, cid.lower(), SECONDS, SECONDS,
        cid, card["name"], fam, stage_html(kind, card, sc),
        ('<script src="./three.global.js"></script>' if cid in NEEDS_THREE else ""),
        cid, js)

    d = out_root / "源" / fam / cid
    d.mkdir(parents=True, exist_ok=True)
    (d / "index.html").write_text(html, encoding="utf-8")
    shutil.copy(VENDOR / "gsap.min.js", d / "gsap.min.js")
    shutil.copy(VENDOR / "bg-kit.js", d / "bg-kit.js")
    shutil.copy(VENDOR / "motion-kit.js", d / "motion-kit.js")
    if cid in NEEDS_THREE:
        shutil.copy(VENDOR / "three.global.js", d / "three.global.js")
    if "photo.png" in html:
        shutil.copy(PHOTO, d / "photo.png")
    (d / "hyperframes.json").write_text(json.dumps({
        "name": "card-" + cid.lower(), "version": 1, "composition": "index.html",
        "width": 1080, "height": 1920, "fps": 30, "duration": SECONDS
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="只生成某一张（编号）")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--tsv", action="store_true", help="只打印 族/编号/名字/目录，给渲染脚本用")
    args = ap.parse_args()
    cards = [c for c in json.loads(PRESETS.read_text(encoding="utf-8"))["presets"] if c.get("status") == "ready"]
    if args.only:
        cards = [c for c in cards if c["id"] == args.only]
        if not cards:
            raise SystemExit("没有这张卡：" + args.only)
    if args.list:
        for c in cards:
            print(c["id"], c["name"], c.get("family", ""))
        return
    rows = []
    for c in cards:
        d = build_one(c, OUT)
        rows.append("\t".join([c.get("family", "其他"), c["id"], c["name"], str(d)]))
        if args.tsv:
            print("\t".join([c.get("family", "其他"), c["id"], c["name"], str(d)]))
        else:
            print("%s %-10s -> %s" % (c["id"], c["name"], d.relative_to(WORKSPACE)))
    if not args.only:
        (OUT / "渲染清单.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    if not args.tsv:
        print("共 %d 张" % len(cards))


if __name__ == "__main__":
    main()
