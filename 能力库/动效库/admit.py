#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用进件流水线：scan → build → render → keep / drop。

铁规则（AGENTS.md「加卡顺序」）：候选只落在 样片/待筛/<批次>/，
本脚本**不写 presets.json、不写 全卡审阅/**。转正由人点头后走 add_card.py。

    python3 能力库/动效库/admit.py scan   --src <来源目录> [--batch 名] [--limit N]
    python3 能力库/动效库/admit.py build  --src <来源目录> --batch 名 (--slugs a,b | --limit 12)
    python3 能力库/动效库/admit.py render --batch 名 [--workers 4] [--force]
    python3 能力库/动效库/admit.py keep   <slug...> --family 入场 [--note "一句话用途"]
    python3 能力库/动效库/admit.py drop   [--keep slug...]

scan 判的是来源台账 §一 的四条硬标准；build 用 adapters/ 里对应来源形态的适配器
把候选拷成可渲工程；keep 只登记结论 + 分配编号，卡代码仍需按机制重写后走 add_card.py。
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
from collections import Counter

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
BATCH_ROOT = HERE / "样片" / "待筛"
PRESETS = HERE / "presets.json"
LEDGER = HERE / "来源台账.md"
HF_BIN = WORK / "runtime" / "vendor" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
CHROME = os.environ.get("HYPERFRAMES_BROWSER_PATH",
                        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")

sys.path.insert(0, str(HERE))
import adapters  # noqa: E402

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

FAMILY_PREFIX = {"入场": "T", "状态": "S", "字形": "K", "版面": "G", "结构": "X", "照片": "W",
                 "材质": "M", "绘制": "U", "组件": "U", "UI": "UA",
                 "离场": "X", "镜头": "C", "交互": "I", "背景": "B", "页间转场": "PT"}


def read_text(path, cap=400_000):
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:cap]
    except Exception:
        return ""


def units_of(src: pathlib.Path):
    for p in sorted(src.rglob("*")):
        if p.is_dir() and (p / "index.html").is_file():
            yield ("package", p)
        elif p.is_file() and p.suffix.lower() in (".html", ".htm"):
            if (p.parent / "index.html").is_file():
                continue
            yield ("html", p)
        elif p.is_file() and p.suffix.lower() == ".glsl":
            yield ("glsl", p)


def inspect(kind, path):
    if kind == "glsl":
        return {"verdict": "需重写", "why": "shader：只能进照片层/双图转场", "w": 0, "h": 0,
                "dur": 0.0, "files": 1, "bytes": path.stat().st_size,
                "tl": 0, "canvas": 0, "webgl": 1, "raf": 0, "rand": 0, "loop": 0, "ptr": 0}
    files = [path] if kind == "html" else [path / "index.html"] + [h for h in sorted(path.glob("*.html")) if h.name != "index.html"]
    texts = [read_text(f) for f in files]
    body = "\n".join(texts[1:]) if len(texts) > 1 else texts[0]
    allt = "\n".join(texts)
    w = h = 0
    m = RE_DIM.search(allt)
    if m:
        g = [x for x in m.groups() if x]
        if len(g) >= 2:
            w, h = int(g[0]), int(g[1])
    dur = 0.0
    md = RE_DUR.search(allt)
    if md:
        dur = float(md.group(1))
    reg = path / "registry-item.json" if kind == "package" else None
    if not dur and reg and reg.is_file():
        try:
            dur = float(json.loads(read_text(reg)).get("duration") or 0)
        except Exception:
            dur = 0.0
    f = dict(tl=bool(RE_TL.search(allt)), canvas=bool(RE_CANVAS.search(body)),
             webgl=bool(RE_WEBGL.search(allt)), raf=bool(RE_RAF.search(body)),
             rand=bool(RE_RAND.search(body)), loop=bool(RE_LOOP.search(body)),
             ptr=bool(RE_PTR.search(allt)),
             files=len(list(path.rglob("*"))) if path.is_dir() else 1,
             bytes=sum(x.stat().st_size for x in path.rglob("*") if x.is_file()) if path.is_dir() else path.stat().st_size)
    if f["webgl"] and not f["tl"]:
        return dict(f, verdict="不能提", why="shader-only，没有时间轴", w=w, h=h, dur=dur)
    if not f["tl"]:
        return dict(f, verdict="不能提", why="没有可 seek 的时间轴", w=w, h=h, dur=dur)
    hard = [k for k in ("raf", "rand", "loop", "ptr") if f[k]]
    soft = [k for k in ("canvas", "webgl") if f[k]]
    if hard or soft:
        why = []
        if hard:
            why.append("需改写：" + "/".join(hard))
        if soft:
            why.append("渲染方式：" + "/".join(soft))
        return dict(f, verdict="需重写", why="；".join(why), w=w, h=h, dur=dur)
    return dict(f, verdict="可直接提", why="四条硬标准全过", w=w, h=h, dur=dur)


def ledger_deleted():
    """读来源台账 §二，展开成已删编号集合（这些号永不复用）。"""
    if not LEDGER.is_file():
        return set()
    s = LEDGER.read_text(encoding="utf-8")
    if "## 二、" not in s:
        return set()
    sec = s.split("## 二、")[1].split("## 三、")[0]
    out = set()
    for a, n1, b, n2 in re.findall(r"([A-Z]{1,2})(\d{2})\s*[–-]\s*([A-Z]{1,2})(\d{2})", sec):
        if a == b:
            for i in range(int(n1), int(n2) + 1):
                out.add("%s%02d" % (a, i))
    for a, n in re.findall(r"(?<![A-Z0-9])([A-Z]{1,2})(\d{2})(?![0-9])", sec):
        out.add("%s%02d" % (a, int(n)))
    return out


def allocate(family: str, count: int):
    fam = FAMILY_PREFIX.get(family)
    if not fam:
        raise SystemExit("不认识的族：%s（可选 %s）" % (family, "/".join(FAMILY_PREFIX)))
    used = {c["id"] for c in json.loads(PRESETS.read_text(encoding="utf-8"))["presets"]}
    banned = ledger_deleted() | used
    nums = [int(i[len(fam):]) for i in banned if i.startswith(fam) and i[len(fam):].isdigit()]
    nxt = (max(nums) + 1) if nums else 1
    out = []
    while len(out) < count:
        cid = "%s%02d" % (fam, nxt)
        nxt += 1
        if cid in banned:
            continue
        out.append(cid)
    return out


def node_bin():
    for pat in sorted(pathlib.Path.home().glob(".nvm/versions/node/v22*/bin/node")):
        return str(pat)
    return shutil.which("node") or "node"


def cmd_scan(a):
    src = a.src.expanduser().resolve()
    if not src.is_dir():
        raise SystemExit("来源不是目录：%s" % src)
    batch = a.batch or ("scan-" + src.name)
    out = BATCH_ROOT / batch
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for kind, path in units_of(src):
        if a.limit and len(rows) >= a.limit:
            break
        if a.kinds and kind not in a.kinds:
            continue
        rows.append((kind, path, inspect(kind, path)))
    rep = out / "体检.tsv"
    with rep.open("w", encoding="utf-8") as fh:
        fh.write("结论\t类型\t路径\t宽x高\t原时长\t文件数\t体积KB\t说明\n")
        for kind, path, r in rows:
            fh.write("%s\t%s\t%s\t%dx%d\t%.1f\t%d\t%d\t%s\n" % (
                r["verdict"], kind, path.relative_to(src).as_posix(), r["w"], r["h"],
                r["dur"], r["files"], r["bytes"] // 1024, r["why"]))
    c = Counter(r["verdict"] for _, _, r in rows)
    print("来源：%s" % src)
    print("单元：%d" % len(rows))
    for k in ("可直接提", "需重写", "不能提"):
        print("  %-6s %d" % (k, c.get(k, 0)))
    print("报告：%s" % rep.relative_to(WORK))
    return 0


def cmd_build(a):
    src = a.src.expanduser().resolve()
    batch_dir = BATCH_ROOT / a.batch
    src_root = batch_dir / "源"
    src_root.mkdir(parents=True, exist_ok=True)
    want = [s.strip() for s in (a.slugs or "").split(",") if s.strip()]
    picked = []
    for kind, path in units_of(src):
        rel = path.relative_to(src).as_posix()
        slug = path.stem if kind == "html" else path.name
        if want and slug not in want and rel not in want:
            continue
        picked.append((kind, path, slug, rel))
        if not want and a.limit and len(picked) >= a.limit:
            break
    if not picked:
        raise SystemExit("没挑到任何单元；先用 scan 看体检报告，再 --slugs 点名")
    rows, seen = [], set()
    for kind, path, slug, rel in picked:
        base, n = slug, 1
        while slug in seen:
            n += 1
            slug = "%s-%d" % (base, n)
        seen.add(slug)
        dst = src_root / slug
        info = None
        for ad in adapters.REGISTRY:
            if ad.can_handle(path, kind):
                info = ad.prepare(path, dst)
                if info:
                    break
        if not info:
            print("  跳过（没有适配器能处理）：%s" % rel)
            continue
        comp_name = info.get("composition_id") or ("admit-" + re.sub(r"[^a-z0-9-]+", "-", slug.lower()))
        (dst / "hyperframes.json").write_text(json.dumps({
            "name": comp_name,
            "version": 1, "composition": info["composition"],
            "width": info["width"], "height": info["height"], "fps": 30,
            "duration": info["duration"],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append((slug, rel, info["width"], info["height"], info["duration"], info["note"]))
    man = batch_dir / "候选清单.tsv"
    with man.open("w", encoding="utf-8") as fh:
        fh.write("slug\t来源路径\t宽\t高\t时长\t说明\n")
        for r in rows:
            fh.write("%s\t%s\t%d\t%d\t%.1f\t%s\n" % r)
    print("候选工程：%d 个 → %s" % (len(rows), src_root.relative_to(WORK)))
    print("下一步：python3 能力库/动效库/admit.py render --batch %s --workers 4" % a.batch)
    return 0


def cmd_render(a):
    batch_dir = BATCH_ROOT / a.batch
    src_root = batch_dir / "源"
    if not src_root.is_dir():
        raise SystemExit("没有候选工程：%s" % src_root)
    node = node_bin()
    env = dict(os.environ)
    if pathlib.Path(CHROME).exists():
        env["HYPERFRAMES_BROWSER_PATH"] = CHROME
    ok = fail = 0
    for d in sorted(p for p in src_root.iterdir() if p.is_dir()):
        out = batch_dir / (d.name + ".mp4")
        if out.exists() and not a.force:
            print("  已有：%s" % out.name)
            ok += 1
            continue
        cmd = [node, str(HF_BIN), "render", ".", "-w", str(a.workers), "-f", "30", "-q", "looks",
               "--no-browser-gpu", "--experimental-fast-capture=false", "-o", "out.mp4"]
        env2 = dict(env, HYPERFRAMES_CACHE_DIR=str(d / ".hyperframes" / "cache"))
        r = subprocess.run(cmd, cwd=str(d), env=env2, capture_output=True, text=True)
        built = d / "out.mp4"
        if r.returncode == 0 and built.exists():
            shutil.move(str(built), str(out))
            shutil.rmtree(d / ".hyperframes", ignore_errors=True)
            print("  ✓ %s" % out.name)
            ok += 1
        else:
            print("  ✗ %s（渲染失败）" % d.name)
            logdir = batch_dir / "诊断"
            logdir.mkdir(exist_ok=True)
            (logdir / (d.name + ".log")).write_text((r.stderr or "") + "\n" + (r.stdout or ""), encoding="utf-8")
            why = ""
            for line in ((r.stderr or "") + (r.stdout or "")).splitlines():
                if any(k in line for k in ("zero duration", "unregistered", "ReferenceError", "TypeError", "is not defined")):
                    why = line.strip()
            print("     ", (why or "见 诊断/%s.log" % d.name)[:150])
            fail += 1
    print("渲染完成：成功 %d，失败 %d" % (ok, fail))
    print("看片：%s" % batch_dir.relative_to(WORK))
    return 0 if fail == 0 else 1


def cmd_keep(a):
    batch_dir = BATCH_ROOT / a.batch
    ids = allocate(a.family, len(a.slugs))
    rows = []
    for slug, cid in zip(a.slugs, ids):
        mp4 = batch_dir / (slug + ".mp4")
        rows.append((cid, slug, a.family, "有片" if mp4.exists() else "缺片", a.note))
    tsv = batch_dir / "通过.tsv"
    header = not tsv.exists()
    with tsv.open("a", encoding="utf-8") as fh:
        if header:
            fh.write("分配编号\tslug\t族\t片\tnote\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")
    print("登记通过 %d 个（族=%s）：" % (len(rows), a.family))
    for cid, slug, fam, st, _ in rows:
        print("  %-6s %-40s %s" % (cid, slug, st))
    print("\n下一步（这一步必须人写卡，不自动）：")
    print("  按机制重写卡 code → python3 能力库/动效库/add_card.py 卡.json --render")
    print("  → python3 能力库/动效库/check_catalog_sync.py")
    return 0


def cmd_drop(a):
    batch_dir = BATCH_ROOT / a.batch
    keep = set(a.keep or [])
    src_root = batch_dir / "源"
    dropped = 0
    if src_root.is_dir():
        for d in list(src_root.iterdir()):
            if d.name in keep:
                continue
            shutil.rmtree(d, ignore_errors=True)
            mp4 = batch_dir / (d.name + ".mp4")
            if mp4.exists():
                mp4.unlink()
            dropped += 1
    print("清掉 %d 个候选（保留 %s）" % (dropped, "、".join(sorted(keep)) or "无"))
    left = sorted(p.stem for p in batch_dir.glob("*.mp4"))
    print("批次里还剩 %d 条片：%s" % (len(left), "、".join(left[:12]) + ("…" if len(left) > 12 else "")))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan"); s.add_argument("--src", type=pathlib.Path, required=True)
    s.add_argument("--batch", default=""); s.add_argument("--limit", type=int, default=0)
    s.add_argument("--kinds", nargs="*", default=["package", "html", "glsl"]); s.set_defaults(fn=cmd_scan)

    b = sub.add_parser("build"); b.add_argument("--src", type=pathlib.Path, required=True)
    b.add_argument("--batch", required=True); b.add_argument("--slugs", default="")
    b.add_argument("--limit", type=int, default=12); b.set_defaults(fn=cmd_build)

    r = sub.add_parser("render"); r.add_argument("--batch", required=True)
    r.add_argument("--workers", type=int, default=4); r.add_argument("--force", action="store_true")
    r.set_defaults(fn=cmd_render)

    k = sub.add_parser("keep"); k.add_argument("slugs", nargs="+")
    k.add_argument("--batch", required=True); k.add_argument("--family", required=True)
    k.add_argument("--note", default=""); k.set_defaults(fn=cmd_keep)

    d = sub.add_parser("drop"); d.add_argument("--batch", required=True)
    d.add_argument("--keep", nargs="*", default=[]); d.set_defaults(fn=cmd_drop)

    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
