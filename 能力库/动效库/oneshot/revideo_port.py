#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""revideo（MIT，Motion Canvas 分支）候选样片生成器。

外部仓库：~/Downloads/revideo-main（TypeScript 场景图引擎，canvas 2D 渲染）。
我们不搬引擎，只搬**能落到 HTML+GSAP+canvas 上的机制**，每张一个 3 秒 1080×1920 确认片。

用法：
    python3 能力库/动效库/revideo_port.py build        # 生成 16 个工程 + 清单.tsv
    python3 能力库/动效库/revideo_port.py render       # 并行 4 渲染（约 1 分钟）
    python3 能力库/动效库/revideo_port.py sheet        # 出一张联系表 jpg
    python3 能力库/动效库/revideo_port.py all

产物：
    能力库/动效库/样片/待筛/revideo/<RVnn>/index.html   工程（可单独重渲）
    能力库/动效库/样片/待筛/revideo/out/<RVnn>-<名字>.mp4
    能力库/动效库/样片/待筛/revideo/清单.tsv
    能力库/动效库/样片/待筛/revideo/revideo候选-联系表.jpg

候选号用 RV 前缀，**不占正式编号**；用户点头后才走「一批卡入表：全链 14 处」。
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
VENDOR = WORK / "成品" / "workflow_runtime" / "assets" / "vendor"
PHOTO = HERE / "assets" / "demo" / "photo.png"
BATCH = HERE / "样片" / "待筛" / "revideo"
SRC = BATCH / "src"
OUT = BATCH / "out"
HF = WORK / "成品" / "workflow_runtime" / "vendor" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
NODE = "/Users/jinfeiqing/.nvm/versions/node/v22.23.3/bin/node"

DUR = 3.0
KEY = "rv"

BASE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000;font-family:"PingFang SC","Helvetica Neue",sans-serif;-webkit-font-smoothing:antialiased}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:#0a0b0b;color:#F4F1E9}
.layer{position:absolute;inset:0;overflow:hidden}
.hdr{position:absolute;left:64px;top:74px;z-index:60;display:flex;align-items:baseline;gap:20px}
.hdr .id{font-family:"SF Mono",Menlo,monospace;font-size:30px;letter-spacing:.16em;color:#86F0C0}
.hdr .nm{font-size:40px;font-weight:640;letter-spacing:-.01em}
.hdr .fm{font-family:"SF Mono",Menlo,monospace;font-size:22px;color:#7e8a84;letter-spacing:.14em}
.ftr{position:absolute;right:64px;bottom:70px;z-index:60;font-family:"SF Mono",Menlo,monospace;
  font-size:24px;letter-spacing:.12em;color:rgba(244,241,233,.32)}
.mono{font-family:"SF Mono",Menlo,monospace}
.shot{position:absolute;left:64px;right:64px;top:420px;height:820px;border-radius:22px;overflow:hidden;
  background-image:url("./photo.png");background-size:cover;background-position:52% 40%;
  border:1px solid rgba(255,255,255,.09)}
.full{position:absolute;inset:0;background-image:url("./photo.png");background-size:cover;
  background-position:50% 46%}
.panel{position:absolute;left:64px;right:64px;top:520px;border-radius:24px;padding:56px;
  background:rgba(255,255,255,.045);border:1px solid rgba(255,255,255,.09)}
.panel .k{font-family:"SF Mono",Menlo,monospace;font-size:22px;letter-spacing:.2em;color:#86F0C0}
.panel .h{margin-top:26px;font-size:74px;line-height:1.2;font-weight:680;letter-spacing:-.02em}
.panel .s{margin-top:22px;font-size:30px;line-height:1.5;color:#A9B4AD}
.guide{position:absolute;left:0;right:0;height:0;border-top:1px dashed rgba(134,240,192,.45);z-index:30}
.guide span{position:absolute;right:64px;top:-34px;font-family:"SF Mono",Menlo,monospace;font-size:20px;
  letter-spacing:.14em;color:rgba(134,240,192,.7)}
"""

SHELL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{no} · {name}</title>
<style>{base_css}{css}</style></head><body>
<div id="stage" data-composition-id="{key}" data-duration="{dur}">
{body}
  <div class="hdr"><span class="id">{no}</span><span class="nm">{name}</span><span class="fm">{family}·候选</span></div>
  <div class="ftr">{no} / 共 {total}</div>
</div>
<script src="./gsap.min.js"></script>
<script>
(function(){{
"use strict";
var tl = gsap.timeline({{paused:true}});
window.__timelines = window.__timelines || {{}};
window.__timelines['{key}'] = tl;
window.addEventListener('hf-seek', function(e){{ tl.time(e.detail.time); }});
var AT = 0.0;
{js}
}})();
</script></body></html>
"""

# ---------------------------------------------------------------- 共用 JS 片段

SPRING_JS = """
// ---- 弹簧曲线：直接照搬 revideo core/tweening/spring.ts 的显式积分 ----
// F = -k*(x-1) - d*v ；v += F/m*h ；x += v*h。固定步长，无随机，逐帧可复现。
function springTable(mass, stiffness, damping, v0, tEnd, N) {
  var h = 1 / 600, x = 0, v = v0 || 0, t = 0, out = [0], step = tEnd / (N - 1), next = step;
  while (t < tEnd + h) {
    var a = (-stiffness * (x - 1) - damping * v) / mass;
    v += a * h;
    x += v * h;
    t += h;
    while (t >= next && out.length < N) { out.push(x); next += step; }
  }
  while (out.length < N) out.push(1);
  return out;
}
function springEase(mass, stiffness, damping, v0, tEnd) {
  var tbl = springTable(mass, stiffness, damping, v0, tEnd, 300);
  return function (p) {
    var i = Math.round(Math.max(0, Math.min(1, p)) * (tbl.length - 1));
    return tbl[i];
  };
}
// revideo 自带的六个预置
var SP = {
  plop:   [0.20, 20.00, 0.68, 0.0],
  bounce: [0.08,  4.75, 0.05, 0.0],
  swing:  [0.39, 19.85, 2.82, 0.0],
  smooth: [0.16, 15.35, 1.88, 0.0],
  beat:   [0.13,  5.70, 1.20, 10.0],
  jump:   [0.04, 10.00, 0.70, 8.0],
  strike: [0.03, 20.00, 0.90, 4.8]
};
"""


def card(key, no, name, family, why, css, body, js):
    return dict(key=key, no=no, name=name, family=family, why=why, css=css, body=body, js=js)


CARDS = []

# ============================================================ 族一：弹簧（core/spring.ts）

CARDS.append(card(
    "RV01", "RV01", "弹簧落位", "入场",
    "revideo 的 spring 是显式积分，不是缓动表；Plop 预置落定干净、带一次极轻回弹",
    """
.panel{top:600px}
.panel .h{font-size:88px}
""",
    """
  <div class="panel" id="card">
    <div class="k">SPRING · PLOP</div>
    <div class="h">落位不用缓动</div>
    <div class="s">位移 + 缩放同一条曲线，落定前只有一次极轻回弹。</div>
  </div>
""",
    SPRING_JS + """
var ease = springEase(SP.plop[0], SP.plop[1], SP.plop[2], SP.plop[3], 1.5);
gsap.set('#card', {opacity: 1, y: 150, scale: 0.88, transformOrigin: '50% 60%'});
tl.to('#card', {y: 0, scale: 1, duration: 1.5, ease: ease}, 0.55);
""",
))

CARDS.append(card(
    "RV02", "RV02", "长摆回弹", "入场",
    "同一套积分换成 damping=0.05 的 Bounce 预置：来回摆五六次才停，且幅度真的衰减",
    """
.panel{top:600px}
.panel .h{font-size:88px}
""",
    """
  <div class="guide" id="g"><span>TARGET</span></div>
  <div class="panel" id="card">
    <div class="k">SPRING · BOUNCE</div>
    <div class="h">回弹要衰减</div>
    <div class="s">阻尼 0.05：来回五六次，每次都小一点，最后停住。</div>
  </div>
""",
    SPRING_JS + """
document.getElementById('g').style.top = (600 + 0) + 'px';
var ease = springEase(SP.bounce[0], SP.bounce[1], SP.bounce[2], SP.bounce[3], 2.35);
gsap.set('#card', {opacity: 1, y: 320, scale: 1, transformOrigin: '50% 50%'});
tl.to('#card', {y: 0, duration: 2.35, ease: ease}, 0.5);
""",
))

CARDS.append(card(
    "RV03", "RV03", "摇摆归位", "入场",
    "Swing 预置（k=19.85 / d=2.82）拿来转角度：角标、图标、印章这类小元素归位用",
    """
.badge{position:absolute;left:50%;top:760px;width:300px;height:300px;margin-left:-150px;border-radius:72px;
  background:linear-gradient(150deg,#86F0C0,#2f6b55);display:flex;align-items:center;justify-content:center;
  font-family:"SF Mono",Menlo,monospace;font-size:96px;font-weight:700;color:#08120e;letter-spacing:.06em;
  box-shadow:0 40px 90px rgba(0,0,0,.55)}
.badge:after{content:"";position:absolute;inset:16px;border-radius:56px;border:2px dashed rgba(8,18,14,.35)}
""",
    """
  <div class="badge" id="bd">A+</div>
""",
    SPRING_JS + """
var ease = springEase(SP.swing[0], SP.swing[1], SP.swing[2], SP.swing[3], 1.7);
gsap.set('#bd', {opacity: 1, rotation: -22, scale: 0.82, transformOrigin: '50% 50%'});
tl.to('#bd', {rotation: 0, scale: 1, duration: 1.7, ease: ease}, 0.55);
""",
))

# ============================================================ 族二：场景转场（core/transitions）

CARDS.append(card(
    "RV04", "RV04", "推挤换屏", "结构",
    "slideTransition：前屏被整块推出、新屏同时滑入，硬边切割；DOM 变换即可，不用 WebGL",
    """
.a,.b{position:absolute;inset:0}
.a .cap{position:absolute;left:64px;right:64px;bottom:150px;font-size:60px;font-weight:680;line-height:1.24;
  letter-spacing:-.02em;text-shadow:0 4px 30px rgba(0,0,0,.8)}
.b{background:#0e1413;display:flex;align-items:center;padding:0 90px}
.b .big{font-size:112px;font-weight:700;line-height:1.14;letter-spacing:-.03em}
.b .big em{font-style:normal;color:#86F0C0}
.b .sm{margin-top:44px;font-size:30px;color:#A9B4AD;line-height:1.6}
""",
    """
  <div class="layer a" id="sa">
    <div class="full"></div>
    <div class="cap">这一屏整块推走<br>新屏跟着挤进来</div>
  </div>
  <div class="layer b" id="sb">
    <div>
      <div class="big">不是淡入<br>是<em>推挤</em></div>
      <div class="sm">两屏同时在动，边是硬的；<br>一屏 0.6 秒，节奏比淡入干脆。</div>
    </div>
  </div>
""",
    """
gsap.set('#sb', {x: 1080});
tl.to('#sa', {x: -1080, duration: 0.72, ease: 'power3.inOut'}, 1.05);
tl.to('#sb', {x: 0, duration: 0.72, ease: 'power3.inOut'}, 1.05);
""",
))

CARDS.append(card(
    "RV05", "RV05", "区域聚焦进入", "结构",
    "zoomInTransition：新屏从画面上某一块矩形长到满屏，旧屏淡出——从「一个格子」推进到「这一格」",
    """
.grid{position:absolute;left:64px;right:64px;top:420px;height:820px;display:grid;
  grid-template-columns:1fr 1fr;grid-template-rows:1fr 1fr;gap:14px}
.t{position:relative;border-radius:16px;overflow:hidden;background-image:url("./photo.png");
  background-size:200% 200%;border:1px solid rgba(255,255,255,.08)}
.t1{background-position:0% 0%}.t2{background-position:100% 0%}
.t3{background-position:0% 100%}.t4{background-position:100% 100%}
.t2:after{content:"";position:absolute;inset:0;border:4px solid #86F0C0;border-radius:16px}
.b{position:absolute;inset:0;background:#0d1211;display:flex;align-items:flex-end;padding:0 90px 260px}
.b .big{font-size:96px;font-weight:700;line-height:1.16;letter-spacing:-.03em}
.b .big em{font-style:normal;color:#86F0C0}
""",
    """
  <div class="layer a" id="sa">
    <div class="grid"><div class="t t1"></div><div class="t t2"></div><div class="t t3"></div><div class="t t4"></div></div>
  </div>
  <div class="layer b" id="sb">
    <div class="big">从<em>一格</em><br>推进到这一格</div>
  </div>
""",
    """
// 目标格 = 第 2 格（右上）：中心 (778,625)，满屏中心 (540,960)
var dx = 778 - 540, dy = 625 - 960, s0 = 0.44;
gsap.set('#sb', {x: dx, y: dy, scale: s0, transformOrigin: '50% 50%', opacity: 0});
tl.to('#sb', {opacity: 1, duration: 0.2, ease: 'none'}, 1.0);
tl.to('#sa', {opacity: 0, duration: 0.45, ease: 'power1.in'}, 1.0);
tl.to('#sb', {x: 0, y: 0, scale: 1, duration: 0.95, ease: 'power3.inOut'}, 1.0);
""",
))

CARDS.append(card(
    "RV06", "RV06", "拉远离场", "结构",
    "zoomOutTransition：新屏从过近的 1.6 倍拉回正常，旧屏同时缩进画面中心并消失",
    """
.a{background:#0d1211;display:flex;align-items:center;padding:0 90px}
.a .big{font-size:104px;font-weight:700;line-height:1.16;letter-spacing:-.03em}
.a .big em{font-style:normal;color:#86F0C0}
.b .cap{position:absolute;left:64px;right:64px;bottom:150px;font-size:56px;font-weight:660;
  line-height:1.28;letter-spacing:-.02em;text-shadow:0 4px 30px rgba(0,0,0,.85)}
""",
    """
  <div class="layer b" id="sb">
    <div class="full"></div>
    <div class="cap">镜头往后退<br>这一屏才装得下</div>
  </div>
  <div class="layer a" id="sa">
    <div class="big">先看清<em>一个字</em><br>再退到全景</div>
  </div>
""",
    """
gsap.set('#sb', {scale: 1.62, transformOrigin: '50% 46%', opacity: 0});
gsap.set('#sa', {scale: 1, transformOrigin: '50% 46%', opacity: 1});
tl.to('#sb', {opacity: 1, duration: 0.3, ease: 'none'}, 1.0);
tl.to('#sb', {scale: 1, duration: 1.15, ease: 'power2.out'}, 1.0);
tl.to('#sa', {scale: 0.66, opacity: 0, duration: 1.0, ease: 'power2.in'}, 1.0);
""",
))

# ============================================================ 族三：CSS 滤镜调色（Filter.ts）

CARDS.append(card(
    "RV07", "RV07", "去色聚焦", "材质",
    "filters 数组里 grayscale + saturate 同一条时间线：整幅先灰掉，再让主体恢复颜色",
    """
.shot{filter:grayscale(1) saturate(1)}
.cap{position:absolute;left:64px;right:64px;top:1330px;font-size:58px;font-weight:660;line-height:1.3;
  letter-spacing:-.02em}
.cap em{font-style:normal;color:#86F0C0}
""",
    """
  <div class="shot" id="ph"></div>
  <div class="cap" id="cap">先抽掉颜色，<br>再只把<em>主体</em>还回来</div>
""",
    """
var drv = {g: 1, s: 1};
gsap.set('#ph', {opacity: 1});
gsap.set('#cap', {opacity: 0, y: 26});
function paint(){ document.getElementById('ph').style.filter = 'grayscale(' + drv.g + ') saturate(' + drv.s + ')'; }
tl.to(drv, {g: 1, s: 1, duration: 0.6, ease: 'none', onUpdate: paint}, 0.55);
tl.to(drv, {g: 0.08, s: 1.12, duration: 1.1, ease: 'power2.out', onUpdate: paint}, 0.75);
tl.to('#cap', {opacity: 1, y: 0, duration: 0.6, ease: 'power2.out'}, 1.35);
""",
))

CARDS.append(card(
  "RV08", "RV08", "色相漂移", "材质",
  "hue-rotate 从 0 扫到 300 度：照片整幅换色而不改亮度，适合同一个镜头做「时间/版本变了」",
  """
.shot{filter:hue-rotate(0deg)}
.cap{position:absolute;left:64px;right:64px;top:1330px;display:flex;align-items:baseline;gap:24px}
.cap .t{font-size:58px;font-weight:660;letter-spacing:-.02em}
.cap .n{font-family:"SF Mono",Menlo,monospace;font-size:30px;color:#86F0C0;letter-spacing:.1em}
""",
  """
  <div class="shot" id="ph"></div>
  <div class="cap"><span class="t" id="cap">整幅换色，亮度不变</span><span class="n" id="num">0°</span></div>
""",
  """
var drv = {h: 0};
gsap.set('#ph', {opacity: 1});
function paint(){
  document.getElementById('ph').style.filter = 'hue-rotate(' + drv.h + 'deg)';
  document.getElementById('num').textContent = Math.round(drv.h) + '°';
}
tl.to(drv, {h: 300, duration: 2.0, ease: 'power1.inOut', onUpdate: paint}, 0.7);
tl.to('#cap', {opacity: 1, duration: 0.4}, 0.9);
gsap.set('#cap', {opacity: 0});
""",
))

CARDS.append(card(
    "RV09", "RV09", "反相闪现", "材质",
    "invert 一次性冲到底再回来，压 0.18 秒：强调、故障、章节切点都用它，比闪白柔和",
    """
.shot{filter:invert(0)}
.flash{position:absolute;inset:0;background:#fff;opacity:0;mix-blend-mode:normal}
.cap{position:absolute;left:64px;right:64px;top:1330px;font-size:58px;font-weight:660;line-height:1.3;
  letter-spacing:-.02em}
""",
    """
  <div class="shot" id="ph"></div>
  <div class="flash" id="fl"></div>
  <div class="cap" id="cap">一次反相<br>比闪白更像「信号断了」</div>
""",
    """
var drv = {v: 0};
gsap.set('#ph', {opacity: 1});
gsap.set('#cap', {opacity: 0});
function paint(){ document.getElementById('ph').style.filter = 'invert(' + drv.v + ')'; }
tl.to(drv, {v: 1, duration: 0.09, ease: 'power2.in', onUpdate: paint}, 1.05);
tl.to(drv, {v: 0, duration: 0.22, ease: 'power2.out', onUpdate: paint}, 1.16);
tl.to('#fl', {opacity: 0.16, duration: 0.09, ease: 'none'}, 1.05);
tl.to('#fl', {opacity: 0, duration: 0.22, ease: 'power2.out'}, 1.16);
tl.to('#cap', {opacity: 1, duration: 0.45}, 1.45);
""",
))

CARDS.append(card(
    "RV10", "RV10", "棕褐老化", "材质",
    "sepia + contrast + brightness 三个一起推：老照片/回忆/资料感，一次到位",
    """
.shot{filter:sepia(0) contrast(1) brightness(1)}
.cap{position:absolute;left:64px;right:64px;top:1330px;font-size:58px;font-weight:660;line-height:1.3;
  letter-spacing:-.02em}
.cap em{font-style:normal;color:#E7C98A}
""",
    """
  <div class="shot" id="ph"></div>
  <div class="cap" id="cap">颜色收旧，对比压住<br>画面就<em>退到十年前</em></div>
""",
    """
var drv = {se: 0, c: 1, b: 1};
gsap.set('#ph', {opacity: 1});
gsap.set('#cap', {opacity: 0, y: 20});
function paint(){
  document.getElementById('ph').style.filter =
    'sepia(' + drv.se + ') contrast(' + drv.c + ') brightness(' + drv.b + ')';
}
tl.to(drv, {se: 0.72, c: 1.12, b: 1.04, duration: 1.3, ease: 'power2.inOut', onUpdate: paint}, 0.7);
tl.to('#cap', {opacity: 1, y: 0, duration: 0.55, ease: 'power2.out'}, 1.35);
""",
))

# ============================================================ 族四：合成遮罩（composite / clip）

CARDS.append(card(
    "RV11", "RV11", "文字镂空照片", "结构",
    "把照片当字色（background-clip:text），字本身就是取景框；照片在字里平移，字不动",
    """
.wrap{position:absolute;left:0;right:0;top:560px;height:800px;display:flex;align-items:center;
  justify-content:center;overflow:hidden}
.masked{font-family:"Helvetica Neue",Arial,sans-serif;font-size:250px;font-weight:800;letter-spacing:-.04em;
  line-height:1;white-space:nowrap;
  background-image:url("./photo.png");background-size:1200px auto;background-position:0% 46%;
  -webkit-background-clip:text;background-clip:text;color:transparent}
.sub{position:absolute;left:64px;right:64px;top:1420px;font-size:34px;color:#A9B4AD;line-height:1.55}
""",
    """
  <div class="wrap"><div class="masked" id="mk">LEADS</div></div>
  <div class="sub" id="sub">字是取景框：照片在字里横移，<br>字本身一点不动。</div>
""",
    """
gsap.set('#mk', {opacity: 1, backgroundPosition: '-260px 46%'});
gsap.set('#sub', {opacity: 0});
tl.to('#mk', {backgroundPosition: '340px 46%', duration: 1.9, ease: 'power1.inOut'}, 0.6);
tl.to('#sub', {opacity: 1, duration: 0.6}, 1.5);
""",
))

CARDS.append(card(
    "RV12", "RV12", "形状镂空照片", "结构",
    "照 revideo 的 stencil 做法：canvas 先画网格线，再 source-in 盖照片 —— 照片只在旋转的线里可见",
    """
canvas.cv{position:absolute;left:64px;top:420px;width:952px;height:820px;display:block;border-radius:22px}
.cap{position:absolute;left:64px;right:64px;top:1330px;font-size:58px;font-weight:660;line-height:1.3;
  letter-spacing:-.02em}
.cap em{font-style:normal;color:#86F0C0}
""",
    """
  <canvas class="cv" id="cv"></canvas>
  <div class="cap" id="cap">照片只在<em>转起来的线</em>里出现</div>
""",
    """
var cv = document.getElementById('cv'), ctx = cv.getContext('2d');
cv.width = 952; cv.height = 820;
var img = new Image(); img.src = './photo.png';
var last = 0;
function paint(p) {
  last = p;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, cv.width, cv.height);
  // 1) stencil：网格线
  ctx.save();
  ctx.translate(cv.width / 2, cv.height / 2);
  ctx.rotate(-0.5 + p * 0.9);
  ctx.strokeStyle = '#fff';
  ctx.lineWidth = 7;
  ctx.beginPath();
  var i;
  for (i = -14; i <= 14; i++) {
    ctx.moveTo(i * 62, -900); ctx.lineTo(i * 62, 900);
    ctx.moveTo(-900, i * 62); ctx.lineTo(900, i * 62);
  }
  ctx.stroke();
  ctx.restore();
  // 2) 照片 source-in：只留在画过的线里
  if (img.complete && img.naturalWidth) {
    ctx.globalCompositeOperation = 'source-in';
    var s = Math.max(cv.width / img.naturalWidth, cv.height / img.naturalHeight) * 1.12;
    var w = img.naturalWidth * s, h = img.naturalHeight * s;
    ctx.drawImage(img, (cv.width - w) / 2 - 40 + p * 80, (cv.height - h) / 2, w, h);
    ctx.globalCompositeOperation = 'source-over';
  }
}
img.onload = function () { paint(last); };
var drv = {p: 0};
tl.to(drv, {p: 1, duration: 2.1, ease: 'none', onUpdate: function () { paint(drv.p); }}, 0.55);
tl.to('#cap', {opacity: 1, duration: 0.5}, 0.8);
gsap.set('#cap', {opacity: 0});
paint(0);
""",
))

# ============================================================ 族五：代码（Code / CodeBlock）

CARDS.append(card(
    "RV13", "RV13", "代码行级 diff", "UI",
    "CodeDiffer 的语义：不是整段重打，是「这一行换掉了」——旧行划掉压暗，新行就地长出来",
    """
.code{position:absolute;left:64px;right:64px;top:520px;border-radius:22px;padding:48px 44px;
  background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.08);
  font-family:"SF Mono",Menlo,monospace;font-size:30px;line-height:1.9;color:#C9D3CC}
.ln{position:relative;display:flex;gap:28px;white-space:pre}
.ln i{font-style:normal;color:rgba(244,241,233,.28);width:34px;text-align:right;flex:none}
.ln .tx{position:relative}
.ln .tx .fn{color:#86F0C0}
.ln .tx .st{color:#E7C98A}
.ln.old .tx{text-decoration:line-through;text-decoration-color:rgba(226,84,58,.85)}
.ln.new{overflow:hidden}
.bar{position:absolute;left:0;top:0;bottom:0;width:4px;border-radius:2px}
""",
    """
  <div class="code" id="code">
    <div class="ln"><i>1</i><span class="tx"><span class="fn">def</span> run(q):</span></div>
    <div class="ln old" id="old"><i>2</i><span class="tx">    leads = search.run(q)</span><span class="bar" style="background:rgba(226,84,58,.75)"></span></div>
    <div class="ln new" id="new"><i>3</i><span class="tx">    leads = search.<span class="fn">run</span>(q).<span class="st">enrich</span>()</span><span class="bar" style="background:rgba(134,240,192,.85)"></span></div>
    <div class="ln"><i>4</i><span class="tx">    <span class="fn">return</span> leads</span></div>
  </div>
""",
    """
gsap.set('#code', {opacity: 0, y: 18});
gsap.set('#old', {opacity: 1});
gsap.set('#new', {opacity: 0, height: 0});
gsap.set('#code .bar', {opacity: 0, scaleY: 0, transformOrigin: '50% 0%'});
tl.to('#code', {opacity: 1, y: 0, duration: 0.4, ease: 'power2.out'}, 0.55);
tl.to('#old', {opacity: 0.32, duration: 0.35, ease: 'none'}, 1.15);
tl.to('#old .bar', {opacity: 1, scaleY: 1, duration: 0.3, ease: 'power2.out'}, 1.15);
tl.to('#new', {opacity: 1, height: 57, duration: 0.42, ease: 'power2.out'}, 1.5);
tl.to('#new .bar', {opacity: 1, scaleY: 1, duration: 0.3, ease: 'power2.out'}, 1.55);
tl.fromTo('#new .tx', {clipPath: 'inset(0 100% 0 0)'}, {clipPath: 'inset(0 0% 0 0)', duration: 0.7, ease: 'none'}, 1.62);
""",
))

CARDS.append(card(
    "RV14", "RV14", "代码选区扫", "UI",
    "selection(range)：底色块按字符范围从左铺到右，扫完停在原地；讲一段代码指哪打哪",
    """
.code{position:absolute;left:64px;right:64px;top:520px;border-radius:22px;padding:48px 44px;
  background:rgba(255,255,255,.035);border:1px solid rgba(255,255,255,.08);
  font-family:"SF Mono",Menlo,monospace;font-size:30px;line-height:1.9;color:#C9D3CC}
.ln{display:flex;gap:28px;white-space:pre}
.ln i{font-style:normal;color:rgba(244,241,233,.28);width:34px;text-align:right;flex:none}
.ln .tx .fn{color:#86F0C0}
.ln .tx .st{color:#E7C98A}
.sel{background-image:linear-gradient(rgba(134,240,192,.24),rgba(134,240,192,.24));
  background-repeat:no-repeat;background-size:0% 100%;border-radius:4px}
.sel2{background-image:linear-gradient(rgba(231,201,138,.22),rgba(231,201,138,.22));
  background-repeat:no-repeat;background-size:0% 100%;border-radius:4px}
""",
    """
  <div class="code" id="code">
    <div class="ln"><i>1</i><span class="tx"><span class="fn">def</span> <span class="sel2" id="s2">run</span>(q):</span></div>
    <div class="ln"><i>2</i><span class="tx">    leads = search.<span class="sel" id="s1">run(q).enrich()</span></span></div>
    <div class="ln"><i>3</i><span class="tx">    <span class="fn">return</span> leads</span></div>
  </div>
""",
    """
gsap.set('#code', {opacity: 0, y: 18});
tl.to('#code', {opacity: 1, y: 0, duration: 0.4, ease: 'power2.out'}, 0.55);
var d1 = {w: 0}, d2 = {w: 0};
function p1(){ document.getElementById('s1').style.backgroundSize = d1.w * 100 + '% 100%'; }
function p2(){ document.getElementById('s2').style.backgroundSize = d2.w * 100 + '% 100%'; }
tl.to(d1, {w: 1, duration: 0.55, ease: 'power2.inOut', onUpdate: p1}, 1.05);
tl.to(d2, {w: 1, duration: 0.45, ease: 'power2.inOut', onUpdate: p2}, 1.85);
""",
))

# ============================================================ 族六：其余（Grid / 投影）

CARDS.append(card(
    "RV15", "RV15", "网格铺开", "背景",
    "Grid 的 start/end：线从中间往两头长，横竖错开 30ms —— 比整张网格淡入有方向感",
    """
.gw{position:absolute;left:0;right:0;top:0;bottom:0;overflow:hidden}
.gl{position:absolute;background:rgba(134,240,192,.20);transform-origin:50% 50%}
.gl.v{width:1px;top:0;bottom:0}
.gl.h{height:1px;left:0;right:0}
.ttl{position:absolute;left:0;right:0;top:820px;text-align:center;font-size:76px;font-weight:700;
  letter-spacing:-.03em;line-height:1.2}
.ttl em{font-style:normal;color:#86F0C0}
""",
    """
  <div class="gw" id="gw"></div>
  <div class="ttl" id="ttl">先有<em>格</em>，<br>再有内容</div>
""",
    """
(function () {
  var gw = document.getElementById('gw'), i, n;
  for (i = 0; i <= 12; i++) {
    var d = document.createElement('div');
    d.className = 'gl v';
    d.style.left = (i * 90) + 'px';
    gw.appendChild(d);
  }
  for (i = 0; i <= 20; i++) {
    var e = document.createElement('div');
    e.className = 'gl h';
    e.style.top = (i * 96) + 'px';
    gw.appendChild(e);
  }
  gsap.set('.gl.v', {scaleY: 0});
  gsap.set('.gl.h', {scaleX: 0});
  gsap.set('#ttl', {opacity: 0, y: 24});
  tl.to('.gl.h', {scaleX: 1, duration: 0.75, ease: 'power3.out', stagger: {each: 0.035, from: 'center'}}, 0.5);
  tl.to('.gl.v', {scaleY: 1, duration: 0.75, ease: 'power3.out', stagger: {each: 0.035, from: 'center'}}, 0.62);
  tl.to('#ttl', {opacity: 1, y: 0, duration: 0.6, ease: 'power2.out'}, 1.35);
})();
""",
))

CARDS.append(card(
    "RV16", "RV16", "抬升投影", "材质",
    "Node 的 shadowColor/Blur/Offset 一起动：元素抬起时影子变远变虚，落地时收紧——只靠影子表达高度",
    """
.card{position:absolute;left:120px;right:120px;top:820px;border-radius:28px;padding:56px;
  background:linear-gradient(160deg,#18211f,#0d1211);border:1px solid rgba(255,255,255,.10)}
.card .k{font-family:"SF Mono",Menlo,monospace;font-size:22px;letter-spacing:.2em;color:#86F0C0}
.card .h{margin-top:22px;font-size:60px;font-weight:680;line-height:1.22;letter-spacing:-.02em}
.floor{position:absolute;left:180px;right:180px;top:1160px;height:1px;background:rgba(255,255,255,.10)}
""",
    """
  <div class="floor"></div>
  <div class="card" id="card">
    <div class="k">ELEVATION</div>
    <div class="h">高度由影子说<br>不靠描边</div>
  </div>
""",
    """
var drv = {y: 0, s: 0, b: 26, o: 0.55, sc: 1};
function paint() {
  var el = document.getElementById('card');
  el.style.transform = 'translateY(' + drv.y + 'px) scale(' + drv.sc + ')';
  el.style.boxShadow = '0 ' + drv.s + 'px ' + drv.b + 'px rgba(0,0,0,' + drv.o + ')';
}
paint();
tl.to(drv, {y: -54, s: 46, b: 96, o: 0.78, sc: 1.03, duration: 0.85, ease: 'power2.out', onUpdate: paint}, 0.6);
tl.to(drv, {y: 0, s: 12, b: 30, o: 0.5, sc: 1, duration: 0.55, ease: 'power2.in', onUpdate: paint}, 1.75);
""",
))


# ---------------------------------------------------------------- 生成 / 渲染

def build() -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    if not (SRC / "photo.png").exists():
        shutil.copy2(PHOTO, SRC / "photo.png")
    shutil.copy2(VENDOR / "gsap.min.js", SRC / "gsap.min.js")
    rows = []
    total = len(CARDS)
    for c in CARDS:
        d = SRC / c["key"]
        d.mkdir(exist_ok=True)
        html = SHELL.format(
            no=c["no"], name=c["name"], family=c["family"], key=KEY + "-" + c["key"][2:].lower(),
            dur=DUR, base_css=BASE_CSS, css=c["css"], body=c["body"], js=c["js"], total=total,
        )
        (d / "index.html").write_text(html, encoding="utf-8")
        (d / "hyperframes.json").write_text(json.dumps({
            "name": "rv-" + c["key"].lower(), "version": 1, "composition": "index.html",
            "width": 1080, "height": 1920, "fps": 30, "duration": DUR,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        for f in ("photo.png", "gsap.min.js"):
            if not (d / f).exists():
                shutil.copy2(SRC / f, d / f)
        rows.append("\t".join([c["no"], c["name"], c["family"], c["why"], str(d)]))
    (BATCH / "清单.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("✓ 工程 %d 个 → %s" % (total, SRC))
    print("  清单 → %s" % (BATCH / "清单.tsv"))


def render_one(c):
    d = SRC / c["key"]
    out = OUT / ("%s-%s.mp4" % (c["no"], c["name"]))
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
        return "FAIL %s\n%s" % (c["key"], (r.stderr or r.stdout)[-1200:])
    return "✓ " + out.name


def render() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for msg in ex.map(render_one, CARDS):
            print(msg, flush=True)


def sheet() -> None:
    files = [OUT / ("%s-%s.mp4" % (c["no"], c["name"])) for c in CARDS]
    files = [f for f in files if f.exists()]
    if not files:
        print("没有可用的 mp4")
        return
    cols = 4
    rows = (len(files) + cols - 1) // cols
    args = ["ffmpeg", "-y"]
    for f in files:
        args += ["-ss", "1.9", "-t", "0.1", "-i", str(f)]
    n = len(files)
    filt = "".join("[%d:v]scale=270:480,drawbox=x=0:y=0:w=iw:h=ih:color=0x1a1a1a@1:t=2[v%d];" % (i, i) for i in range(n))
    filt += "".join("[v%d]" % i for i in range(n))
    filt += "xstack=inputs=%d:layout=" % n
    lay = []
    for i in range(n):
        x = (i % cols) * 270
        y = (i // cols) * 480
        lay.append("%d_%d" % (x, y))
    filt += "|".join(lay) + ":fill=0x0a0b0b[out]"
    args += ["-filter_complex", filt, "-map", "[out]", "-frames:v", "1",
             str(BATCH / "revideo候选-联系表.jpg")]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
    else:
        print("✓ %s（%d 张，%d 列）" % (BATCH / "revideo候选-联系表.jpg", n, cols))


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("build", "all"):
        build()
    if cmd in ("render", "all"):
        render()
    if cmd in ("sheet", "all"):
        sheet()


if __name__ == "__main__":
    main()
