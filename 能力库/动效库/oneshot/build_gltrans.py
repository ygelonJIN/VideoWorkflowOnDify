#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 gl-transitions 的 GLSL 转场做成 gltrans-kit 能吃的数据文件。

来源：https://github.com/gl-transitions/gl-transitions（MIT，每个 shader 自带作者与 License 注释）
产物：runtime/assets/vendor/gl-transitions.glsl.js
      每个 shader = 原文（含注释、uniform 声明、transition 函数）+ 解析出的参数默认值。

用法：
    python3 build_gltrans.py                     # 全量（跳过需要额外贴图的两支）
    python3 build_gltrans.py --list              # 只打印清单（名字 / 标签 / 参数数）
    python3 build_gltrans.py --only BurnThrough,InkBleed --out /tmp/x.js
    python3 build_gltrans.py --src ~/Downloads/gl-transitions-master

约定：
- 需要额外贴图的（DisplacementMap 的 displacementMap、LumaWipe 的 luma）跳过：素材管线不会给第二张蒙版。
- 数据文件不手改；改 shader 只认上游，改渲染逻辑只认 gltrans-kit.js。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORKSPACE = HERE.parent.parent
DEFAULT_SRC = pathlib.Path.home() / "Downloads" / "gl-transitions-master"
DEFAULT_OUT = WORKSPACE / "runtime" / "assets" / "vendor" / "gl-transitions.glsl.js"

META_RE = {
    "author": re.compile(r"^//\s*Author:\s*(.*)$", re.M),
    "license": re.compile(r"^//\s*License:\s*(.*)$", re.M),
    "description": re.compile(r"^//\s*Description:\s*(.*)$", re.M),
    "tags": re.compile(r"^//\s*Tags:\s*(.*)$", re.M),
}

NUM_RE = re.compile(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")
PARAM_RE = re.compile(
    r"^\s*uniform\s+(float|int|bool|vec2|vec3|vec4|ivec2|ivec3|ivec4|bvec2|bvec3|bvec4)\s+"
    r"(\w+)\s*;\s*(?://+\s*=?|/\*\s*=?)\s*(.+?)\s*(?:\*/)?\s*$",
    re.M,
)

_TYPE_PREFIX = re.compile(r"^\s*(?:vec|ivec|bvec)\d\s*")


def _numbers(raw: str) -> list[str]:
    """从默认值字面量里取数字：先剥掉 `vec2(` 这种类型名，否则 2 会被当成第一个分量。"""
    return NUM_RE.findall(_TYPE_PREFIX.sub("", raw))


SKIP = {"DisplacementMap", "LumaWipe"}          # 需要宿主再给一张贴图
MAX_PARAMS = 12                                  # 超过这个数的 shader 上下限太宽，卡片不好给参数


def parse_params(src: str) -> dict:
    out = {}
    for typ, name, raw in PARAM_RE.findall(src):
        raw = raw.strip()
        if typ == "bool":
            val = raw.lower().startswith("true")
        elif typ in ("int", "ivec2", "ivec3", "ivec4"):
            val = [int(float(n)) for n in _numbers(raw)]
            if typ == "int":
                val = val[0] if val else 0
        else:
            val = [round(float(n), 6) for n in _numbers(raw)]
            if typ == "float":
                val = val[0] if val else 0.0
        want = {"float": 1, "int": 1, "bool": 1,
                "vec2": 2, "vec3": 3, "vec4": 4,
                "ivec2": 2, "ivec3": 3, "ivec4": 4,
                "bvec2": 2, "bvec3": 3, "bvec4": 4}.get(typ, 1)
        if typ == "bool":
            want = 1
        if want > 1 and isinstance(val, list):
            if len(val) == 1:
                val = val * want          # ivec2(20) 这类标量构造：GLSL 会广播到每个分量
            elif len(val) != want:
                raise SystemExit("%s 的默认值解析出 %d 个分量（%s 应为 %d）：%r"
                                 % (name, len(val), typ, want, raw))
        out[name] = {"type": typ, "default": val}
    return out


def parse(path: pathlib.Path) -> dict:
    src = path.read_text(encoding="utf-8", errors="replace")
    meta = {}
    for k, rx in META_RE.items():
        m = rx.search(src)
        meta[k] = m.group(1).strip() if m else ""
    return {
        "name": path.stem,
        "src": src,
        "params": parse_params(src),
        "meta": meta,
        "lines": len(src.splitlines()),
    }


def usable(item: dict) -> tuple[bool, str]:
    if item["name"] in SKIP:
        return False, "需要额外贴图"
    if "vec4 transition" not in item["src"]:
        return False, "没有 transition(vec2)"
    if "sampler2D" in item["src"].replace("sampler2D from", "").replace("sampler2D to", ""):
        return False, "额外贴图"
    if len(item["params"]) > MAX_PARAMS:
        return False, "参数过多"
    return True, ""


def build(src_dir: pathlib.Path, only: list[str] | None, out: pathlib.Path) -> tuple[int, int]:
    files = sorted(src_dir.glob("transitions/*.glsl"))
    if not files:
        raise SystemExit("没找到 shader：%s/transitions/*.glsl" % src_dir)
    keep, dropped = [], []
    for f in files:
        item = parse(f)
        if only and item["name"] not in only:
            continue
        ok, why = usable(item)
        (keep if ok else dropped).append((item, why))

    chunk = []
    for item, _ in keep:
        chunk.append(
            '  %s: %s'
            % (
                json.dumps(item["name"]),
                json.dumps(
                    {"src": item["src"], "params": item["params"], "meta": item["meta"]},
                    ensure_ascii=False,
                ),
            )
        )
    body = ",\n".join(chunk)
    stamp = "gl-transitions" + (" · " + ", ".join(sorted(only)) if only else "")
    doc = (
        "/* 生成文件，不要手改。\n"
        " * 来源：%s（MIT）。每个 shader 保留原作者与 License 注释。\n"
        " * 生成器：能力库/动效库/build_gltrans.py\n"
        " * 运行时：assets/vendor/gltrans-kit.js（自己先加载，再加载本文件）\n"
        " */\n"
        "(function (global) {\n"
        "  if (!global.glt || !global.glt.registerAll) return;\n"
        "  global.glt.registerAll({\n%s\n  });\n"
        "})(window);\n" % (stamp, body)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(doc, encoding="utf-8")
    return len(keep), len(dropped)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=pathlib.Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    ap.add_argument("--only", default="")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    only = [s.strip() for s in args.only.split(",") if s.strip()]
    if not args.src.exists():
        raise SystemExit("来源不存在：%s（用 --src 指到 gl-transitions 仓库）" % args.src)

    if args.list:
        rows = []
        for f in sorted(args.src.glob("transitions/*.glsl")):
            item = parse(f)
            ok, why = usable(item)
            if only and item["name"] not in only:
                continue
            rows.append((item["name"], ok, item["meta"].get("tags", ""), len(item["params"]), why))
        for name, ok, tags, n, why in rows:
            print("%s %-22s 参数%-2d %-46s %s" % ("✓" if ok else "×", name, n, tags, why))
        print("\n共 %d 支，可用 %d 支" % (len(rows), sum(1 for r in rows if r[1])))
        return

    n_keep, n_drop = build(args.src, only, args.out)
    size = args.out.stat().st_size
    print("✓ %s" % args.out)
    print("  收录 %d 支，跳过 %d 支，%.1f KB" % (n_keep, n_drop, size / 1024))


if __name__ == "__main__":
    sys.exit(main())
