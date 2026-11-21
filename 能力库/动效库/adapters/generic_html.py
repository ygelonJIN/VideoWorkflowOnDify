# -*- coding: utf-8 -*-
"""通用 HTML 适配器：单页 HTML / 包目录（index.html 只是 iframe 壳）。

只做三件事：找出真正的 composition 文件、把整包拷到目标目录、写 hyperframes.json。
不改它的 CSS/JS —— 我们要看的是原样的动效，重写发生在人审通过之后。
"""
from __future__ import annotations

import json
import pathlib
import re
import shutil

RE_DIM = re.compile(r"data-width\s*=\s*[\"'](\d+)[\"'][^>]*data-height\s*=\s*[\"'](\d+)[\"']|"
                    r"data-height\s*=\s*[\"'](\d+)[\"'][^>]*data-width\s*=\s*[\"'](\d+)[\"']")
RE_DUR = re.compile(r"data-duration\s*=\s*[\"']([\d.]+)[\"']")
RE_IFRAME = re.compile(r"<iframe[^>]+src\s*=\s*[\"']([^\"']+)[\"']")
RE_CDN_GSAP = re.compile(r"<script[^>]+src\s*=\s*[\"'](https?:)?//[^\"']*(?:gsap|jsdelivr|unpkg|cdnjs)[^\"']*[\"'][^>]*></script>\s*", re.I)
SEEK_DRIVER = """<script>
(function(){
  function seek(t){
    var T = window.__timelines || {};
    for (var k in T) { try { T[k].pause(t); T[k].time(t); } catch (e) {} }
  }
  window.addEventListener('hf-seek', function (e) {
    var t = (e && e.detail && typeof e.detail.time === 'number') ? e.detail.time : 0;
    seek(t);
  });
  setTimeout(function () { seek(0); }, 60);
})();
</script>
"""
VENDOR_GSAP = pathlib.Path(__file__).resolve().parents[3] / "runtime" / "assets" / "vendor" / "gsap.min.js"


def can_handle(path: pathlib.Path, kind: str) -> bool:
    return kind in ("package", "html")


def _is_document(txt: str) -> bool:
    """完整页面才渲得动；`<template>` 片段要由包的 runtime 注入。"""
    low = txt.lower()
    return ("<html" in low) or ("<head" in low) or ("<body" in low)


def _pick_composition(path: pathlib.Path, kind: str) -> pathlib.Path | None:
    if kind == "html":
        return path
    htmls = sorted(p for p in path.glob("*.html"))
    if not htmls:
        return None
    idx = path / "index.html"
    # 1) index.html 是 iframe 壳 → 跟到内层
    if idx.is_file():
        itxt = idx.read_text(encoding="utf-8", errors="ignore")
        m = RE_IFRAME.search(itxt)
        if m:
            target = path / m.group(1)
            if target.is_file():
                return target
        if _is_document(itxt):
            return idx
    # 2) 非 index 的完整页面
    for h in htmls:
        if h.name == "index.html":
            continue
        if _is_document(h.read_text(encoding="utf-8", errors="ignore")):
            return h
    # 3) 同名的文件（可能只是片段，仍比没有强）
    for h in htmls:
        if h.stem.lower() == path.name.lower():
            return h
    return idx if idx.is_file() else None


def prepare(src_unit: pathlib.Path, dst_dir: pathlib.Path) -> dict | None:
    kind = "html" if src_unit.is_file() else "package"
    comp = _pick_composition(src_unit, kind)
    if comp is None:
        return None
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    if kind == "package":
        for item in src_unit.iterdir():
            if item.name in (".git", "node_modules"):
                continue
            if item.is_dir():
                shutil.copytree(item, dst_dir / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst_dir / item.name)
        rel = comp.relative_to(src_unit).as_posix()
    else:
        shutil.copy2(comp, dst_dir / comp.name)
        rel = comp.name
    # 1) GSAP 本地化：包里的 CDN 引用在离线渲染里会 404，整页就静止
    comp_path = dst_dir / rel
    txt = comp_path.read_text(encoding="utf-8", errors="ignore")
    local_gsap = dst_dir / "gsap.min.js"
    if VENDOR_GSAP.is_file():
        shutil.copy2(VENDOR_GSAP, local_gsap)
        txt = RE_CDN_GSAP.sub('<script src="gsap.min.js"></script>\n', txt)
        plugin_dir = VENDOR_GSAP.parent / "gsap-plugins"
        def _local_plugin(m):
            name = m.group(1)
            cand = plugin_dir / (name + ".min.js")
            if cand.is_file():
                shutil.copy2(cand, dst_dir / cand.name)
                return '<script src="%s"></script>' % cand.name
            return m.group(0)
        txt = re.sub(r'<script[^>]+src\\s*=\\s*["\'](?:https?:)?//[^"\']*/([A-Za-z]+)\\.min\\.js["\'][^>]*></script>', _local_plugin, txt)
        if "gsap.min.js" not in txt and "gsap" in txt.lower():
            txt = txt.replace("</head>", '<script src="gsap.min.js"></script></head>', 1)
    # 2) 接 seek：这批包的 timeline 是 paused 的，宿主不发时间就一直是第一帧
    if "hf-seek" not in txt:
        txt = txt.replace("</body>", SEEK_DRIVER + "</body>", 1) if "</body>" in txt else txt + SEEK_DRIVER
    comp_path.write_text(txt, encoding="utf-8")
    # 3) 入口统一成 index.html（HyperFrames 只认它）
    if comp_path.name != "index.html":
        shutil.copy2(comp_path, dst_dir / "index.html")
        rel = "index.html"
    m = RE_DIM.search(txt)
    w, h = (1920, 1080)
    if m:
        g = [x for x in m.groups() if x]
        if len(g) >= 2:
            w, h = int(g[0]), int(g[1])
    dur = 3.0
    md = RE_DUR.search(txt)
    reg = src_unit / "registry-item.json" if kind == "package" else None
    if md:
        dur = float(md.group(1))
    elif reg and reg.is_file():
        try:
            dur = float(json.loads(reg.read_text(encoding="utf-8")).get("duration") or 3)
        except Exception:
            dur = 3.0
    cid = None
    mc = re.search(r'data-composition-id\s*=\s*["\']([^"\']+)["\']', txt)
    if mc:
        cid = mc.group(1)
    note = "整包拷贝，未改实现" + ("，原时长 %.1fs 截到 3s" % dur if dur > 3 else "")
    return {"composition": rel, "width": w, "height": h, "duration": min(max(dur, 1.0), 3.0), "note": note, "composition_id": cid}
