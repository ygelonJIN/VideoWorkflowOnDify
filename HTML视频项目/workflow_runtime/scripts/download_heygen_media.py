#!/usr/bin/env python3
"""Download only the HeyGen media belonging to the current response/video_id."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


def load_payload(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, str):
        payload = json.loads(payload)
    if not isinstance(payload, dict):
        raise SystemExit("heygen_response.json 必须是 JSON 对象或包含 JSON 对象的字符串")
    return payload


def pick(payload: dict, *paths: tuple[str, ...]) -> str:
    for path in paths:
        value = payload
        for key in path:
            if not isinstance(value, dict) or key not in value:
                value = None
                break
            value = value[key]
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def response_identity(payload: dict) -> tuple[str, str, str, str]:
    video_id = pick(
        payload,
        ("data", "id"), ("data", "video_id"), ("data", "videoId"),
        ("id",), ("video_id",), ("videoId",),
    )
    video_url = pick(
        payload,
        ("data", "video_url"), ("data", "videoUrl"),
        ("video_url",), ("videoUrl",),
    )
    audio_url = pick(
        payload,
        ("data", "audio_url"), ("data", "audioUrl"),
        ("audio_url",), ("audioUrl",),
    )
    transcript_url = pick(
        payload,
        ("data", "transcript_url"), ("data", "transcriptUrl"),
        ("data", "caption_url"), ("data", "captionUrl"),
        ("data", "subtitle_url"), ("data", "subtitleUrl"),
        ("data", "srt_url"), ("data", "srtUrl"),
        ("transcript_url",), ("transcriptUrl",), ("caption_url",), ("captionUrl",),
        ("subtitle_url",), ("subtitleUrl",), ("srt_url",), ("srtUrl",),
    )
    return video_id, video_url, audio_url, transcript_url


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    last_error = None
    for attempt in range(1, 4):
        temp = destination.with_suffix(destination.suffix + ".part")
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=90) as response, temp.open("wb") as output:
                shutil.copyfileobj(response, output)
            if temp.stat().st_size <= 0:
                raise RuntimeError("下载内容为空")
            temp.replace(destination)
            return
        except Exception as exc:
            last_error = exc
            temp.unlink(missing_ok=True)
            print(f"下载失败，重试 {attempt}/3：{exc}")
            time.sleep(2 * attempt)
            try:
                result = subprocess.run([
                    "curl", "-L", "--fail", "--retry", "3", "--retry-delay", "2",
                    "--connect-timeout", "20", "--max-time", "180",
                    "-A", "Mozilla/5.0", "-o", str(destination), url,
                ], check=False)
                if result.returncode == 0 and destination.exists() and destination.stat().st_size > 0:
                    return
            except Exception as curl_error:
                last_error = curl_error
    raise RuntimeError(f"下载失败：{url}") from last_error


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def matching_cache(media_dir: Path, video_id: str, transcript_url: str) -> bool:
    manifest = load_manifest(media_dir / "媒体身份.json")
    if not video_id or manifest.get("video_id") != video_id:
        return False
    named_files = {
        "HeyGen数字人.mp4": media_dir / "HeyGen数字人.mp4",
        "HeyGen口播.mp3": media_dir / "HeyGen口播.mp3",
        "背景音乐.mp3": media_dir / "背景音乐.mp3",
    }
    if transcript_url:
        named_files["字幕/HeyGen转写.json"] = Path("字幕/HeyGen转写.json")
    for name, path in named_files.items():
        recorded = manifest.get("files", {}).get(name, {})
        if not path.is_file() or path.stat().st_size <= 0:
            return False
        if recorded.get("sha256") != sha256(path) or int(recorded.get("size", -1)) != path.stat().st_size:
            return False
    return True

def write_manifest(path: Path, video_id: str, video_url: str, audio_url: str, transcript_url: str, media_dir: Path) -> None:
    files = {}
    named_files = {
        "HeyGen数字人.mp4": media_dir / "HeyGen数字人.mp4",
        "HeyGen口播.mp3": media_dir / "HeyGen口播.mp3",
        "背景音乐.mp3": media_dir / "背景音乐.mp3",
        "字幕/HeyGen转写.json": Path("字幕/HeyGen转写.json"),
    }
    for name, file_path in named_files.items():
        if file_path.is_file():
            files[name] = {"size": file_path.stat().st_size, "sha256": sha256(file_path)}
    path.write_text(json.dumps({
        "video_id": video_id,
        "video_url": video_url,
        "audio_url": audio_url,
        "transcript_url": transcript_url,
        "downloaded_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "files": files,
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("response_json", type=Path)
    parser.add_argument("--media-dir", type=Path, default=Path("媒体"))
    parser.add_argument("--if-needed", action="store_true", help="身份和文件哈希匹配时复用，否则强制重下")
    args = parser.parse_args()

    payload = load_payload(args.response_json)
    video_id, video_url, audio_url, transcript_url = response_identity(payload)
    if not video_id:
        raise SystemExit("当前 HeyGen 响应缺少 video_id/id，拒绝下载以避免串片")
    if not video_url:
        raise SystemExit("当前 HeyGen 响应缺少明确的 video_url，拒绝递归猜测旧链接")
    if video_id not in video_url:
        raise SystemExit(f"video_url 与当前 video_id 不一致：video_id={video_id}, video_url={video_url}")

    args.media_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.media_dir / "媒体身份.json"
    if args.if_needed and matching_cache(args.media_dir, video_id, transcript_url):
        print(f"复用已验证的 HeyGen 媒体：video_id={video_id}")
        return

    for name in ("HeyGen数字人.mp4", "HeyGen口播.mp3", "媒体身份.json"):
        (args.media_dir / name).unlink(missing_ok=True)
    Path("字幕/HeyGen转写.json").unlink(missing_ok=True)

    video_path = args.media_dir / "HeyGen数字人.mp4"
    audio_path = args.media_dir / "HeyGen口播.mp3"
    download(video_url, video_path)
    if audio_url:
        download(audio_url, audio_path)
    else:
        subprocess.run([
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-acodec", "libmp3lame", "-q:a", "2", str(audio_path),
        ], check=True)

    transcript_path = Path("字幕/HeyGen转写.json")
    if transcript_url:
        download(transcript_url, transcript_path)

    music_mp3 = args.media_dir / "背景音乐.mp3"
    if not music_mp3.exists():
        music_wav = args.media_dir / "背景音乐.wav"
        subprocess.run([
            sys.executable, str(Path(__file__).resolve().parent / "generate_background_music.py"),
            "--output", str(music_wav),
        ], check=True)
        subprocess.run([
            "ffmpeg", "-y", "-i", str(music_wav),
            "-acodec", "libmp3lame", "-b:a", "160k",
            "-af", "loudnorm=I=-24:TP=-2:LRA=11", str(music_mp3),
        ], check=True)

    write_manifest(manifest_path, video_id, video_url, audio_url, transcript_url, args.media_dir)
    print("video_id:", video_id)
    print("video_url:", video_url)
    print("audio_url:", audio_url or "未提供，已从 MP4 提取")
    print("transcript_url:", transcript_url or "未提供，将使用本地 ASR")
    print("saved:", video_path)
    print("saved:", audio_path)
    print("saved:", manifest_path)


if __name__ == "__main__":
    main()
