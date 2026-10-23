#!/usr/bin/env python3
"""Save a manually copied Dify html_document as a browser-viewable HTML preview."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
BASE = TOOLS_DIR.parent.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(TOOLS_DIR.parent / "scripts"))
from dify_auto_build import clean_html_document, decode_json_value, parse_json_object, read_pasted_text  # noqa: E402
from sync_video import enforce_production_layout, ensure_root_composition, normalize_wall_clock_controller  # noqa: E402


def extract_html(value: object) -> str:
    data = decode_json_value(value)
    if isinstance(data, dict):
        data = data.get("html_document", data.get("html", ""))
    html = clean_html_document(data)
    if "<!doctype html>" not in html.lower():
        raise SystemExit("输入中没有完整 html_document")
    return html


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_file", type=Path, nargs="?")
    parser.add_argument("--paste", action="store_true", help="从终端手动粘贴 Dify 输出，解析完成后回车即结束")
    parser.add_argument("--output", type=Path, default=Path("HTML预览/preview.html"))
    parser.add_argument("--open", action="store_true", help="保存后在浏览器打开")
    args = parser.parse_args()

    if args.paste and args.input_file:
        raise SystemExit("--paste 与 input_file 只能二选一")
    if args.paste:
        text = read_pasted_text("请把 Dify 输出直接粘贴到终端（粘贴后不回显是正常的）；检测到完整内容后自动开始，无需回车：")
    elif args.input_file:
        text = args.input_file.read_text(encoding="utf-8")
    else:
        raise SystemExit("必须提供 input_file，或使用 --paste")
    parsed = parse_json_object(text)
    raw = parsed if isinstance(parsed, dict) and any(
        key in parsed for key in ("html_document", "html", "build_package_json", "build_package")
    ) else text
    html = extract_html(raw)
    html = normalize_wall_clock_controller(html)
    html = ensure_root_composition(html, 30.0)
    html = enforce_production_layout(html)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print("saved:", args.output.resolve())
    if args.open:
        import subprocess
        subprocess.run(["open", str(args.output.resolve())], check=True)


if __name__ == "__main__":
    main()
