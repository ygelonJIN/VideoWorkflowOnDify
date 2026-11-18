#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一栏式之后全力改提示词（2026-11-18）。

1. H02SM：每屏每个内容元素各一条入场（不再固定 2 条）
2. H01X：不许按目录顺序挑背景/组件；entrance 会被展开到每个元素
3. A08：不再写 composition（构图由本地固定规则生成）
4. H02S：不再输出 layout（zone / align / scale）
"""
import pathlib
import sys

ROOT = pathlib.Path("/Volumes/TUF ESD-T1A Media/视频工作流")
FILES = [ROOT / "Dify工作流/04_黑帧口播_分组生成.yml",
         ROOT / "Dify工作流/01_有数字人完整视频工作流.yml"]


def esc(t: str) -> str:
    """转成 YAML 双引号字符串里的形态。"""
    return t.replace('"', '\\"').replace("\n", "\\n")


PAIRS = []

# ---------- H02SM：每元素一条入场 ----------
PAIRS.append((
    "2. 每屏输出 **2 条**，顺序固定：先入场，再状态变化。唯一例外是 `motion_budget.state` 为空：这时只输出入场，并写 `\"budget_gap\": \"state\"`，让本地点名 H01X 补编号——静默只给一条是错的，编一个编号顶上也是错的。",
    """2. **入场条数 = 本屏内容元素数量**：`copy` 每条 `role` 各一条、`components` 每个 `anim` 各一条、有照片时 `media` 一条（`bg` / `scrim` 不算）。**一个元素少一条，它就停在最终态、直接出现在画面上**——观众看到的是"东西一上来就全在"。这些入场之外，再写至少一条状态变化，落在这一屏最该"从 A 变成 B"的那个元素上。`motion_budget.state` 为空时写 `"budget_gap": "state"`，让本地点名 H01X 补编号。"""
))

PAIRS.append((
    "2. 2 条：入场 + 状态变化；有组件时再加 1 条组件动效。**`motion_budget.state` 为空时**只输出入场那条，并在 JSON 顶层写 `\"budget_gap\": \"state\"`——不要自己编一个编号顶上，也不要因为少一条就把入场也省掉。",
    """2. 条数自检：先把本屏内容元素列全（`copy[].role` + `components[].anim` + `media`），**每一个都必须有一条入场**，再确认至少一条状态变化。`motion_budget.state` 为空时写 `"budget_gap": "state"`，不要编编号顶替。条数 = 元素数 + 状态条数。"""
))

PAIRS.append((
    "3. 每条 `target` 都在规格里出现过（`copy[].role`、`components[].anim`、`media` 三选一）。动手前先把本屏 `copy[].role` 抄成一行（例如 `lead, body`），再逐个 target 与这一行**逐字**比对；不在这一行里的 target 一律不写。",
    """3. `target` 只能取本屏真实存在的元素名（`copy[].role`、`components[].anim`、`media`）。动手前先把本屏内容元素抄成一行（例如 `title, body, card-1, media`），**这一行有几个就输出几条入场**，一个不漏、一个不加。"""
))

# ---------- H01X：不许按顺序 ----------
PAIRS.append((
    "1. **background**：从 `catalog.background` 里选一张。先看这一句讲的是什么对象、什么情绪，再找 `note` 对得上的那张。**相邻两屏不许同 `family`**；全片尽量不重复，屏数超过目录张数才允许复用。`background_why` 一句话写清\"这句的什么东西让这张卡成立\"，不许写\"按顺序\"\"顺手选\"。",
    """1. **background**：从 `catalog.background` 里选一张。**目录里的编号是文件顺序，跟内容无关，不许按编号往下挑**——每屏都重新读一遍 `note`，先看这一句讲的是什么对象、什么情绪，再找画的东西对得上的那张。第一屏尤其不许顺手拿目录第一张（B23）：第一屏是全片的定调，选错了后面全在将就。**相邻两屏不许同 `family`**；全片尽量不重复，屏数超过目录张数才允许复用。`background_why` 必须写清"这张卡画的是什么、为什么对上这一句"；写不出具体的画面和语义对应，就说明选错了，换下一张。"""
))

PAIRS.append((
    "3. **entrance**：文字主体用 `entrance_text`，整块/卡片/照片用 `entrance_block`。相邻两屏不许同一个编号。",
    """3. **entrance**：文字主体用 `entrance_text`，整块/卡片/照片用 `entrance_block`。**这一屏的 `entrance` 会被展开到本屏每一个内容元素上**（H02SM 逐元素一条），所以要选一张"作用在任意元素上都成立"的卡（位移/淡入/揭幕这一类）；只对某一类元素有效的卡（拆字、划线、数值滚动）不要选。相邻两屏不许同一个编号。"""
))

# ---------- A08：不写 composition ----------
PAIRS.append((
    "7. **每一屏必须写 `composition`，构图逐屏变。** 全片只有你一个人能同时看到所有屏，构图分配必须在这里一次做完，不能留给后面的场景组各自即兴——它们互相看不见，最后一定长成一个样。",
    """7. **不要写构图。** 版面只有一栏（左 120、宽 840、上 150、内容底线 1533），由本地固定规则生成，逐屏完全相同。`composition` / `text_zone` / `align` / `scale` / `family` 这些字段不再接受，写了也会被忽略——你要做的是写清这一屏讲什么、画面承担者是什么，不要安排位置和字号。"""
))

# ---------- H02S：不输出 layout ----------
PAIRS.append((
    "- `layout`：从 `scene_json.composition` 抄 `text_zone` / `align`。`scale` 只认 `vertical` 一个值（这一屏要竖排才写），写别的无效——字号不由它决定。",
    "- **不要写 `layout`。** 版面只有一栏，字号、位置、对齐全部由本地按内容算，模型写什么都不生效。"
))

PAIRS.append((
    '    "layout": {"zone": "center-middle", "align": "center", "scale": "两行块"},\n',
    ""
))

PAIRS.append((
    "5. `scene_id`、`bg`、`layout` 与输入一致。",
    "5. `scene_id`、`bg` 与输入一致；`layout` 不许出现。"
))

report = []
for path in FILES:
    s = path.read_text(encoding="utf-8")
    name = path.name
    for i, (old, new) in enumerate(PAIRS, 1):
        hit = esc(old) in s
        if not hit:
            report.append(f"{name} 第 {i} 处：未找到")
            continue
        s = s.replace(esc(old), esc(new))
        report.append(f"{name} 第 {i} 处：✓")
    path.write_text(s, encoding="utf-8")

print("\n".join(report))
