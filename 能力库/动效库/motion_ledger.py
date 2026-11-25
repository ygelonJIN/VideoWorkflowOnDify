#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨片用量台账：扫成片里的 `/* preset: ID */`，算出"每支片用过哪些编号"。

用法：
    python3 能力库/动效库/motion_ledger.py            # 写 能力库/动效库/usage_ledger.json
    python3 能力库/动效库/motion_ledger.py --check    # 只比对，落后就退出 1

为什么要有：选择层每一支都从零开始，模型看不到"上一支刚用过 T02 五次"，于是
五支片的文字入场、组件、背景收敛到同几张（2026-11-22 实测：331 张卡，五支只用
62 张，组件 38 张只用 7 张）。这里把事实算出来，`gen_catalog.py` 再把最近三支的
`recent_usage` 塞进目录，让模型在同等条件下自己换——**不替它换卡**（§3.3 禁止）。

口径：
- 只扫 `成品/<项目>/index.html`，`试验/`、`失败项目/`、`项目备份/` 不算成片；
- 计数按 `/* preset: ID */` 出现次数，背景卡也在内（背景同样是重复的来源）；
- 台账只记事实，不做任何过滤：哪张卡用了 0 次也照样能在台账里查出来。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
OUT = HERE / "usage_ledger.json"
PROJECTS = REPO / "成品"
PRESET_RE = re.compile(r"/\* preset: ([A-Z]+\d+) \*/")
# 首屏背景：第一块 scene-bg。recent_openers 用它算“最近三支的首页用了哪张”。
FIRST_BG_RE = re.compile(r'class="scene-bg"\s+data-bg="(B\d+)"')


def scan() -> dict:
    films = []
    for html in sorted(PROJECTS.glob("*/index.html")):
        project = html.parent.name
        if project in ("Dify输出", "HTML预览", "试验", "失败项目", "项目备份"):
            continue
        text = html.read_text(encoding="utf-8", errors="replace")
        first_bg = FIRST_BG_RE.search(text)
        used: dict[str, int] = {}
        for cid in PRESET_RE.findall(text):
            used[cid] = used.get(cid, 0) + 1
        films.append({
            "id": project,
            "mtime": int(html.stat().st_mtime),
            "scenes": text.count("<section"),
            "first_bg": first_bg.group(1) if first_bg else None,
            "invocations": sum(used.values()),
            "used": dict(sorted(used.items())),
        })
    films.sort(key=lambda f: (f["mtime"], f["id"]))
    for film in films:
        film.pop("mtime", None)
    return {
        "version": 1,
        "note": "由 能力库/动效库/motion_ledger.py 从成片 index.html 重算，不要手改。"
                "只作报告；gen_catalog.py 每次生成时直接 scan() 现算 recent_usage / recent_openers。",
        "films": films,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    fresh = scan()
    if args.check:
        if not OUT.exists():
            print("缺少 %s，跑一次 motion_ledger.py" % OUT.relative_to(REPO))
            return 1
        old = json.loads(OUT.read_text(encoding="utf-8"))
        if old.get("films") != fresh.get("films"):
            print("台账落后于成片，跑一次 python3 能力库/动效库/motion_ledger.py")
            return 1
        print("台账一致：%d 支片。" % len(fresh["films"]))
        return 0
    OUT.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    distinct = set()
    for film in fresh["films"]:
        distinct |= set(film["used"])
    print("已写入 %s：%d 支片，覆盖 %d 个编号。" % (OUT.relative_to(REPO), len(fresh["films"]), len(distinct)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
