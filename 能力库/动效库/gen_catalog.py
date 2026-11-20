#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 presets.json 生成「选择层」：H00 的 catalog、能力卡.md、组件卡.md。

选择层 = 模型能选哪些编号。它只由每张卡的 `role` 决定：

    bg              背景卡（catalog.background）
    component       组件卡（catalog.component，结构见 组件卡.md）
    entrance_text   文字入场（catalog.motion.entrance_text）
    entrance_block  整块入场
    state_text      文字状态变化
    state_block     块级状态变化
    component_motion 组件动效
    decoration      只能给装饰元素
    page_transition 页间转场（catalog.page_transition，由 H01T 选、H03 生成）

表里没有"选了也用不上"的卡：每张 ready 卡都必须落进上面某一格。

用法：
    python3 能力库/动效库/gen_catalog.py            # 写入 YAML 与两份 md
    python3 能力库/动效库/gen_catalog.py --check    # 只检查，不一致退出 1

这张脚本是唯一被允许写 H00 目录与 能力卡.md / 组件卡.md 的地方。
手改这两个 md 或手改 H00 的 CATALOG 块，下次生成就会被覆盖。
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import yaml_nodes  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
PRESETS = HERE / "presets.json"
YAML = REPO / "Dify工作流" / "04_黑帧口播_分组生成.yml"
# 01 = 04 + 数字人小窗，两份共用能力层：H00 目录 / H02S 组件段 / A10 编号清单都要一起写，
# 只写 04 会让 01 的目录停在加卡之前（2026-11-17 发现：01 里还留着已删的 special_dom）。
YAMLS = [YAML, REPO / "Dify工作流" / "01_有数字人完整视频工作流.yml"]
CARDS_MD = HERE / "能力卡.md"
COMP_MD = HERE / "组件卡.md"

FAMILY_ORDER = ["入场", "状态", "字形", "版面", "离场", "结构", "照片",
                "材质", "镜头", "交互", "绘制", "UI", "背景", "页间转场", "组件"]

MOTION_ROLES = ["entrance_text", "entrance_block", "state_text", "state_block",
                "component_motion", "decoration"]

HARD_RULES = """## 四条硬规则（v2，2026-11-13）

1. **字由 HTML 承载**：canvas 里不放文字。
2. **每屏一个主运动**，其余是次级；相邻两屏的主运动不能是同一张卡。切点前 0.3–0.5 秒要有收束（离场或自带回位），**不强制用 X 卡**。
3. **动效由时间线驱动**，任意一帧可 seek 复现；禁 `requestAnimationFrame`、`performance.now`、`Math.random`、`yoyo`/`repeat` 无限循环（按 `t` 的周期函数不算循环）。
4. **模型写数据不写实现**：只给编号 + 目标 `data-anim` 名 + 时序；坐标、目标框、路径一律由场景 HTML 给。
"""

HEADER = """# 动效能力卡（自动生成）

> 本文件由 `能力库/动效库/gen_catalog.py` 从 `presets.json` 生成，**不要手改**。
> 改内容 → 改 `presets.json` → 跑 `python3 能力库/动效库/gen_catalog.py`。
> 组件结构见 [`组件卡.md`](组件卡.md)；来源与归档见 [`来源台账.md`](来源台账.md)。
> 选择层只认每张卡的 `role`；表里每张 ready 卡都在目录里。

"""


def load():
    return json.loads(PRESETS.read_text(encoding="utf-8"))["presets"]


def catalog_of(cards):
    bg, comp, pt = {}, {}, {}
    motion = collections.OrderedDict((r, []) for r in MOTION_ROLES)
    for c in sorted(cards, key=lambda x: x["id"]):
        role = c.get("role") or ""
        cid = c["id"]
        if role == "bg":
            bg[cid] = {"name": c.get("name", ""), "note": c.get("note", ""),
                       "family": c.get("bg_family", "")}
        elif role == "component":
            comp[cid] = {"name": c.get("name", ""), "note": c.get("note", "")}
        elif role == "page_transition":
            pt[cid] = {"name": c.get("name", ""), "note": c.get("note", ""),
                       "kind": c.get("kind", "")}
        elif role in motion:
            motion[role].append(cid)
    return {
        "background": bg,
        "component": comp,
        "motion": {k: v for k, v in motion.items()},
        "page_transition": pt,
    }


def _fmt_params(params):
    if not params:
        return "—"
    return " · ".join("%s=%s" % (k, v) for k, v in params.items())


def render_cards_md(cards):
    out = [HEADER, HARD_RULES]
    by_family = collections.defaultdict(list)
    shapes = 0
    for c in cards:
        if not c.get("role"):
            continue
        # role=shape 是图形素材（整屏 SVG / mermaid 形状），不进选择层：
        # 模型选不到，就不会再出现"整屏坐标系的图被塞进 840 文字栏"。
        if c["role"] == "shape":
            shapes += 1
            continue
        by_family[c.get("family", "未分类")].append(c)

    order = [f for f in FAMILY_ORDER if f in by_family] + \
            [f for f in by_family if f not in FAMILY_ORDER]
    role_label = {"entrance_text": "文字入场", "entrance_block": "整块入场",
                  "state_text": "文字状态", "state_block": "块级状态",
                  "component_motion": "组件动效", "decoration": "只给装饰元素",
                  "page_transition": "页间转场", "bg": "背景", "component": "组件"}
    out.append("## 可选总表（按 role）\n")
    out.append("| role | 数量 | 编号 |")
    out.append("|---|---:|---|")
    by_role = collections.defaultdict(list)
    for c in cards:
        r = c.get("role")
        if r in role_label:
            by_role[r].append(c["id"])
    for r in ("entrance_text", "entrance_block", "state_text", "state_block",
              "component_motion", "decoration", "bg", "component", "page_transition"):
        ids = sorted(by_role.get(r, []))
        if ids:
            out.append("| `%s` %s | %d | %s |" % (r, role_label[r], len(ids), " ".join(ids)))
    out.append("")

    out.append("## 各族明细\n")
    for fam in order:
        items = sorted(by_family[fam], key=lambda x: x["id"])
        out.append("### %s\n" % fam)
        if fam == "组件":
            out.append("组件只给编号，HTML 片段见 [`组件卡.md`](组件卡.md)。\n")
            out.append("| 编号 | 名字 | 什么时候用 |")
            out.append("|---|---|---|")
            for c in items:
                out.append("| %s | %s | %s |" % (c["id"], c.get("name", ""), c.get("note", "")))
            out.append("")
            continue
        if fam == "背景":
            out.append("| 编号 | 名字 | 视觉族 | 适合什么内容 | 触发词 |")
            out.append("|---|---|---|---|---|")
            for c in items:
                kw = "、".join(c.get("keywords") or [])
                out.append("| %s | %s | %s | %s | %s |" % (
                    c["id"], c.get("name", ""), c.get("bg_family", ""), c.get("note", ""), kw))
            out.append("")
            continue
        if fam == "页间转场":
            out.append("页间转场由 `H01T_转场设计` 选编号，`H03` 按切点表生成 `window.__pt` 调用。\n")
            out.append("| 编号 | 名字 | kind | 用在哪 | 别用在哪 |")
            out.append("|---|---|---|---|---|")
            for c in items:
                out.append("| %s | %s | `%s` | %s | %s |" % (
                    c["id"], c.get("name", ""), c.get("kind", ""), c.get("use", ""), c.get("avoid", "")))
            out.append("")
            continue
        out.append("| 编号 | 名字 | 角色 | 参数 | 用在哪 | 别用在哪 |")
        out.append("|---|---|---|---|---|---|")
        for c in items:
            out.append("| %s | %s | %s | %s | %s | %s |" % (
                c["id"], c.get("name", ""), role_label.get(c.get("role"), c.get("role", "")),
                _fmt_params(c.get("params")), c.get("use", ""), c.get("avoid", "")))
        out.append("")

    if shapes:
        out.append("> 另有 %d 张图形素材（`role=shape`，整屏 SVG / mermaid 形状）留在 `presets.json`，"
                   "**不进选择层**：它们按 1080×1920 整屏坐标画，塞进 840 栏必然出画布。" % shapes)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render_comp_md(cards):
    comps = sorted((c for c in cards if c.get("role") == "component"), key=lambda x: x["id"])
    out = ["# 组件卡（自动生成）\n",
           "> 由 `能力库/动效库/gen_catalog.py` 从 `presets.json` 生成，**不要手改**。",
           "> 样式在 `assets/vendor/components.css`，本地渲染前自动注入。**只写下面这些结构，不自己加样式、不加图形。**",
           "> 变量只用 `--ui-*`；同一支片子只改颜色与圆角，不改结构。",
           "> 组件**逐条入场**，不要整块淡入。\n",
           "## 总表\n",
           "| 编号 | 名字 | 什么时候用 |",
           "|---|---|---|"]
    for c in comps:
        out.append("| %s | %s | %s |" % (c["id"], c.get("name", ""), c.get("note", "")))
    out.append("")
    for c in comps:
        out.append("## %s %s\n" % (c["id"], c.get("name", "")))
        if c.get("note"):
            out.append(c["note"] + "\n")
        out.append("```html\n%s\n```\n" % (c.get("code") or "").rstrip())
    return "\n".join(out).rstrip() + "\n"


def splice_h00(code: str, blob: str) -> str:
    """把 CATALOG 块写进 H00；第一次运行时顺手删掉三张手写字典。"""
    block = ('    # >>> CATALOG（由 gen_catalog.py 生成，勿手改）\n'
             '    CATALOG = json.loads(r"""%s""")\n'
             '    # <<< CATALOG\n' % blob)
    if "# >>> CATALOG" in code:
        i0 = code.index("    # >>> CATALOG")
        i1 = code.index("    # <<< CATALOG\n") + len("    # <<< CATALOG\n")
        return code[:i0] + block + code[i1:]
    # 首次：删掉 BG_CARDS / COMPONENT_CARDS / MOTION_CATALOG 三块
    i0 = code.index("    BG_CARDS = {")
    i1 = code.index("    # 逐屏载荷：")
    code = code[:i0] + block + "\n" + code[i1:]
    # 首次：目录不再手拼，直接用生成的
    j0 = code.index("    catalog = {")
    j1 = code.index("    result.update({", j0)
    code = code[:j0] + (
        "    catalog = dict(CATALOG)\n"
        "    catalog[\"scene_ids\"] = [entry[\"scene_id\"] for entry in ledger]\n\n"
    ) + code[j1:]
    return code


def h00_code(path=None):
    return yaml_nodes.get_code("h00", path)


def write_h00(new_code: str, path=None) -> None:
    yaml_nodes.set_code("h00", new_code, path)


INV_START = "<!-- CATALOG:INVENTORY:START -->"
INV_END = "<!-- CATALOG:INVENTORY:END -->"

ROLE_TITLES = {
    "entrance_text": "文字入场", "entrance_block": "整块入场",
    "state_text": "文字状态", "state_block": "块级状态",
    "component": "组件结构（只给编号，见 组件卡.md）", "component_motion": "组件动效",
    "decoration": "只能给装饰元素", "page_transition": "页间转场（归转场节点，不在这里写）",
    "bg": "背景（归 H01X）",
}


def render_inventory_prompt(cards):
    """A10 动效计划能选的编号全量：只列选择层，从 presets 现算。"""
    out = [INV_START]
    by_role = collections.defaultdict(list)
    for c in cards:
        if c.get("role"):
            by_role[c["role"]].append(c)
    for role in ("entrance_text", "entrance_block", "state_text", "state_block",
                 "component", "component_motion", "decoration", "page_transition", "bg"):
        items = by_role.get(role)
        if not items:
            continue
        out.append("- **%s**：%s" % (
            ROLE_TITLES.get(role, role),
            "、".join("%s %s" % (c["id"], c.get("name", ""))
                     for c in sorted(items, key=lambda x: x["id"]))))
    out.append(INV_END)
    return "\n".join(out)


COMP_START = "<!-- CATALOG:COMPONENTS:START -->"
COMP_END = "<!-- CATALOG:COMPONENTS:END -->"


def render_components_prompt(cards):
    """H02S 单屏节点里那段组件结构，必须和 presets 同源，否则模型写出来的类名会过期。"""
    comps = sorted((c for c in cards if c.get("role") == "component"), key=lambda x: x["id"])
    out = [COMP_START, ""]
    for c in comps:
        out.append("### %s %s" % (c["id"], c.get("name", "")))
        out.append("")
        if c.get("note"):
            out.append(c["note"])
            out.append("")
        out.append("```html")
        out.append((c.get("code") or "").rstrip())
        out.append("```")
        out.append("")
    out.append(COMP_END)
    return "\n".join(out)


def splice_between(text, block, start, end):
    if start in text and end in text:
        i0 = text.index(start)
        i1 = text.index(end) + len(end)
        return text[:i0] + block + text[i1:]
    return text


def splice_components_prompt(text, block):
    return splice_between(text, block, COMP_START, COMP_END)


def splice_inventory_prompt(text, block):
    return splice_between(text, block, INV_START, INV_END)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查是否已同步")
    args = ap.parse_args()

    cards = load()
    cat = catalog_of(cards)
    blob = json.dumps(cat, ensure_ascii=False)
    if '"""' in blob:
        raise SystemExit("目录里出现三引号，无法安全嵌入 H00")

    prompt_block = render_components_prompt(cards)
    inv_block = render_inventory_prompt(cards)
    md_cards = render_cards_md(cards)
    md_comp = render_comp_md(cards)

    diffs, plans = [], []
    for path in YAMLS:
        code = h00_code(path)
        new_code = splice_h00(code, blob)
        compile(new_code, "h00", "exec")
        h02s_text = yaml_nodes.get_prompt_text("h02s", path)
        h02s_new = splice_components_prompt(h02s_text, prompt_block)
        # A10 编号清单段：2026-11-18 起工作流里已经没有 a10 节点（A10/A11 并入 A12 与 A09）。
        # 节点不在就跳过这一段，不当成错误——否则整个加删卡链路会被一个不存在的节点卡死。
        try:
            a10_text = yaml_nodes.get_prompt_text("a10", path)
        except SystemExit:
            a10_text = None
        a10_new = splice_inventory_prompt(a10_text, inv_block) if a10_text is not None else None
        plans.append((path, code, new_code, h02s_text, h02s_new, a10_text, a10_new))
        if new_code != code:
            diffs.append("%s 的 H00 目录" % path.name)
        if h02s_new != h02s_text:
            diffs.append("%s 的 H02S 组件段" % path.name)
        if a10_text is not None and a10_new != a10_text:
            diffs.append("%s 的 A10 编号清单" % path.name)

    if not CARDS_MD.exists() or CARDS_MD.read_text(encoding="utf-8") != md_cards:
        diffs.append("能力卡.md")
    if not COMP_MD.exists() or COMP_MD.read_text(encoding="utf-8") != md_comp:
        diffs.append("组件卡.md")

    n_sel = (len(cat["background"]) + len(cat["component"])
             + len(cat["page_transition"]) + sum(len(v) for v in cat["motion"].values()))

    if args.check:
        if diffs:
            print("未同步：" + "、".join(diffs) + "；请运行 gen_catalog.py")
            return 1
        print("已同步：%d 张卡，可选 %d 张（两份 YAML 一致）" % (len(cards), n_sel))
        return 0

    for path, code, new_code, h02s_text, h02s_new, a10_text, a10_new in plans:
        if new_code != code:
            write_h00(new_code, path)
        if h02s_new != h02s_text:
            yaml_nodes.set_prompt_text("h02s", h02s_new, path)
        if a10_text is not None and a10_new != a10_text:
            yaml_nodes.set_prompt_text("a10", a10_new, path)
    CARDS_MD.write_text(md_cards, encoding="utf-8")
    COMP_MD.write_text(md_comp, encoding="utf-8")
    print("已写入：能力卡.md / 组件卡.md / H00 目录（两份 YAML）；可选 %d 张（背景 %d / 组件 %d / 转场 %d / 动效 %d）"
          % (n_sel, len(cat["background"]), len(cat["component"]), len(cat["page_transition"]),
             sum(len(v) for v in cat["motion"].values())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
