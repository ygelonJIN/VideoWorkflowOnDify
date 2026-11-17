#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""外部效果进件：一次渲，筛完就地转正或删掉，不再渲两遍。

适用：拿到一批外部效果（目前支持 gl-transitions 的 .glsl），先按**确认片的规格**渲染一遍
（同样的舞台、同样的时长），你直接在文件上做筛选：
    留下的 → promote 把它移进 全卡审阅/<族>/ 并改名为 <编号>-<中文名>.mp4，同时写进 presets
    不要的 → drop 直接删掉样片与源工程

用法（在 能力库/动效库/样片/待筛/ 里工作）：
    python3 ../../intake.py build  --src ~/Downloads/gl-transitions-master     # 生成工程 + 待筛清单.tsv
    bash ../../intake.py render                                                 # 渲染（并行 4）
    python3 ../../intake.py keep  12 45 68 --family 转场 --start 69 \\
            --names names.json                                                  # 转正
    python3 ../../intake.py drop                                                        # 删掉没留的

`names.json` 形如 {"Pixelize": "像素化", "Halftone": "半调网点"}；不给就用英文名。
转正时起止点默认 0–1（确认片就是生产里的样子）；要打磨手感，之后再单独
`render_card.sh <编号>` 一次，把 p0/p1 写进卡里。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent            # 能力库/动效库
WORK = HERE.parent.parent
LIB_SAMPLES = HERE / "样片"
BATCH = LIB_SAMPLES / "待筛"
SRC = BATCH / "源"
VENDOR = WORK / "成品" / "workflow_runtime" / "assets" / "vendor"
REELS = LIB_SAMPLES / "全卡审阅"
PHOTO_SRC = HERE / "assets" / "demo" / "photo.png"
PRESETS = HERE / "presets.json"
CARDS_MD = HERE / "能力卡.md"

STAGE_CSS = """
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#000;font-family:"PingFang SC","Helvetica Neue",sans-serif;-webkit-font-smoothing:antialiased}
#stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:#0a0b0b;color:#F4F1E9}
.scene{position:absolute;inset:0;display:block;overflow:hidden}
.shotbox{position:absolute;inset:0;z-index:1;overflow:hidden}
.shotbox img{width:100%;height:100%;object-fit:cover;display:block}
.hdr{position:absolute;left:64px;top:74px;z-index:20;display:flex;align-items:baseline;gap:20px;
  text-shadow:0 2px 18px rgba(0,0,0,.8)}
.hdr .id{font-family:"SF Mono",Menlo,monospace;font-size:30px;letter-spacing:.16em;color:#86F0C0}
.hdr .nm{font-size:40px;font-weight:640;letter-spacing:-.01em}
.hdr .fm{font-family:"SF Mono",Menlo,monospace;font-size:22px;color:#7e8a84;letter-spacing:.14em}
.ftr{position:absolute;right:64px;bottom:70px;z-index:20;font-family:"SF Mono",Menlo,monospace;
  font-size:24px;letter-spacing:.12em;color:rgba(244,241,233,.32)}
.warn{position:absolute;left:48px;top:290px;z-index:60;display:none;font-family:"SF Mono",Menlo,monospace;
  font-size:22px;color:#ffd9d2;background:rgba(226,84,58,.24);border:1px solid rgba(226,84,58,.6);
  border-radius:10px;padding:12px 18px}
.nogl .warn{display:block}
"""

STAGE_SHELL = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{name}</title>
<style>{css}</style></head><body class="{cls}">
<div id="stage" data-composition-id="{key}" data-width="1080" data-height="1920" data-duration="{dur}">
<section class="scene active" data-scene="s01" data-start="0" data-duration="{dur}">
  <div class="shotbox"><img id="photo" src="../photo.jpg" alt=""></div>
  <div class="hdr"><span class="id">{idx}</span><span class="nm">{name}</span><span class="fm">待筛</span></div>
  <div class="warn">WebGL 不可用</div>
  <div class="ftr">{idx} / {total}</div>
</section>
</div>
<script src="../gsap.min.js"></script>
<script src="../gltrans-kit.js"></script>
<script src="./glsl.js"></script>
<script>
(function () {{
"use strict";
var tl = gsap.timeline({{ paused: true }});
window.__timelines = window.__timelines || {{}};
window.__timelines['{key}'] = tl;
window.addEventListener('hf-seek', function (e) {{ tl.time(e.detail.time); }});

var fx = glt.mount(document.getElementById('photo'), '{name}', {{ from: '#0a0b0b', params: {params} }});
if (!fx) document.body.classList.add('nogl');

var drv = {{ p: 0 }};
function draw() {{ if (fx) fx.draw(drv.p); }}
tl.to(drv, {{ p: 1, duration: {dur_s}, ease: 'none', onUpdate: draw }}, {at});
draw();
}})();
</script></body></html>
"""

sys.path.insert(0, str(HERE))
import build_gltrans  # noqa: E402


def cmd_build(args) -> None:
    SRC.mkdir(parents=True, exist_ok=True)
    if not (SRC / "photo.jpg").exists():
        from PIL import Image
        im = Image.open(PHOTO_SRC).convert("RGB").resize((810, 1215), Image.LANCZOS)
        im.save(SRC / "photo.jpg", quality=88, optimize=True)
    shutil.copy2(VENDOR / "gltrans-kit.js", SRC / "gltrans-kit.js")
    shutil.copy2(VENDOR / "gsap.min.js", SRC / "gsap.min.js")

    names = sorted(p.stem for p in (args.src / "transitions").glob("*.glsl"))
    names = [n for n in names if n not in build_gltrans.SKIP]
    if args.only:
        want = {s.strip() for s in args.only.split(",") if s.strip()}
        names = [n for n in names if n in want]
    if args.limit:
        names = names[: args.limit]

    css = STAGE_CSS
    shell = STAGE_SHELL

    rows = []
    for i, name in enumerate(names, 1):
        d = SRC / name
        d.mkdir(parents=True, exist_ok=True)
        build_gltrans.build(args.src, [name], d / "glsl.js")
        meta = build_gltrans.parse(args.src / "transitions" / (name + ".glsl"))
        (d / "hyperframes.json").write_text(json.dumps({
            "name": name, "version": 1, "composition": "index.html",
            "width": 1080, "height": 1920, "fps": 30, "duration": 3.0,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (d / "index.html").write_text(
            "<!DOCTYPE html>\n<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>%s</title>\n<style>%s</style></head><body>\n"
            % (name, css)
            + shell.format(name=name, key=name, dur="3.0", css="", cls="", tags="", desc="",
                           params_line="", params=json.dumps({k: v["default"] for k, v in meta["params"].items()},
                                                             ensure_ascii=False),
                           dur_s="2.55", at="0.18", idx=str(i), total=len(names))
            + "\n</body></html>\n", encoding="utf-8")
        rows.append((i, name, meta["meta"].get("tags", ""), len(meta["params"])))

    tsv = BATCH / "待筛清单.tsv"
    with tsv.open("w", encoding="utf-8") as f:
        f.write("序号\tshader\t标签\t参数数\n")
        for r in rows:
            f.write("%s\t%s\t%s\t%d\n" % r)
    print("✓ %d 个工程 → %s" % (len(rows), SRC))
    print("✓ %s" % tsv)
    print("\n下一步：bash 能力库/动效库/intake.py render")


def cmd_render(args) -> None:
    hf = WORK / "成品" / "workflow_runtime" / "vendor" / "node_modules" / "hyperframes" / "bin" / "hyperframes.mjs"
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    node = sorted(pathlib.Path.home().glob(".nvm/versions/node/v22*/bin/node"))
    node = str(node[-1]) if node else shutil.which("node")
    if not hf.exists():
        raise SystemExit("缺 HyperFrames CLI：%s" % hf)

    def one(d: pathlib.Path) -> bool:
        out = BATCH / ("%s-%s.mp4" % (rows[d.name], d.name))
        if out.exists() and not args.force:
            return True
        env = dict(HYPERFRAMES_BROWSER_PATH=chrome, HYPERFRAMES_CACHE_DIR=str(d / ".hyperframes" / "cache"))
        r = subprocess.run([node, str(hf), "render", ".", "-w", "1", "-f", "30", "-q", "looks",
                            "--no-browser-gpu", "--experimental-fast-capture=false", "-o", "out.mp4"],
                           cwd=str(d), env={**__import__("os").environ, **env},
                           capture_output=True)
        if r.returncode != 0 or not (d / "out.mp4").exists():
            print("✗", d.name)
            return False
        shutil.move(str(d / "out.mp4"), str(out))
        shutil.rmtree(d / ".hyperframes", ignore_errors=True)
        print("✓", out.name)
        return True

    rows = {}
    for line in (BATCH / "待筛清单.tsv").read_text(encoding="utf-8").rstrip().split("\n")[1:]:
        p = line.split("\t")
        rows[p[1]] = p[0]
    dirs = sorted([d for d in SRC.iterdir() if d.is_dir()])
    if args.only:
        dirs = [d for d in dirs if d.name == args.only]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        list(ex.map(one, dirs))
    print("完成：%d 张" % len(list(BATCH.glob("*-*.mp4"))))


def cmd_keep(args) -> None:
    rows = {}
    for line in (BATCH / "待筛清单.tsv").read_text(encoding="utf-8").rstrip().split("\n")[1:]:
        p = line.split("\t")
        rows[p[0]] = p[1]
    names = json.loads(pathlib.Path(args.names).read_text(encoding="utf-8")) if args.names else {}
    data = json.loads(PRESETS.read_text(encoding="utf-8"))
    have = {c["id"] for c in data["presets"]}
    start = args.start
    added = []
    for seq in args.picks:
        shader = rows[str(seq)]
        cid = "GT%02d" % start
        while cid in have:
            start += 1
            cid = "GT%02d" % start
        start += 1
        cn = names.get(shader, shader)
        mp4 = BATCH / ("%s-%s.mp4" % (seq, shader))
        dest = REELS / args.family
        dest.mkdir(parents=True, exist_ok=True)
        target = dest / ("%s-%s.mp4" % (cid, cn))
        print("%s %-20s → %s" % (seq, shader, target.relative_to(WORK)))
        if args.dry_run:
            continue
        if not mp4.exists():
            print("  ✗ 缺片，跳过")
            continue
        shutil.move(str(mp4), str(target))
        meta = build_gltrans.parse(args.src / "transitions" / (shader + ".glsl"))
        types = {k: v["type"] for k, v in meta["params"].items()}
        params = {k: v["default"] for k, v in meta["params"].items()}
        for k, t in types.items():
            if t == "bool":
                params[k] = 1 if params[k] else 0
        bits = []
        for k, t in types.items():
            if t == "bool" or t.startswith("bvec"):
                bits.append('"%s": _b({{%s}})' % (k, k))
            elif t in ("vec2", "vec3", "vec4", "ivec2", "ivec3", "ivec4"):
                bits.append('"%s": _n({{%s}}, %d)' % (k, k, int(t[-1])))
            else:
                bits.append('"%s": {{%s}}' % (k, k))
        data["presets"].append({
            "id": cid, "name": cn, "family": args.family, "role": args.role,
            "layer": "media", "status": args.status, "cap": "gl-transition",
            "src": "gltrans:" + shader, "note": (meta["meta"].get("description", "") or shader)[:80],
            "group": "待归类", "origin": "gltrans",
            "params": dict({"dur": 2.2, "p0": 0.0, "p1": 1.0, "ease": "none", "from": "#0a0b0b"}, **params),
            "use": (meta["meta"].get("description", "") or shader)[:80],
            "avoid": "一屏最多一张；不要和页间转场抢同一次交接",
            "code": """(function () {
  var _el = document.querySelector('{{sel}}');
  if (!_el || !window.glt || !glt.has('%s')) return;
  function _n(v, n) { v = Array.isArray(v) ? v.slice(0) : [v]; while (v.length < n) { v.push(v.length ? v[v.length - 1] : 0); } return v.slice(0, n); }
  function _b(v) { return (v === true || v === 1 || v === '1' || v === 'true') ? 1 : 0; }
  var _fx = glt.mount(_el, '%s', { from: '{{from}}', params: {%s} });
  if (!_fx) return;
  var _p0 = {{p0}}, _p1 = {{p1}}, _d = { u: 0 };
  function _P(u) {
    if (u <= 0.1) { return _p0 * (u / 0.1); }
    if (u >= 0.9) { return _p1 + (1 - _p1) * ((u - 0.9) / 0.1); }
    return _p0 + (_p1 - _p0) * ((u - 0.1) / 0.8);
  }
  timeline.to(_d, { u: 1, duration: {{dur}}, ease: '{{ease}}',
    onUpdate: function () { _fx.draw(_P(_d.u)); } }, {{at}});
})();""" % (shader, shader, ", ".join(bits)),
        })
        added.append(cid)
        shutil.rmtree(SRC / shader, ignore_errors=True)
    if args.dry_run:
        print("\n（dry-run，什么都没写）")
        return
    PRESETS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("✓ presets：+%d 张 %s" % (len(added), " ".join(added)))
    subprocess.run([sys.executable, str(HERE / "gen_catalog.py")], cwd=str(WORK))
    subprocess.run([sys.executable, str(HERE / "sync_expander.py")], cwd=str(WORK))
    print("\n剩两件事：")
    print("  1. 在 能力库/动效库/来源台账.md 记一行这批的结论")
    print("  2. 走 `check_catalog_sync.py`；文案（use / avoid / note）脚本不替你写")


def cmd_drop(args) -> None:
    keep = set(str(x) for x in args.keep)
    for mp4 in sorted(BATCH.glob("*-*.mp4")):
        seq = mp4.name.split("-")[0]
        if seq in keep:
            continue
        print("删", mp4.name)
        if not args.dry_run:
            mp4.unlink()
    for d in sorted([p for p in SRC.iterdir() if p.is_dir()]):
        if d.name in args.keep_names:
            continue
        if not args.dry_run and not (BATCH / ("%s.mp4" % d.name)).exists():
            pass
    if args.prune_src:
        for d in sorted([p for p in SRC.iterdir() if p.is_dir()]):
            if not any(BATCH.glob("*-%s.mp4" % d.name)):
                print("删工程", d.name)
                if not args.dry_run:
                    shutil.rmtree(d, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--src", type=pathlib.Path, default=pathlib.Path.home() / "Downloads" / "gl-transitions-master")
    b.add_argument("--only", default="")
    b.add_argument("--limit", type=int, default=0)
    b.set_defaults(fn=cmd_build)

    r = sub.add_parser("render")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--only", default="")
    r.add_argument("--force", action="store_true")
    r.set_defaults(fn=cmd_render)

    k = sub.add_parser("keep")
    k.add_argument("picks", nargs="+")
    k.add_argument("--family", default="转场")
    k.add_argument("--start", type=int, default=69)
    k.add_argument("--names", default="")
    k.add_argument("--role", required=True, help="选择层归属，必须是可选 role（没有 archive/none 了）")
    k.add_argument("--status", default="archived", help="ready 才会进展开器；素材默认 archived")
    k.add_argument("--src", type=pathlib.Path, default=pathlib.Path.home() / "Downloads" / "gl-transitions-master")
    k.add_argument("--dry-run", action="store_true")
    k.set_defaults(fn=cmd_keep)

    d = sub.add_parser("drop")
    d.add_argument("--keep", nargs="*", default=[])
    d.add_argument("--keep-names", nargs="*", default=[])
    d.add_argument("--prune-src", action="store_true")
    d.add_argument("--dry-run", action="store_true")
    d.set_defaults(fn=cmd_drop)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
