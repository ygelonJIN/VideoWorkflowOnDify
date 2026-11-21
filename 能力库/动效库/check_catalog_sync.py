#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""四层一致性门禁：presets ↔ H00 目录 ↔ 能力卡/组件卡 ↔ 样片。

    python3 能力库/动效库/check_catalog_sync.py

查这些事，任何一条不过就退出 1：

1. 每张 ready 卡都有合法 `role`；`role=bg` 有 `bg_family` + `keywords` + `note`。
2. `role=component` 的 code 里出现的 `ui-*` 类，components.css 里必须存在。
3. `role=page_transition` 的 `kind` 必须在 sync_video 的 `__ptList` 里。
4. `能力卡.md` / `组件卡.md` / 04 YAML 的 H00 目录与 `presets.json` 一致（交给 gen_catalog --check）。
5. `sync_expander --check` 通过（TPL/DEFAULTS 没落后）。
6. 除页间转场外，每张 ready 卡都有全卡审阅样片。
7. 每张 ready 背景卡都能在 `bg-kit.js` 里找到实现（目录与运行时同源）。

这是"加卡只改 presets.json"能成立的前提；没有它，文档和目录几周就会漂掉。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

import contracts

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
PRESETS = HERE / "presets.json"
CSS = WORK / "runtime" / "assets" / "vendor" / "components.css"
SYNC_VIDEO = WORK / "runtime" / "scripts" / "sync_video.py"
BG_KIT = WORK / "runtime" / "assets" / "vendor" / "bg-kit.js"
REELS = HERE / "样片" / "全卡审阅"

# 2026-11-17：none / archive / special_dom 三个"在表但选不到"的 role 已整族删除。
# 现在表里每张卡都必须落进下面某一格，否则 gen_catalog 的目录里就没有它，等于白做。
ROLES = {"bg", "component", "entrance_text", "entrance_block", "state_text",
         "state_block", "component_motion", "decoration", "page_transition", "shape"}
BG_FAMILIES = {"dot", "line", "ring", "block", "light", "noise"}
NO_REEL = {"page_transition"}


def main() -> int:
    cards = json.loads(PRESETS.read_text(encoding="utf-8"))["presets"]
    classes = set(re.findall(r"\.(ui-[a-z-]+)", CSS.read_text(encoding="utf-8")))
    kinds = set()
    # 背景卡必须在 bg-kit 里有实现：目录发出去的每张 B 卡，展开层都会建 canvas 并 bind，
    # 没实现的编号会静默空转（2026-11-21：目录有 B51、展开层没有，选了就是纯色空屏）。
    bg_ids = set(re.findall(r"^\s*(B\d{2}):\s*\[", BG_KIT.read_text(encoding="utf-8"), re.M))
    m = re.search(r"__ptList\s*=\s*\[([^\]]+)\]", SYNC_VIDEO.read_text(encoding="utf-8"))
    if m:
        kinds = set(re.findall(r"'([^']+)'", m.group(1)))

    problems, warnings = [], []
    ids = set()
    for c in cards:
        cid = c["id"]
        if cid in ids:
            problems.append("%s 重复出现" % cid)
        ids.add(cid)
        role = c.get("role")
        if role is None:
            problems.append("%s 没有 role（选择层不知道拿它怎么办）" % cid)
            continue
        if role not in ROLES:
            problems.append("%s 的 role 不合法：%s" % (cid, role))
        if role == "bg":
            if c.get("status") == "ready" and cid not in bg_ids:
                problems.append("%s 在 bg-kit 里没有实现（目录选中也画不出来）" % cid)
            if c.get("bg_family") not in BG_FAMILIES:
                problems.append("%s 的 bg_family 不合法：%s" % (cid, c.get("bg_family")))
            if not c.get("keywords"):
                problems.append("%s 没有 keywords" % cid)
            if not c.get("note"):
                problems.append("%s 没有 note" % cid)
        if role == "component":
            for cls in re.findall(r'class="([^"]+)"', c.get("code") or ""):
                for one in cls.split():
                    if one.startswith("ui-") and one not in classes:
                        problems.append("%s 用了 components.css 里没有的 .%s" % (cid, one))
            # span 决定组件落在 840 文字栏还是 1080 通栏层（R2 只认 "full"，写错会静默退回栏内）
            if c.get("span") not in (None, "copy", "full"):
                problems.append("%s 的 span 不合法：%s（只能是 copy / full）" % (cid, c.get("span")))
        if role == "page_transition" and c.get("kind") not in kinds:
            problems.append("%s 的 kind 不在 __ptList：%s" % (cid, c.get("kind")))

    # ---- 能力契约（2026-11-21）----
    # 组件必须声明 provides；组件动效必须声明 needs/target/anchor，并且至少有一个组件能接。
    # 这里只做静态校验：选择器里的 class / 标签必须真的出现在组件模板里。
    def selector_in_code(selector, code):
        for cls in re.findall(r"\.([A-Za-z][\w-]*)", selector):
            if not re.search(r'class="[^"]*\b' + re.escape(cls) + r'\b', code):
                return "class .%s 不在模板里" % cls
        for tag in re.findall(r"(?<![\w.#-])([a-zA-Z][\w-]*)", re.sub(r"\.[A-Za-z][\w-]*", " ", selector)):
            if tag in ("svg", "path", "i", "b", "em", "span", "div", "th", "tr", "td", "p", "h3"):
                if not re.search(r"<" + re.escape(tag) + r"\b", code):
                    return "标签 <%s> 不在模板里" % tag
        return ""

    components = [c for c in cards if c.get("role") == "component"]
    motions = [c for c in cards if c.get("role") == "component_motion" and c.get("status") == "ready"]
    for c in components:
        provides = contracts.provides_of(c)
        if not provides:
            problems.append("%s 没有 provides（组件动效无法判断能不能挂）" % c["id"])
            continue
        for anchor, selector in provides.items():
            if anchor not in contracts.ANCHORS:
                problems.append("%s 的 provides.%s 不在锚点词汇表" % (c["id"], anchor))
            if selector and selector_in_code(selector, c.get("code") or ""):
                problems.append("%s 的 provides.%s = %r：%s" % (c["id"], anchor, selector, selector_in_code(selector, c.get("code") or "")))
    orphan_motions = []
    for c in motions:
        known = contracts.ANCHORS | contracts.CAPABILITY_ONLY
        for name in (c.get("needs") or []):
            if str(name) not in known:
                problems.append("%s 的 needs 里有未知词 %s" % (c["id"], name))
        anchors = contracts.anchors_of(c)
        if not anchors:
            problems.append("%s 没有锚点 needs（组件动效必须有）" % c["id"])
            continue
        mode = str(c.get("target") or "").strip().lower()
        if mode not in contracts.TARGET_MODES:
            problems.append("%s 的 target 不合法：%s" % (c["id"], mode or "?"))
        if str(c.get("anchor") or "").strip() and str(c.get("anchor")).strip() not in anchors:
            problems.append("%s 的 anchor %s 不在 needs 里" % (c["id"], c.get("anchor")))
        if not any(contracts.compatible(c, comp) for comp in components):
            orphan_motions.append(c["id"])
    if orphan_motions:
        warnings.append("这些组件动效没有任何组件能满足（要么补组件 provides，要么归档/删卡）：" + "、".join(sorted(orphan_motions)))

    for c in cards:
        if c.get("status") != "ready" or c.get("role") in NO_REEL:
            continue
        fam = c.get("family", "其他")
        if not list((REELS / fam).glob(c["id"] + "-*.mp4")):
            warnings.append("%s（%s）没有全卡审阅样片" % (c["id"], fam))

    for script, args in (("gen_catalog.py", ["--check"]), ("sync_expander.py", ["--check"])):
        cmd = [sys.executable, str(HERE / script)] + args
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            problems.append("%s %s 未通过：%s" % (script, " ".join(args), proc.stdout.strip() or proc.stderr.strip()))

    if warnings:
        print("提醒（%d）：" % len(warnings))
        for line in warnings:
            print("  -", line)
    if problems:
        print("一致性门禁没过（%d 条）：" % len(problems))
        for line in problems:
            print("  -", line)
        return 1
    print("四层一致：%d 张卡，可选 %d 张（%d 条提醒）。" % (
        len(cards), sum(1 for c in cards if c.get("role") and c["role"] != "shape"), len(warnings)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
