#!/usr/bin/env python3
"""Build a black-frame video from Dify HTML plus the approved voice-over script."""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import urllib.request
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = TOOLS_DIR.parent
BASE = RUNTIME_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from dify_auto_build import clean_html_document, decode_json_value, parse_json_object  # noqa: E402


def valid_project_name(value: str) -> str:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise SystemExit("项目名不能为空，也不能包含路径分隔符")
    return value


def extract_package(data: dict) -> dict:
    package = decode_json_value(data.get("build_package_json", data.get("build_package", data)))
    if isinstance(package, str):
        package = parse_json_object(package)
    return package if isinstance(package, dict) else data


def normalize_input(data: dict) -> dict:
    package = extract_package(data)
    html = clean_html_document(package.get("html_document", package.get("html", "")))
    voiceover = str(package.get("voiceover_script", package.get("approved_voiceover_script", ""))).strip()
    if "<!doctype html>" not in html.lower():
        raise SystemExit("Dify 输出缺少完整 html_document")
    if not voiceover:
        raise SystemExit("Dify 输出缺少 voiceover_script/approved_voiceover_script")
    if 'data-render-mode="black-frame"' not in html:
        raise SystemExit("HTML 缺少 data-render-mode=\"black-frame\"，拒绝混入数字人版本")
    if 'data-video-role="avatar"' in html or 'data-media-id="heygen_avatar"' in html:
        raise SystemExit("黑帧项目不得包含数字人媒体占位")
    return {"html_document": html, "voiceover_script": voiceover, "render_mode": "black_frame"}


def generate_mimo_voice(script: str, output: Path, model: str, voice: str, base_url: str) -> None:
    api_key = os.environ.get("MIMO_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("缺少 MIMO_API_KEY；请设置环境变量，但不要把 Key 写入项目文件或日志")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model or "mimo-v2.5-tts",
        "messages": [
            {"role": "user", "content": "自然、清晰、适合中文短视频口播的语气。"},
            {"role": "assistant", "content": script.strip()},
        ],
        "audio": {"format": "mp3", "voice": voice or "mimo_default"},
        "stream": False,
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={"api-key": api_key, "Content-Type": "application/json", "Accept": "application/json"},
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise SystemExit(f"MiMo TTS API 调用失败：{type(exc).__name__}: {exc}") from exc
    try:
        audio_b64 = result["choices"][0]["message"]["audio"]["data"]
        audio = base64.b64decode(audio_b64)
    except Exception as exc:
        raise SystemExit("MiMo TTS 响应缺少 choices[0].message.audio.data") from exc
    if len(audio) < 1000:
        raise SystemExit("MiMo TTS 返回的音频过短，拒绝写入项目")
    output.write_bytes(audio)
    print(f"tts_provider=mimo model={model} voice={voice}")


def generate_macos_voice(script: str, output: Path, voice_name: str, rate: int) -> None:
    if shutil.which("say") is None:
        raise SystemExit("缺少 macOS say 命令，无法生成本地口播")
    if shutil.which("ffmpeg") is None:
        raise SystemExit("缺少 ffmpeg，无法生成 MP3 口播")
    output.parent.mkdir(parents=True, exist_ok=True)
    aiff = output.with_suffix(".aiff")
    script_path = output.with_suffix(".txt")
    script_path.write_text(script.strip() + "\n", encoding="utf-8")
    subprocess.run([
        "say", "-v", voice_name, "-r", str(rate), "-f", str(script_path), "-o", str(aiff),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(aiff),
        "-ac", "1", "-ar", "44100", "-acodec", "libmp3lame", "-b:a", "160k",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(output),
    ], check=True)
    aiff.unlink(missing_ok=True)


def generate_api_voice(script: str, output: Path, base_url: str, model: str, voice: str) -> None:
    api_key = os.environ.get("TTS_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("缺少 TTS_API_KEY；API 音色需要设置环境变量，但不会把 Key 写入项目文件")
    endpoint = base_url.rstrip("/") + "/audio/speech"
    payload = json.dumps({
        "model": model,
        "voice": voice,
        "input": script.strip(),
        "response_format": "mp3",
    }, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            audio = response.read()
    except Exception as exc:
        raise SystemExit(f"TTS API 调用失败：{type(exc).__name__}: {exc}") from exc
    if len(audio) < 1000:
        raise SystemExit("TTS API 返回的音频过短，拒绝写入项目")
    output.write_bytes(audio)
    print(f"tts_provider=openai-compatible voice={voice} model={model}")


def generate_background_music(project_dir: Path) -> None:
    media_dir = project_dir / "媒体"
    music_mp3 = media_dir / "背景音乐.mp3"
    if music_mp3.exists():
        return
    music_wav = media_dir / "背景音乐.wav"
    subprocess.run([
        sys.executable, str(RUNTIME_DIR / "scripts" / "generate_background_music.py"), "--output", str(music_wav),
    ], check=True)
    subprocess.run([
        "ffmpeg", "-y", "-i", str(music_wav),
        "-acodec", "libmp3lame", "-b:a", "160k",
        "-af", "loudnorm=I=-24:TP=-2:LRA=11", str(music_mp3),
    ], check=True)
    music_wav.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="处理黑帧口播 Dify 输出：生成口播并渲染 MP4")
    parser.add_argument("project_name", type=valid_project_name)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--voice-file", type=Path, help="可选：使用已有音频替代 TTS")
    parser.add_argument("--voice-name", default=os.environ.get("MIMO_TTS_VOICE", os.environ.get("TTS_VOICE", "mimo_default")), help="音色名称：MiMo 预置音色、macOS voice 或其他 TTS voice ID")
    parser.add_argument("--voice-rate", type=int, default=190, help="仅 macOS TTS 使用的语速")
    parser.add_argument("--tts-provider", choices=("mimo", "macos", "openai-compatible"), default=os.environ.get("TTS_PROVIDER", "mimo"))
    parser.add_argument("--tts-base-url", default=os.environ.get("TTS_BASE_URL", "https://api.xiaomimimo.com/v1"), help="MiMo/OpenAI-compatible API 基础地址")
    parser.add_argument("--tts-model", default=os.environ.get("TTS_MODEL", "mimo-v2.5-tts"), help="TTS API 模型名")
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()

    raw = json.loads(args.input_file.read_text(encoding="utf-8"))
    data = normalize_input(raw)
    project_dir = BASE / args.project_name
    if project_dir.exists() and not args.replace:
        raise SystemExit(f"项目文件夹已存在：{project_dir}。确认重渲染时添加 --replace")

    staging = BASE / "Dify输出" / args.project_name
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "html_document.html").write_text(data["html_document"], encoding="utf-8")
    (staging / "voiceover_script.txt").write_text(data["voiceover_script"] + "\n", encoding="utf-8")

    if args.skip_render:
        print(f"已保存：{staging / 'html_document.html'}")
        print(f"已保存：{staging / 'voiceover_script.txt'}")
        return

    backup_dir = None
    if project_dir.exists():
        backup_root = BASE / "项目备份"
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
        (project_dir / "媒体").mkdir(parents=True, exist_ok=True)
        (project_dir / "成片").mkdir(parents=True, exist_ok=True)
        (project_dir / "字幕").mkdir(parents=True, exist_ok=True)
        shutil.copy2(RUNTIME_DIR / "hyperframes.json", project_dir / "hyperframes.json")
        shutil.copy2(RUNTIME_DIR / "render.sh", project_dir / "render.sh")
        shutil.copytree(RUNTIME_DIR / "scripts", project_dir / "脚本")
        shutil.copytree(RUNTIME_DIR / "assets", project_dir / "素材")
        shutil.copy2(RUNTIME_DIR / "docs" / "视频说明.md", project_dir / "视频说明.md")
        shutil.copy2(RUNTIME_DIR / "docs" / "项目说明.md", project_dir / "项目说明.md")
        (project_dir / "index.html").write_text(data["html_document"], encoding="utf-8")
        voice_path = project_dir / "媒体" / "口播.mp3"
        (project_dir / "口播文案.txt").write_text(data["voiceover_script"] + "\n", encoding="utf-8")
        if args.voice_file:
            if not args.voice_file.exists():
                raise SystemExit(f"找不到口播音频：{args.voice_file}")
            subprocess.run([
                "ffmpeg", "-y", "-i", str(args.voice_file), "-ac", "1", "-ar", "44100",
                "-acodec", "libmp3lame", "-b:a", "160k",
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", str(voice_path),
            ], check=True)
        elif args.tts_provider == "macos":
            generate_macos_voice(data["voiceover_script"], voice_path, args.voice_name, args.voice_rate)
        elif args.tts_provider == "mimo":
            generate_mimo_voice(
                data["voiceover_script"], voice_path, args.tts_model,
                args.voice_name, args.tts_base_url,
            )
        else:
            generate_api_voice(
                data["voiceover_script"], voice_path, args.tts_base_url,
                args.tts_model, args.voice_name,
            )
        generate_background_music(project_dir)
        subprocess.run(["bash", str(project_dir / "render.sh")], cwd=project_dir, check=True)
    except Exception:
        failed_root = BASE / "失败项目"
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
