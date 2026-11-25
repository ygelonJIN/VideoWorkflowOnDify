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
    page_transition 页间转场（catalog.page_transition，由 S2 给偏好、R3 逐刀生成）

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
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import yaml_nodes  # noqa: E402
import component_slots  # noqa: E402
import contracts  # noqa: E402
import motion_ledger  # noqa: E402

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
                "component_motion", "decoration", "exit"]

# 跨片用量台账（2026-11-22）：放在定义层外面、由 motion_ledger.py 扫成片重算。
# 目的只有一个：把"最近几支用过哪些编号"喂给选择层，让模型在同等条件下换别的。
# 这里不替模型换卡（那是 §3.3 禁止的），只把事实摆到它面前。
# 2026-11-23：不再读 usage_ledger.json（会过期），每次生成时直接 scan() 现算。
RECENT_FILMS = 3

HARD_RULES = """## 七条硬规则（v3，2026-11-22）

1. **字由 HTML 承载**：canvas 里不放文字。
2. **每屏一个主运动**，其余是次级；相邻两屏的主运动不能是同一张卡。切点前 0.3–0.5 秒要有收束（用 `exit` 族的卡，或元素自带回位）。
3. **动效由时间线驱动**，任意一帧可 seek 复现；禁 `requestAnimationFrame`、`performance.now`、`Math.random`、`yoyo`/`repeat` 无限循环（按 `t` 的周期函数不算循环）。
4. **模型写数据不写实现**：只给编号 + 目标 `data-anim` 名 + 时序；坐标、目标框、路径一律由场景 HTML 给。
5. **状态卡只能改它自己的那个元素**：`writes=content`（会改写目标文字）的卡只许落在文字节点或组件声明的锚点（叶子）上；落在组件根上会把组件拆掉。没有锚点的 `overlay` 卡（自己 append 元素）同理，不许落在组件根。
6. **触发型状态卡必须配后续**（`catalog.state_meta[编号].trigger`）：点击/勾选/拖动/切换/状态灯只是"发生了一件事"，同一屏必须再给一条 `then` 说明结果；给不出就别用这张卡——孤零零一次点击不算动效，算错。
7. **标注卡讲的是语义，不是装饰**：叉/划掉 = 否掉一个具体做法（陈述现象不算否定），括号/框 = 给一句旁注或归组（旁边没有那句旁注就别画），圈/荧光/下划线 = 强调一个关键词（不是整句），进度条/数值条 = 有真实数字（`state_meta.requires_number`）。选卡先读 `catalog.motion_cards` 的 `use`/`avoid`；**标注不许落标题**，全片 `deco` ≤ ⌈屏数÷3⌉ 且相邻两屏不都写。
"""

HEADER = """# 动效能力卡（自动生成）

> 本文件由 `能力库/动效库/gen_catalog.py` 从 `presets.json` 生成，**不要手改**。
> 改内容 → 改 `presets.json` → 跑 `python3 能力库/动效库/gen_catalog.py`。
> 组件结构见 [`组件卡.md`](组件卡.md)；来源与归档见 [`来源台账.md`](来源台账.md)。
> 选择层只认每张卡的 `role`；表里每张 ready 卡都在目录里。

"""


def load():
    return json.loads(PRESETS.read_text(encoding="utf-8"))["presets"]


# 照片带能接的入场（2026-11-21）：这是一格**派生族**，不是新 role。
# 为什么要有：`entrance_block` 里有 14 张卡，S2 只能从那里挑，于是 G09（Flip +
# gridTemplateColumns + 动 _t.children 的版面卡）落到了单张 <img> 上，整张卡退化成
# "屏首藏起来、2.6 秒后才淡入"，成片里那段就是一块空占位板。
# 判据只看卡自己，不看名字：
#   - 只动根节点（不碰 _t.children / Flip / gridTemplateColumns，也不按内部结构查元素）；
#   - 不依赖元素自带属性（getAttribute('data-…')），照片框没有这些属性，卡会静默空转；
#   - 声明能落照片/整块（needs 里有 photo/media/img/block），或者 presets 里显式
#     media_safe: true（T41 这类"任何内容都能用"的纯根变换）。
def media_entrance_ok(card):
    if str(card.get("role") or "") != "entrance_block":
        return False
    code = str(card.get("code") or "")
    if any(k in code for k in (".children", "Flip.", "gridTemplateColumns")):
        return False
    if any(sel != "{{sel}}" for sel in re.findall(r"querySelectorAll?\('([^']*)'\)", code)):
        return False
    if re.search(r"getAttribute\('data-", code):
        return False
    if "media_safe" in card:
        return bool(card["media_safe"])
    caps = {str(n) for n in (card.get("needs") or [])}
    return bool(caps & {"photo", "media", "img", "block"}) and not (caps & {"ui", "text", "svg"})


def media_entrances(cards):
    return sorted(c["id"] for c in cards
                  if c.get("status") == "ready" and media_entrance_ok(c))


def state_meta_of(cards):
    """状态卡的能力声明（2026-11-22）。

    writes  卡对目标做了什么：
              content = 改写目标文字（textContent / innerHTML）
              overlay = 往目标里 append 自己造的元素
              style   = 只改目标自己的样式/变换
    trigger 是不是"发生了一件事"的交互市值（点击/勾选/拖动/切换/状态灯）：
            这类卡在 S2 规格里必须带 `then`（结果），R1 也会再验一次。
    requires 目标要求：
              text  = 必须是文字节点（title/lead/body/…）
              item  = 必须是组件声明的锚点元素（看 card_needs）
              block = 可以落在成块面板/组件根
              空    = 没声明

    判据只看卡自己的 code 和 needs，不看名字——加卡时不用再手写一遍。
    """
    out = {}
    for c in sorted(cards, key=lambda x: x["id"]):
        if c.get("status") != "ready" or not str(c.get("role") or "").startswith("state_"):
            continue
        code = str(c.get("code") or "")
        if "textContent" in code or "innerHTML" in code:
            writes = "content"
        elif "createElement" in code or "appendChild" in code:
            writes = "overlay"
        else:
            writes = "style"
        needs = {str(n) for n in (c.get("needs") or [])}
        if "text" in needs:
            requires = "text"
        elif contracts.anchors_of(c):
            requires = "item"
        elif "block" in needs:
            requires = "block"
        else:
            requires = ""
        entry = {"writes": writes, "trigger": bool(c.get("trigger")),
                 "requires": requires}
        # 比例条必须挂在真实数值上（S02/S18 的 avoid 就写着这一条）：本屏没有任何数字
        # 就不许用，S2N / R1 各自判一次。
        if c.get("requires_number"):
            entry["requires_number"] = True
        out[c["id"]] = entry
    return out


def card_desc(card, omit=()):
    """每张可选卡的描述面：`use` / `avoid`（有 note 就带上）。

    所有族共用这一份——背景、组件、转场、动效卡都从这里取。以前只有动效卡
    走了统一函数，背景/组件/转场各自拼 name/note，加一族就会静默漏发；
    漏发的结果模型只看到一串编号（"老是那几张"和"乱用"都从这儿长出来）。

    `omit` 是整族一字不差、已经被提到 `family_rules` 的字段（见 family_rules_of），
    卡级条目里不再重复。
    """
    out = {}
    if "use" not in omit:
        out["use"] = str(card.get("use") or "").strip()
    if "avoid" not in omit:
        out["avoid"] = str(card.get("avoid") or "").strip()
    note = str(card.get("note") or "").strip()
    if note:
        out["note"] = note
    return out


def family_rules_of(cards):
    """整族 `use`/`avoid` 一字不差 → 那是"族规则"，不是"卡描述"。

    背景 21 张的 avoid 全是"和照片满屏同时用（会互相抢）"、组件 38 张的 avoid
    全是"自己改样式、加图形、加图标"、转场 15 张的 use 全是"每一刀的页间交接"。
    逐卡发 74 份一样的话，既占体积又不给选择层任何区分度；提到
    `catalog.family_rules` 发一次、写明"对整族生效"才对。

    判据只看数据，不用手维护：**能逐卡区分就逐卡发，区分不了就归族**。
    以后给某张卡单独写了 use，它自动回到卡级。
    """
    rules = {}
    roles = sorted({str(c.get("role") or "") for c in cards
                    if c.get("status") == "ready" and c.get("role")})
    for role in roles:
        group = [c for c in cards if c.get("status") == "ready" and str(c.get("role") or "") == role]
        if len(group) < 2:
            continue
        for field in ("use", "avoid"):
            vals = [str(c.get(field) or "").strip() for c in group]
            if all(vals) and len(set(vals)) == 1:
                rules.setdefault(role, {})[field] = vals[0]
    return rules


def motion_cards_of(cards, rules=None):
    """每张可选动效卡的语义（2026-11-22）。

    以前 `catalog.motion.*` 只发编号：79 张装饰、21 张状态、47 张文字入场在模型眼里
    都是一串 `K43`/`S18`/`T29`。结果有两头：一头是"老是那几张"（只有编号，没有理由
    挑别的），另一头是"乱用"——`K50 打叉`（use=划掉一个错误做法）被画在"原始部落分肉"
    上、`S18 数值映射条`（avoid=没有真实数值时会变装饰）被画在没有任何数字的屏上、
    `K43 括号`（use=右侧挂一句旁注）被画在根本没有旁注的屏上。

    这里把每张卡的 `name` / `use` / `avoid` 一并发出去；判据仍在 presets.json，
    选择层只是终于能看到"这张卡是干什么的、什么时候不该用"。
    """
    out = {}
    for c in sorted(cards, key=lambda x: x["id"]):
        if c.get("status") != "ready":
            continue
        if c.get("role") in ("bg", "component", "page_transition", "shape"):
            continue
        omit = tuple((rules or {}).get(str(c.get("role") or ""), {}).keys())
        item = {
            "name": str(c.get("name") or ""),
            "family": str(c.get("family") or ""),
            **card_desc(c, omit),
        }
        # 目标字数上限（2026-11-23）：字距/描边这类会改变行宽的卡，标题超过这个
        # 字宽就会在动画中途折行。定义在卡上（`title_max_units`），选择层和展开层
        # 都拿同一个数，不各写一套。
        if c.get("title_max_units"):
            item["title_max_units"] = int(c["title_max_units"])
        out[c["id"]] = item
    return out


def _films():
    """每次生成时现扫成片；不再读 usage_ledger.json（2026-11-23）。"""
    try:
        data = motion_ledger.scan()
    except Exception:
        return []
    films = data.get("films") if isinstance(data, dict) else None
    return films if isinstance(films, list) else []


def recent_usage_of(limit=RECENT_FILMS, alive=None, films=None):
    """最近几支成片各自用过哪些编号（片数口径，不是次数）。

    只喂给选择层当参考，不参与任何"换卡"逻辑。
    2026-11-23：改成每次生成时现扫 `成品/*/index.html`，不再读可能过期的
    `usage_ledger.json`。台账文件只作报告。
    """
    if films is None:
        films = _films()
    recent = films[-limit:]
    tally = collections.Counter()
    for film in recent:
        used = film.get("used") if isinstance(film.get("used"), dict) else {}
        for cid in used:
            # 删过的编号不发给模型：它查不到、只会污染"最近用过"的判断。
            if alive is not None and str(cid) not in alive:
                continue
            tally[str(cid)] += 1
    return dict(sorted(tally.items()))


def recent_openers_of(films, bg, limit=RECENT_FILMS):
    """最近几支成片的首页背景（编号 + 视觉族），给首屏候选清单用。"""
    out = []
    for film in (films or [])[-limit:]:
        bgid = str(film.get("first_bg") or "").strip().upper()
        entry = bg.get(bgid)
        if not entry:
            continue
        out.append({"film": str(film.get("id") or ""),
                    "bg": bgid,
                    "family": str(entry.get("family") or "")})
    return out


def first_screen_background_of(bg, openers):
    """首屏候选：最近 3 支的同一张 + 上一支同 family 直接不进清单。

    2026-11-23 定：不是靠提示词求模型换，而是首屏根本拿不到这几张。
    """
    if not openers:
        return dict(bg)
    exclude_ids = {str(o.get("bg") or "") for o in openers}
    last_family = str(openers[-1].get("family") or "")
    out = {cid: entry for cid, entry in bg.items()
           if cid not in exclude_ids
           and (not last_family or str(entry.get("family") or "") != last_family)}
    if out:
        return out
    # 极端情况（所有族都被占）：至少保证不撞最近 3 支的同一张。
    out = {cid: entry for cid, entry in bg.items() if cid not in exclude_ids}
    return out or dict(bg)


def catalog_of(cards):
    bg, comp, pt = {}, {}, {}
    rules = family_rules_of(cards)
    motion = collections.OrderedDict((r, []) for r in MOTION_ROLES)
    films = _films()
    for c in sorted(cards, key=lambda x: x["id"]):
        # 目录只发 ready：needs-work 的卡连编号都不出现，模型不会选了再被丢。
        if c.get("status") != "ready":
            continue
        role = c.get("role") or ""
        cid = c["id"]
        if role == "bg":
            ink = c.get("ink")
            if isinstance(ink, dict):
                ink = ink.get("primary", "")
            bg[cid] = {"name": c.get("name", ""),
                       "family": c.get("bg_family", ""), "base": c.get("base", ""),
                       "ink_primary": ink or "", **card_desc(c, rules.get(role, {}).keys())}
        elif role == "component":
            info = component_slots.build(c.get("code") or "", component_slots.REPEAT_HINTS.get(cid))
            entry = component_slots.catalog_entry(c, info) if info else {"name": c.get("name", "")}
            entry.update(card_desc(c, rules.get(role, {}).keys()))
            comp[cid] = entry
        elif role == "page_transition":
            pt[cid] = {"name": c.get("name", ""),
                       "kind": c.get("kind", ""), **card_desc(c, rules.get(role, {}).keys())}
        elif role in motion:
            # 离场卡单独一格：它只在屏尾收束时用，塞进 decoration 会被当成普通装饰
            # 落在屏中，元素一消失就补不回来（2026-11-22）。
            if role == "decoration" and c.get("exit"):
                motion["exit"].append(cid)
            else:
                motion[role].append(cid)

    # 派生族：照片带入场的可选项（选择层里单独一格，见 media_entrance_ok 的注释）。
    motion["entrance_media"] = media_entrances(cards)

    # ---- 能力契约（2026-11-21）----
    # 组件声明 provides（锚点 → 组件内选择器），组件动效声明 needs/target/anchor。
    # 兼容矩阵由 contracts.py 算出，S2 只看到每个组件可用的卡，落版层再校验一次。
    comp_meta = {}
    motion_meta = {}
    for c in sorted(cards, key=lambda x: x["id"]):
        role = c.get("role") or ""
        cid = c["id"]
        if role == "component" and contracts.provides_of(c):
            comp_meta[cid] = {"provides": contracts.provides_of(c)}
        elif role == "component_motion" and c.get("status") == "ready":
            motion_meta[cid] = {
                "name": c.get("name", ""),
                "needs": contracts.anchors_of(c),
                "target": contracts.target_mode(c),
                "anchor": str(c.get("anchor") or ""),
                "bind": {str(k): str(v) for k, v in (c.get("bind") or {}).items()},
            }
    # 每张卡需要的锚点（只取 ANCHORS 词汇表里的词）。组件动效用它算兼容矩阵；
    # 状态卡也走这张表：S36 要 num，S2N / R1 据此把 sel 绑到组件声明的锚点元素上，
    # 绑不上就丢卡——不再让卡自己在目标里猜选择器（2026-11-21 s07 的「156」）。
    card_needs = {}
    for c in sorted(cards, key=lambda x: x["id"]):
        anchors = contracts.anchors_of(c)
        if anchors and c.get("status") == "ready":
            card_needs[c["id"]] = anchors
    openers = recent_openers_of(films, bg)
    return {
        "background": bg,
        # 首屏单独一份候选：最近 3 支的同一张 + 上一支同 family 已经排除。
        # 模型第一屏只能从这格选，拿不到被排除的编号（2026-11-23）。
        "first_screen_background": first_screen_background_of(bg, openers),
        "recent_openers": openers,
        "component": comp,
        "motion": {k: v for k, v in motion.items()},
        "page_transition": pt,
        "component_meta": comp_meta,
        "motion_meta": motion_meta,
        "motion_by_component": contracts.component_motions(cards),
        "card_needs": card_needs,
        # 状态卡的能力声明（writes / trigger / requires）：S2 据此知道哪张卡要 then、
        # 哪张卡只能落在文字节点；R1 用同一份表把落错目标的卡丢掉并点名。
        "state_meta": state_meta_of(cards),
        # 每张元素卡自己声明的 needs（text / block / media / 锚点…）：S2N 用它在
        # 展开前判断"这张卡能不能落在文字上"，deco 那格尤其需要（K 族 30 张只要文字）。
        # 每张可选动效卡的名字 / 用途 / 禁忌：模型靠它选，不靠编号猜。
        "motion_cards": motion_cards_of(cards, rules),
        # 整族一字不差的 use/avoid（对整族生效的规则），卡级条目里不再重复。
        # 现在通常是空的：这些族只是"多数相同"，不是"全部相同"（见 family_rules_of），
        # 所以仍然逐卡发；哪天整族统一了，它会自动出现。
        **({"family_rules": rules} if rules else {}),
        "motion_needs": {c["id"]: [str(n) for n in (c.get("needs") or [])]
                         for c in sorted(cards, key=lambda x: x["id"])
                         if c.get("status") == "ready"
                         and c.get("role") not in ("bg", "component", "page_transition", "shape")},
        # 最近几支成片用过的编号（片数口径）：选择层"同等条件下换别的"的依据。
        "recent_usage": recent_usage_of(alive={c["id"] for c in cards if c.get("status") == "ready"},
                                        films=films),
    }


def _fmt_params(params):
    if not params:
        return "—"
    return " · ".join("%s=%s" % (k, v) for k, v in params.items())


def render_cards_md(cards):
    out = [HEADER, HARD_RULES]
    by_family = collections.defaultdict(list)
    disabled = []
    shapes = 0
    for c in cards:
        if not c.get("role"):
            continue
        # role=shape 是图形素材（整屏 SVG / mermaid 形状），不进选择层：
        # 模型选不到，就不会再出现"整屏坐标系的图被塞进 840 文字栏"。
        if c["role"] == "shape":
            shapes += 1
            continue
        # 非 ready 卡不进可选总表和各族明细；单独列在“未启用”，
        # 否则文档会写着"能选"、目录里却没有它（2026-11-23 S04）。
        if c.get("status") != "ready":
            disabled.append(c)
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
        if c.get("status") != "ready":
            continue
        r = c.get("role")
        if r in role_label:
            by_role[r].append(c["id"])
    for r in ("entrance_text", "entrance_block", "state_text", "state_block",
              "component_motion", "decoration", "bg", "component", "page_transition"):
        ids = sorted(by_role.get(r, []))
        if ids:
            out.append("| `%s` %s | %d | %s |" % (r, role_label[r], len(ids), " ".join(ids)))
    media_ids = media_entrances(cards)
    if media_ids:
        out.append("| `entrance_media` 照片带入场 | %d | %s |" % (len(media_ids), " ".join(media_ids)))
    out.append("")
    out.append("`entrance_media` 是从 `entrance_block` 里派生的一格：只收\"只动根节点、不依赖子结构和元素自带属性\"的卡，"
               "照片槽只能从这里选（`S2N` 与 `R1` 都会验，见 `经验文档/能力层架构.md`）。\n")
    if disabled:
        out.append("## 未启用（不进选择层）\n")
        out.append("| 编号 | 名字 | role | 原因 |")
        out.append("|---|---|---|---|")
        for c in sorted(disabled, key=lambda x: x["id"]):
            out.append("| %s | %s | `%s` | %s |" % (
                c["id"], c.get("name", ""), c.get("role", ""),
                c.get("note") or c.get("avoid") or "status=%s" % c.get("status")))
        out.append("")

    out.append("## 各族明细\n")
    for fam in order:
        items = sorted(by_family[fam], key=lambda x: x["id"])
        out.append("### %s\n" % fam)
        if fam == "组件":
            out.append("组件只给编号，HTML 片段见 [`组件卡.md`](组件卡.md)。\n")
            out.append("| 编号 | 名字 | 结构 | 什么时候选 | 什么时候别选 |")
            out.append("|---|---|---|---|---|")
            for c in items:
                out.append("| %s | %s | %s | %s | %s |" % (
                    c["id"], c.get("name", ""), c.get("note", ""),
                    c.get("use", ""), c.get("avoid", "")))
            out.append("")
            continue
        if fam == "背景":
            out.append("| 编号 | 名字 | 视觉族 | 什么时候选 | 什么时候别选 | 长什么样 | 触发词 |")
            out.append("|---|---|---|---|---|---|---|")
            for c in items:
                kw = "、".join(c.get("keywords") or [])
                out.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                    c["id"], c.get("name", ""), c.get("bg_family", ""),
                    c.get("use", ""), c.get("avoid", ""), c.get("note", ""), kw))
            out.append("")
            continue
        if fam == "页间转场":
            out.append("页间转场由 `S2` 逐刀给编号偏好，`R3` 按切点表逐刀生成 `window.__pt` 调用（N 屏必出 N-1 条）。\n")
            out.append("| 编号 | 名字 | kind | 用在哪 | 别用在哪 |")
            out.append("|---|---|---|---|---|")
            for c in items:
                out.append("| %s | %s | `%s` | %s | %s |" % (
                    c["id"], c.get("name", ""), c.get("kind", ""), c.get("use", ""), c.get("avoid", "")))
            out.append("")
            continue
        out.append("| 编号 | 名字 | 角色 | 需要锚点 | 参数 | 用在哪 | 别用在哪 |")
        out.append("|---|---|---|---|---|---|---|")
        for c in items:
            anchors = "、".join(contracts.anchors_of(c)) if c.get("role") == "component_motion" else "—"
            out.append("| %s | %s | %s | %s | %s | %s | %s |" % (
                c["id"], c.get("name", ""), role_label.get(c.get("role"), c.get("role", "")),
                anchors or "—", _fmt_params(c.get("params")), c.get("use", ""), c.get("avoid", "")))
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
           "| 编号 | 名字 | 结构 | 什么时候选 | 什么时候别选 |",
           "|---|---|---|---|---|"]
    for c in comps:
        out.append("| %s | %s | %s | %s | %s |" % (
            c["id"], c.get("name", ""), c.get("note", ""),
            c.get("use", ""), c.get("avoid", "")))
    out.append("")
    for c in comps:
        out.append("## %s %s\n" % (c["id"], c.get("name", "")))
        if c.get("note"):
            out.append(c["note"] + "\n")
        provides = contracts.provides_of(c)
        if provides:
            out.append("动效锚点：%s\n" % "、".join("`%s`=%s" % (k, v or "（根）") for k, v in provides.items()))
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


def render_h00_code(catalog, templates):
    """H00 是纯生成物：目录 + 组件模板。整段重建，不再往旧代码里插块。"""
    cat_blob = json.dumps(catalog, ensure_ascii=False)
    tpl_blob = json.dumps(templates, ensure_ascii=False)
    return ('def main() -> dict:\n'
            '    """选择层：目录（含槽位元数据）与组件模板。由 gen_catalog.py 生成，不要手改。"""\n'
            '    import json\n'
            '    CATALOG = json.loads(r"""%s""")\n'
            '    COMPONENT_TPL = json.loads(r"""%s""")\n'
            '    return {"catalog_json": json.dumps(CATALOG, ensure_ascii=False),\n'
            '            "component_tpl_json": json.dumps(COMPONENT_TPL, ensure_ascii=False)}\n'
            % (cat_blob, tpl_blob))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查是否已同步")
    args = ap.parse_args()

    cards = load()
    cat = catalog_of(cards)
    templates = {}
    for card in cards:
        if card.get("role") == "component":
            info = component_slots.build(card.get("code") or "", component_slots.REPEAT_HINTS.get(card.get("id")))
            if info:
                entry = component_slots.template_entry(info)
                # span=full：这张组件要落在 1080 通栏层（R2 读它决定放 .scene-ui 还是 .scene-copy）。
                # 以前所有组件都塞进 840 文字栏，对话气泡被挤成两个小方块（2026-11-21 定）。
                if card.get("span"):
                    entry["span"] = str(card["span"])
                templates[card["id"]] = entry
    h00_code = render_h00_code(cat, templates)
    compile(h00_code, "h00", "exec")
    md_cards = render_cards_md(cards)
    md_comp = render_comp_md(cards)

    diffs = []
    for path in YAMLS:
        if yaml_nodes.get_code("h00", path) != h00_code:
            diffs.append("%s 的 H00 选择层" % path.name)
    if not CARDS_MD.exists() or CARDS_MD.read_text(encoding="utf-8") != md_cards:
        diffs.append("能力卡.md")
    if not COMP_MD.exists() or COMP_MD.read_text(encoding="utf-8") != md_comp:
        diffs.append("组件卡.md")

    n_sel = (len(cat["background"]) + len(cat["component"])
             + len(cat["page_transition"])
             + sum(len(v) for k, v in cat["motion"].items() if k != "entrance_media"))

    if args.check:
        if diffs:
            print("未同步：" + "、".join(diffs) + "；请运行 gen_catalog.py")
            return 1
        print("已同步：%d 张卡，可选 %d 张（两份 YAML 一致）" % (len(cards), n_sel))
        return 0

    for path in YAMLS:
        if yaml_nodes.get_code("h00", path) != h00_code:
            yaml_nodes.set_code("h00", h00_code, path)
    CARDS_MD.write_text(md_cards, encoding="utf-8")
    COMP_MD.write_text(md_comp, encoding="utf-8")
    print("已写入：能力卡.md / 组件卡.md / H00 选择层（两份 YAML）；可选 %d 张（背景 %d / 组件 %d / 转场 %d / 动效 %d）"
          % (n_sel, len(cat["background"]), len(cat["component"]), len(cat["page_transition"]),
             sum(len(v) for k, v in cat["motion"].items() if k != "entrance_media")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
