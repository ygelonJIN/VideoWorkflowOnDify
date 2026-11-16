#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revideo 全量扫描：把仓库里**每一个**能落到 HTML+GSAP+canvas 上的机制都出一张确认片。

不是挑几张，是按族穷举：
    E  缓动        33  core/tweening/timingFunctions.ts 全量
    SP 弹簧        14  core/tweening/spring.ts 7 个预置 × 位移/角度
    TR 转场        16  core/transitions 4 类 × 4 向
    FL 滤镜        24  partials/Filter.ts 8 个 × 进/出/循环
    CM 合成        52  canvas globalCompositeOperation 26 个 × 两种层次
    CP 组件        23  2d/components 可画的组件
    CV 曲线剖面    15  curves 5 条剖面 × 描边/跟随/环绕
    CD 代码        8   Code 的 8 个方法
    ND 节点属性    12  Node 的可动画属性
    LY 版面        10  Layout 的 flex 配置
    FW 流程        7   flow 生成器
    EX 模板与示例  18  packages/template + packages/examples 里带画面的

用法：
    python3 能力库/动效库/revideo_sweep.py build
    python3 能力库/动效库/revideo_sweep.py render      # 并行 4
    python3 能力库/动效库/revideo_sweep.py sheet       # 每族一张联系表
    python3 能力库/动效库/revideo_sweep.py inventory   # 从仓库现抽清单（不改任何文件）
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from revideo_port import (  # noqa: E402
    BASE_CSS, SHELL, SPRING_JS, DUR, KEY, VENDOR, PHOTO, WORK, HF, CHROME, NODE,
)

REPO = pathlib.Path.home() / "Downloads" / "revideo-main"
BATCH = HERE / "样片" / "待筛" / "revideo" / "sweep"
SRC = BATCH / "src"
OUT = BATCH / "out"

SWEEP_CSS = """
.plab{position:absolute;left:64px;top:186px;z-index:55;font-family:"SF Mono",Menlo,monospace;
  font-size:26px;letter-spacing:.06em;color:rgba(244,241,233,.62)}
.plab b{color:#86F0C0;font-weight:600}
.track{position:absolute;left:64px;top:1000px;width:952px;height:2px;background:rgba(255,255,255,.14)}
.track .dot{position:absolute;top:-25px;left:0;width:50px;height:50px;border-radius:50%;background:#86F0C0;
  box-shadow:0 0 46px rgba(134,240,192,.5)}
.track .ghost{position:absolute;top:-13px;left:0;width:26px;height:26px;border-radius:50%;
  border:1px solid rgba(255,255,255,.3)}
.track .fin{position:absolute;right:-3px;top:-16px;width:4px;height:34px;background:rgba(255,255,255,.34)}
.badge{position:absolute;left:50%;top:820px;width:280px;height:280px;margin-left:-140px;border-radius:64px;
  background:linear-gradient(150deg,#86F0C0,#2f6b55);display:flex;align-items:center;justify-content:center;
  font-family:"SF Mono",Menlo,monospace;font-size:84px;font-weight:700;color:#08120e}
svg.stage2{position:absolute;inset:0;width:1080px;height:1920px}
.code{position:absolute;left:64px;right:64px;top:440px;border-radius:22px;padding:52px 44px;
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
  font-family:"SF Mono",Menlo,monospace;font-size:34px;line-height:1.95;color:#D5DED7}
.code .ln{display:flex;gap:26px;white-space:pre;position:relative}
.code .ln i{font-style:normal;color:rgba(244,241,233,.26);width:30px;text-align:right;flex:none}
.code .fn{color:#86F0C0}.code .st{color:#E7C98A}.code .cm{color:#7e8a84}
.rowbox{position:absolute;left:64px;right:64px;top:520px;border-radius:22px;padding:44px;
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)}
.chip{display:inline-flex;align-items:center;justify-content:center;padding:22px 34px;border-radius:16px;
  background:rgba(134,240,192,.16);border:1px solid rgba(134,240,192,.34);color:#DFF7EC;font-size:28px}
.photo2{position:absolute;left:64px;right:64px;top:420px;height:900px;border-radius:22px;overflow:hidden;
  background-image:url("./photo.png");background-size:cover;background-position:52% 40%;
  border:1px solid rgba(255,255,255,.09)}
canvas.cv{position:absolute;inset:0;width:1080px;height:1920px;display:block}
"""

EASE_JS = """
var EASE = (function () {
  function ob(x){var n1=7.5625,d1=2.75;
    if(x<1/d1)return n1*x*x;
    if(x<2/d1)return n1*(x-=1.5/d1)*x+0.75;
    if(x<2.5/d1)return n1*(x-=2.25/d1)*x+0.9375;
    return n1*(x-=2.625/d1)*x+0.984375;}
  var c1=1.70158,c3=c1+1,c2=c1*1.525,c4=(2*Math.PI)/3,c5=(2*Math.PI)/4.5;
  return {
    linear:function(x){return x;},
    easeInSine:function(x){return 1-Math.cos(x*Math.PI/2);},
    easeOutSine:function(x){return Math.sin(x*Math.PI/2);},
    easeInOutSine:function(x){return -(Math.cos(Math.PI*x)-1)/2;},
    easeInQuad:function(x){return x*x;},
    easeOutQuad:function(x){return 1-Math.pow(1-x,2);},
    easeInOutQuad:function(x){return x<0.5?2*x*x:1-Math.pow(-2*x+2,2)/2;},
    easeInCubic:function(x){return x*x*x;},
    easeOutCubic:function(x){return 1-Math.pow(1-x,3);},
    easeInOutCubic:function(x){return x<0.5?4*x*x*x:1-Math.pow(-2*x+2,3)/2;},
    easeInQuart:function(x){return x*x*x*x;},
    easeOutQuart:function(x){return 1-Math.pow(1-x,4);},
    easeInOutQuart:function(x){return x<0.5?8*x*x*x*x:1-Math.pow(-2*x+2,4)/2;},
    easeInQuint:function(x){return x*x*x*x*x;},
    easeOutQuint:function(x){return 1-Math.pow(1-x,5);},
    easeInOutQuint:function(x){return x<0.5?16*x*x*x*x*x:1-Math.pow(-2*x+2,5)/2;},
    easeInExpo:function(x){return x===0?0:Math.pow(2,10*x-10);},
    easeOutExpo:function(x){return x===1?1:1-Math.pow(2,-10*x);},
    easeInOutExpo:function(x){return x===0?0:x===1?1:x<0.5?Math.pow(2,20*x-10)/2:(2-Math.pow(2,-20*x+10))/2;},
    easeInCirc:function(x){return 1-Math.sqrt(1-Math.pow(x,2));},
    easeOutCirc:function(x){return Math.sqrt(1-Math.pow(x-1,2));},
    easeInOutCirc:function(x){return x<0.5?(1-Math.sqrt(1-Math.pow(2*x,2)))/2:(Math.sqrt(1-Math.pow(-2*x+2,2))+1)/2;},
    easeInBack:function(x){return c3*x*x*x-c1*x*x;},
    easeOutBack:function(x){return 1+c3*Math.pow(x-1,3)+c1*Math.pow(x-1,2);},
    easeInOutBack:function(x){return x<0.5?(Math.pow(2*x,2)*((c2+1)*2*x-c2))/2:(Math.pow(2*x-2,2)*((c2+1)*(x*2-2)+c2)+2)/2;},
    easeInElastic:function(x){return x===0?0:x===1?1:-Math.pow(2,10*x-10)*Math.sin((x*10-10.75)*c4);},
    easeOutElastic:function(x){return x===0?0:x===1?1:Math.pow(2,-10*x)*Math.sin((x*10-0.75)*c4)+1;},
    easeInOutElastic:function(x){return x===0?0:x===1?1:x<0.5?-(Math.pow(2,20*x-10)*Math.sin((20*x-11.125)*c5))/2:Math.pow(2,-20*x+10)*Math.sin((20*x-11.125)*c5)/2+1;},
    easeInBounce:function(x){return 1-ob(1-x);},
    easeOutBounce:ob,
    easeInOutBounce:function(x){return x<0.5?(1-ob(1-2*x))/2:(1+ob(2*x-1))/2;}
  };
})();
"""

CANVAS_HEAD = """
var cv = document.getElementById('cv'), ctx = cv.getContext('2d');
cv.width = 1080; cv.height = 1920;
var img = new Image(); img.src = './photo.png';
var lastP = 0;
function photo() {
  if (!img.complete || !img.naturalWidth) return;
  var s = Math.max(1080 / img.naturalWidth, 1920 / img.naturalHeight);
  var w = img.naturalWidth * s, h = img.naturalHeight * s;
  ctx.drawImage(img, (1080 - w) / 2, (1920 - h) / 2, w, h);
}
function reset() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, 1080, 1920);
  ctx.globalCompositeOperation = 'source-over';
}
img.onload = function () { paint(lastP); };
"""

ITEMS = []


def add(fam, no, name, note, body, js, css="", dur=None):
    ITEMS.append(dict(fam=fam, no=no, name=name, note=note, body=body, js=js, css=css, dur=dur or DUR))


# ==================================================================== E 缓动（33）

EASINGS = [
    ("linear", "线性"), ("easeInSine", "正弦进"), ("easeOutSine", "正弦出"), ("easeInOutSine", "正弦进出"),
    ("easeInQuad", "二次进"), ("easeOutQuad", "二次出"), ("easeInOutQuad", "二次进出"),
    ("easeInCubic", "三次进"), ("easeOutCubic", "三次出"), ("easeInOutCubic", "三次进出"),
    ("easeInQuart", "四次进"), ("easeOutQuart", "四次出"), ("easeInOutQuart", "四次进出"),
    ("easeInQuint", "五次进"), ("easeOutQuint", "五次出"), ("easeInOutQuint", "五次进出"),
    ("easeInExpo", "指数进"), ("easeOutExpo", "指数出"), ("easeInOutExpo", "指数进出"),
    ("easeInCirc", "圆弧进"), ("easeOutCirc", "圆弧出"), ("easeInOutCirc", "圆弧进出"),
    ("easeInBack", "回拉进"), ("easeOutBack", "回拉出"), ("easeInOutBack", "回拉进出"),
    ("easeInElastic", "弹性进"), ("easeOutElastic", "弹性出"), ("easeInOutElastic", "弹性进出"),
    ("easeInBounce", "弹跳进"), ("easeOutBounce", "弹跳出"), ("easeInOutBounce", "弹跳进出"),
]
for i, (fn, cn) in enumerate(EASINGS, 1):
    add("缓动", "E%02d" % i, cn, "timingFunctions.ts 原样实现（easings.net 公式），绿点是该曲线，灰圈是线性对照",
        """
  <div class="track" id="trk"><div class="ghost" id="gh"></div><div class="dot" id="dot"></div><div class="fin"></div></div>
""",
        EASE_JS + """
var f = EASE['__FN__'];
gsap.set('#dot', {x: 0, opacity: 1});
tl.to('#gh', {x: 900, duration: 1.75, ease: 'none'}, 0.6);
tl.to('#dot', {x: 900, duration: 1.75, ease: f}, 0.6);
""".replace("__FN__", fn))

# ==================================================================== SP 弹簧（7×2）

SPRINGS = [
    ("plop", "Plop 落定", 1.5), ("bounce", "Bounce 长摆", 2.35), ("swing", "Swing 摇摆", 1.7),
    ("smooth", "Smooth 顺滑", 1.5), ("beat", "Beat 冲过", 1.6), ("jump", "Jump 起跳", 1.6),
    ("strike", "Strike 打击", 0.55),
]
for i, (sp, cn, te) in enumerate(SPRINGS, 1):
    add("弹簧", "SP%02d" % i, cn + "·位移",
        "spring.ts 的 %s 预置（显式积分，非缓动表）；灰圈是线性对照" % sp,
        """
  <div class="track" id="trk"><div class="ghost" id="gh"></div><div class="dot" id="dot"></div><div class="fin"></div></div>
""",
        SPRING_JS + """
var cfg = SP['__SP__'];
var te = __TE__, play = te < 1.0 ? te * 4.5 : te;   // 落定太快的预置慢放，否则读不出曲线
var ease = springEase(cfg[0], cfg[1], cfg[2], cfg[3], te);
gsap.set('#dot', {x: 0, opacity: 1});
tl.to('#gh', {x: 900, duration: play, ease: 'none'}, 0.5);
tl.to('#dot', {x: 900, duration: play, ease: ease}, 0.5);
""".replace("__SP__", sp).replace("__TE__", str(te)))
    add("弹簧", "SP%02d" % (i + 7), cn + "·角度",
        "同一条弹簧曲线驱动角度：小元素（角标/图标）归位用",
        """
  <div class="badge" id="bd">A+</div>
""",
        SPRING_JS + """
var cfg = SP['__SP__'];
var te = __TE__, play = te < 1.0 ? te * 4.5 : te;   // 落定太快的预置慢放
var ease = springEase(cfg[0], cfg[1], cfg[2], cfg[3], te);
gsap.set('#bd', {rotation: -26, scale: 0.8, transformOrigin: '50% 50%', opacity: 1});
tl.to('#bd', {rotation: 0, scale: 1, duration: play, ease: ease}, 0.5);
""".replace("__SP__", sp).replace("__TE__", str(te)))

# ==================================================================== TR 转场（4×4）

def two_scene(a_html, b_html, a_css="", b_css=""):
    return """
  <div class="layer" id="sa">%s</div>
  <div class="layer" id="sb">%s</div>
""" % (a_html, b_html)


TR_CSS = """
.a1{background:#0d1211;display:flex;align-items:center;padding:0 84px}
.a1 .big{font-size:96px;font-weight:700;line-height:1.16;letter-spacing:-.03em}
.a1 .big em{font-style:normal;color:#86F0C0}
.b1 .cap{position:absolute;left:64px;right:64px;bottom:150px;font-size:54px;font-weight:660;line-height:1.3;
  letter-spacing:-.02em;text-shadow:0 4px 30px rgba(0,0,0,.85)}
"""
A_TEXT = """<div class="a1"><div class="big">上一屏<em>整块</em><br>被推走</div></div>"""
B_PHOTO = """<div class="full"></div><div class="cap">下一屏跟着进来<br>边是硬的，不叠淡</div>"""

for i, (d, cn) in enumerate([("Left", "向左"), ("Right", "向右"), ("Top", "向上"), ("Bottom", "向下")], 1):
    dx = {"Left": -1080, "Right": 1080, "Top": 0, "Bottom": 0}[d]
    dy = {"Left": 0, "Right": 0, "Top": -1920, "Bottom": 1920}[d]
    add("转场", "TR%02d" % i, "推挤·" + cn,
        "slideTransition(Direction.%s)：前屏整块移出 %s，新屏从对侧同时压进来" % (d, cn),
        two_scene(A_TEXT, B_PHOTO),
        """
gsap.set('#sb', {x: __DX__, y: __DY__});
tl.to('#sa', {x: __NDX__, y: __NDY__, duration: 0.72, ease: 'power3.inOut'}, 1.05);
tl.to('#sb', {x: 0, y: 0, duration: 0.72, ease: 'power3.inOut'}, 1.05);
""".replace("__DX__", str(dx)).replace("__DY__", str(dy)).replace("__NDX__", str(-dx)).replace("__NDY__", str(-dy)),
        TR_CSS)

AREAS = [("右上", 778, 625, 0.44), ("左下", 302, 1035, 0.44), ("正中", 540, 830, 0.52), ("下方", 540, 1240, 0.4)]
for i, (cn, cx, cy, s0) in enumerate(AREAS, 5):
    add("转场", "TR%02d" % i, "聚焦进入·" + cn,
        "zoomInTransition：新屏从 (x=%d,y=%d) 那块矩形长到满屏，旧屏淡出" % (cx, cy),
        """
  <div class="layer" id="sa"><div class="grid4"><div class="t"></div><div class="t"></div><div class="t"></div><div class="t"></div></div></div>
  <div class="layer b1" id="sb"><div class="full"></div><div class="cap">从<em>一格</em>推进到这一格</div></div>
""",
        """
gsap.set('#sb', {x: __DX__, y: __DY__, scale: __S0__, transformOrigin: '50% 50%', opacity: 0});
tl.to('#sb', {opacity: 1, duration: 0.2, ease: 'none'}, 1.0);
tl.to('#sa', {opacity: 0, duration: 0.45, ease: 'power1.in'}, 1.0);
tl.to('#sb', {x: 0, y: 0, scale: 1, duration: 0.95, ease: 'power3.inOut'}, 1.0);
""".replace("__DX__", str(cx - 540)).replace("__DY__", str(cy - 960)).replace("__S0__", str(s0)),
        TR_CSS + """
.grid4{position:absolute;left:64px;right:64px;top:420px;height:820px;display:grid;
  grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:14px}
.grid4 .t{border-radius:16px;background-image:url("./photo.png");background-size:200% 200%;
  border:1px solid rgba(255,255,255,.08)}
.grid4 .t:nth-child(1){background-position:0% 0%}.grid4 .t:nth-child(2){background-position:100% 0%}
.grid4 .t:nth-child(3){background-position:0% 100%}.grid4 .t:nth-child(4){background-position:100% 100%}
""")

for i, (cn, sc0) in enumerate([("拉远 1.6×", 1.62), ("拉远 2.2×", 2.2), ("拉远 1.3×", 1.3), ("拉远 2.8×", 2.8)], 9):
    add("转场", "TR%02d" % i, "拉远离场·" + cn,
        "zoomOutTransition：新屏从 %s 拉回 1 倍，旧屏同时缩进中心消失" % cn,
        two_scene("""<div class="a1"><div class="big">先看清<em>一个字</em><br>再退到全景</div></div>""",
                  """<div class="full"></div><div class="cap">镜头往后退<br>这一屏才装得下</div>"""),
        """
gsap.set('#sb', {scale: __S0__, transformOrigin: '50% 46%', opacity: 0});
tl.to('#sb', {opacity: 1, duration: 0.3, ease: 'none'}, 1.0);
tl.to('#sb', {scale: 1, duration: 1.15, ease: 'power2.out'}, 1.0);
tl.to('#sa', {scale: 0.66, opacity: 0, duration: 1.0, ease: 'power2.in'}, 1.0);
""".replace("__S0__", str(sc0)), TR_CSS)

for i, (cn, d, y0, sc0) in enumerate([
        ("淡出 0.3s", 0.3, 0, 1.0), ("淡出 0.8s", 0.8, 0, 1.0),
        ("淡出带上浮", 0.6, 40, 1.0), ("淡出带放大", 0.6, 0, 1.06)], 13):
    add("转场", "TR%02d" % i, cn,
        "fadeTransition：时长/位移/缩放三种变体，都是整体 alpha 过渡",
        two_scene("""<div class="a1"><div class="big">淡出<em>最省</em><br>但也最没信息</div></div>""",
                  """<div class="full"></div><div class="cap">用在节奏不该被注意的地方</div>"""),
        """
gsap.set('#sb', {opacity: 0, y: __Y0__, scale: __SC0__});
tl.to('#sa', {opacity: 0, duration: __D__}, 1.0);
tl.to('#sb', {opacity: 1, y: 0, scale: 1, duration: __D__}, 1.0);
""".replace("__D__", str(d)).replace("__Y0__", str(y0)).replace("__SC0__", str(sc0)), TR_CSS)

# ==================================================================== FL 滤镜（8×3）

FILTERS = [
    ("blur", "模糊", "0px", "24px"),
    ("grayscale", "去色", "0", "1"),
    ("sepia", "棕褐", "0", "0.9"),
    ("invert", "反相", "0", "1"),
    ("brightness", "亮度", "1", "1.7"),
    ("contrast", "对比", "1", "0.2"),
    ("saturate", "饱和", "1", "2.4"),
    ("hue-rotate", "色相", "0deg", "300deg"),
]
FL_CSS = """
.fwrap{position:absolute;left:64px;right:64px;top:400px;height:1020px;border-radius:22px;overflow:hidden;
  border:1px solid rgba(255,255,255,.09)}
.fwrap .ph{position:absolute;inset:0;background-image:url("./photo.png");background-size:cover;
  background-position:52% 40%}
.fwrap .chips{position:absolute;left:0;right:0;bottom:0;height:190px;display:flex}
.fwrap .chips b{flex:1;display:block}
.fwrap .chips b:nth-child(1){background:#E23A2E}
.fwrap .chips b:nth-child(2){background:#E8B22A}
.fwrap .chips b:nth-child(3){background:#2FA85A}
.fwrap .chips b:nth-child(4){background:#2B6BD6}
.fwrap .chips b:nth-child(5){background:#8E3FD0}
"""
for i, (fn, cn, v0, v1) in enumerate(FILTERS, 1):
    for j, mode in enumerate(["进", "出", "来回"], 1):
        if mode == "进":
            init = "gsap.set('#ph',{opacity:1});d.v=0;paint();"
            seq = "tl.to(d,{v:1,duration:1.4,ease:'power2.out',onUpdate:paint},0.65);"
        elif mode == "出":
            init = "gsap.set('#ph',{opacity:1});d.v=1;paint();"
            seq = "tl.to(d,{v:0,duration:1.4,ease:'power2.in',onUpdate:paint},0.65);"
        else:
            init = "gsap.set('#ph',{opacity:1});d.v=0;paint();"
            seq = ("tl.to(d,{v:1,duration:0.85,ease:'power2.inOut',onUpdate:paint},0.6);"
                   "tl.to(d,{v:0,duration:0.9,ease:'power2.inOut',onUpdate:paint},1.45);")
        add("滤镜", "FL%02d" % ((i - 1) * 3 + j), cn + "·" + mode,
            "Filter.ts 的 %s：%s → %s（%s）；色块条是为了让低彩度照片上的变化也看得见" % (fn, v0, v1, mode),
            """
  <div class="fwrap"><div class="ph" id="ph"><div class="chips"><b></b><b></b><b></b><b></b><b></b></div></div></div>
""",
            """
var d = {v: 0};
function paint() {
  var v = d.v, val;
  if (v <= 0) val = '__V0__';
  else if (v >= 1) val = '__V1__';
  else if ('__FN__' === 'blur') val = (24 * v) + 'px';
  else if ('__FN__' === 'hue-rotate') val = (300 * v) + 'deg';
  else if ('__FN__' === 'brightness') val = (1 + 0.7 * v);
  else if ('__FN__' === 'contrast') val = (1 - 0.8 * v);
  else if ('__FN__' === 'saturate') val = (1 + 1.4 * v);
  else if ('__FN__' === 'sepia') val = (0.9 * v);
  else val = v;
  document.getElementById('ph').style.filter = '__FN__(' + val + ')';
}
__INIT__
__SEQ__
""".replace("__INIT__", init).replace("__SEQ__", seq)
               .replace("__V0__", v0).replace("__V1__", v1).replace("__FN__", fn),
            css=FL_CSS)

# ==================================================================== CM 合成（26×2）

OPS = ["source-over", "source-in", "source-out", "source-atop", "destination-over", "destination-in",
       "destination-out", "destination-atop", "lighter", "copy", "xor", "multiply", "screen", "overlay",
       "darken", "lighten", "color-dodge", "color-burn", "hard-light", "soft-light", "difference",
       "exclusion", "hue", "saturation", "color", "luminosity"]

# 演示带：中间一条 1080×900 的横带。带外保留原样照片当参照，
# 否则 source-in / copy 这类运算会把整幅照片清掉，看起来只有「画面没了」，看不出做了什么。
# 照片先垫 saturate(1.9)：仓库的示例照片本身彩度低，hue / saturation / color 这几档几乎看不出差别。
BAND_JS = """
var BX = 0, BY = 700, BW = 1080, BH = 900;
ctx.filter = 'saturate(1.9)';
function band() {
  ctx.save();
  ctx.beginPath();
  ctx.rect(BX, BY, BW, BH);
  ctx.clip();
  ctx.clearRect(BX, BY, BW, BH);
  photo();
}
function bandEnd() {
  ctx.globalCompositeOperation = 'source-over';
  ctx.restore();
  ctx.strokeStyle = 'rgba(255,255,255,.22)';
  ctx.lineWidth = 2;
  ctx.strokeRect(BX, BY, BW, BH);
}
function card(p) {
  var w = 620, h = 620, x = 60 + p * 340, y = BY + 140;
  ctx.save();
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, 40);
  ctx.clip();
  photo();
  ctx.restore();
}
"""

for i, op in enumerate(OPS, 1):
    # 变体 A：照片在下，圆在上
    add("合成", "CM%02d" % i, op + "·圆压照片",
        "globalCompositeOperation=%s：中间横带里是运算结果，带外保留原样照片当参照" % op,
        """
  <canvas class="cv" id="cv"></canvas>
""",
        CANVAS_HEAD + BAND_JS + """
var OP = '__OP__';
function paint(p) {
  lastP = p; reset();
  photo();
  band();
  ctx.globalCompositeOperation = OP;
  ctx.beginPath();
  ctx.arc(200 + p * 680, BY + 450, 330, 0, Math.PI * 2);
  ctx.fillStyle = '#FF2E88';
  ctx.fill();
  bandEnd();
}
var d = {p: 0};
tl.to(d, {p: 1, duration: 2.0, ease: 'none', onUpdate: function () { paint(d.p); }}, 0.55);
paint(0);
""".replace("__OP__", op))
    # 变体 B：条纹在下，照片卡在上（stencil / 遮罩用法）
    add("合成", "CM%02d" % (i + 26), op + "·照片当笔",
        "反过来：带里先画斜条纹，再用 %s 盖一张移动的照片卡 —— revideo 的 stencil 遮罩写法" % op,
        """
  <canvas class="cv" id="cv"></canvas>
""",
        CANVAS_HEAD + BAND_JS + """
var OP = '__OP__';
function paint(p) {
  lastP = p; reset();
  photo();
  ctx.save();
  ctx.beginPath();
  ctx.rect(BX, BY, BW, BH);
  ctx.clip();
  ctx.clearRect(BX, BY, BW, BH);
  ctx.save();
  ctx.translate(540, BY + 450);
  ctx.rotate(-0.5 + p * 0.9);
  ctx.fillStyle = '#FF2E88';
  var k;
  for (k = -8; k <= 8; k++) {
    ctx.fillRect(-900, k * 92 - 24, 1800, 48);
  }
  ctx.restore();
  ctx.globalCompositeOperation = OP;
  card(p);
  bandEnd();
}
var d = {p: 0};
tl.to(d, {p: 1, duration: 2.0, ease: 'none', onUpdate: function () { paint(d.p); }}, 0.55);
paint(0);
""".replace("__OP__", op))

# ==================================================================== CP 组件（23）

SVG_HEAD = '<svg class="stage2" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">'
SVG_TAIL = "</svg>"

COMPONENTS = []

COMPONENTS.append(("Circle 圆", "半径 0→320，同时描边收细",
                    SVG_HEAD + '<circle id="c" cx="540" cy="960" r="0" fill="none" stroke="#86F0C0" stroke-width="10"/>' + SVG_TAIL,
                    "tl.to('#c', {attr: {r: 320}, duration: 1.4, ease: 'power3.out'}, 0.6);"
                    "tl.to('#c', {attr: {'stroke-width': 2}, duration: 1.4, ease: 'power2.out'}, 0.6);"))
COMPONENTS.append(("Rect 矩形", "宽高与圆角一起长",
                    SVG_HEAD + '<rect id="r" x="540" y="960" width="0" height="0" rx="0" fill="rgba(134,240,192,.14)" stroke="#86F0C0"/>' + SVG_TAIL,
                    "tl.to('#r', {attr: {x: 160, y: 660, width: 760, height: 600, rx: 64}, duration: 1.3, ease: 'power3.out'}, 0.6);"))
COMPONENTS.append(("Polygon 多边形", "边数 3→8、半径同时长",
                    SVG_HEAD + '<polygon id="p" points="" fill="rgba(134,240,192,.14)" stroke="#86F0C0" stroke-width="3"/>' + SVG_TAIL,
                    "var d={n:3,r:0};\n"
                    "function pp(){var n=Math.round(d.n),pts=[],i;"
                    "for(i=0;i<n;i++){var a=-Math.PI/2+i*2*Math.PI/n;pts.push((540+d.r*Math.cos(a)).toFixed(1)+','+(960+d.r*Math.sin(a)).toFixed(1));}"
                    "document.getElementById('p').setAttribute('points',pts.join(' '));}\n"
                    "tl.to(d,{n:8,r:320,duration:1.4,ease:'power2.out',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("Line 直线", "线从一点画到另一点",
                    SVG_HEAD + '<line id="l" x1="140" y1="1500" x2="140" y2="1500" stroke="#86F0C0" stroke-width="6" stroke-linecap="round"/>' + SVG_TAIL,
                    "tl.to('#l', {attr: {x2: 940, y2: 460}, duration: 1.3, ease: 'power2.inOut'}, 0.6);"))
COMPONENTS.append(("Ray 射线", "线 + 箭头，箭头跟切线",
                    SVG_HEAD + '<line id="l" x1="140" y1="1500" x2="140" y2="1500" stroke="#86F0C0" stroke-width="6" stroke-linecap="round"/>'
                    '<polygon id="h" points="0,-26 34,0 0,26" fill="#86F0C0" transform="translate(140,1500)"/>' + SVG_TAIL,
                    "var d={p:0};\n"
                    "function pp(){var x=140+d.p*800,y=1500-d.p*1040,ang=Math.atan2(-1040,800)*180/Math.PI;"
                    "document.getElementById('l').setAttribute('x2',x);document.getElementById('l').setAttribute('y2',y);"
                    "document.getElementById('h').setAttribute('transform','translate('+x+','+y+') rotate('+ang+')');}\n"
                    "tl.to(d,{p:1,duration:1.3,ease:'power2.inOut',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("Curve 曲线", "三次贝塞尔描边画满",
                    SVG_HEAD + '<path id="k" d="M140,1400 C420,700 700,1500 940,620" fill="none" stroke="#86F0C0" stroke-width="7" stroke-linecap="round"/>' + SVG_TAIL,
                    "var len = document.getElementById('k').getTotalLength();\n"
                    "gsap.set('#k', {strokeDasharray: len, strokeDashoffset: len});\n"
                    "tl.to('#k', {strokeDashoffset: 0, duration: 1.6, ease: 'power2.inOut'}, 0.6);"))
COMPONENTS.append(("Bezier 贝塞尔", "控制点带着曲线一起动",
                    SVG_HEAD + '<path id="k" d="M160,1440 C420,600 700,1500 920,700" fill="none" stroke="#86F0C0" stroke-width="7"/>'
                    '<line id="h1" x1="160" y1="1440" x2="420" y2="600" stroke="rgba(255,255,255,.28)" stroke-dasharray="6 8"/>'
                    '<line id="h2" x1="920" y1="700" x2="700" y2="1500" stroke="rgba(255,255,255,.28)" stroke-dasharray="6 8"/>'
                    '<circle id="c1" cx="420" cy="600" r="12" fill="#E7C98A"/>'
                    '<circle id="c2" cx="700" cy="1500" r="12" fill="#E7C98A"/>' + SVG_TAIL,
                    "var d={y:0};\n"
                    "function pp(){var a=600-d.y*260,b=1500-d.y*300;"
                    "document.getElementById('c1').setAttribute('cy',a);document.getElementById('c2').setAttribute('cy',b);"
                    "document.getElementById('h1').setAttribute('y2',a);document.getElementById('h2').setAttribute('y2',b);"
                    "document.getElementById('k').setAttribute('d','M160,1440 C420,'+a+' 700,'+b+' 920,700');}\n"
                    "tl.to(d,{y:1,duration:1.5,ease:'power2.inOut',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("CubicBezier 三次贝塞尔", "两个手柄各自甩出去",
                    SVG_HEAD + '<path id="k" d="M160,1500 C160,1500 920,1500 920,1500" fill="none" stroke="#86F0C0" stroke-width="7"/>'
                    '<circle id="c1" cx="160" cy="1500" r="11" fill="#E7C98A"/><circle id="c2" cx="920" cy="1500" r="11" fill="#E7C98A"/>' + SVG_TAIL,
                    "var d={p:0};\n"
                    "function pp(){var y1=1500-d.p*900,y2=1500-d.p*900;"
                    "document.getElementById('k').setAttribute('d','M160,1500 C160,'+y1+' 920,'+y2+' 920,1500');"
                    "document.getElementById('c1').setAttribute('cy',y1);document.getElementById('c2').setAttribute('cy',y2);}\n"
                    "tl.to(d,{p:1,duration:1.4,ease:'power3.out',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("QuadBezier 二次贝塞尔", "一个控制点拉满",
                    SVG_HEAD + '<path id="k" d="M160,1500 Q540,1500 920,1500" fill="none" stroke="#86F0C0" stroke-width="7"/>'
                    '<circle id="c1" cx="540" cy="1500" r="11" fill="#E7C98A"/>' + SVG_TAIL,
                    "var d={p:0};\n"
                    "function pp(){var y=1500-d.p*950;"
                    "document.getElementById('k').setAttribute('d','M160,1500 Q540,'+y+' 920,1500');"
                    "document.getElementById('c1').setAttribute('cy',y);}\n"
                    "tl.to(d,{p:1,duration:1.4,ease:'power3.out',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("Spline 样条", "四个节点，平滑度从直线到曲线",
                    SVG_HEAD + '<path id="k" d="" fill="none" stroke="#86F0C0" stroke-width="7" stroke-linecap="round"/>' + SVG_TAIL,
                    "var P=[[160,1440],[420,900],[700,1420],[920,700]];\n"
                    "var d={s:0};\n"
                    "function pp(){var s=d.s,a='M'+P[0][0]+','+P[0][1],i;"
                    "for(i=0;i<P.length-1;i++){var p0=P[i],p1=P[i+1];"
                    "var cx1=p0[0]+(p1[0]-p0[0])*0.5*s,cy1=p0[1];"
                    "var cx2=p0[0]+(p1[0]-p0[0])*(1-0.5*s),cy2=p1[1];"
                    "a+=' C'+cx1+','+cy1+' '+cx2+','+cy2+' '+p1[0]+','+p1[1];}"
                    "document.getElementById('k').setAttribute('d',a);}\n"
                    "tl.to(d,{s:1,duration:1.5,ease:'power2.inOut',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("Knot 节点手柄", "手柄绕着节点转，曲线跟着变",
                    SVG_HEAD + '<path id="k" d="" fill="none" stroke="#86F0C0" stroke-width="7"/>'
                    '<line id="h1" x1="540" y1="960" x2="540" y2="960" stroke="rgba(255,255,255,.3)" stroke-dasharray="6 8"/>'
                    '<line id="h2" x1="540" y1="960" x2="540" y2="960" stroke="rgba(255,255,255,.3)" stroke-dasharray="6 8"/>'
                    '<circle id="c" cx="540" cy="960" r="14" fill="#E7C98A"/>' + SVG_TAIL,
                    "var d={a:0};\n"
                    "function pp(){var r=300,a1=(-150+d.a*120)*Math.PI/180,a2=(-30+d.a*120)*Math.PI/180;"
                    "var x1=540+r*Math.cos(a1),y1=960+r*Math.sin(a1),x2=540+r*Math.cos(a2),y2=960+r*Math.sin(a2);"
                    "document.getElementById('h1').setAttribute('x2',x1);document.getElementById('h1').setAttribute('y2',y1);"
                    "document.getElementById('h2').setAttribute('x2',x2);document.getElementById('h2').setAttribute('y2',y2);"
                    "document.getElementById('k').setAttribute('d','M160,1500 C'+x1+','+y1+' '+x2+','+y2+' 920,700');}\n"
                    "tl.to(d,{a:1,duration:1.6,ease:'power2.inOut',onUpdate:pp},0.6);pp();"))
COMPONENTS.append(("Path 路径", "星形路径描边画满",
                    SVG_HEAD + '<path id="k" d="M540,520 L610,780 L880,790 L665,950 L735,1210 L540,1060 L345,1210 L415,950 L200,790 L470,780 Z" fill="none" stroke="#86F0C0" stroke-width="7" stroke-linejoin="round"/>' + SVG_TAIL,
                    "var len=document.getElementById('k').getTotalLength();\n"
                    "gsap.set('#k',{strokeDasharray:len,strokeDashoffset:len});\n"
                    "tl.to('#k',{strokeDashoffset:0,duration:1.7,ease:'power1.inOut'},0.6);"))
COMPONENTS.append(("Grid 网格", "线间距从 0 撑开",
                    SVG_HEAD + '<g id="g" stroke="rgba(134,240,192,.5)" stroke-width="2"></g>' + SVG_TAIL,
                    "var d={s:0};\n"
                    "function pp(){var s=20+d.s*90,o='',i;"
                    "for(i=0;i*40<=1080;i++){o+='<line x1=\"'+(i*40)+'\" y1=\"420\" x2=\"'+(i*40)+'\" y2=\"1420\"/>';}"
                    "for(i=0;i*40<=1000;i++){o+='<line x1=\"0\" y1=\"'+(420+i*40)+'\" x2=\"1080\" y2=\"'+(420+i*40)+'\"/>';}"
                    "document.getElementById('g').innerHTML=o;}\n"
                    "gsap.set('#g',{opacity:1});\n"
                    "tl.fromTo('#g',{opacity:0},{opacity:1,duration:0.9,ease:'power2.out'},0.6);pp();"))
COMPONENTS.append(("Icon 图标", "描边图标 + 一次旋转归位",
                    SVG_HEAD + '<g id="i" transform="translate(540,960)">'
                    '<path id="k" d="M-120,0 L0,120 L120,0" fill="none" stroke="#86F0C0" stroke-width="16" stroke-linecap="round" stroke-linejoin="round"/>'
                    '</g>' + SVG_TAIL,
                    "var len=document.getElementById('k').getTotalLength();\n"
                    "gsap.set('#k',{strokeDasharray:len,strokeDashoffset:len});\n"
                    "gsap.set('#i',{rotation:-40,transformOrigin:'50% 50%'});\n"
                    "tl.to('#i',{rotation:0,duration:1.2,ease:'back.out(1.7)'},0.6);\n"
                    "tl.to('#k',{strokeDashoffset:0,duration:1.1,ease:'power2.out'},0.6);"))
COMPONENTS.append(("SVG 图形", "整块 SVG 缩放 + 旋转",
                    SVG_HEAD + '<g id="g" transform="translate(540,960)"><circle r="260" fill="rgba(134,240,192,.12)" stroke="#86F0C0" stroke-width="3"/>'
                    '<circle r="170" fill="none" stroke="rgba(134,240,192,.5)" stroke-width="2"/>'
                    '<circle r="90" fill="none" stroke="rgba(231,201,138,.7)" stroke-width="2"/></g>' + SVG_TAIL,
                    "gsap.set('#g',{scale:0.4,rotation:-90,transformOrigin:'50% 50%',opacity:1});\n"
                    "tl.to('#g',{scale:1,rotation:0,duration:1.5,ease:'power3.out'},0.6);"))
COMPONENTS.append(("Img 图片", "圆角 + 缩放，焦点不跑",
                    """
  <div class="photo2" id="ph" style="border-radius:0"></div>
""",
                    "gsap.set('#ph',{scale:1.18,opacity:1});\n"
                    "tl.to('#ph',{scale:1,duration:1.6,ease:'power2.out'},0.6);\n"
                    "tl.to('#ph',{borderRadius:'28px',duration:1.6,ease:'power2.out'},0.6);"))
COMPONENTS.append(("Txt 文本", "字距收紧 + 逐行遮罩",
                    """
  <div style="position:absolute;left:64px;right:64px;top:800px;font-size:84px;font-weight:700;
    line-height:1.2;letter-spacing:-.03em" id="t">字距收紧要慢<br>快就看不出</div>
""",
                    "gsap.set('#t',{letterSpacing:'0.18em',opacity:1});\n"
                    "tl.to('#t',{letterSpacing:'-0.03em',duration:1.7,ease:'power2.inOut'},0.6);"))
COMPONENTS.append(("Code 代码", "replace 局部重写（不是重打整段）",
                    """
  <div class="code" id="cd">
    <div class="ln"><i>1</i><span><span class="fn">const</span> n = <span id="old">7</span><span id="new" style="opacity:0">0x1F</span>;</span></div>
    <div class="ln"><i>2</i><span class="cm">// 只换一个 token</span></div>
  </div>
""",
                    "gsap.set('#cd',{opacity:1});\n"
                    "tl.to('#old',{opacity:0.2,textDecoration:'line-through',duration:0.35},1.15);\n"
                    "tl.to('#new',{opacity:1,duration:0.4,ease:'power2.out'},1.5);"))
COMPONENTS.append(("CodeBlock 代码块", "行号 + 行高亮扫过",
                    """
  <div class="code" id="cd">
    <div class="ln" id="l1"><i>1</i><span><span class="fn">def</span> run(q):</span></div>
    <div class="ln" id="l2"><i>2</i><span>    <span class="fn">return</span> search.run(q)</span></div>
    <div class="ln" id="l3"><i>3</i><span>    <span class="cm"># 这一行被选中</span></span></div>
  </div>
""",
                    "gsap.set('#cd',{opacity:1});\n"
                    "tl.to('#l2',{backgroundColor:'rgba(134,240,192,.14)',duration:0.5},0.9);\n"
                    "tl.to('#l2',{backgroundColor:'rgba(0,0,0,0)',duration:0.5},1.6);\n"
                    "tl.to('#l3',{backgroundColor:'rgba(231,201,138,.12)',duration:0.5},1.7);"))
COMPONENTS.append(("Latex 公式", "公式逐项落位（用 HTML 排，不用 MathJax）",
                    """
  <div style="position:absolute;left:0;right:0;top:820px;text-align:center;font-family:Georgia,serif;
    font-size:76px;letter-spacing:.02em;color:#F4F1E9" id="eq">
    <span id="e1">x</span> = <span id="e2">−b ± √(b²−4ac)</span> / <span id="e3">2a</span>
  </div>
""",
                    "gsap.set('#e1,#e2,#e3',{opacity:0,y:26});\n"
                    "tl.to('#e1',{opacity:1,y:0,duration:0.5},0.7);\n"
                    "tl.to('#e2',{opacity:1,y:0,duration:0.6},1.1);\n"
                    "tl.to('#e3',{opacity:1,y:0,duration:0.5},1.7);"))
COMPONENTS.append(("Layout 版面", "gap / direction 变化时元素自动重排",
                    """
  <div class="rowbox" id="box" style="display:flex;gap:16px;flex-direction:column">
    <div class="chip" id="k1">甲</div><div class="chip" id="k2">乙</div><div class="chip" id="k3">丙</div>
  </div>
""",
                    "gsap.set('#box',{opacity:1});\n"
                    "tl.to('#box',{flexDirection:'row',gap:'26px',duration:0.1},1.15);\n"
                    "tl.fromTo('#k1,#k2,#k3',{scale:0.9},{scale:1,duration:0.5,stagger:0.08,ease:'power2.out'},1.15);"))
COMPONENTS.append(("Shape 形状", "填充渐变 + 旋转",
                    SVG_HEAD + '<defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1">'
                    '<stop offset="0" stop-color="#86F0C0"/><stop offset="1" stop-color="#2f6b55"/></linearGradient></defs>'
                    '<rect id="r" x="340" y="760" width="400" height="400" rx="40" fill="url(#lg)" opacity="0.9"/>' + SVG_TAIL,
                    "gsap.set('#r',{rotation:-25,transformOrigin:'50% 50%'});\n"
                    "tl.to('#r',{rotation:0,duration:1.4,ease:'power3.out'},0.6);"))
COMPONENTS.append(("Node 节点", "opacity / scale / rotation 三合一",
                    """
  <div class="badge" id="nd" style="background:linear-gradient(150deg,#22323a,#101816);color:#86F0C0;border:1px solid rgba(134,240,192,.4)">NODE</div>
""",
                    "gsap.set('#nd',{opacity:0,scale:0.6,rotation:12,transformOrigin:'50% 50%'});\n"
                    "tl.to('#nd',{opacity:1,scale:1,rotation:0,duration:1.3,ease:'power3.out'},0.6);"))

for i, (name, note, body, js) in enumerate(COMPONENTS, 1):
    add("组件", "CP%02d" % i, name, note, body, js)

# ==================================================================== CV 曲线剖面（5×3）

def svg(body):
    return SVG_HEAD + body + SVG_TAIL

PROFILES = [
    ("rect", "矩形", 'M180,560 L900,560 L900,1360 L180,1360 Z'),
    ("circle", "圆", 'M540,540 A420,420 0 1,1 539.9,540'),
    ("polyline", "折线", 'M160,1400 L380,900 L600,1240 L820,640 L960,980'),
    ("path", "任意路径", 'M160,1200 C300,600 520,1500 700,820 S900,700 960,1100'),
    ("spline", "平滑样条", 'M160,1400 C300,1000 420,760 540,980 S820,1300 960,700'),
]
for i, (pk, cn, d) in enumerate(PROFILES, 1):
    for j, (mode, mcn) in enumerate([("描边", "draw"), ("跟随", "follow"), ("环绕", "orbit")], 1):
        if mode == "描边":
            body = svg('<path id="k" d="%s" fill="none" stroke="#86F0C0" stroke-width="7" stroke-linejoin="round"/>' % d)
            js = ("var len=document.getElementById('k').getTotalLength();\n"
                  "gsap.set('#k',{strokeDasharray:len,strokeDashoffset:len});\n"
                  "tl.to('#k',{strokeDashoffset:0,duration:1.7,ease:'power1.inOut'},0.6);")
        elif mode == "跟随":
            body = svg('<path id="k" d="%s" fill="none" stroke="rgba(255,255,255,.16)" stroke-width="4"/>'
                       '<path id="tr" d="%s" fill="none" stroke="#86F0C0" stroke-width="9" stroke-linecap="round"/>'
                       '<circle id="dot" cx="0" cy="0" r="28" fill="#86F0C0"/>' % (d, d))
            js = ("var path=document.getElementById('k'),L=path.getTotalLength();\n"
                  "var d={p:0};\n"
                  "function pp(){var pt=path.getPointAtLength(L*d.p),pv=path.getPointAtLength(Math.max(0,L*d.p-2));"
                  "var el=document.getElementById('dot');el.setAttribute('cx',pt.x);el.setAttribute('cy',pt.y);"
                  "var ang=Math.atan2(pt.y-pv.y,pt.x-pv.x)*180/Math.PI;el.setAttribute('transform','rotate('+ang+' '+pt.x+' '+pt.y+')');}\n"
                  "var tr=document.getElementById('tr'),TL=tr.getTotalLength();\n"
                  "gsap.set(tr,{strokeDasharray:TL,strokeDashoffset:TL});\n"
                  "tl.to(tr,{strokeDashoffset:0,duration:1.9,ease:'none'},0.6);\n"
                  "tl.to(d,{p:1,duration:1.9,ease:'none',onUpdate:pp},0.6);pp();")
        else:
            body = svg('<path id="k" d="%s" fill="none" stroke="rgba(255,255,255,.14)" stroke-width="3" stroke-dasharray="8 10"/>'
                       '<g id="g"></g>' % d)
            js = ("var path=document.getElementById('k'),L=path.getTotalLength(),o='',i;\n"
                  "for(i=0;i<28;i++){var pt=path.getPointAtLength(L*i/28);o+='<circle cx=\"'+pt.x+'\" cy=\"'+pt.y+'\" r=\"14\" fill=\"#86F0C0\" opacity=\"0.3\"/>';}\n"
                  "document.getElementById('g').innerHTML=o;\n"
                  "var nodes=document.getElementById('g').querySelectorAll('circle');\n"
                  "gsap.set(nodes,{opacity:0,scale:0,transformOrigin:'50% 50%'});\n"
                  "tl.to(nodes,{opacity:1,scale:1,duration:0.5,ease:'power2.out',stagger:0.05},0.6);")
        add("曲线剖面", "CV%02d" % ((i - 1) * 3 + j), cn + "·" + mode,
            "curves/get%sProfile：沿 %s 剖面取点，%s" % (pk.capitalize(), cn, mode), body, js)

# ==================================================================== CD 代码（8）

CODE_BASE = """
  <div class="code" id="cd">
    <div class="ln"><i>1</i><span><span class="fn">def</span> run(q):</span></div>
    <div class="ln"><i>2</i><span>    leads = search.run(q)</span></div>
    <div class="ln"><i>3</i><span>    <span class="fn">return</span> leads</span></div>
  </div>
"""

CODE_METHODS = [
    ("diff", "整段 diff", "新旧代码用 patience diff 对齐，只动差异部分",
     """
  <div class="code" id="cd">
    <div class="ln"><i>1</i><span><span class="fn">def</span> run(q):</span></div>
    <div class="ln" id="o2"><i>2</i><span>    leads = search.run(q)</span></div>
    <div class="ln" id="n2" style="opacity:0;height:0;overflow:hidden"><i>3</i><span>    leads = search.run(q).<span class="fn">enrich</span>()</span></div>
    <div class="ln"><i>4</i><span>    <span class="fn">return</span> leads</span></div>
  </div>
""",
     "gsap.set('#cd',{opacity:1});\n"
     "tl.to('#o2',{opacity:0.25,textDecoration:'line-through',duration:0.35},1.1);\n"
     "tl.to('#n2',{opacity:1,height:53,duration:0.45,ease:'power2.out'},1.45);"),
    ("append", "尾部追加", "在末尾接一段，前面的行不动",
     CODE_BASE,
     "gsap.set('#cd',{opacity:1});\n"
     "var d=document.createElement('div');d.className='ln';d.style.opacity=0;d.style.height=0;d.style.overflow='hidden';"
     "d.innerHTML='<i>4</i><span>    leads.push_to(crm)</span>';document.getElementById('cd').appendChild(d);\n"
     "tl.to(d,{opacity:1,height:53,duration:0.6,ease:'power2.out'},1.1);"),
    ("prepend", "头部插入", "在最前面塞一段，整体下移",
     CODE_BASE,
     "gsap.set('#cd',{opacity:1});\n"
     "var d=document.createElement('div');d.className='ln';d.style.opacity=0;d.style.height=0;d.style.overflow='hidden';"
     "d.innerHTML='<i>0</i><span><span class=\"fn\">import</span> search</span>';document.getElementById('cd').prepend(d);\n"
     "tl.to(d,{opacity:1,height:53,duration:0.6,ease:'power2.out'},1.1);"),
    ("insert", "中间插入", "在指定位置插一行，下面的行顺移",
     CODE_BASE,
     "gsap.set('#cd',{opacity:1});\n"
     "var d=document.createElement('div');d.className='ln';d.style.opacity=0;d.style.height=0;d.style.overflow='hidden';"
     "d.innerHTML='<i>2</i><span>    <span class=\"cm\"># 校验</span></span>';\n"
     "var lines=document.getElementById('cd').children;lines[1].after(d);\n"
     "tl.to(d,{opacity:1,height:53,duration:0.6,ease:'power2.out'},1.1);"),
    ("remove", "删除一行", "整行收掉，下面的行补上来",
     CODE_BASE,
     "gsap.set('#cd',{opacity:1});\n"
     "var lines=document.getElementById('cd').children;\n"
     "tl.to(lines[1],{opacity:0,height:0,duration:0.6,ease:'power2.in'},1.1);"),
    ("replace", "替换片段", "按范围换掉一个 token，其余字符保持",
     """
  <div class="code" id="cd">
    <div class="ln" id="rl"><i>1</i><span><span class="fn">const</span> n = <span id="o">7</span><span id="n" style="opacity:0;color:#86F0C0">0x1F_FF_AB</span>;</span></div>
    <div class="ln"><i>2</i><span><span class="cm">// 只换一个 token，其余字符不动</span></span></div>
  </div>
""",
     "gsap.set('#cd',{opacity:1});\n"
     "tl.to('#rl',{backgroundColor:'rgba(134,240,192,.16)',duration:0.35},1.05);\n"
     "tl.to('#o',{opacity:0.2,textDecoration:'line-through',duration:0.35},1.1);\n"
     "tl.to('#n',{opacity:1,duration:0.45,ease:'power2.out'},1.45);\n"
     "tl.to('#rl',{backgroundColor:'rgba(0,0,0,0)',duration:0.6},2.1);"),
    ("edit", "进入编辑态", "光标出现、逐字敲进去，像真的在改代码",
     """
  <div class="code" id="cd">
    <div class="ln"><i>1</i><span><span class="fn">def</span> run(q):</span></div>
    <div class="ln"><i>2</i><span>    <span id="ty"></span><span id="cur" style="display:inline-block;width:3px;height:34px;background:#86F0C0;vertical-align:-4px"></span></span></div>
  </div>
""",
     "gsap.set('#cd',{opacity:1});\n"
     "var txt='leads = search.run(q)', el=document.getElementById('ty'), i=0;\n"
     "var d={p:0};\n"
     "function pp(){var k=Math.floor(d.p*txt.length);if(k!==i){i=k;el.textContent=txt.slice(0,k);}}\n"
     "tl.to(d,{p:1,duration:1.5,ease:'none',onUpdate:pp},0.9);\n"
     "tl.to('#cur',{opacity:0,duration:0.12,repeat:5,yoyo:true},0.9);"),
    ("selection", "选区扫过", "按字符范围铺底色，讲哪句点哪句",
     """
  <div class="code" id="cd">
    <div class="ln"><i>1</i><span><span class="fn">def</span> run(q):</span></div>
    <div class="ln"><i>2</i><span>    leads = <span id="s1" style="background-image:linear-gradient(rgba(134,240,192,.24),rgba(134,240,192,.24));background-repeat:no-repeat;background-size:0% 100%;border-radius:4px">search.run(q)</span></span></div>
    <div class="ln"><i>3</i><span>    <span class="fn">return</span> leads</span></div>
  </div>
""",
     "gsap.set('#cd',{opacity:1});\n"
     "var d={w:0};\n"
     "function pp(){document.getElementById('s1').style.backgroundSize=(d.w*100)+'% 100%';}\n"
     "tl.to(d,{w:1,duration:0.7,ease:'power2.inOut',onUpdate:pp},1.0);"),
]

for i, (m, cn, note, body, js) in enumerate(CODE_METHODS, 1):
    add("代码", "CD%02d" % i, cn, "CodeSignalContext.%s：%s" % (m, note), body, js)

# ==================================================================== ND 节点属性（12）

NODE_PROPS = [
    ("opacity", "不透明度", "opacity 0→1", "tl.to('#b',{opacity:1,duration:1.2,ease:'power2.out'},0.6);", "gsap.set('#b',{opacity:0});"),
    ("x", "横向位移", "x −220→0", "tl.to('#b',{x:0,duration:1.2,ease:'power3.out'},0.6);", "gsap.set('#b',{x:-220});"),
    ("y", "纵向位移", "y 260→0", "tl.to('#b',{y:0,duration:1.2,ease:'power3.out'},0.6);", "gsap.set('#b',{y:260});"),
    ("rotation", "旋转", "rotation −18°→0", "tl.to('#b',{rotation:0,duration:1.3,ease:'power3.out'},0.6);", "gsap.set('#b',{rotation:-18});"),
    ("scaleX/Y", "缩放", "scale 0.72→1", "tl.to('#b',{scale:1,duration:1.3,ease:'power3.out'},0.6);", "gsap.set('#b',{scale:0.72});"),
    ("skew", "斜切", "skewX −16°→0", "tl.to('#b',{skewX:0,duration:1.2,ease:'power2.out'},0.6);", "gsap.set('#b',{skewX:-16});"),
    ("anchor", "锚点", "transform-origin 从左上换成中心", "tl.to('#b',{scale:1,duration:1.4,ease:'power2.out'},0.6);", "gsap.set('#b',{scale:0.5,transformOrigin:'0% 0%'});"),
    ("zIndex", "层级", "两个块换层：谁在上谁在下", "tl.to('#z2',{zIndex:1,duration:0.01},1.25);tl.to('#z1',{zIndex:3,duration:0.01},1.25);", "gsap.set('#z1',{zIndex:3});gsap.set('#z2',{zIndex:1});"),
    ("shadow", "投影", "shadowBlur/Offset 一起推（垫中灰台面才看得见黑投影）", "var d={b:10,o:8,al:0.45};function pp(){document.getElementById('b').style.boxShadow='0 '+d.o+'px '+d.b+'px rgba(0,0,0,'+d.al+')';}tl.to(d,{b:110,o:54,al:0.8,duration:1.1,ease:'power2.out',onUpdate:pp},0.6);", "gsap.set('#b',{opacity:1});"),
    ("filters", "滤镜数组", "blur + brightness 叠加", "var d={v:0};function pp(){document.getElementById('b').style.filter='blur('+(14*d.v)+'px) brightness('+(1+0.5*d.v)+')';}tl.to(d,{v:1,duration:1.3,ease:'power2.out',onUpdate:pp},0.6);", "gsap.set('#b',{opacity:1});"),
    ("composite", "合成运算", "canvas 上 source-in 的写法", None, None),
    ("save/restore", "状态存取", "记一次状态，改一圈再退回来", "tl.to('#b',{rotation:-24,scale:0.7,duration:0.7,ease:'power2.out'},0.7);tl.to('#b',{rotation:0,scale:1,duration:0.8,ease:'power2.inOut'},1.55);", "gsap.set('#b',{opacity:1});"),
]

for i, (pk, cn, note, js, init) in enumerate(NODE_PROPS, 1):
    if pk == "composite":
        body = '<canvas class="cv" id="cv"></canvas>'
        js2 = CANVAS_HEAD + """
var OP = 'destination-out';
function paint(p){ lastP=p; reset(); photo(); ctx.globalCompositeOperation=OP;
  ctx.beginPath(); ctx.arc(240+p*600, 960, 280, 0, Math.PI*2); ctx.fillStyle='#000'; ctx.fill();
  ctx.globalCompositeOperation='source-over'; }
var d={p:0};
tl.to(d,{p:1,duration:2.0,ease:'none',onUpdate:function(){paint(d.p);}},0.55);
paint(0);
"""
        add("节点属性", "ND%02d" % i, cn, "Node.%s：%s" % (pk, note), body, js2)
        continue
    if pk == "zIndex":
        body = """
  <div class="badge" id="z1" style="background:linear-gradient(150deg,#86F0C0,#2f6b55);left:38%;top:800px">前</div>
  <div class="badge" id="z2" style="background:linear-gradient(150deg,#E7C98A,#8a6a2f);left:46%;top:900px;color:#1a1206">后</div>
"""
        add("节点属性", "ND%02d" % i, cn, "Node.%s：%s" % (pk, note), body, js)
        continue
    if pk == "shadow":
        body = ('<div style="position:absolute;left:64px;right:64px;top:640px;height:820px;border-radius:28px;'
                'background:linear-gradient(160deg,#7b8a83,#4a5751)"></div>'
                '<div class="badge" id="b" style="top:900px">SHADOW</div>')
        add("节点属性", "ND%02d" % i, cn, "Node.%s：%s" % (pk, note), body, init + js)
        continue
    if pk == "anchor":
        body = '<div class="badge" id="b">ANCHOR</div>'
        add("节点属性", "ND%02d" % i, cn, "Node.%s：%s" % (pk, note), body, init + js)
        continue
    body = '<div class="badge" id="b">PROP</div>'
    add("节点属性", "ND%02d" % i, cn, "Node.%s：%s" % (pk, note), body, init + js)

# ==================================================================== LY 版面（10）

LY_CSS = """
.rowbox{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.16)}
.chip{font-size:40px;padding:28px 46px;background:rgba(134,240,192,.28);border-color:rgba(134,240,192,.5)}
"""
LAYOUTS = [
    ("padding", "内边距", "padding 44→96，内容被推进去",
     "tl.to('#box',{padding:'96px',duration:1.2,ease:'power2.inOut'},0.6);"),
    ("margin", "外边距", "margin 0→90，整块被推下去",
     "tl.to('#k1',{marginTop:'90px',duration:1.2,ease:'power2.inOut'},0.6);"),
    ("gap", "间距", "gap 16→90，子项散开",
     "tl.to('#box',{gap:'90px',duration:1.2,ease:'power2.inOut'},0.6);"),
    ("direction", "方向", "column → row：整块换轴重排",
     "tl.to('#box',{flexDirection:'row',duration:0.01},1.15);"
     "tl.fromTo('#k1,#k2,#k3',{scale:0.86,opacity:0.4},{scale:1,opacity:1,duration:0.6,stagger:0.1,ease:'power2.out'},1.15);"),
    ("alignItems", "交叉轴对齐", "flex-start → center → flex-end",
     "tl.to('#box',{alignItems:'center',duration:0.9,ease:'power2.inOut'},0.6);"
     "tl.to('#box',{alignItems:'flex-end',duration:0.9,ease:'power2.inOut'},1.5);"),
    ("justifyContent", "主轴分布", "space-between + 容器变窄，子项被挤到两头",
     "gsap.set('#box',{justifyContent:'space-between'});"
     "tl.to('#box',{width:'560px',duration:1.3,ease:'power2.inOut'},0.7);"),
    ("wrap", "换行", "容器变窄，子项自动换行",
     "gsap.set('#box',{flexWrap:'wrap'});"
     "tl.to('#box',{width:'520px',duration:1.3,ease:'power2.inOut'},0.7);"),
    ("grow", "权重", "flex-basis 20%→72%，乙撑开",
     "tl.to('#k2',{flexBasis:'72%',duration:1.3,ease:'power2.inOut'},0.7);"),
    ("ratio", "比例", "高度变，子项跟着重排",
     "tl.to('#box',{height:'560px',duration:1.3,ease:'power2.inOut'},0.7);"),
    ("offset", "偏移", "offset 叠在布局结果上，不参与排版",
     "tl.to('#k3',{x:150,y:-90,duration:1.2,ease:'power2.out'},0.7);"),
]
for i, (pk, cn, note, js) in enumerate(LAYOUTS, 1):
    body = """
  <div class="rowbox" id="box" style="display:flex;flex-direction:row;gap:16px;align-items:flex-start;
    justify-content:flex-start;width:952px;height:360px">
    <div class="chip" id="k1" style="flex:0 0 auto">甲</div>
    <div class="chip" id="k2" style="flex:0 0 auto">乙</div>
    <div class="chip" id="k3" style="flex:0 0 auto">丙</div>
  </div>
"""
    add("版面", "LY%02d" % i, cn, "Layout.%s：%s" % (pk, note), body,
        "gsap.set('#box',{opacity:1});\n" + js, css=LY_CSS)

# ==================================================================== FW 流程（7）

FLOWS = [
    ("all", "同时", "四个块同起同落", "tl.to('.blk',{y:-120,opacity:1,duration:1.0,ease:'power2.out',stagger:0},0.7);"),
    ("chain", "串行", "一个接一个，总时长翻四倍", "tl.to('#b1',{y:-120,duration:0.5},0.7);tl.to('#b2',{y:-120,duration:0.5},1.2);tl.to('#b3',{y:-120,duration:0.5},1.7);tl.to('#b4',{y:-120,duration:0.5},2.2);"),
    ("delay", "延迟", "同一动作，错开固定延迟", "tl.to('.blk',{y:-120,duration:0.6,ease:'power2.out',stagger:0.22},0.7);"),
    ("sequence", "序列", "按顺序排开，间隔相等", "tl.to('.blk',{y:-120,duration:0.5,ease:'power2.out',stagger:{each:0.15,from:'start'}},0.7);"),
    ("loop", "循环", "同一动作重复三次（有限次）", "tl.to('.blk',{y:-120,duration:0.4,ease:'power2.out'},0.7);tl.to('.blk',{y:0,duration:0.4,ease:'power2.in'},1.15);tl.to('.blk',{y:-120,duration:0.4,ease:'power2.out'},1.6);"),
    ("any", "任一完成", "谁先到谁就触发下一步", "tl.to('#b1',{y:-120,duration:0.4,ease:'power2.out'},0.7);tl.to('#b2',{y:-120,duration:0.7,ease:'power2.out'},0.7);tl.to('#b3',{y:-120,duration:1.0,ease:'power2.out'},0.7);tl.to('#b4',{y:-120,duration:1.3,ease:'power2.out'},0.7);tl.to('.blk',{scale:1.12,duration:0.3},1.15);tl.to('.blk',{scale:1,duration:0.3},1.45);"),
    ("every", "逐个", "逐个处理，每次等上一次完成", "tl.to('.blk',{y:-120,duration:0.35,ease:'power2.out',stagger:0.35},0.7);"),
]
for i, (pk, cn, note, js) in enumerate(FLOWS, 1):
    body = """
  <div style="position:absolute;left:64px;right:64px;top:900px;display:flex;gap:24px">
    <div class="blk" id="b1"></div><div class="blk" id="b2"></div>
    <div class="blk" id="b3"></div><div class="blk" id="b4"></div>
  </div>
"""
    add("流程", "FW%02d" % i, cn, "flow.%s：%s" % (pk, note), body,
        "gsap.set('.blk',{opacity:1});\n" + js,
        css=".blk{flex:1;height:220px;border-radius:20px;background:linear-gradient(160deg,#86F0C0,#2f6b55)}")

# ==================================================================== EX 模板与示例（18）

EX = [
    ("quickstart", "快速开始", "一个块从左上滑到中间", '<div class="badge" id="b">GO</div>',
     "gsap.set('#b',{x:-260,y:-300,opacity:1});\ntl.to('#b',{x:0,y:0,duration:1.3,ease:'power3.out'},0.6);"),
    ("positioning", "定位与原点", "按 origin 定位到右下角", '<div class="badge" id="b">ORIGIN</div>',
     "gsap.set('#b',{x:320,y:520,scale:0.5,transformOrigin:'0% 0%',opacity:1});\ntl.to('#b',{x:0,y:0,scale:1,transformOrigin:'50% 50%',duration:1.4,ease:'power3.out'},0.6);"),
    ("components", "组合组件", "圆 + 矩形 + 文本一起入场", '<div class="badge" id="b">▢ ● T</div>',
     "gsap.set('#b',{opacity:0,scale:0.8});\ntl.to('#b',{opacity:1,scale:1,duration:1.2,ease:'back.out(1.6)'},0.6);"),
    ("layout", "布局", "三个块按 flex 排开", """
  <div style="position:absolute;left:64px;right:64px;top:860px;display:flex;gap:26px">
    <div class="blk"></div><div class="blk"></div><div class="blk"></div></div>
""",
     "gsap.set('.blk',{opacity:1,scaleX:0.2,transformOrigin:'0% 50%'});\ntl.to('.blk',{scaleX:1,duration:1.0,ease:'power3.out',stagger:0.12},0.6);"),
    ("layout-group", "布局组", "组内再分组，两层排", """
  <div style="position:absolute;left:64px;right:64px;top:820px;display:flex;gap:20px">
    <div style="flex:1 1 auto;display:flex;flex-direction:column;gap:16px"><div class="blk" style="flex:0 0 200px;height:200px"></div><div class="blk" style="flex:0 0 200px;height:200px"></div></div>
    <div style="flex:1 1 auto;display:flex;flex-direction:column;gap:16px"><div class="blk" style="flex:0 0 200px;height:200px"></div><div class="blk" style="flex:0 0 200px;height:200px"></div></div>
  </div>
""",
     "gsap.set('.blk',{opacity:1,y:40});\ntl.to('.blk',{y:0,duration:0.8,ease:'power2.out',stagger:{each:0.1,grid:[2,2],from:'start'}},0.6);"),
    ("code-block", "代码块", "带高亮与行号的代码", """
  <div class="code" id="cd">
    <div class="ln"><i>1</i><span><span class="fn">import</span> search</span></div>
    <div class="ln"><i>2</i><span>leads = search.run(<span class="st">"五金 出口"</span>)</span></div>
  </div>
""",
     "gsap.set('#cd',{opacity:1});\nvar d={p:0};var el=document.getElementById('cd');\n"
     "tl.fromTo(el,{clipPath:'inset(0 100% 0 0)'},{clipPath:'inset(0 0% 0 0)',duration:1.2,ease:'none'},0.6);"),
    ("tex", "公式", "公式整体落位 + 缩放", """
  <div style="position:absolute;left:0;right:0;top:860px;text-align:center;font-family:Georgia,serif;font-size:88px" id="eq">
    E = mc²</div>
""",
     "gsap.set('#eq',{opacity:0,scale:0.9});\ntl.to('#eq',{opacity:1,scale:1,duration:1.1,ease:'power2.out'},0.6);"),
    ("transitions-first", "转场（第一屏）", "整屏推出，接下一屏", """
  <div class="layer" id="sa"><div class="a1"><div class="big">第一屏</div></div></div>
  <div class="layer" id="sb"><div class="full"></div></div>
""",
     "gsap.set('#sb',{x:1080});\ntl.to('#sa',{x:-1080,duration:0.7,ease:'power3.inOut'},1.1);\ntl.to('#sb',{x:0,duration:0.7,ease:'power3.inOut'},1.1);"),
    ("transitions-second", "转场（第二屏）", "第二屏淡入 + 轻推", """
  <div class="layer" id="sa"><div class="a1"><div class="big">第二屏</div></div></div>
  <div class="layer" id="sb"><div class="full"></div></div>
""",
     "gsap.set('#sb',{opacity:0,scale:1.04});\ntl.to('#sa',{opacity:0,duration:0.6},1.1);\ntl.to('#sb',{opacity:1,scale:1,duration:0.9,ease:'power2.out'},1.1);"),
    ("tweening-linear", "线性插值", "位置按线性推进（对照基准）", '<div class="badge" id="b">LINEAR</div>',
     "gsap.set('#b',{y:-360,opacity:1});\ntl.to('#b',{y:360,duration:1.6,ease:'none'},0.6);"),
    ("tweening-cubic", "三次缓动", "easeInOutCubic 对照线性", '<div class="badge" id="b">CUBIC</div>',
     "gsap.set('#b',{y:-360,opacity:1});\ntl.to('#b',{y:360,duration:1.6,ease:'power2.inOut'},0.6);"),
    ("tweening-spring", "弹簧插值", "spring(PlopSpring)", '<div class="badge" id="b">SPRING</div>',
     SPRING_JS + "var ease=springEase(SP.plop[0],SP.plop[1],SP.plop[2],SP.plop[3],1.5);\n"
     "gsap.set('#b',{y:-360,opacity:1});\ntl.to('#b',{y:360,duration:1.5,ease:ease},0.6);"),
    ("tweening-vector", "向量插值", "x 与 y 同时但不同速", '<div class="badge" id="b">VEC</div>',
     "gsap.set('#b',{x:-380,y:-320,opacity:1});\ntl.to('#b',{x:380,duration:1.5,ease:'power2.out'},0.6);\ntl.to('#b',{y:320,duration:1.9,ease:'power3.out'},0.6);"),
    ("tweening-color", "颜色插值", "填充色沿色环过渡", '<div class="badge" id="b">COLOR</div>',
     "gsap.set('#b',{background:'linear-gradient(150deg,#2f6b55,#101816)',opacity:1});\n"
     "tl.to('#b',{background:'linear-gradient(150deg,#E7C98A,#8a6a2f)',duration:1.5,ease:'power2.inOut'},0.6);"),
    ("tweening-save-restore", "存取状态", "存 → 改 → 复原", '<div class="badge" id="b">SAVE</div>',
     "gsap.set('#b',{opacity:1});\ntl.to('#b',{rotation:30,scale:0.6,duration:0.8,ease:'power2.out'},0.7);\ntl.to('#b',{rotation:0,scale:1,duration:0.9,ease:'power2.inOut'},1.6);"),
    ("tweening-visualiser", "曲线可视化", "画一条缓动曲线 + 一个点沿它走", """
  <svg class="stage2" viewBox="0 0 1080 1920" xmlns="http://www.w3.org/2000/svg">
    <rect x="140" y="700" width="800" height="560" fill="none" stroke="rgba(255,255,255,.14)"/>
    <path id="k" d="" fill="none" stroke="#86F0C0" stroke-width="4"/>
    <circle id="dot" cx="140" cy="1260" r="14" fill="#E7C98A"/>
  </svg>
""",
     "var d={p:0};function pp(){var x=140+d.p*800,y=1260-560*d.p;"
     "document.getElementById('dot').setAttribute('cx',x);document.getElementById('dot').setAttribute('cy',y);"
     "document.getElementById('k').setAttribute('d','M140,1260 C300,1260 320,700 940,700');}\n"
     "tl.to(d,{p:1,duration:1.8,ease:'none',onUpdate:pp},0.6);pp();"),
    ("presentation", "演示页", "标题 + 正文 + 页脚，逐层落位", """
  <div style="position:absolute;left:64px;right:64px;top:640px" id="pt">
    <div style="font-family:'SF Mono',Menlo,monospace;font-size:24px;letter-spacing:.2em;color:#86F0C0" class="pr">SLIDE 01</div>
    <div style="margin-top:30px;font-size:92px;font-weight:700;line-height:1.16;letter-spacing:-.03em" class="pr">一页讲一件事</div>
    <div style="margin-top:34px;font-size:32px;color:#A9B4AD;line-height:1.6" class="pr">副标题只补一句，不要抢主句。</div>
  </div>
""",
     "gsap.set('.pr',{opacity:0,y:26});\ntl.to('.pr',{opacity:1,y:0,duration:0.7,ease:'power2.out',stagger:0.18},0.6);"),
    ("switch", "开关", "开关从关到开，滑块跟底色同时走", """
  <div id="sw" style="position:absolute;left:50%;top:920px;margin-left:-110px;width:220px;height:110px;
    border-radius:999px;background:rgba(255,255,255,.12)">
    <div id="kn" style="position:absolute;left:10px;top:10px;width:90px;height:90px;border-radius:50%;
      background:#F4F1E9"></div>
  </div>
""",
     "tl.to('#kn',{x:100,duration:0.6,ease:'power2.inOut'},0.9);\n"
     "tl.to('#sw',{backgroundColor:'rgba(134,240,192,.55)',duration:0.6,ease:'power2.inOut'},0.9);"),
    ("rubiks-cube", "自绘立体方块", "正交投影 + 分层旋转（canvas 2D，不用三维库）", '<canvas class="cv" id="cv"></canvas>',
     """
var cv=document.getElementById('cv'),ctx=cv.getContext('2d');
cv.width=1080;cv.height=1920;
function paint(p){
  ctx.setTransform(1,0,0,1,0,0);ctx.clearRect(0,0,1080,1920);
  var S=240,cx=540,cy=960,a=p*Math.PI*0.6,b=0.5;
  function pr(x,y,z){
    var x1=x*Math.cos(a)-z*Math.sin(a), z1=x*Math.sin(a)+z*Math.cos(a);
    var y1=y*Math.cos(b)-z1*Math.sin(b), z2=y*Math.sin(b)+z1*Math.cos(b);
    var f=1400/(1400+z2);
    return [cx+x1*f,cy+y1*f,f];
  }
  var i,j,k,cs=[];
  for(i=-1;i<=1;i++)for(j=-1;j<=1;j++)for(k=-1;k<=1;k++)cs.push([i*S,j*S,k*S]);
  cs.sort(function(A,B){return pr(A[0],A[1],A[2])[2]-pr(B[0],B[1],B[2])[2];});
  for(i=0;i<cs.length;i++){
    var q=pr(cs[i][0],cs[i][1],cs[i][2]);
    ctx.beginPath();ctx.arc(q[0],q[1],44*q[2],0,Math.PI*2);
    ctx.fillStyle='rgba(134,240,192,'+(0.16+0.55*q[2]*0.6)+')';ctx.fill();
  }
}
var d={p:0};
tl.to(d,{p:1,duration:2.0,ease:'none',onUpdate:function(){paint(d.p);}},0.55);
paint(0);
"""),
]
for i, (k, cn, note, body, js) in enumerate(EX, 1):
    add("示例", "EX%02d" % i, cn, "packages/examples|template 的 %s" % k, body, js,
        css=".blk{flex:1;height:220px;border-radius:20px;background:linear-gradient(160deg,#86F0C0,#2f6b55)}"
            ".a1{background:#0d1211;display:flex;align-items:center;padding:0 84px}"
            ".a1 .big{font-size:96px;font-weight:700;line-height:1.16;letter-spacing:-.03em}")


# ---------------------------------------------------------------- 生成 / 渲染

def build() -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if not (SRC / "photo.png").exists():
        shutil.copy2(PHOTO, SRC / "photo.png")
    shutil.copy2(VENDOR / "gsap.min.js", SRC / "gsap.min.js")
    total = len(ITEMS)
    rows = []
    for it in ITEMS:
        d = SRC / it["no"]
        d.mkdir(exist_ok=True)
        html = SHELL.format(
            no=it["no"], name=it["name"], family=it["fam"], key=KEY + "-" + it["no"].lower(),
            dur=it["dur"], base_css=BASE_CSS + SWEEP_CSS, css=it["css"], body=it["body"],
            js=it["js"], total=total,
        )
        (d / "index.html").write_text(html, encoding="utf-8")
        (d / "hyperframes.json").write_text(json.dumps({
            "name": "rv-" + it["no"].lower(), "version": 1, "composition": "index.html",
            "width": 1080, "height": 1920, "fps": 30, "duration": it["dur"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        for f in ("photo.png", "gsap.min.js"):
            if not (d / f).exists():
                shutil.copy2(SRC / f, d / f)
        rows.append("\t".join([it["fam"], it["no"], it["name"], it["note"], str(d)]))
    (BATCH / "清单.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    fams = {}
    for it in ITEMS:
        fams[it["fam"]] = fams.get(it["fam"], 0) + 1
    print("✓ 工程 %d 个 → %s" % (total, SRC))
    for k, v in fams.items():
        print("   %-6s %3d" % (k, v))


def render_one(it):
    d = SRC / it["no"]
    out = OUT / ("%s-%s.mp4" % (it["no"], it["name"]))
    if out.exists():
        return "skip " + out.name
    env = {
        "HYPERFRAMES_BROWSER_PATH": CHROME,
        "HYPERFRAMES_CACHE_DIR": str(d / ".hyperframes" / "cache"),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
    }
    cmd = [NODE, str(HF), "render", ".", "-w", "1", "-f", "30", "-q", "looks",
           "--no-browser-gpu", "--experimental-fast-capture=false", "-o", str(out)]
    r = subprocess.run(cmd, cwd=str(d), env=env, capture_output=True, text=True)
    shutil.rmtree(d / ".hyperframes", ignore_errors=True)
    if r.returncode != 0 or not out.exists():
        return "FAIL %s %s" % (it["no"], (r.stderr or r.stdout)[-400:])
    return "✓ " + out.name


def render() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(render_one, ITEMS):
            print(msg, flush=True)
            if msg.startswith("✓"):
                ok += 1
    print("完成 %d / %d" % (ok, len(ITEMS)))


def sheet() -> None:
    fams = {}
    for it in ITEMS:
        fams.setdefault(it["fam"], []).append(it)
    for fam, items in fams.items():
        files = [OUT / ("%s-%s.mp4" % (i["no"], i["name"])) for i in items]
        files = [f for f in files if f.exists()]
        if not files:
            continue
        cols = 6 if len(files) > 12 else 4
        n = len(files)
        args = ["ffmpeg", "-y"]
        for f in files:
            args += ["-ss", "1.9", "-t", "0.1", "-i", str(f)]
        filt = "".join("[%d:v]scale=180:320,drawbox=x=0:y=0:w=iw:h=ih:color=0x222222@1:t=1[v%d];" % (i, i) for i in range(n))
        filt += "".join("[v%d]" % i for i in range(n))
        lay = "|".join("%d_%d" % ((i % cols) * 180, (i // cols) * 320) for i in range(n))
        filt += "xstack=inputs=%d:layout=%s:fill=0x0a0b0b[out]" % (n, lay)
        args += ["-filter_complex", filt, "-map", "[out]", "-frames:v", "1",
                 str(BATCH / ("联系表-%s.jpg" % fam))]
        r = subprocess.run(args, capture_output=True, text=True)
        print(("✓ " if r.returncode == 0 else "FAIL ") + "联系表-%s.jpg (%d)" % (fam, n))
        if r.returncode != 0:
            print(r.stderr[-600:])


def inventory() -> None:
    """从仓库现抽清单：证明覆盖面（不改任何文件）。"""
    if not REPO.exists():
        print("仓库不存在：%s" % REPO)
        return
    tf = REPO / "packages/core/src/tweening/timingFunctions.ts"
    sp = REPO / "packages/core/src/tweening/spring.ts"
    fl = REPO / "packages/2d/src/lib/partials/Filter.ts"
    comps = REPO / "packages/2d/src/lib/components"
    eas = re.findall(r"^export function (?:create)?(?:ease)?([A-Za-z]+)", tf.read_text(encoding="utf-8"), re.M)
    springs = re.findall(r"^export const ([A-Za-z]+Spring)", sp.read_text(encoding="utf-8"), re.M)
    filters = re.findall(r"^  (\w+): \{", fl.read_text(encoding="utf-8"), re.M)
    comp = sorted(p.stem for p in comps.glob("*.ts") if p.stem not in ("index", "types", "Txt.test"))
    print("缓动函数      %2d" % len(set(eas)))
    print("弹簧预置      %2d  %s" % (len(springs), " ".join(springs)))
    print("滤镜          %2d  %s" % (len(filters), " ".join(filters)))
    print("2d 组件       %2d" % len(comp))
    print("合成运算      26  (MDN globalCompositeOperation 全量)")
    print("本批出片      %3d" % len(ITEMS))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("build", "all"):
        build()
    if cmd in ("render", "all"):
        render()
    if cmd in ("sheet", "all"):
        sheet()
    if cmd == "inventory":
        inventory()


if __name__ == "__main__":
    main()
