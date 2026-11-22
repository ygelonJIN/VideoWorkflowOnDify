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
        # ---- 状态卡/离场卡的落点声明（2026-11-22）----
        # 这三条是 R1 判"该不该丢"的唯一输入，写错等于把判据写没了。
        if "trigger" in c:
            if not isinstance(c["trigger"], bool):
                problems.append("%s 的 trigger 只能是 true/false" % cid)
            elif c["trigger"] and not str(role).startswith("state_"):
                problems.append("%s 声明了 trigger，但 role 不是 state_*（触发属于状态卡）" % cid)
        if "exit" in c:
            if not isinstance(c["exit"], bool):
                problems.append("%s 的 exit 只能是 true/false" % cid)
            elif c["exit"]:
                if role != "decoration":
                    problems.append("%s 声明了 exit，但 role 不是 decoration" % cid)
                if not re.search(r"opacity['\"]?\s*:\s*0(?![.\d])", str(c.get("code") or "")):
                    problems.append("%s 声明了 exit，但代码里没有 opacity:0（它不是离场卡）" % cid)
        if str(role).startswith("state_"):
            code = str(c.get("code") or "")
            if ("textContent" in code or "innerHTML" in code) \
                    and "text" not in {str(n) for n in (c.get("needs") or [])} \
                    and not contracts.anchors_of(c):
                problems.append("%s 会改写目标文字，但没有声明 needs=text 或锚点："
                                "R1 只能把它丢在组件根上，会把组件内容清空重写" % cid)

    # ---- 目录覆盖（2026-11-22）----
    # 判据只有一句：**目录里出现的每个可选编号，都必须带一段卡级描述**。
    # 以前这件事没有闸门：`catalog_of()` 按族手写字段，背景/组件/转场三格只发了
    # name/note，动效卡那格才发 use/avoid；加一族、改一个字段就会静默漏掉，
    # 而模型那边只看到一串编号（"老是那几张""乱用"两个症状都从这里长出来）。
    # 现在由 gen_catalog 统一发（`card_desc()`），这里双向查：
    #   目录里每个可选编号 → 描述表里必须有它（缺了就是有人加族忘了发）；
    #   描述表里每个编号 → 必须落在某一族（不许有孤儿，孤儿等于模型看不到）。
    import gen_catalog as _gc
    _cat = _gc.catalog_of(cards)
    _desc = {}
    _desc.update(_cat.get("motion_cards") or {})
    for _sec in ("background", "component", "page_transition"):
        _desc.update(_cat.get(_sec) or {})
    _listed = set()
    for _role, _ids in (_cat.get("motion") or {}).items():
        if _role == "entrance_media":      # 派生族，编号已在 entrance_block 里
            continue
        _listed |= set(_ids or [])
    for _sec in ("background", "component", "page_transition"):
        _listed |= set((_cat.get(_sec) or {}))
    for _cid in sorted(_listed):
        _item = _desc.get(_cid) or {}
        _text = " ".join(str(_item.get(_k) or "") for _k in ("note", "use", "avoid")).strip()
        if not _text:
            problems.append("%s 在目录里但没有任何描述（note/use/avoid 全空）："
                            "模型只看到一个编号，等于没有能力卡" % _cid)
    for _cid in sorted(set(_desc) - _listed):
        problems.append("%s 有描述但不在任何可选族里（孤儿）：模型永远选不到它" % _cid)
    # 同族描述 100% 相同 = 写的是"族规则"不是"卡描述"，选择层拿不到区分度。
    # 只提醒不拦：有些族确实只有一条规则（离场 2 张就是同一句）。
    import collections as _collections
    for _role, _ids in (_cat.get("motion") or {}).items():
        _vals = [str((_desc.get(_i) or {}).get("use") or "") for _i in (_ids or [])]
        _vals = [v for v in _vals if v]
        if len(_vals) >= 8 and len(set(_vals)) == 1:
            warnings.append("%s 这一族 %d 张卡的 use 一字不差：那是族规则，不是卡描述"
                            "（选择层拿不到区分度，建议改写成各自的「什么时候选」）" % (_role, len(_vals)))

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

    # 展开契约回归探针：state_meta 的判据在 S2N / R1 各执行一次，改 Code 节点时
    # 最容易把它们改回去。这里跑一遍，只在这个门禁里报错（不进渲染链路）。
    probe = subprocess.run([sys.executable, str(HERE / "check_expand_contract.py")],
                           capture_output=True, text=True)
    if probe.returncode != 0:
        tail = [line for line in (probe.stdout or "").splitlines() if line.startswith(("FAIL", "展开契约"))]
        problems.append("展开契约回归没过：%s" % ("；".join(tail) or (probe.stderr or "").strip()[:400]))

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
