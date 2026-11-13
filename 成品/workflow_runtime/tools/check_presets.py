#!/usr/bin/env python3
"""校验动效计划与页面里的动效实现是否符合能力白名单。

两个用法：

    python3 check_presets.py --plan motion_plan.json
    python3 check_presets.py --html index.html

--plan   检查 A10 输出的 `motion_plan_json`：
         · 每条 sequences 的 preset 必须在白名单里（或为空）
         · 相邻场景不能重复同一个 preset
         · preset 与 action 的语义要能对上

--html   检查生成的页面：
         · kit.* 只调用白名单里的函数
         · 必须存在字面量的 timeline.from/fromTo/to/set
         · 不能出现 requestAnimationFrame / performance.now / Math.random

退出码 0 = 通过，1 = 有问题（--strict 才拦相邻重复以外的错误，默认只报告）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WHITELIST = {
    "T01": ("enter", "keyword_highlight"),
    "T02": ("enter",),
    "T03": ("enter",),
    "T04": ("keyword_highlight", "highlight"),
    "T05": ("enter",),
    "T06": ("count_up",),
    "T07": ("enter",),
    "T08": ("enter",),
    "T09": ("enter",),
    "T10": ("enter",),
    "T11": ("enter",),
    "X01": ("state_change", "row_reveal"),
    "X02": ("state_change", "status_update"),
    "P01": ("zoom_focus", "cursor_move"),
    "P02": ("zoom_focus",),
    "P03": ("zoom_focus",),
    "W01": ("enter", "zoom_focus"),
    "G02": ("state_change", "row_reveal", "enter"),
    "I01": ("click", "cursor_move", "state_change"),
    "I02": ("click", "cursor_move", "state_change"),
    "G03": ("state_change", "zoom_focus", "enter"),
    "Z02": ("zoom_focus", "enter"),
    "S12": ("state_change", "row_reveal"),
    "W02": ("zoom_focus", "enter"),
    "Z01": ("zoom_focus", "enter"),
    "U01": ("state_change", "row_reveal"),
    "U02": ("state_change",),
    "U03": ("state_change", "row_reveal"),
    "U04": ("status_update",),
    "U05": ("row_reveal", "state_change"),
}

# 2026-11-13：白名单不再是手抄的第二份清单——以 presets.json 为准，
# 表里存在的编号一律合法；语义映射只对下面这张表里登记过的卡做检查。
import json as _json
from pathlib import Path as _Path

def _load_known_ids():
    for up in _Path(__file__).resolve().parents:
        cand = up / "能力库" / "动效库" / "presets.json"
        if cand.exists():
            try:
                data = _json.loads(cand.read_text(encoding="utf-8"))
                return {c["id"] for c in data.get("presets", []) if c.get("status") == "ready"}
            except Exception:
                return set()
    return set()

KNOWN_IDS = _load_known_ids()

KIT_FUNCS = {"split", "pointer", "spring", "cubicBezier", "seeded"}


def check_plan(plan: dict) -> list[str]:
    problems: list[str] = []
    seqs = [s for s in (plan.get("sequences") or []) if isinstance(s, dict)]
    if not seqs:
        return ["sequences 为空，A10 没产出动效计划"]

    by_scene: dict[str, list[str]] = {}
    for seq in seqs:
        mid = seq.get("motion_id", "?")
        preset = str(seq.get("preset") or "").strip()
        action = str(seq.get("action") or "").strip()
        scene = str(seq.get("scene_id") or "").strip()
        if not preset:
            problems.append(f"{mid}（{scene}）没有 preset")
            continue
        if preset not in WHITELIST:
            if preset in KNOWN_IDS:
                by_scene.setdefault(scene, []).append(preset)
                continue
            problems.append(f"{mid}（{scene}）的 preset「{preset}」不在能力表")
            continue
        if action and action not in WHITELIST[preset]:
            problems.append(
                f"{mid}（{scene}）preset {preset} 与 action {action} 语义不符，允许：{'/'.join(WHITELIST[preset])}")
        by_scene.setdefault(scene, []).append(preset)

    for scene, presets in by_scene.items():
        if len(presets) > 2:
            problems.append(f"{scene} 用了 {len(presets)} 个 preset（上限 2）：{'/'.join(presets)}")

    order = []
    for seq in seqs:
        scene = str(seq.get("scene_id") or "")
        if scene and scene not in order:
            order.append(scene)
    for left, right in zip(order, order[1:]):
        a, b = set(by_scene.get(left, [])), set(by_scene.get(right, []))
        same = a & b
        if same:
            problems.append(f"相邻场景 {left} 与 {right} 重复使用 preset：{'/'.join(sorted(same))}")
    return problems


def check_html(doc: str) -> list[str]:
    problems: list[str] = []
    for match in re.finditer(r"\bkit\.([A-Za-z_$][\w$]*)", doc):
        name = match.group(1)
        if name not in KIT_FUNCS:
            problems.append(f"kit.{name} 不在白名单（允许：{'/'.join(sorted(KIT_FUNCS))}）")
    if not re.search(r"\b(?:master|timeline)\.(?:from|fromTo|to|set)\s*\(", doc):
        problems.append("没有字面量的 timeline.from/fromTo/to/set，契约会判为无可寻址时间线")
    for bad in ("requestAnimationFrame", "performance.now", "Math.random"):
        if bad + "(" in doc:
            problems.append(f"出现 {bad}(，违反确定性要求")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan")
    ap.add_argument("--html")
    args = ap.parse_args()
    if not args.plan and not args.html:
        ap.error("至少给一个 --plan 或 --html")

    failed = False
    if args.plan:
        path = Path(args.plan)
        raw = path.read_text(encoding="utf-8")
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            plan = json.loads(raw[start:end + 1]) if 0 <= start < end else {}
        problems = check_plan(plan)
        print(f"[plan] {path}: {len(plan.get('sequences') or [])} 条节拍，{len(problems)} 个问题")
        for item in problems:
            print("  - " + item)
        failed = failed or bool(problems)

    if args.html:
        path = Path(args.html)
        problems = check_html(path.read_text(encoding="utf-8"))
        print(f"[html] {path}: {len(problems)} 个问题")
        for item in problems:
            print("  - " + item)
        failed = failed or bool(problems)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
