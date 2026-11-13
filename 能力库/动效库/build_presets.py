#!/usr/bin/env python3
"""presets.json 的派生工具（2026-11-13 起只留 Dify 模板与参数展开）。

用法：
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
    ap.add_argument("--dify", action="store_true")
    args = ap.parse_args()
    data = load()
    if args.dify:
        emit_dify(data)


if __name__ == "__main__":
    main()
