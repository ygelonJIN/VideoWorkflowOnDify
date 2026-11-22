#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""加卡：一条命令走完，和 remove_card.py 对称。

用法：
    python3 add_card.py card.json                 # 已经出过样片才允许加
    python3 add_card.py card.json --render        # 没样片就顺手渲一张
    python3 add_card.py card.json --dry-run       # 只校验，不写

做五件事，顺序固定：
    1. 校验字段（role / params / 背景族 / 组件类名 / PT kind）
    2. presets.json 追加条目（唯一源）
    3. gen_catalog.py 重生成 能力卡.md / 组件卡.md / H00 目录
    4. sync_expander.py 写 TPL/DEFAULTS 并 --check
    5. 确认样片存在（或 --render 现场渲）

card.json 的最小形态：

    {"id": "T27", "name": "逐行推开", "family": "入场", "role": "entrance_block",
     "layer": "element", "status": "ready", "cap": "stagger", "src": "手写",
     "params": {"dur": 0.6, "stagger": 0.05},
     "use": "整段文字逐行进场", "avoid": "超过 5 行会拖尾",
     "code": "timeline.fromTo('{{sel}}', {opacity:0, y:24}, {opacity:1, y:0, duration:{{dur}}, stagger:{{stagger}}}, {{at}});"}
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

import contracts

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
PRESETS = HERE / "presets.json"
CSS = WORK / "runtime" / "assets" / "vendor" / "components.css"
SYNC_VIDEO = WORK / "runtime" / "scripts" / "sync_video.py"
PLUGIN_DIR = WORK / "runtime" / "assets" / "vendor" / "gsap-plugins"
REELS = HERE / "样片" / "全卡审阅"
BATCH_ROOT = HERE / "样片" / "待筛"


def approved(batch_dir: pathlib.Path, cid: str) -> bool:
    """批次里有 通过.tsv 且点名了这个编号，才算人看过。只有人被点名通过后才写这个文件。"""
    f = batch_dir / "通过.tsv"
    if not f.is_file():
        return False
    for line in f.read_text(encoding="utf-8").splitlines()[1:]:
        if line.split("\t")[0].strip() == cid:
            return True
    return False

# 2026-11-17：none / archive / special_dom 三个"在表但选不到"的 role 已整族删除。
# 现在表里每张卡都必须落进下面某一格，否则 gen_catalog 的目录里就没有它，等于白做。
ROLES = {"bg", "component", "entrance_text", "entrance_block", "state_text",
         "state_block", "component_motion", "decoration", "page_transition"}
BG_FAMILIES = {"dot", "line", "ring", "block", "light", "noise"}
STATUSES = {"ready", "needs-work", "skip", "archived"}
REQUIRED = ["id", "name", "family", "role", "status", "cap", "use", "avoid"]


def run(cmd):
    print("  $", " ".join(str(c) for c in cmd))
    return subprocess.run([str(c) for c in cmd], cwd=str(WORK)).returncode


def pt_kinds():
    text = SYNC_VIDEO.read_text(encoding="utf-8")
    m = re.search(r"__ptList\s*=\s*\[([^\]]+)\]", text)
    return set(re.findall(r"'([^']+)'", m.group(1))) if m else set()


def component_classes():
    return set(re.findall(r"\.(ui-[a-z-]+)", CSS.read_text(encoding="utf-8")))


def injected_plugins():
    """运行时真正会注入的 GSAP 插件（sync_video.GSAP_PLUGINS 是唯一真值）。"""
    text = SYNC_VIDEO.read_text(encoding="utf-8")
    m = re.search(r"GSAP_PLUGINS\s*=\s*\(([^)]*)\)", text)
    return set(re.findall(r'"([^"]+)"', m.group(1))) if m else set()


def vendor_plugins():
    """vendor 里躺着、但可能没被注入的插件名（CustomBounce / CustomEase 这类）。"""
    if not PLUGIN_DIR.is_dir():
        return set()
    return {p.stem.replace(".min", "") for p in PLUGIN_DIR.glob("*.min.js")}


def plugin_deps(card, known):
    """这张卡依赖哪些 GSAP 插件：src 的 gsap: 前缀 + code 里的 window.XXX 守卫。"""
    need = set()
    m = re.match(r"gsap:([A-Za-z0-9_]+)", str(card.get("src") or "").strip())
    if m:
        need.add(m.group(1))
    for name in re.findall(r"window\.([A-Za-z_$][\w$]*)", str(card.get("code") or "")):
        if name in known:
            need.add(name)
    return need


def validate(card, existing, kinds, classes):
    bad = []
    for key in REQUIRED:
        if not str(card.get(key) or "").strip():
            bad.append("缺字段 " + key)
    if bad:
        return bad
    if card["role"] not in ROLES:
        bad.append("role 不合法：%s" % card["role"])
    if card["status"] not in STATUSES:
        bad.append("status 不合法：%s" % card["status"])
    if card["id"] in existing:
        bad.append("%s 已经在表里" % card["id"])
    params = card.get("params") if isinstance(card.get("params"), dict) else {}
    auto = {"sel", "at", "k", "sel2"}          # 展开器自动注入，不需要写进 params
    for name in re.findall(r"\{\{(\w+)\}\}", str(card.get("code") or "")):
        if name not in params and name not in auto:
            bad.append("code 里的 {{%s}} 在 params 里没有默认值" % name)
    # 插件依赖（2026-11-19）：卡片代码里 `if (!window.CustomBounce) return;` 这种守卫
    # 意味着插件没注入时整张卡静默空转，只剩前面那句 `set opacity:1` —— 成片里就是
    # "啪一下出现"，观众看到的是"这一屏根本没有动效"（2026-11-19 s02 实测）。
    # CustomEase / CustomBounce / CustomWiggle 已于 2026-11-15 从 GSAP_PLUGINS 主动移除
    # （CustomEase 会让逐帧 seek 崩、整片渲染失败），所以依赖它们的卡在这里就拒收。
    injected = injected_plugins()
    known = injected | vendor_plugins()
    for name in sorted(plugin_deps(card, known)):
        if name not in injected:
            bad.append("依赖插件 %s 没有被注入（sync_video.GSAP_PLUGINS 里没有），"
                       "这张卡在浏览器里会静默空转；改用内置 ease 重写" % name)
    # text_safe：这张卡能不能落在常驻文字节点（data-role）上。默认 true。
    # 卡结束时元素偏离原位（S21 甩出去只回来一部分）、或放大后不回落（T16 到 4 倍）的，
    # 一旦点在 title/body 上，文字就跑出画布或糊满整屏。这类卡必须显式写 false，
    # 并给一张同槽位的 text_swap —— 展开层拿到 false 就换卡，不会把文字留在画外。
    if "text_safe" in card:
        if not isinstance(card["text_safe"], bool):
            bad.append("text_safe 只能是 true / false")
        elif card["text_safe"] is False:
            swap = str(card.get("text_swap") or "").strip().upper()
            if not swap:
                bad.append("text_safe=false 必须给 text_swap（落在文字上换成哪张）")
            elif swap not in existing:
                bad.append("text_swap %s 不在表里" % swap)
            else:
                other = existing[swap]
                slot = "entrance" if str(card["role"]).startswith("entrance") else "state"
                if not str(other.get("role") or "").startswith(slot):
                    bad.append("text_swap %s 的 role 是 %s，同槽位要求 %s_*" % (swap, other.get("role"), slot))
                if other.get("status") != "ready":
                    bad.append("text_swap %s 不是 ready" % swap)
                if other.get("text_safe") is False:
                    bad.append("text_swap %s 自己也不能落在文字上，换过去等于没换" % swap)
    role = card["role"]
    # ---- 状态卡不许把根元素重新藏起来（2026-11-21）----
    # state_* 的职责是改变一个**已经可见**的元素。它一旦给根元素设了隐藏起始态，就成了
    # 第二张入场卡：元素先出现在画面上，几秒后又缩回去/散开再飞回来（2026-11-21 s02 的
    # S19 实测：三行被"打散重来"，观众看到的是左右乱晃）。
    # 判据只看**目标是谁**：根元素（{{sel}}）不行；自己 createElement 出来的新内容
    # （文案替换的新 span）随便；动已有子元素的，必须在 params 里声明 child —— 让
    # "我动的是子元素"成为显式事实，不让落版层去猜代码。
    if str(role).startswith("state"):
        code = str(card.get("code") or "")
        params = card.get("params") if isinstance(card.get("params"), dict) else {}
        root_vars = set(re.findall(
            r"var\s+([A-Za-z_$][\w$]*)\s*=\s*document\.querySelector\(\s*['\"]\{\{sel\}\}['\"]\s*\)", code))
        child_vars = set(re.findall(
            r"var\s+([A-Za-z_$][\w$]*)\s*=\s*(?:\[\]\.slice\.call\(\s*\w+\.children|document\.querySelectorAll\()", code))
        created = set(re.findall(r"var\s+([A-Za-z_$][\w$]*)\s*=\s*document\.createElement", code))
        for m in re.finditer(r"(?:fromTo|\.from)\(\s*([^,]+),\s*\{(.*?)\}", code, re.S):
            target = m.group(1).strip().strip("'\"")
            if target in created:
                continue
            st = m.group(2)
            hidden = bool(
                re.search(r"opacity['\"]?\s*:\s*0(?![.\d])", st)
                or re.search(r"scaleY['\"]?\s*:\s*0?\.\d+", st)
                or re.search(r"clipPath['\"]?\s*:\s*['\"]?(?:inset\([^)]*100%|circle\(\s*0%)", st)
            )
            if not hidden:
                continue
            if target == "{{sel}}" or target in root_vars:
                bad.append("这是入场卡，不是状态卡（起始态把根元素藏起来）。state_* 卡把根元素"
                           "重新藏起来，成片里会先出现再缩掉/散开；role 改成 entrance_*")
                break
            if target in child_vars and "child" not in params:
                bad.append("这张 state 卡藏的是子元素，但 params 里没有 child：请声明动的是哪个"
                           "子元素选择器，否则落版层定位不到")
                break
    # ---- 能力契约（2026-11-21）----
    # 组件必须声明它对外暴露哪些锚点；组件动效必须声明需要哪些锚点、怎么动。
    # 这是选择层算兼容矩阵、落版层解析目标的唯一依据。
    if role == "component":
        provides = card.get("provides")
        if not isinstance(provides, dict) or not provides:
            bad.append("组件卡必须有 provides（锚点 → 组件内选择器），否则动效卡不知道能挂什么")
        else:
            for anchor, selector in provides.items():
                if anchor not in contracts.ANCHORS:
                    bad.append("provides 里的锚点 %s 不在词汇表" % anchor)
                if not isinstance(selector, str):
                    bad.append("provides.%s 必须是选择器字符串" % anchor)
    if role == "component_motion":
        raw_needs = [str(n) for n in (card.get("needs") or [])]
        known = contracts.ANCHORS | contracts.CAPABILITY_ONLY
        for name in raw_needs:
            if name not in known:
                bad.append("needs 里的 %s 不是已知锚点/能力词（词汇表见 contracts.py）" % name)
        anchors = contracts.anchors_of(card)
        if not anchors:
            bad.append("组件动效必须在 needs 里声明至少一个锚点（card/row/cell/bar/tag/node/path/...）")
        mode = str(card.get("target") or "").strip().lower()
        if mode not in contracts.TARGET_MODES:
            bad.append("target 必须是 %s" % "/".join(sorted(contracts.TARGET_MODES)))
        anchor = str(card.get("anchor") or "").strip()
        if anchor and anchor not in anchors:
            bad.append("anchor %s 不在 needs 里" % anchor)
        bind = card.get("bind")
        if bind is not None and not isinstance(bind, dict):
            bad.append("bind 必须是 {参数名: 锚点} 的对象")
        components = [c for c in existing.values() if c.get("role") == "component"]
        if anchors and not any(contracts.compatible(card, comp) for comp in components):
            bad.append("没有组件能满足它需要的锚点 %s：先补组件 provides，或改卡" % "/".join(anchors))
    # 非组件动效也能声明锚点（S36 要 num）。声明了就必须有组件提供，
    # 否则运行时只能丢卡：卡自己在目标里猜选择器，猜不到就会改错文字（2026-11-21 s07）。
    if role.startswith(("state_", "entrance_")):
        anchors = contracts.anchors_of(card)
        if anchors:
            known = contracts.ANCHORS | contracts.CAPABILITY_ONLY
            for name in [str(n) for n in (card.get("needs") or [])]:
                if name not in known:
                    bad.append("needs 里的 %s 不是已知锚点/能力词（词汇表见 contracts.py）" % name)
            components = [c for c in existing.values() if c.get("role") == "component"]
            if not any(all(a in contracts.provides_of(c) for a in anchors) for c in components):
                bad.append("没有组件提供这张卡需要的锚点 %s：先补组件 provides，或改卡" % "/".join(anchors))
    # ---- 状态卡的落点声明（2026-11-22）----
    # 判据只有一条：这张卡会不会把目标的内容改掉/塞进新元素？
    # 会改内容的，必须声明它只落文字（needs 里有 text）或声明一个锚点（落叶子元素），
    # 否则运行时只能把它丢在组件根上——那正是 s05 把三格指标清成一行 16px 的原因。
    if str(role).startswith("state_"):
        code = str(card.get("code") or "")
        writes_content = ("textContent" in code or "innerHTML" in code)
        if writes_content:
            needs = {str(n) for n in (card.get("needs") or [])}
            if "text" not in needs and not contracts.anchors_of(card):
                bad.append("这张卡会改写目标文字（textContent/innerHTML），必须声明 needs 里有 text "
                           "（只能落文字节点）或一个锚点（落组件内的叶子元素）")
        if "trigger" in card and not isinstance(card["trigger"], bool):
            bad.append("trigger 只能是 true / false")
        if card.get("trigger") is True:
            # 触发卡（点击/勾选/拖动/切换/状态灯）必须能落在一个真实元素上，
            # 否则它连"发生了什么事"都画不出来，只剩一条没有结果的动画。
            if not contracts.anchors_of(card) and "text" not in {str(n) for n in (card.get("needs") or [])}:
                bad.append("trigger=true 的卡必须有锚点或 needs=text：触发总得有个被点的东西")
    # ---- 离场卡（2026-11-22）----
    # exit=true 只给"结束时真的消失"的卡，R1 把它固定在切点前 0.5 秒。
    if "exit" in card:
        if not isinstance(card["exit"], bool):
            bad.append("exit 只能是 true / false")
        elif card["exit"]:
            if role != "decoration":
                bad.append("exit=true 只给 decoration（离场是元素级收束，不占内容槽位）")
            if not re.search(r"opacity['\"]?\s*:\s*0(?![.\d])", str(card.get("code") or "")):
                bad.append("exit=true 的卡必须真的把元素藏掉（代码里要有 opacity:0），"
                           "否则它不是离场卡，只是另一张入场/装饰卡")
    if role == "bg":
        if not card.get("note"):
            bad.append("背景卡必须有 note（模型靠它选卡）")
        if card.get("bg_family") not in BG_FAMILIES:
            bad.append("背景卡 bg_family 必须是 %s" % "/".join(sorted(BG_FAMILIES)))
        if not card.get("keywords"):
            bad.append("背景卡必须有 keywords")
    if role == "component":
        code = str(card.get("code") or "")
        if not code.startswith("<"):
            bad.append("组件卡的 code 必须是 HTML 片段")
        for cls in set(re.findall(r'class="([^"]+)"', code)):
            for one in cls.split():
                if one.startswith("ui-") and one not in classes:
                    bad.append("components.css 里没有 .%s" % one)
        # 新链路用槽位模板渲染：卡必须能被 component_slots 解析出至少一个文本洞，
        # 否则它进了目录却不在 COMPONENT_TPL 里，落版会静默丢掉。
        import component_slots
        info = component_slots.build(code)
        if not info:
            bad.append("component_slots 解析不出槽位（模板必须是有文本节点的 HTML 片段）")
        elif info["before"] + info["row_slots"] * info["rows_default"] + info["after"] == 0:
            bad.append("这张组件没有可填的文本槽位（纯装饰）")
    if role == "page_transition":
        if card.get("kind") not in kinds:
            bad.append("kind 必须是 sync_video.__ptList 里的：%s" % "/".join(sorted(kinds)))
        if card.get("code"):
            bad.append("页间转场不写 code（由 __pt 实现）")
        if card.get("cap") != "page-transition":
            bad.append("页间转场的 cap 必须是 page-transition")
    return bad


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("json_file")
    ap.add_argument("--render", action="store_true",
                    help="这批卡还没有待筛候选片时，先出候选片到 样片/待筛/ 再停（不转正）")
    ap.add_argument("--jobs", type=int, default=4, help="--render 时的并发路数，默认 4")
    ap.add_argument("--batch", default="", help="从哪个待筛批次取片（该批次必须有 通过.tsv 点名）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PRESETS.read_text(encoding="utf-8"))
    existing = {c["id"]: c for c in data["presets"]}
    kinds, classes = pt_kinds(), component_classes()
    payload = json.loads(pathlib.Path(args.json_file).read_text(encoding="utf-8"))
    cards = payload if isinstance(payload, list) else [payload]

    problems = []
    for card in cards:
        problems += ["%s：%s" % (card.get("id", "?"), msg)
                     for msg in validate(card, existing, kinds, classes)]
    if problems:
        print("不能加：")
        for line in problems:
            print("  -", line)
        return 1

    if args.dry_run:
        print("校验通过，可以加：%s" % "、".join(c["id"] for c in cards))
        return 0

    # ── 审阅闸门（必须在写表之前）：片得先在 样片/待筛/<批次>/ 里被人点名通过 ──
    # 以前是"没片就现场渲一张到 全卡审阅"，等于绕过人审；候选片和审过的片混在一处，
    # 审阅就失效了。现在只有两条路：已在全卡审阅（复查重渲），或待筛里有 通过.tsv 点名的候选片。
    todo, pending_batch = [], {}
    for card in cards:
        if card["role"] == "page_transition":
            continue
        if list((REELS / card["family"]).glob(card["id"] + "-*.mp4")):
            print("✓ 样片已在全卡审阅：%s" % card["id"])
            continue
        cand = [c for c in sorted(BATCH_ROOT.glob("*/" + card["id"] + "-*.mp4"))
                if approved(c.parent, card["id"])]
        if args.batch:
            narrowed = [c for c in cand if c.parent.name == args.batch]
            if narrowed:
                cand = narrowed
        if cand:
            pending_batch[card["id"]] = cand[0]
            continue
        todo.append(card["id"])

    if todo:
        if args.render:
            batch = args.batch or (__import__("datetime").date.today().strftime("%Y%m%d")
                                   + "-" + pathlib.Path(args.json_file).stem)
            print("这批卡还没有待筛候选片，先出候选片给人审（落 样片/待筛/%s/）：" % batch)
            run(["bash", str(HERE / "render_candidates.sh"), batch, args.json_file])
            print("\n候选片已出，表没有改动。人审完写 待筛/%s/通过.tsv 再跑一次。" % batch)
            return 1
        print("不能加（表未改动）：这些卡没有\"人已点名通过\"的候选片：")
        for cid in todo:
            print("  -", cid)
        print("\n正确顺序：")
        print("  1) bash 能力库/动效库/render_candidates.sh <批次> %s" % args.json_file)
        print("  2) 人看 样片/待筛/<批次>/ 里的片 → 点名通过后写 待筛/<批次>/通过.tsv")
        print("  3) python3 能力库/动效库/add_card.py %s --batch <批次>" % args.json_file)
        return 1

    # ── 写表；生成/同步任一步失败就整体回滚，不留半生效状态 ──
    old_text = PRESETS.read_text(encoding="utf-8")
    data["presets"].extend(cards)
    data["updated"] = __import__("datetime").date.today().isoformat()
    PRESETS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("✓ presets.json：%d → %d 张" % (len(existing), len(data["presets"])))

    ok = (run([sys.executable, str(HERE / "gen_catalog.py")]) == 0
          and run([sys.executable, str(HERE / "sync_expander.py")]) == 0
          and run([sys.executable, str(HERE / "sync_expander.py"), "--check"]) == 0)
    if not ok:
        PRESETS.write_text(old_text, encoding="utf-8")
        subprocess.run([sys.executable, str(HERE / "gen_catalog.py")], cwd=str(WORK),
                       capture_output=True, text=True)
        subprocess.run([sys.executable, str(HERE / "sync_expander.py")], cwd=str(WORK),
                       capture_output=True, text=True)
        print("生成/同步失败，已回滚 presets.json 与派生文件；没有留下半生效状态。")
        return 1

    # 把审过的候选片从待筛搬进 全卡审阅：审阅物只留一处，搬完待筛里就少一条
    for cid, src_mp4 in pending_batch.items():
        fam = next(c["family"] for c in cards if c["id"] == cid)
        dest_dir = REELS / fam
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src_mp4), str(dest_dir / src_mp4.name))
        print("✓ 样片从待筛搬入：%s" % (dest_dir / src_mp4.name).relative_to(WORK))

    print("加卡完成。外部来源的批次记得在 能力库/动效库/来源台账.md 补一行结论。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
