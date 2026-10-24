#!/usr/bin/env python3
"""Accept either HTML-only or full-video Dify output through one CLI entry."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
BASE = TOOLS_DIR.parent.parent
sys.path.insert(0, str(TOOLS_DIR))
sys.path.insert(0, str(TOOLS_DIR.parent / "scripts"))

from dify_auto_build import (  # noqa: E402
    clean_html_document,
    decode_json_value,
    parse_json_object,
    paste_is_complete,
    read_pasted_text,
)
from sync_video import (  # noqa: E402
    enforce_production_layout,
    ensure_root_composition,
    normalize_wall_clock_controller,
)


def unwrap_package(data: dict) -> dict:
    package = decode_json_value(data.get("build_package_json", data.get("build_package", data)))
    if isinstance(package, str):
        package = parse_json_object(package)
    return package if isinstance(package, dict) else data


def get_response(package: dict) -> dict:
    response = decode_json_value(package.get("heygen_response_json", package.get("heygen_response", {})))
    return response if isinstance(response, dict) else {}


def is_black_frame_output(package: dict, response: dict) -> bool:
    if response:
        return False
    return bool(str(package.get("voiceover_script", package.get("approved_voiceover_script", ""))).strip())


def is_full_video_output(package: dict, response: dict) -> bool:
    if not response:
        return False
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    return any((
        data.get("id"),
        data.get("video_id"),
        data.get("videoId"),
        data.get("status"),
        data.get("state"),
        data.get("video_url"),
        data.get("videoUrl"),
        response.get("video_id"),
        response.get("videoId"),
        response.get("status"),
        response.get("state"),
        response.get("video_url"),
        response.get("videoUrl"),
    ))


def read_editor_payload(project_name: str, input_path: Path | None = None, open_editor: bool = True) -> str:
    """Open a plain-text file in TextEdit and process it as soon as it is complete."""
    if input_path is None:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        input_path = BASE / "Dify输出" / f"{project_name}-{stamp}-dify-output.txt"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    if input_path.exists() and input_path.read_text(encoding="utf-8").strip():
        raise SystemExit(f"编辑器输入文件已存在且非空：{input_path}")
    input_path.write_text("", encoding="utf-8")
    print("TextEdit 将打开一个纯文本文件。请把 Dify 完整输出粘贴到TextEdit，不要粘贴到终端。")
    print(f"输入文件：{input_path}")
    print("内容完整后本命令会自动继续；通常无需手动保存，必要时按 Cmd-S。")
    if open_editor:
        subprocess.run(["open", "-a", "TextEdit", str(input_path)], check=True)
    deadline = time.time() + 1800
    while time.time() < deadline:
        try:
            text = input_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if text.strip() and paste_is_complete(text):
            print(f"已读取完整 Dify 输出：{len(text)} 字符")
            return text.strip()
        time.sleep(0.5)
    raise SystemExit(f"等待 TextEdit 输入超时：{input_path}")


def read_payload(input_file: Path | None, project_name: str, terminal_paste: bool = False) -> str:
    if input_file and terminal_paste:
        raise SystemExit("input_file 与 --terminal-paste 只能二选一")
    if input_file:
        return input_file.read_text(encoding="utf-8")
    if terminal_paste:
        return read_pasted_text("请把 Dify 完整最终输出直接粘贴到终端；检测到完整内容后自动开始：")
    return read_editor_payload(project_name)


def save_html_preview(project_name: str, html: str) -> Path:
    html = normalize_wall_clock_controller(html)
    html = ensure_root_composition(html, 30.0)
    html = enforce_production_layout(html)
    output = BASE / "HTML预览" / f"{project_name}.html"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html, encoding="utf-8")
    return output


def valid_project_name(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise SystemExit("项目名不能为空，也不能包含路径分隔符")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name", type=valid_project_name)
    parser.add_argument("input_file", type=Path, nargs="?")
    parser.add_argument("--terminal-paste", action="store_true", help="兼容模式：直接向终端粘贴；长内容可能受终端模拟器转码影响")
    parser.add_argument("--replace", action="store_true", help="需要重建同名项目时使用；旧项目会自动备份")
    parser.add_argument("--voice-file", type=Path, help="黑帧口播模式可选：使用已有音频替代 TTS")
    parser.add_argument("--tts-provider", choices=("mimo", "macos", "openai-compatible"), help="黑帧口播 TTS 供应商类型；默认 mimo")
    parser.add_argument("--tts-base-url", help="MiMo/OpenAI-compatible API 基础地址")
    parser.add_argument("--tts-model", help="TTS 模型或音色模型名")
    parser.add_argument("--tts-voice", help="音色 voice ID 或 macOS voice 名")
    parser.add_argument("--no-open", action="store_true", help="HTML-only 输出保存后不打开浏览器")
    args = parser.parse_args()

    text = read_payload(args.input_file, args.project_name, args.terminal_paste)
    parsed = parse_json_object(text)
    if isinstance(parsed, dict) and any(
        key in parsed for key in ("html_document", "html", "build_package_json", "build_package", "heygen_response_json", "voiceover_script")
    ):
        data = parsed
    elif "<html" in text.lower():
        data = {"html_document": text}
    else:
        raise SystemExit("输入内容不是合法 Dify JSON，也不是完整 HTML")
    package = unwrap_package(data)
    html = clean_html_document(package.get("html_document", package.get("html", "")))
    if "<!doctype html>" not in html.lower():
        raise SystemExit("Dify 输出缺少完整 html_document")
    response = get_response(package)

    tts_args = (args.voice_file, args.tts_provider, args.tts_base_url, args.tts_model, args.tts_voice)
    if any(tts_args) and not is_black_frame_output(package, response):
        raise SystemExit("TTS/音色参数只能用于黑帧口播输出")
    if is_black_frame_output(package, response):
        normalized_input = {
            "build_package_json": {
                **package,
                "html_document": html,
                "voiceover_script": str(package.get("voiceover_script", package.get("approved_voiceover_script", ""))).strip(),
            }
        }
        input_path = BASE / "Dify输出" / f"{args.project_name}-blackframe-input.json"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(json.dumps(normalized_input, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [sys.executable, str(TOOLS_DIR / "build_black_frame_project.py"), args.project_name, "--input-file", str(input_path)]
        if args.replace:
            command.append("--replace")
        if args.voice_file:
            command.extend(["--voice-file", str(args.voice_file)])
        if args.tts_provider:
            command.extend(["--tts-provider", args.tts_provider])
        if args.tts_base_url:
            command.extend(["--tts-base-url", args.tts_base_url])
        if args.tts_model:
            command.extend(["--tts-model", args.tts_model])
        if args.tts_voice:
            command.extend(["--voice-name", args.tts_voice])
        print("检测到黑帧口播输出：生成口播并渲染 MP4。")
        subprocess.run(command, check=True)
        print(f"完成：{BASE / args.project_name / '成片' / '最终视频.mp4'}")
        return

    if is_full_video_output(package, response):
        normalized_input = {
            "build_package_json": {
                **package,
                "html_document": html,
                "heygen_response_json": response,
            }
        }
        input_path = BASE / "Dify输出" / f"{args.project_name}-unified-input.json"
        input_path.parent.mkdir(parents=True, exist_ok=True)
        input_path.write_text(json.dumps(normalized_input, ensure_ascii=False, indent=2), encoding="utf-8")
        command = [sys.executable, str(TOOLS_DIR / "dify_auto_build.py"), args.project_name, "--input-file", str(input_path)]
        if args.replace:
            command.append("--replace")
        print("检测到全合一输出：自动下载媒体、同步字幕并渲染 MP4。")
        subprocess.run(command, check=True)
        print(f"完成：{BASE / args.project_name / '成片' / '最终视频.mp4'}")
        return

    output = save_html_preview(args.project_name, html)
    print("检测到仅生成 HTML 输出：已生成浏览器预览。")
    print(f"预览已生成：{output}")
    if not args.no_open:
        subprocess.run(["open", str(output)], check=True)


if __name__ == "__main__":
    main()
