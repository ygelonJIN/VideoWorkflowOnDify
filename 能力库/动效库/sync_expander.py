#!/usr/bin/env python3
"""把 presets.json 里 status=ready 的卡同步进 Dify 的 H02SX 展开器。

展开器（04_黑帧口播_分组生成.yml 的 H02SX 节点）里有两块手写数据：
    TPL = { 卡号: 模板 }
    DEFAULTS = { 卡号: 默认参数 }
以前是手抄的，加卡就会漏。这个脚本从 presets.json 生成这两块并写回 YAML。

用法：
    python3 sync_expander.py            # 写入
    python3 sync_expander.py --check    # 只检查是否已同步，不同步退出码 1

约定：
- 只同步 status=ready 的元素动效卡：背景（bgkit 走 canvas）、组件（HTML 结构）、
  页间转场（sync_video 的 __pt）都不进 TPL。
- {{x}} → %(x)s，% 转义成 %%。
- 缺 sel2 时给个默认值，避免 L01 这类双目标卡展开时报 KeyError。
"""
import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent.parent
# 两份共用能力层（01 = 04 + 数字人小窗），H02SX 的 TPL/DEFAULTS/UNSAFE_TEXT 必须一起变。
# 双引号标量的折行续行：`\` + 换行 + 缩进，后面可能跟一个 `\ `（转义空格）。
_YAML_CONT = re.compile(r"\\\n[ \t]*(\\ )?")

YAMLS = [REPO / "Dify工作流" / "04_黑帧口播_分组生成.yml",
         REPO / "Dify工作流" / "01_有数字人完整视频工作流.yml"]

sys.path.insert(0, str(ROOT))
import build_presets as bp  # noqa: E402


def build_blocks():
    cards = [
        c for c in bp.load()["presets"]
        if c.get("status") == "ready" and not c["id"].startswith("B")
        and c.get("role") not in ("bg", "shape")
        and c.get("cap") not in ("component-html", "page-transition")
    ]
    tpl = ["    TPL = {"]
    for c in cards:
        tpl.append('        "%s": """%s""",' % (c["id"], bp.to_python_template(c["code"])))
    tpl += ["    }", ""]

    default = ["    DEFAULTS = {"]
    for c in cards:
        keys = dict(c.get("params") or {})
        keys.setdefault("dur", 0.6)
        keys.setdefault("stagger", 0.05)
        default.append('        "%s": %r,' % (c["id"], keys))
    default += ["    }", ""]

    # text_safe=false：卡结束时元素偏离原位（S21 甩出去只回一部分）或放大后不回落
    # （T16 到 4 倍）。这类卡一旦点在 title/body 上，文字就跑出画布或糊满整屏，
    # 逐帧检查还全过。展开层拿到这张表就换成同槽位的替身卡，并把原编号记进 skipped。
    unsafe = [
        "    # 不能落在常驻文字上的卡：落在 data-role 节点时换同槽位替身。",
        "    # 由 sync_expander.py 从 presets.json 的 text_safe / text_swap 生成，不要手改。",
        "    UNSAFE_TEXT = {",
    ]
    for c in bp.load()["presets"]:
        if c.get("text_safe") is False:
            swap = str(c.get("text_swap") or "").strip().upper()
            if swap:
                unsafe.append('        "%s": "%s",' % (c["id"], swap))
    unsafe += ["    }", ""]
    return ("\n".join(tpl) + "\n" + "\n".join(default) + "\n" + "\n".join(unsafe),
            [c["id"] for c in cards])


def audit_params():
    """每张 ready 卡只带自己的 params 也必须能格式化；缺参数就是坏卡。"""
    bad = []
    ready = {}
    for c in bp.load()["presets"]:
        if c.get("status") == "ready":
            ready[c["id"]] = c
    for c in bp.load()["presets"]:
        if c.get("status") != "ready" or c["id"].startswith("B") or c.get("role") == "shape" or c.get("cap") in ("component-html", "page-transition"):
            continue
        vals = dict(c.get("params") or {})
        vals.update({"sel": "x", "at": "at(0.2)", "k": "0", "sel2": "y"})
        try:
            bp.to_python_template(c["code"]) % vals
        except Exception as e:
            bad.append((c["id"], str(e)[:40]))
        # text_swap 必须真的能被展开：不在 TPL 里换了也白换。
        if c.get("text_safe") is False:
            swap = str(c.get("text_swap") or "").strip().upper()
            if not swap:
                bad.append((c["id"], "text_safe=false 但没有 text_swap"))
            elif swap.startswith("B") or swap not in ready:
                bad.append((c["id"], "text_swap %s 不是可展开的 ready 卡" % swap))
            elif ready[swap].get("cap") in ("component-html", "page-transition"):
                bad.append((c["id"], "text_swap %s 是组件/转场卡，进不了 TPL" % swap))
    return bad


def unfold_yaml_wraps(text):
    """把双引号标量里被折开的长行折回去。

    Dify 导出（或编辑器）会把超长的一行按 700 字符折开：行尾一个 `\\` 续行，
    下一行开头用 `\\ ` 补回那个空格。值是一模一样的，但**原文**和 `json.dumps`
    出来的转义串从此对不上，下面按原文定位就会 count==0（2026-11-20 实测：
    04/01 各有一处折行，sync_expander 直接"定位失败"，删卡链在这里断）。
    定位前先把续行还原，写入时保持还原后的单行。"""
    return _YAML_CONT.sub(lambda m: " " if m.group(1) else "", text)


def splice(code):
    new_block, ids = build_blocks()
    i0 = code.index("    TPL = {")
    i1 = code.index("    DEFAULTS = {")
    i2 = code.index("\n\n    parts = []", i1)
    out = code[:i0] + new_block + code[i2:]
    if 'values.setdefault("sel2"' not in out:
        out = out.replace(
            '        values.update({"sel": sel, "at": at_expr, "k": "%d" % idx})',
            '        values.setdefault("sel2", sel)\n'
            '        values.update({"sel": sel, "at": at_expr, "k": "%d" % idx})')
    return out, ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    import yaml
    bad = audit_params()
    if bad:
        print("参数不全的卡：")
        for cid, msg in bad:
            print("  %s  %s" % (cid, msg))
        return 1

    pending, ids = [], []
    for path in YAMLS:
        raw = unfold_yaml_wraps(path.read_text(encoding="utf-8"))
        data = yaml.safe_load(raw)
        node = None
        for n in data["workflow"]["graph"]["nodes"]:
            # 优先按 id 找（节点标题会随语义改），旧文件退回按标题
            if n.get("id") == "h02sx" or n.get("data", {}).get("title", "").startswith(("H02SX", "R1_")):
                node = n
                break
        if not node:
            print("找不到动效展开节点（h02sx / H02SX / R1_）：%s" % path.name)
            return 1
        code = node["data"]["code"]
        new_code, ids = splice(code)
        compile(new_code, "h02sx", "exec")
        if new_code == code:
            print("已同步：%s（%d 张卡）" % (path.name, len(ids)))
            continue
        pending.append((path, raw, code, new_code))

    if not pending:
        return 0
    if args.check:
        print("未同步：%s 与 presets.json 不一致，请运行 sync_expander.py"
              % "、".join(p.name for p, _, _, _ in pending))
        return 1

    for path, raw, code, new_code in pending:
        esc_old = json.dumps(code, ensure_ascii=False)[1:-1]
        esc_new = json.dumps(new_code, ensure_ascii=False)[1:-1]
        if raw.count(esc_old) != 1:
            print("YAML 里的代码块定位失败：%s" % path.name)
            return 1
        path.write_text(raw.replace(esc_old, esc_new), encoding="utf-8")
        yaml.safe_load(path.read_text(encoding="utf-8"))
        print("已写入：%s（%d 张卡）" % (path.name, len(ids)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
