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
- 只同步 status=ready 且不是 B 开头的卡（背景由 bgkit 走 canvas，不进 TPL）。
- {{x}} → %(x)s，% 转义成 %%。
- 缺 sel2 时给个默认值，避免 L01 这类双目标卡展开时报 KeyError。
"""
import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
REPO = ROOT.parent.parent
YAML = REPO / "Dify工作流" / "04_黑帧口播_分组生成.yml"

sys.path.insert(0, str(ROOT))
import build_presets as bp  # noqa: E402


def build_blocks():
    cards = [
        c for c in bp.load()["presets"]
        if c.get("status") == "ready" and not c["id"].startswith("B")
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
    return "\n".join(tpl) + "\n" + "\n".join(default), [c["id"] for c in cards]


def audit_params():
    """每张 ready 卡只带自己的 params 也必须能格式化；缺参数就是坏卡。"""
    bad = []
    for c in bp.load()["presets"]:
        if c.get("status") != "ready" or c["id"].startswith("B"):
            continue
        vals = dict(c.get("params") or {})
        vals.update({"sel": "x", "at": "at(0.2)", "k": "0", "sel2": "y"})
        try:
            bp.to_python_template(c["code"]) % vals
        except Exception as e:
            bad.append((c["id"], str(e)[:40]))
    return bad


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

    raw = YAML.read_text(encoding="utf-8")
    import yaml
    data = yaml.safe_load(raw)
    node = None
    for n in data["workflow"]["graph"]["nodes"]:
        if n.get("data", {}).get("title", "").startswith("H02SX"):
            node = n
            break
    if not node:
        print("找不到 H02SX 节点")
        return 1

    code = node["data"]["code"]
    new_code, ids = splice(code)
    compile(new_code, "h02sx", "exec")

    bad = audit_params()
    if bad:
        print("参数不全的卡：")
        for cid, msg in bad:
            print("  %s  %s" % (cid, msg))
        return 1

    if new_code == code:
        print("已同步：%d 张卡" % len(ids))
        return 0
    if args.check:
        print("未同步：展开器与 presets.json 不一致，请运行 sync_expander.py")
        return 1

    esc_old = json.dumps(code, ensure_ascii=False)[1:-1]
    esc_new = json.dumps(new_code, ensure_ascii=False)[1:-1]
    if raw.count(esc_old) != 1:
        print("YAML 里的代码块定位失败，未写入")
        return 1
    YAML.write_text(raw.replace(esc_old, esc_new), encoding="utf-8")

    yaml.safe_load(YAML.read_text(encoding="utf-8"))
    print("已写入：%d 张卡" % len(ids))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
