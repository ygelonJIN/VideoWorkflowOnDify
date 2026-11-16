#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用进件体检（scan）：任何来源的包，先体检再决定要不要渲候选片。

只读，不改 presets.json、不渲片、不写全卡审阅。

用法：
    python3 能力库/动效库/admit.py scan --src <来源目录> [--batch 20261116-ui2v]
    python3 能力库/动效库/admit.py scan --src <来源目录> --limit 50

判定口径就是来源台账 §一 的四条硬标准：
    1. 不依赖指针输入   2. DOM 卡不用 WebGL/shader
    3. 能由时间线给 t 驱动（注册了 __timelines 或自带 paused GSAP 时间轴）
    4. 不无限循环（repeat:-1 / repeatCount:-1）

输出三档：
    可直接提  四条全过，逐字重写成卡即可
    需重写    有 canvas / rAF / 随机 / 无限循环 / 指针，得改写实现
    不能提    shader-only、没有时间轴、或找不到可执行画面

报告落到 样片/待筛/<batch>/体检.tsv，并在终端打汇总。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
BATCH_ROOT = HERE / "样片" / "待筛"

RE_TL = re.compile(r"__timelines|gsap\s*\.\s*timeline\s*\(\s*\{[^}]*paused\s*:\s*true")
RE_CANVAS = re.compile(r"<canvas|getContext\(\s*['\"]2d")
RE_WEBGL = re.compile(r"getContext\(\s*['\"](?:webgl|experimental-webgl)|ShaderMaterial|THREE\.\w+")
RE_RAF = re.compile(r"requestAnimationFrame")
RE_RAND = re.compile(r"Math\.random|Date\.now|performance\.now")
RE_LOOP = re.compile(r"repeat\s*:\s*-1|repeatCount\s*:\s*-1")
RE_PTR = re.compile(r"addEventListener\(\s*['\"](?:mouse|pointer|click|wheel|touch|key|scroll)")
RE_DIM = re.compile(r"data-width\s*=\s*[\"'](\d+)[\"'][^>]*data-height\s*=\s*[\"'](\d+)[\"']|"
                    r"data-height\s*=\s*[\"'](\d+)[\"'][^>]*data-width\s*=\s*[\"'](\d+)[\"']")
RE_DUR = re.compile(r"data-duration\s*=\s*[\"']([\d.]+)[\"']")


def read_text(path: pathlib.Path, cap: int = 400_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:cap]
    except Exception:
        return ""


def units_of(src: pathlib.Path):
    """把来源目录切成"一个可评估单元"：包（含 index.html 的目录）/ 单个 html / glsl。"""
    for p in sorted(src.rglob("*")):
        if p.is_dir():
            idx = p / "index.html"
            if idx.is_file():
                inner = [h for h in sorted(p.glob("*.html")) if h.name != "index.html"]
                yield ("package", p, [idx] + inner)
        elif p.suffix.lower() in (".html", ".htm"):
            if (p.parent / "index.html").is_file():
                continue                      # 已被包收走
            yield ("html", p, [p])
        elif p.suffix.lower() == ".glsl":
            yield ("glsl", p, [p])


def inspect(kind, path, files):
    texts = [read_text(f) for f in files]
    # 内层 composition 才是实现，index.html 常只是 iframe 壳
    body = "\n".join(texts[1:]) if len(texts) > 1 else texts[0]
    skin = texts[0]
    allt = skin + "\n" + body
    w = h = 0
    m = RE_DIM.search(allt)
    if m:
        g = [x for x in m.groups() if x]
        w, h = (int(g[0]), int(g[1])) if len(g) >= 2 else (0, 0)
    dur = 0.0
    md = RE_DUR.search(allt)
    if md:
        dur = float(md.group(1))
    else:
        reg = path / "registry-item.json"
        if reg.is_file():
            try:
                dur = float(json.loads(read_text(reg)).get("duration") or 0)
            except Exception:
                dur = 0.0
    f = dict(
        tl=bool(RE_TL.search(allt)),
        canvas=bool(RE_CANVAS.search(body)),
        webgl=bool(RE_WEBGL.search(allt)),
        raf=bool(RE_RAF.search(body)),
        rand=bool(RE_RAND.search(body)),
        loop=bool(RE_LOOP.search(body)),
        ptr=bool(RE_PTR.search(allt)),
        files=len(list(path.rglob("*"))) if path.is_dir() else 1,
        bytes=sum(x.stat().st_size for x in path.rglob("*") if x.is_file()) if path.is_dir() else path.stat().st_size,
    )
    if kind == "glsl":
        return dict(f, verdict="需重写", why="shader，只能进照片层/转场，得改写", w=0, h=0, dur=0)
    if f["webgl"] and not f["tl"]:
        return dict(f, verdict="不能提", why="shader-only，没有时间轴", w=w, h=h, dur=dur)
    if not f["tl"]:
        return dict(f, verdict="不能提", why="没有可 seek 的时间轴", w=w, h=h, dur=dur)
    hard = [k for k in ("raf", "rand", "loop", "ptr") if f[k]]
    soft = [k for k in ("canvas", "webgl") if f[k]]
    if hard or soft:
        why = []
        if hard: why.append("需改写：" + "/".join(hard))
        if soft: why.append("渲染方式：" + "/".join(soft))
        return dict(f, verdict="需重写", why="；".join(why), w=w, h=h, dur=dur)
    return dict(f, verdict="可直接提", why="四条硬标准全过", w=w, h=h, dur=dur)


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sc = sub.add_parser("scan")
    sc.add_argument("--src", type=pathlib.Path, required=True)
    sc.add_argument("--batch", default="")
    sc.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    src = a.src.expanduser().resolve()
    if not src.is_dir():
        raise SystemExit("来源不是目录：%s" % src)
    batch = a.batch or ("scan-" + src.name)
    out = BATCH_ROOT / batch
    out.mkdir(parents=True, exist_ok=True)

    rows, n = [], 0
    for kind, path, files in units_of(src):
        n += 1
        if a.limit and n > a.limit:
            break
        r = inspect(kind, path, files)
        rows.append((kind, str(path.relative_to(src)), r))

    report = out / "体检.tsv"
    with report.open("w", encoding="utf-8") as fh:
        fh.write("结论\t类型\t路径\t宽x高\t时长\t帧数\t体积KB\t说明\n")
        for kind, rel, r in rows:
            fh.write("%s\t%s\t%s\t%dx%d\t%.1f\t%s\t%d\t%s\n" % (
                r["verdict"], kind, rel, r["w"], r["h"], r["dur"], r["files"], r["bytes"] // 1024, r["why"]))

    from collections import Counter
    c = Counter(r["verdict"] for _, _, r in rows)
    print("来源：%s" % src)
    print("单元：%d 个" % len(rows))
    for k in ("可直接提", "需重写", "不能提"):
        print("  %-6s %d" % (k, c.get(k, 0)))
    print("报告：%s" % report.relative_to(WORK))
    return 0


if __name__ == "__main__":
    sys.exit(main())
