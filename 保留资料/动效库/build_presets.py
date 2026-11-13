#!/usr/bin/env python3
"""把 保留资料/动效库/presets.json 派生成两份产物，避免三处手抄。

用法：
  python3 build_presets.py --demo <目录>     # 写出 cards.js，给能力卡样张页用
  python3 build_presets.py --dify            # 打印 Dify H02SX 需要的 TPL / DEFAULTS 片段

约定：
  presets.json 里的 code 用 {{name}} 占位；Dify 侧需要 %(name)s，
  这里统一转换，并转义 % 号。新增卡片只改 presets.json，再跑一次。
"""
import argparse
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent
PRESETS = ROOT / "presets.json"


def load():
    data = json.loads(PRESETS.read_text(encoding="utf-8"))
    return data


def to_python_template(code: str) -> str:
    """{{x}} -> %(x)s，同时把裸 % 转义，供 Python % 格式化使用。"""
    sentinel = "\x00"
    code = code.replace("%", sentinel)
    code = re.sub(r"\{\{(\w+)\}\}", r"%(\1)s", code)
    return code.replace(sentinel, "%%")


def emit_demo(outdir: pathlib.Path, data):
    outdir.mkdir(parents=True, exist_ok=True)
    cards = {p["id"]: p for p in data["presets"] if p.get("status") == "ready"}
    payload = {
        cid: {
            "id": cid,
            "name": c["name"],
            "family": c.get("family", ""),
            "layer": c.get("layer", ""),
            "params": c.get("params", {}),
            "code": c["code"],
            "use": c.get("use", ""),
        }
        for cid, c in cards.items()
    }
    js = "/* 由 build_presets.py 从 presets.json 生成，不要手改 */\nwindow.CARDS = "
    js += json.dumps(payload, ensure_ascii=False, indent=1)
    js += ";\n"
    (outdir / "cards.js").write_text(js, encoding="utf-8")
    print(f"cards.js -> {outdir} ({len(payload)} 张)")


def emit_dify(data):
    cards = [p for p in data["presets"] if p.get("status") == "ready"]
    lines = ["TPL = {"]
    for c in cards:
        tpl = to_python_template(c["code"])
        lines.append('    "%s": """%s""",' % (c["id"], tpl))
    lines.append("}")
    lines.append("")
    lines.append("DEFAULTS = {")
    for c in cards:
        keys = {k: v for k, v in (c.get("params") or {}).items()}
        keys.setdefault("dur", 0.6)
        keys.setdefault("stagger", 0.05)
        lines.append('    "%s": %s,' % (c["id"], json.dumps(keys, ensure_ascii=False)))
    lines.append("}")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo")
    ap.add_argument("--dify", action="store_true")
    args = ap.parse_args()
    data = load()
    if args.demo:
        emit_demo(pathlib.Path(args.demo), data)
    if args.dify:
        emit_dify(data)


if __name__ == "__main__":
    main()
