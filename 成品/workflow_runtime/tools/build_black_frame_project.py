#!/usr/bin/env python3
"""Build a black-frame video from Dify HTML plus the approved voice-over script."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import urllib.error
import urllib.request
import subprocess
import sys
import tempfile
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


def repair_scene_anchors(html: str) -> tuple[str, list[str]]:
    """把 #s01 这类场景锚点改写成 [data-scene="s01"]。

    本地同步会把 section 的 id 改写成 scene-<id>，模型若用 #s01 写选择器，
    动效会全部命中 0 个元素，成片是静帧。这里与 Dify 的 H03 保持同一套兜底逻辑。
    """
    scene_ids: list[str] = []
    for match in re.finditer(r'data-scene=["\']([^"\']+)["\']', html):
        if match.group(1) not in scene_ids:
            scene_ids.append(match.group(1))
    fixed: list[str] = []
    for sid in scene_ids:
        if re.search(r'(?<![\w-])id=["\']' + re.escape(sid) + r'["\']', html):
            continue
        pattern = re.compile(r"#" + re.escape(sid) + r"(?![\w-])")
        if not pattern.search(html):
            continue

        def _swap(match, _sid=sid):
            head = match.string[:match.start()]
            outer = '"' if head.rfind('"') > head.rfind("'") else "'"
            inner = "'" if outer == '"' else '"'
            return "[data-scene=%s%s%s]" % (inner, _sid, inner)

        html = pattern.sub(_swap, html)
        fixed.append(sid)
    return html, fixed


def sanitize_scene_scope(html: str, storyboard: dict) -> tuple[str, list[str]]:
    """只保留分镜里的 scene、去掉重复 scene，并把 sentence_ids 校正回分镜。

    Dify 的 H03 也会做同一件事；这里再做一次是为了让旧的 Dify 输出、
    或者 H03 之前生成的 html_document 也能被本地构建修好。
    """
    scenes = storyboard.get("scenes") if isinstance(storyboard, dict) else []
    storyboard_ids = set()
    sentence_by_scene = {}
    for scene in scenes or []:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id") or "").strip()
        if not scene_id:
            continue
        storyboard_ids.add(scene_id)
        refs = scene.get("sentence_ids")
        if isinstance(refs, str):
            refs = [refs]
        if not isinstance(refs, list):
            refs = []
        sentence_by_scene[scene_id] = [str(item).strip() for item in refs if str(item).strip()]

    def set_attribute(tag: str, name: str, value: str) -> str:
        pattern = re.compile(r"\s" + re.escape(name) + r'="[^"]*"')
        replacement = ' %s="%s"' % (name, value)
        if pattern.search(tag):
            return pattern.sub(replacement, tag, count=1)
        return tag[:-1].rstrip() + replacement + ">"

    seen = set()
    dropped = []

    def repl(match):
        tag, inner = match.group(1), match.group(2)
        sid_match = re.search(r'\bdata-scene="([^"]+)"', tag)
        scene_id = sid_match.group(1) if sid_match else ""
        if storyboard_ids:
            if scene_id not in storyboard_ids:
                dropped.append(scene_id or "?")
                return ""
            if scene_id in seen:
                dropped.append(scene_id)
                return ""
        if scene_id:
            seen.add(scene_id)
            refs = sentence_by_scene.get(scene_id)
            if refs:
                tag = set_attribute(tag, "data-sentence-ids", " ".join(refs))
        return tag + inner

    html = re.sub(r"(<section\b[^>]*>)([\s\S]*?</section>)", repl, html, flags=re.I)
    return html, dropped


def normalize_input(data: dict) -> dict:
    package = extract_package(data)
    html = clean_html_document(package.get("html_document", package.get("html", "")))
    html, anchored = repair_scene_anchors(html)
    if anchored:
        print("已修正动效场景锚点 #id → [data-scene=...]：" + "、".join(anchored))
    storyboard = package.get("storyboard") if isinstance(package.get("storyboard"), dict) else {}
    html, dropped_scenes = sanitize_scene_scope(html, storyboard)
    if dropped_scenes:
        print("已丢弃 %d 个重复或分镜外的 scene：%s" % (len(dropped_scenes), "、".join(dropped_scenes[:10])))
    voiceover = str(package.get("voiceover_script", package.get("approved_voiceover_script", ""))).strip()
    if "<!doctype html>" not in html.lower():
        raise SystemExit("Dify 输出缺少完整 html_document")
    if not voiceover:
        raise SystemExit("Dify 输出缺少 voiceover_script/approved_voiceover_script")
    if 'data-render-mode="black-frame"' not in html:
        raise SystemExit("HTML 缺少 data-render-mode=\"black-frame\"，拒绝混入数字人版本")
    if re.search(r'data-video-role="avatar"|data-media-id="heygen_avatar"|class="[^"]*(?:avatar-window|black-frame)', html, re.I):
        raise SystemExit("无数字人项目不得包含数字人媒体、数字人窗口或黑帧占位")
    raw_tts = package.get("tts_config", {})
    tts_config = raw_tts if isinstance(raw_tts, dict) else {}
    return {
        "html_document": html,
        "image_plan": extract_image_plan(data, package),
        "voiceover_script": voiceover,
        "render_mode": "black_frame",
        "tts_config": {
            "provider": str(tts_config.get("provider", "")).strip(),
            "base_url": str(tts_config.get("base_url", "")).strip(),
            "model": str(tts_config.get("model", "")).strip(),
            "voice": str(tts_config.get("voice", "")).strip(),
        },
    }


IMAGE_PLACEHOLDER = re.compile(r"\{\{IMG:([A-Za-z0-9_-]+)\}\}")


def extract_image_plan(raw: dict, package: dict) -> dict:
    """图像计划可能来自 H01P 的透传字段，也可能被包成字符串。"""
    candidates = [
        raw.get("image_plan_json") if isinstance(raw, dict) else None,
        package.get("image_plan_json"),
        raw.get("image_plan") if isinstance(raw, dict) else None,
        package.get("image_plan"),
    ]
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
        if isinstance(candidate, str) and candidate.strip():
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def placeholder_ids(html: str) -> list[str]:
    return sorted(set(IMAGE_PLACEHOLDER.findall(html)))


def generate_images(project_dir: Path, plan_path: Path, args) -> None:
    script = RUNTIME_DIR / "scripts" / "generate_images.py"
    if not script.exists():
        raise SystemExit("缺少 generate_images.py：" + str(script))
    command = [
        sys.executable, str(script),
        "--plan", str(plan_path),
        "--out", str(project_dir / "媒体" / "图片"),
    ]
    if args.image_dry_run:
        command.append("--dry-run")
    if args.image_only_ids:
        command.extend(["--only", args.image_only_ids])
    print("开始生成图像：" + str(plan_path))
    subprocess.run(command, check=True)


IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def image_mapping(project_dir: Path, image_ids: list[str]) -> dict[str, Path]:
    """按「已按 id 命名的优先 → 其余按修改时间从早到晚」对号，不改用户文件名。"""
    image_dir = project_dir / "媒体" / "图片"
    if not image_dir.exists():
        return {}
    files = [
        item for item in image_dir.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_EXTS and not item.name.startswith("_")
    ]
    by_id = {item.stem: item for item in files if item.stem in image_ids}
    unnamed = sorted(
        [item for item in files if item.stem not in image_ids],
        key=lambda item: (item.stat().st_mtime, item.name),
    )
    mapping: dict[str, Path] = {}
    cursor = 0
    for image_id in image_ids:
        if image_id in by_id:
            mapping[image_id] = by_id[image_id]
        elif cursor < len(unnamed):
            mapping[image_id] = unnamed[cursor]
            cursor += 1
    return mapping


def replace_image_placeholders(html: str, project_dir: Path, image_ids: list[str], allow_missing: bool) -> str:
    """把 {{IMG:id}} 换成真实文件路径；文件保持原名，只做映射。"""
    mapping = image_mapping(project_dir, image_ids)
    missing: list[str] = []
    used: list[str] = []

    def _swap(match):
        image_id = match.group(1)
        used.append(image_id)
        target = mapping.get(image_id)
        if target is not None and target.stat().st_size > 10000:
            safe_name = image_id + target.suffix.lower()
            if target.name == safe_name:
                return "媒体/图片/" + target.name
            # 即梦下载名带中文和标点，HTML 里引用会出问题；副本放 _resolved/，主目录保持干净
            safe_dir = target.parent / "_resolved"
            safe_dir.mkdir(parents=True, exist_ok=True)
            safe_path = safe_dir / safe_name
            if not safe_path.exists() or safe_path.stat().st_mtime < target.stat().st_mtime:
                shutil.copy2(target, safe_path)
            return "媒体/图片/_resolved/" + safe_name
        missing.append(image_id)
        return "媒体/图片/" + image_id + ".png"

    html = IMAGE_PLACEHOLDER.sub(_swap, html)
    if used:
        print("图片引用 %d 处，涉及 %d 张：%s" % (len(used), len(set(used)), "、".join(sorted(set(used))[:12])))
    if missing:
        message = "这些图片没有生成，画面会缺图：" + "、".join(sorted(set(missing)))
        if not allow_missing:
            raise SystemExit(message + "（先跑生图，或加 --allow-missing-images 强行出片）")
        print("警告：" + message)
    return html


def check_scene_images(html: str) -> list[str]:
    """返回既没有图片、也没有声明 data-visual=html 的 scene id。"""
    without: list[str] = []
    for match in re.finditer(r"<(?:section|div)\b[^>]*>", html, flags=re.I):
        head = match.group(0)
        cls = re.search(r'class=["\']([^"\']*)["\']', head)
        if not cls or "scene" not in cls.group(1).split():
            continue
        sid = re.search(r'data-scene=["\']([^"\']+)["\']', head)
        visual = re.search(r'data-visual=["\']([^"\']+)["\']', head)
        visual = visual.group(1).strip().lower() if visual else ""
        end = html.find("</section>", match.end())
        inner = html[match.end():end if end >= 0 else len(html)]
        if "媒体/图片/" in inner or visual == "html":
            continue
        without.append(sid.group(1) if sid else "?")
    return without


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
    output.parent.mkdir(parents=True, exist_ok=True)
    auth_options = [
        {"Authorization": "Bearer " + api_key},
        {"api-key": api_key},
        {"X-Api-Key": api_key},
    ]
    result = None
    last_error = None
    for auth_headers in auth_options:
        headers = {"Content-Type": "application/json", "Accept": "application/json", **auth_headers}
        request = urllib.request.Request(endpoint, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code == 401:
                continue
            raise SystemExit(f"MiMo TTS API 调用失败：HTTP Error {exc.code}") from exc
        except Exception as exc:
            raise SystemExit(f"MiMo TTS API 调用失败：{type(exc).__name__}: {exc}") from exc
    if result is None:
        raise SystemExit("MiMo TTS 鉴权失败（401）：请确认 MIMO_API_KEY 是 Xiaomi MiMo 的有效 API Key，并匹配当前 Base 地址")
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
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(line_buffering=True)
    parser = argparse.ArgumentParser(description="处理黑帧口播 Dify 输出：生成口播并渲染 MP4")
    parser.add_argument("project_name", type=valid_project_name)
    parser.add_argument("--input-file", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--voice-file", type=Path, help="可选：使用已有音频替代 TTS")
    parser.add_argument("--voice-name", default=None, help="音色名称：MiMo 预置音色、macOS voice 或其他 TTS voice ID；默认读取 Dify 配置或 mimo_default")
    parser.add_argument("--voice-rate", type=int, default=190, help="仅 macOS TTS 使用的语速")
    parser.add_argument("--tts-provider", choices=("mimo", "macos", "openai-compatible"), default=None)
    parser.add_argument("--tts-base-url", default=None, help="MiMo/OpenAI-compatible API 基础地址；默认读取 Dify 配置或 https://api.xiaomimimo.com/v1")
    parser.add_argument("--tts-model", default=None, help="TTS API 模型名；默认读取 Dify 配置或 mimo-v2.5-tts")
    parser.add_argument("--no-open", action="store_true", help="准备完成后不自动打开图片目录")
    parser.add_argument("--prepare", action="store_true", help="只建项目、落图像计划、出提示词包，不出图不渲染（手动出图的第一步）")
    parser.add_argument("--skip-images", action="store_true", help="跳过生图，直接用 媒体/图片/ 里已有的文件")
    parser.add_argument("--images-only", action="store_true", help="只生成图片，不生成口播、不渲染")
    parser.add_argument("--allow-missing-images", action="store_true", help="缺图也继续渲染（只用于排查版面）")
    parser.add_argument("--image-dry-run", action="store_true", help="用占位图跑通链路，不调用生图 API")
    parser.add_argument("--image-only-ids", default="", help="只生成这些图片 id，逗号分隔，用于先看一张效果")
    parser.add_argument("--skip-render", action="store_true")
    args = parser.parse_args()
    if args.prepare:
        args.images_only = True
        args.skip_images = True

    raw = json.loads(args.input_file.read_text(encoding="utf-8"))
    data = normalize_input(raw)
    tts_config = data.get("tts_config", {})
    provider = args.tts_provider or tts_config.get("provider") or os.environ.get("TTS_PROVIDER", "mimo")
    base_url = args.tts_base_url or tts_config.get("base_url") or os.environ.get("TTS_BASE_URL", "https://api.xiaomimimo.com/v1")
    model = args.tts_model or tts_config.get("model") or os.environ.get("TTS_MODEL", "mimo-v2.5-tts")
    voice_name = args.voice_name or tts_config.get("voice") or os.environ.get("MIMO_TTS_VOICE", os.environ.get("TTS_VOICE", "mimo_default"))
    project_dir = BASE / args.project_name
    if project_dir.exists() and not args.replace:
        final_video = project_dir / "成片" / "最终视频.mp4"
        if final_video.exists():
            raise SystemExit(f"项目文件夹已存在且包含成片：{project_dir}。确认重渲染时添加 --replace")
        print(f"发现未完成项目：{project_dir}；将自动备份半成品并重建")
        args.replace = True

    staging = BASE / "Dify输出" / args.project_name
    staging.mkdir(parents=True, exist_ok=True)
    (staging / "html_document.html").write_text(data["html_document"], encoding="utf-8")
    (staging / "voiceover_script.txt").write_text(data["voiceover_script"] + "\n", encoding="utf-8")

    if args.skip_render:
        print(f"已保存：{staging / 'html_document.html'}")
        print(f"已保存：{staging / 'voiceover_script.txt'}")
        return

    backup_dir = None
    preserved_media = None
    if project_dir.exists():
        final_video = project_dir / "成片" / "最终视频.mp4"
        if not final_video.exists():
            # 未完成项目重建时保住 媒体/：已经花钱生成的图片和口播不该被删掉
            media_dir = project_dir / "媒体"
            if media_dir.exists() and any(media_dir.iterdir()):
                preserved_media = Path(tempfile.mkdtemp(prefix="blackframe-media-")) / "媒体"
                shutil.move(str(media_dir), str(preserved_media))
                print("未完成项目已清理，媒体目录临时保留（图片/口播不会被重新生成）")
            else:
                print("未完成项目已清理，不保留备份")
            shutil.rmtree(project_dir)
        else:
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
        if preserved_media and preserved_media.exists():
            for item in sorted(preserved_media.iterdir()):
                target = project_dir / "媒体" / item.name
                if target.exists():
                    continue
                shutil.move(str(item), str(target))
            shutil.rmtree(preserved_media.parent, ignore_errors=True)
            print("已恢复 媒体/ 里的图片与音频")
        (project_dir / "成片").mkdir(parents=True, exist_ok=True)
        (project_dir / "字幕").mkdir(parents=True, exist_ok=True)
        (project_dir / "媒体" / "图片").mkdir(parents=True, exist_ok=True)
        shutil.copy2(RUNTIME_DIR / "hyperframes.json", project_dir / "hyperframes.json")
        shutil.copy2(RUNTIME_DIR / "render.sh", project_dir / "render.sh")
        shutil.copytree(RUNTIME_DIR / "scripts", project_dir / "脚本")
        shutil.copytree(RUNTIME_DIR / "assets", project_dir / "素材")
        shutil.copy2(RUNTIME_DIR / "docs" / "视频说明.md", project_dir / "视频说明.md")
        shutil.copy2(RUNTIME_DIR / "docs" / "项目说明.md", project_dir / "项目说明.md")

        image_plan = data.get("image_plan") or {}
        plan_path = project_dir / "媒体" / "图片计划.json"
        if image_plan:
            plan_path.write_text(json.dumps(image_plan, ensure_ascii=False, indent=2), encoding="utf-8")
            images = image_plan.get("images") if isinstance(image_plan.get("images"), list) else []
            photo_images = [item for item in images if isinstance(item, dict) and str(item.get("role") or "").lower() != "html"]
            html_images = [item for item in images if isinstance(item, dict) and str(item.get("role") or "").lower() == "html"]
            print("图像计划：%d 张照片 + %d 屏 HTML 背景，已写入 %s" % (len(photo_images), len(html_images), plan_path))
        wanted = placeholder_ids(data["html_document"])
        if wanted:
            if not image_plan:
                raise SystemExit("HTML 里有 %d 个图片占位，但 Dify 输出没有 image_plan_json：H01P 没产出图像计划，重跑 Dify" % len(wanted))
            if not args.skip_images:
                generate_images(project_dir, plan_path, args)
        else:
            if not re.search(r'data-visual=["\']html["\']', data["html_document"]):
                print("警告：HTML 里没有任何 {{IMG:...}} 占位，也没有 data-visual=html 的无图屏（旧版输出）")
        if args.images_only:
            if plan_path.exists():
                subprocess.run([
                    sys.executable, str(RUNTIME_DIR / "scripts" / "generate_images.py"),
                    "--plan", str(plan_path),
                    "--sheet", str(project_dir / "媒体" / "出图清单.html"),
                ], check=False, cwd=str(project_dir))
            if args.skip_images:
                image_dir = project_dir / "媒体" / "图片"
                print("项目已准备好。提示词在 媒体/出图/，图片放进 " + str(image_dir))
                print("放好后重跑同一条命令（去掉 --prepare），加 --skip-images 合并出片。")
                if sys.platform == "darwin" and not args.no_open:
                    subprocess.run(["open", str(image_dir)], check=False)
            else:
                print("图片已生成，跳过口播与渲染：" + str(project_dir / "媒体" / "图片"))
            return
        image_ids = [str(item.get("id")) for item in (image_plan.get("images") or [])
                     if isinstance(item, dict) and item.get("id") and str(item.get("role") or "").lower() != "html"]
        if not image_ids:
            image_ids = wanted
        html_final = replace_image_placeholders(data["html_document"], project_dir, image_ids, args.allow_missing_images)
        no_image_scenes = check_scene_images(html_final)
        if no_image_scenes:
            print("警告：这些场景没有图片，画面只剩文字：" + "、".join(no_image_scenes[:10]))
        (project_dir / "index.html").write_text(html_final, encoding="utf-8")
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
        elif provider == "macos":
            generate_macos_voice(data["voiceover_script"], voice_path, voice_name, args.voice_rate)
        elif provider == "mimo":
            generate_mimo_voice(
                data["voiceover_script"], voice_path, model,
                voice_name, base_url,
            )
        else:
            generate_api_voice(
                data["voiceover_script"], voice_path, base_url,
                model, voice_name,
            )
        generate_background_music(project_dir)
        ascii_media = project_dir / "media"
        ascii_assets = project_dir / "assets"
        ascii_media.mkdir(parents=True, exist_ok=True)
        ascii_assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(voice_path, ascii_media / "voice.mp3")
        shutil.copy2(project_dir / "媒体" / "背景音乐.mp3", ascii_media / "bgm.mp3")
        for _asset in sorted((RUNTIME_DIR / "assets" / "vendor").glob("*.js")):
            shutil.copy2(_asset, ascii_assets / _asset.name)
        log_lines: list[str] = []
        proc = subprocess.Popen(
            ["bash", str(project_dir / "render.sh")],
            cwd=project_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            log_lines.append(line.rstrip())
        proc.wait()
        if proc.returncode != 0:
            stage = next(
                (item for item in reversed(log_lines) if item.startswith("❌ 失败关卡")),
                "未知关卡（没有捕获到阶段标记）",
            )
            reason = "\n".join([
                stage,
                "时间：" + time.strftime("%Y-%m-%d %H:%M:%S"),
                "项目：" + str(project_dir),
                "",
                "最后 40 行日志：",
                *log_lines[-40:],
            ])
            (project_dir / "失败原因.txt").write_text(reason + "\n", encoding="utf-8")
            print("")
            print("❌ 渲染失败，原因已写入 失败原因.txt：")
            print(reason)
            raise SystemExit(2)
    except (Exception, SystemExit):
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
