#!/usr/bin/env python3
"""Paste a complete Dify workflow output in the terminal, wait for HeyGen, then render."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def decode_json_value(value, max_rounds: int = 6):
    for _ in range(max_rounds):
        if not isinstance(value, str):
            return value
        text = value.strip()
        try:
            value = json.loads(text)
        except Exception:
            return value
    return value


def clean_html_document(value: object) -> str:
    html = decode_json_value(value)
    if not isinstance(html, str):
        return ""
    lower = html.lower()
    start = lower.find("<!doctype html>")
    if start < 0:
        start = lower.find("<html")
    if start >= 0:
        html = html[start:]
    end = html.lower().rfind("</html>")
    if end >= 0:
        html = html[:end + len("</html>")]
    return html.strip()


def parse_json_object(text: str):
    """Parse a pasted Dify result even when it is wrapped in labels or a code fence."""
    raw = text.strip()
    if not raw:
        return None
    candidates = [raw]
    if raw.startswith("```"):
        first_newline = raw.find("\n")
        if first_newline >= 0:
            body = raw[first_newline + 1:]
            candidates.append(body[:body.rfind("```")] if "```" in body else body)
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except Exception:
            value = None
        value = decode_json_value(value)
        if isinstance(value, dict):
            return value
    decoder = json.JSONDecoder()
    for index, char in enumerate(raw):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(raw[index:])
        except Exception:
            continue
        value = decode_json_value(value)
        if isinstance(value, dict):
            return value
    return None


def paste_is_complete(text: str) -> bool:
    value = parse_json_object(text)
    if isinstance(value, dict) and any(
        key in value for key in ("html_document", "html", "build_package_json", "build_package", "heygen_response_json", "voiceover_script", "approved_script", "approved_package_json")
    ):
        return True
    lower = text.lower()
    if "</html>" not in lower:
        return False
    if "视频内容生产资料" in text:
        return any(marker in text for marker in ('"approved_script"', '"approved_package_json"', '"voiceover_script"'))
    return True


def read_terminal_paste(prompt: str, fd: int | None = None) -> str:
    """Read a large terminal paste in raw mode, avoiding the TTY canonical-line limit."""
    import termios
    import tty

    owns_fd = fd is None
    if owns_fd:
        fd = os.open("/dev/tty", os.O_RDWR)
    print(prompt)
    previous = termios.tcgetattr(fd)
    chunks: list[bytes] = []
    try:
        tty.setraw(fd)
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                break
            if b"\x03" in chunk:
                raise KeyboardInterrupt
            chunks.append(chunk)
            text = b"".join(chunks).decode("utf-8", errors="replace")
            if paste_is_complete(text):
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        try:
            termios.tcflush(fd, termios.TCIFLUSH)
        except OSError:
            pass
        if owns_fd:
            os.close(fd)
    text = b"".join(chunks).decode("utf-8", errors="replace").strip()
    if not text:
        raise SystemExit("没有读取到粘贴内容")
    return text


def read_pasted_text(prompt: str) -> str:
    """Read one complete Dify result without END markers or Ctrl-D.

    On a real terminal, raw mode allows arbitrarily long pastes. Piped input
    falls back to line reading and stops as soon as the result is complete.
    """
    if sys.stdin.isatty():
        return read_terminal_paste(prompt, fd=sys.stdin.fileno())
    print(prompt)
    lines: list[str] = []
    while True:
        line = sys.stdin.readline()
        if line == "":
            break
        if line.strip() in {"__END__", "**END__", "END"}:
            if lines:
                break
            continue
        lines.append(line)
        text = "".join(lines)
        if paste_is_complete(text):
            break
    text = "".join(lines).strip()
    if not text:
        raise SystemExit("没有读取到粘贴内容")
    return text


def parse_build_package(data: dict) -> dict:
    package = data.get("build_package_json", data.get("build_package", data))
    package = decode_json_value(package)
    if not isinstance(package, dict):
        raise SystemExit("Dify 输出必须是 JSON 对象或包含 build_package_json 的对象")
    response = decode_json_value(package.get("heygen_response_json", package.get("heygen_response", {})))
    if not isinstance(response, dict):
        raise SystemExit("heygen_response_json 必须是 JSON 对象")
    normalized = dict(package)
    normalized["html_document"] = clean_html_document(package.get("html_document"))
    normalized["heygen_response_json"] = response
    declared_id = str(package.get("heygen_video_id") or "").strip()
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    actual_id = str(data.get("id") or data.get("video_id") or data.get("videoId") or response.get("video_id") or "").strip()
    if declared_id and actual_id and declared_id != actual_id:
        raise SystemExit(f"顶层 heygen_video_id={declared_id} 与响应 video_id={actual_id} 不一致，拒绝混用旧响应")
    return normalized

def read_pasted_json() -> dict:
    raw = read_pasted_text("请把 Dify 本次运行的完整最终输出直接粘贴到终端（粘贴后不回显是正常的）；检测到完整内容后自动开始，无需回车：")
    data = parse_json_object(raw)
    if not isinstance(data, dict):
        raise SystemExit("Dify 输出不是合法 JSON 对象。请粘贴包含 build_package_json 的完整输出。")
    return parse_build_package(data)


def parse_response(value: object) -> dict:
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise SystemExit("heygen_response_json 必须是对象")
    return value


def find_value(value: object, names: list[str]):
    if isinstance(value, dict):
        for name in names:
            if value.get(name) not in (None, ""):
                return value[name]
        for child in value.values():
            found = find_value(child, names)
            if found not in (None, ""):
                return found
    elif isinstance(value, list):
        for child in value:
            found = find_value(child, names)
            if found not in (None, ""):
                return found
    return None


def poll_heygen(video_id: str, timeout_seconds: int, interval_seconds: int) -> dict:
    api_key = os.environ.get("HEYGEN_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("当前输出仍是 waiting。新版 Dify 工作流应内部等待完成；若使用旧流程，请设置 HEYGEN_API_KEY 后再等待")
    api_base = os.environ.get("HEYGEN_API_BASE", "https://api.heygen.com").rstrip("/")
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        request = urllib.request.Request(
            f"{api_base}/v3/videos/{video_id}",
            headers={"X-Api-Key": api_key, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            print(f"查询状态失败，稍后重试：{exc}")
            time.sleep(interval_seconds)
            continue
        status = str(find_value(payload, ["status", "state"]) or "").strip().lower()
        print(f"HeyGen 状态：{status or 'unknown'}")
        if status in {"completed", "failed", "cancelled"}:
            return payload
        time.sleep(interval_seconds)
    raise SystemExit(f"等待 HeyGen 超时（{timeout_seconds} 秒），video_id={video_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("project_name")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument("--input-file", type=Path, help="读取 Dify build_package_json/完整最终输出文件，无需粘贴")
    parser.add_argument("--replace", action="store_true", help="重渲染已有项目；旧项目先移动到 项目备份/，成功后保留备份")
    args = parser.parse_args()
    if (not args.project_name or args.project_name in {".", ".."} or
            "/" in args.project_name or "\\" in args.project_name):
        raise SystemExit("项目名不能为空，也不能包含路径分隔符")

    tools_dir = Path(__file__).resolve().parent
    base = tools_dir.parent.parent
    project_dir = base / args.project_name
    backup_dir = None
    if project_dir.exists() and not args.replace:
        raise SystemExit(f"项目文件夹已存在：{project_dir}。确认要重渲染时添加 --replace，旧项目会先备份")

    if args.input_file:
        try:
            raw_data = json.loads(args.input_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SystemExit(f"输入文件不是合法 JSON：{args.input_file}") from exc
        raw_data = decode_json_value(raw_data)
        if not isinstance(raw_data, dict):
            raise SystemExit("输入文件必须是 JSON 对象")
        data = parse_build_package(raw_data)
    else:
        data = read_pasted_json()
    html = data.get("html_document")
    response = parse_response(data.get("heygen_response_json"))
    if not isinstance(html, str) or "<!doctype html>" not in html.lower():
        raise SystemExit("Dify 输出缺少完整 html_document")

    staging = base / "Dify输出" / args.project_name
    staging.mkdir(parents=True, exist_ok=True)
    html_path = staging / "html_document.html"
    response_path = staging / "heygen_response.json"
    html_path.write_text(html, encoding="utf-8")
    response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
    voiceover = str(data.get("voiceover_script", data.get("approved_voiceover_script", ""))).strip()
    if voiceover:
        (staging / "voiceover_script.txt").write_text(voiceover + "\n", encoding="utf-8")

    def response_path_value(payload, *path):
        value = payload
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return ""
            value = value[key]
        return value if value not in (None, "") else ""

    status = str(response_path_value(response, "data", "status") or response_path_value(response, "data", "state") or find_value(response, ["status", "state"]) or "").strip().lower()
    video_id = str(response_path_value(response, "data", "id") or response_path_value(response, "data", "video_id") or response_path_value(response, "data", "videoId") or find_value(response, ["video_id", "videoId"]) or "").strip()
    if args.skip_render:
        print(f"已保存：{html_path}\n{response_path}")
        return
    if status != "completed" and video_id:
        print(f"HeyGen 尚未完成，开始自动等待：{video_id}")
        response = poll_heygen(video_id, args.timeout, args.interval)
        response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")

    if str(find_value(response, ["status", "state"]) or "").lower() != "completed":
        raise SystemExit("HeyGen 未完成，不能生成最终视频")
    video_url = str(find_value(response, ["video_url", "videoUrl"]) or "").strip()
    if not video_url:
        raise SystemExit("HeyGen completed 响应中缺少明确的 video_url")
    if video_id and video_id not in video_url:
        raise SystemExit(f"HeyGen video_url 与 video_id 不一致，拒绝渲染可能串片的旧视频：{video_id}")

    if project_dir.exists():
        backup_root = base / "项目备份"
        backup_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_dir = backup_root / f"{args.project_name}-{stamp}"
        suffix = 1
        while backup_dir.exists():
            backup_dir = backup_root / f"{args.project_name}-{stamp}-{suffix}"
            suffix += 1
        shutil.move(str(project_dir), str(backup_dir))
        print(f"旧项目已备份到：{backup_dir}")

    try:
        subprocess.run([
            "bash", str(tools_dir / "render_new_project.sh"),
            args.project_name, str(html_path), str(response_path),
        ], check=True)
    except Exception:
        failed_root = base / "失败项目"
        if project_dir.exists():
            failed_root.mkdir(parents=True, exist_ok=True)
            failed_dir = failed_root / f"{args.project_name}-{time.strftime('%Y%m%d-%H%M%S')}"
            shutil.move(str(project_dir), str(failed_dir))
            print(f"失败的半成品移动到：{failed_dir}")
        if backup_dir and backup_dir.exists():
            shutil.move(str(backup_dir), str(project_dir))
            print(f"已恢复旧项目：{project_dir}")
        raise


if __name__ == "__main__":
    main()
