#!/usr/bin/env python3
"""Activate media placeholders and align captions to real speech timestamps."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path

PUNCTUATION = set("，。！？；：、,.!?;:…—-()（）[]【】\"'“”‘’")
CAPTION_START = "<!-- CAPTIONS_START -->"
CAPTION_END = "<!-- CAPTIONS_END -->"

TRADITIONAL_TO_SIMPLIFIED = str.maketrans({
    "個": "个", "們": "们", "來": "来", "這": "这", "麼": "么", "為": "为", "與": "与", "於": "于",
    "後": "后", "裡": "里", "點": "点", "時": "时", "間": "间", "過": "过", "還": "还", "沒": "没",
    "開": "开", "關": "关", "發": "发", "現": "现", "實": "实", "際": "际", "網": "网", "絡": "络",
    "數": "数", "據": "据", "資": "资", "料": "料", "業": "业", "務": "务", "產": "产", "品": "品",
    "銷": "销", "營": "营", "轉": "转", "換": "换", "體": "体", "驗": "验", "問": "问", "題": "题",
    "團": "团", "隊": "队", "員": "员", "戶": "户", "戶": "户", "從": "从", "眾": "众", "萬": "万",
    "買": "买", "賣": "卖", "錢": "钱", "價": "价", "費": "费", "節": "节", "約": "约", "達": "达",
    "觸": "触", "獲": "获", "線": "线", "索": "索", "準": "准", "備": "备", "記": "记", "錄": "录",
    "對": "对", "錯": "错", "當": "当", "應": "应", "該": "该", "將": "将", "會": "会", "進": "进",
    "動": "动", "態": "态", "運": "运", "營": "营", "銷": "销", "專": "专", "注": "注", "談": "谈",
    "單": "单", "絕": "绝", "決": "决", "擇": "选", "擇": "选", "標": "标", "題": "题", "內": "内",
    "容": "容", "視": "视", "頻": "频", "聲": "声", "音": "音", "圖": "图", "片": "片", "檔": "档",
    "案": "案", "載": "载", "傳": "传", "輸": "输", "輸": "输", "電": "电", "腦": "脑", "機": "机",
    "臺": "台", "灣": "湾", "廣": "广", "東": "东", "門": "门", "戶": "户", "員": "员", "聯": "联",
    "繫": "系", "訊": "讯", "號": "号", "話": "话", "語": "语", "詞": "词", "義": "义", "術": "术",
    "學": "学", "習": "习", "練": "练", "檢": "检", "測": "测", "試": "试", "驗": "验", "認": "认",
    "證": "证", "確": "确", "認": "认", "準": "准", "確": "确", "錯": "错", "誤": "误", "報": "报",
    "錶": "表", "顯": "显", "示": "示", "觀": "观", "眾": "众", "顧": "顾", "客": "客", "訪": "访",
    "問": "问", "訂": "订", "購": "购", "費": "费", "億": "亿", "萬": "万", "兩": "两", "並": "并",
    "齊": "齐", "協": "协", "議": "议", "優": "优", "勢": "势", "競": "竞", "爭": "争", "贏": "赢",
    "輸": "输", "敗": "败", "風": "风", "險": "险", "機": "机", "會": "会", "戰": "战", "略": "略",
    "執": "执", "行": "行", "導": "导", "航": "航", "頁": "页", "點": "点", "擊": "击", "開": "开",
    "始": "始", "創": "创", "建": "建", "設": "设", "置": "置", "權": "权", "限": "限", "賬": "账",
    "號": "号", "碼": "码", "鑰": "钥", "匙": "匙", "庫": "库", "儲": "储", "存": "存", "備": "备",
    "份": "份", "刪": "删", "除": "除", "輯": "辑", "組": "组", "織": "织", "結": "结", "構": "构",
    "簡": "简", "潔": "洁", "雜": "杂", "亂": "乱", "豐": "丰", "富": "富", "強": "强", "弱": "弱",
    "長": "长", "短": "短", "寬": "宽", "窄": "窄", "輕": "轻", "重": "重", "輕": "轻", "鬆": "松",
    "緊": "紧", "張": "张", "壓": "压", "縮": "缩", "擴": "扩", "展": "展", "縮": "缩", "減": "减",
    "增": "增", "總": "总", "結": "结", "匯": "汇", "報": "报", "統": "统", "計": "计", "額": "额",
    "昇": "升", "級": "级", "階": "阶", "層": "层", "級": "级", "檔": "档", "次": "次", "優": "优",
    "先": "先", "級": "级", "備": "备", "註": "注", "釋": "释", "內": "内", "標": "标", "籤": "签",
})

PRODUCTION_LAYOUT_CSS = """
<style id="production-layout-contract">
  @font-face{font-family:"PingFang SC";src:local("PingFang SC");}
  @font-face{font-family:"Microsoft YaHei";src:local("Microsoft YaHei");}
  @font-face{font-family:"Noto Sans CJK SC";src:local("Noto Sans CJK SC");}
  @font-face{font-family:"Source Han Sans SC";src:local("Source Han Sans SC");}
  @font-face{font-family:"Hiragino Sans GB";src:local("Hiragino Sans GB");}
  html,body{width:100%;height:100%;margin:0;padding:0;overflow:hidden;background:#000;}
  #stage{position:relative!important;width:1080px!important;height:1920px!important;overflow:hidden!important;}
  [data-composition-id]{position:absolute!important;inset:0!important;width:1080px!important;height:1920px!important;overflow:hidden!important;}
  #captions,.caption-layer{position:absolute!important;left:50%!important;right:auto!important;bottom:24%!important;top:auto!important;
    width:62%!important;max-width:62%!important;transform:translateX(-50%)!important;z-index:70!important;pointer-events:none!important;}
  .clip.caption,.caption{box-sizing:border-box!important;display:none!important;width:100%!important;max-width:100%!important;
    background:rgba(6,10,20,.72)!important;border:1px solid rgba(120,150,200,.25)!important;border-radius:14px!important;
    padding:14px 26px!important;font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC","Hiragino Sans GB",sans-serif!important;
    font-size:37px!important;line-height:1.35!important;font-weight:700!important;color:#fff!important;text-align:center!important;white-space:normal!important;}
  .clip.caption.show,.caption.show{display:block!important;}
  .caption .cap-inner{display:inline!important;padding:0!important;background:transparent!important;border:0!important;backdrop-filter:none!important;}
  video[data-video-role="avatar"]{object-fit:cover!important;}
</style>
"""

DETERMINISTIC_CONTROLLER_JS = r"""
  /* ---------- deterministic HyperFrames controller (generated by sync_video.py) ---------- */
  function sceneIndexAt(t){
    let idx=0;
    for(let i=0;i<scenes.length;i++){
      const st=Number(scenes[i].getAttribute('data-start')||0);
      if(t>=st) idx=i;
    }
    return idx;
  }
  function syncVisuals(t){
    const idx=sceneIndexAt(t);
    if(idx!==currentScene){
      currentScene=idx;
      scenes.forEach((s,i)=>s.classList.toggle('active',i===idx));
      dotEls.forEach((d,i)=>d.classList.toggle('on',i<=idx));
    }
    updateCaptions(t);
  }
  tl.eventCallback('onUpdate',()=>syncVisuals(tl.time()));
  syncVisuals(0);
  window.__seekTo=function(sec){tl.seek(Number(sec)||0);syncVisuals(tl.time());};
"""


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


def refresh_media_identity_manifest() -> None:
    manifest_path = Path("媒体/媒体身份.json")
    if not manifest_path.exists():
        return
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    named_files = {
        "HeyGen数字人.mp4": Path("媒体/HeyGen数字人.mp4"),
        "HeyGen口播.mp3": Path("媒体/HeyGen口播.mp3"),
        "背景音乐.mp3": Path("媒体/背景音乐.mp3"),
        "字幕/HeyGen转写.json": Path("字幕/HeyGen转写.json"),
    }
    for name, path in named_files.items():
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[name] = {"size": path.stat().st_size, "sha256": digest}
    manifest["files"] = files
    manifest["normalized_at"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%S%z")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def media_duration(path: Path) -> float:
    result = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(result.stdout.strip())


def normalize_media_duration(path: Path, target: float) -> float:
    actual = media_duration(path)
    if actual < 1.0:
        raise SystemExit(f"媒体时长无效：{path.name} 为 {actual:.3f}s")
    with tempfile.TemporaryDirectory(prefix="video-sync-") as temp_dir:
        output = Path(temp_dir) / path.name
        if path.suffix.lower() in {".mp3", ".wav", ".m4a", ".aac"}:
            command = ["ffmpeg", "-y", "-i", str(path), "-af", "apad", "-t", f"{target:.3f}",
                       "-ar", "48000", "-ac", "2"]
            command += ["-c:a", "libmp3lame", "-b:a", "192k"] if path.suffix.lower() == ".mp3" else ["-c:a", "aac", "-b:a", "192k"]
            command.append(str(output))
        else:
            pad = max(0.0, target - actual)
            video_filter = f"tpad=stop_mode=clone:stop_duration={pad:.3f}" if pad > 0.001 else "null"
            command = ["ffmpeg", "-y", "-i", str(path), "-vf", video_filter, "-t", f"{target:.3f}", "-an",
                       "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                       "-movflags", "+faststart", str(output)]
        run(command)
        shutil.move(str(output), str(path))
    return media_duration(path)


def to_simplified(value: object) -> str:
    return str(value or "").translate(TRADITIONAL_TO_SIMPLIFIED)


def clean_text(value: object) -> str:
    return to_simplified(re.sub(r"\s+", " ", str(value or "")).strip().replace("<|", "").replace("|>", "").strip())


def visible_length(text: str) -> int:
    return sum(1 for char in text if not char.isspace())


def collect_entries(payload: object) -> list[dict]:
    if isinstance(payload, list):
        raw = payload
    elif isinstance(payload, dict):
        raw = next((payload[key] for key in ("segments", "cues", "entries", "transcript", "words")
                    if isinstance(payload.get(key), list)), None)
        if raw is None:
            return collect_entries(next((payload[key] for key in ("data", "result", "transcript") if payload.get(key) is not None), []))
    else:
        raw = []
    entries = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = clean_text(item.get("text", item.get("word", item.get("value"))))
        start = item.get("start", item.get("start_time", item.get("from")))
        end = item.get("end", item.get("end_time", item.get("to")))
        if not text or start is None or end is None:
            continue
        try:
            entries.append({"text": text, "start": float(start), "end": float(end)})
        except (TypeError, ValueError):
            continue
    return sorted(entries, key=lambda item: (item["start"], item["end"]))


def parse_srt(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8-sig")
    pattern = re.compile(
        r"(?m)^(?:\d+\s*\n)?(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*\n(.*?)(?=\n{2,}|\Z)", re.S)
    entries = []
    for match in pattern.finditer(content):
        h1, m1, s1, ms1, h2, m2, s2, ms2, text = match.groups()
        start = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
        end = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000
        entries.append({"text": clean_text(re.sub(r"<[^>]+>", "", text)), "start": start, "end": end})
    return entries


def load_transcript(path: Path) -> list[dict]:
    content = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in {".srt", ".vtt"}:
        return parse_srt(path)
    stripped = content.lstrip()
    return collect_entries(json.loads(content)) if stripped.startswith(("{", "[")) else parse_srt(path)


def transcript_char_timeline(entries: list[dict]) -> tuple[str, list[float]]:
    chars: list[str] = []
    times: list[float] = []
    for item in entries:
        text = "".join(char for char in clean_text(item["text"]) if not char.isspace())
        if not text:
            continue
        start = max(0.0, float(item["start"]))
        end = max(start + 0.01, float(item["end"]))
        step = (end - start) / len(text)
        for index, char in enumerate(text):
            chars.append(char)
            times.append(start + step * (index + 0.5))
    return "".join(chars), times


def align_reference_char_times(reference: str, entries: list[dict]) -> tuple[str, list[float], float]:
    ref_text = "".join(char for char in clean_text(reference) if not char.isspace())
    asr_text, asr_times = transcript_char_timeline(entries)
    total_end = max((float(item["end"]) for item in entries), default=0.0)
    if not ref_text:
        return "", [], total_end
    if not asr_text:
        span = max(total_end, max(1.0, len(ref_text) * 0.16))
        return ref_text, [span * (index + 0.5) / len(ref_text) for index in range(len(ref_text))], span

    ref_times: list[float | None] = [None] * len(ref_text)
    matcher = SequenceMatcher(None, asr_text, ref_text, autojunk=False)
    matched_chars = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(j2 - j1):
                ref_times[j1 + offset] = asr_times[i1 + offset]
            matched_chars += j2 - j1
        elif j2 > j1:
            before = asr_times[i1 - 1] if i1 > 0 else 0.0
            after = asr_times[i2] if i2 < len(asr_times) else total_end
            if after <= before:
                after = before + 0.04 * max(1, j2 - j1)
            for offset, j in enumerate(range(j1, j2)):
                ratio = (offset + 1) / (j2 - j1 + 1)
                ref_times[j] = before + (after - before) * ratio

    known = [(index, value) for index, value in enumerate(ref_times) if value is not None]
    if not known:
        span = max(total_end, len(ref_text) * 0.16)
        return ref_text, [span * (index + 0.5) / len(ref_text) for index in range(len(ref_text))], span
    for index in range(len(ref_times)):
        if ref_times[index] is not None:
            continue
        previous = next(((pos, value) for pos, value in reversed(known) if pos < index), None)
        following = next(((pos, value) for pos, value in known if pos > index), None)
        if previous and following:
            ratio = (index - previous[0]) / (following[0] - previous[0])
            ref_times[index] = previous[1] + (following[1] - previous[1]) * ratio
        elif previous:
            ref_times[index] = previous[1] + 0.04 * (index - previous[0])
        else:
            ref_times[index] = max(0.0, following[1] - 0.04 * (following[0] - index))

    values = [float(value) for value in ref_times]
    for index in range(1, len(values)):
        values[index] = max(values[index], values[index - 1] + 0.002)
    ratio = matched_chars / max(1, len(ref_text))
    return ref_text, values, ratio


def split_complete_sentences(text: str) -> list[str]:
    text = clean_text(text)
    if not text:
        return []
    return [match.group(0).strip() for match in re.finditer(r'.*?(?:[。！？!?]+(?:["”’\'）\]】》]+)?|$)', text, flags=re.S) if match.group(0).strip()]


def cues_from_reference(reference: str, entries: list[dict]) -> tuple[list[dict], float]:
    ref_text, char_times, match_ratio = align_reference_char_times(reference, entries)
    if not ref_text:
        return [], match_ratio
    total_end = max((float(item["end"]) for item in entries), default=char_times[-1] + 0.35)
    spans = [(match.start(), match.end()) for match in re.finditer(
        r'.*?(?:[。！？!?]+(?:["”’\'）\]】》]+)?|$)', ref_text, flags=re.S
    ) if match.group(0).strip()]
    cues: list[dict] = []
    for span_index, (start_index, end_index) in enumerate(spans):
        text = clean_text(ref_text[start_index:end_index])
        if not text:
            continue
        if span_index == 0:
            start = max(0.0, char_times[start_index] - 0.08)
        else:
            start = (char_times[start_index - 1] + char_times[start_index]) / 2
        if end_index >= len(ref_text):
            end = min(total_end, char_times[end_index - 1] + 0.35)
        else:
            end = (char_times[end_index - 1] + char_times[end_index]) / 2
        if end <= start:
            end = start + 0.2
        cues.append({"text": text, "start": round(start, 3), "end": round(end, 3)})
    return cues, match_ratio


def group_entries_into_sentences(entries: list[dict]) -> list[dict]:
    transcript_text = "".join(clean_text(item["text"]) for item in entries)
    return cues_from_reference(transcript_text, entries)[0]


def format_srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def scale_cues(cues: list[dict], factor: float) -> list[dict]:
    return [{"text": c["text"], "start": round(c["start"] * factor, 3), "end": round(c["end"] * factor, 3)} for c in cues]


def fit_cues_to_duration(cues: list[dict], duration: float) -> list[dict]:
    """Keep transcript order and land the final cue exactly on the voice clock."""
    if not cues or duration <= 0:
        return cues
    last_end = max(float(cue["end"]) for cue in cues)
    if last_end <= 0:
        return cues
    factor = duration / last_end
    fitted = scale_cues(cues, factor)
    for index, cue in enumerate(fitted):
        if index:
            cue["start"] = round(max(cue["start"], fitted[index - 1]["end"]), 3)
        cue["end"] = round(max(cue["start"] + 0.2, cue["end"]), 3)
    fitted[-1]["end"] = round(duration, 3)
    return fitted


def remove_css_rules(document: str, selectors: list[str]) -> str:
    for selector in selectors:
        pattern = re.compile(
            rf'(?m)^\s*{re.escape(selector)}(?:\s*::(?:before|after))?\s*\{{[^{{}}]*\}}\s*',
            re.I,
        )
        document = pattern.sub("", document)
    return document


def sanitize_no_avatar_composition(document: str) -> str:
    """Remove legacy avatar windows and black reserve boxes from no-avatar output."""
    legacy_shift = re.search(r'\.kicker\s*\{[^}]*\bleft:\s*(\d+)px', document, re.I)
    if legacy_shift and int(legacy_shift.group(1)) >= 300:
        block = legacy_shift.group(0)
        document = document.replace(block, re.sub(r'\bleft:\s*\d+px', 'left:84px', block, count=1), 1)
    document = remove_css_rules(document, [".black-frame", ".avatar-window", ".avatar-zone"])
    document = re.sub(r'/\*[^*]*纯黑帧保留区[^*]*\*/', '', document)
    document = re.sub(
        r'<template\b[^>]*data-media-type="video"[^>]*data-video-role="avatar"[^>]*>\s*</template>',
        "",
        document,
        flags=re.I,
    )
    document = re.sub(
        r'<div\b[^>]*class="[^"]*(?:avatar-window|black-frame)[^"]*"[^>]*>.*?</div>',
        "",
        document,
        flags=re.I | re.S,
    )
    document = re.sub(
        r'<(?:video|div|section)\b[^>]*(?:data-video-role="avatar"|data-media-id="heygen_avatar")[^>]*>.*?</(?:video|div|section)>',
        "",
        document,
        flags=re.I | re.S,
    )
    return document


def write_outputs(cues: list[dict], json_path: Path, srt_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    blocks = [f"{i}\n{format_srt_time(c['start'])} --> {format_srt_time(c['end'])}\n{c['text']}\n"
              for i, c in enumerate(cues, 1)]
    srt_path.write_text("\n".join(blocks), encoding="utf-8")


def activate_media_placeholders(document: str, black_frame: bool = False) -> str:
    pattern = re.compile(r'<template\b(?P<attrs>[^>]*\bdata-media-type="(?:video|audio)"[^>]*)>\s*</template>', re.I)

    def replace(match: re.Match[str]) -> str:
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', match.group("attrs")))
        kind = attrs.get("data-media-type", "").lower()
        element_id = attrs.get("data-media-id", "")
        role = attrs.get("data-video-role") or attrs.get("data-audio-role") or ""
        source = {
            ("video", "avatar"): "media/avatar.mp4",
            ("audio", "voiceover"): "media/voice.mp3",
            ("audio", "background-music"): "media/bgm.mp3",
        }.get((kind, role), attrs.get("data-media-src", ""))
        if kind not in {"video", "audio"} or not element_id or not source:
            raise SystemExit("媒体占位缺少 data-media-type/data-media-id/data-media-src")
        keep = [f'{name}="{attrs[name]}"' for name in
                ("data-start", "data-duration", "data-track-index", "data-volume", "data-video-role", "data-audio-role")
                if name in attrs]
        if "data-start" not in attrs:
            keep.insert(0, 'data-start="0"')
        common = f'id="{element_id}" src="{source}" ' + " ".join(keep)
        if kind == "audio":
            return f"<audio {common}></audio>"
        tag = f"<video {common} muted playsinline></video>"
        return f'<div class="pip avatar-window" aria-hidden="true">{tag}</div>' if role == "avatar" else tag

    document = pattern.sub(replace, document)
    voice_source = "media/voice.mp3"
    document = re.sub(
        r'(<audio\b[^>]*\bid="voiceover-track"[^>]*\bsrc=")[^"]*(")',
        lambda match: match.group(1) + voice_source + match.group(2),
        document,
        flags=re.I,
    )
    document = re.sub(
        r'(<audio\b[^>]*\bid="bgm-track"[^>]*\bsrc=")[^"]*(")',
        lambda match: match.group(1) + "media/bgm.mp3" + match.group(2),
        document,
        flags=re.I,
    )
    document = re.sub(r'</(audio|video)\b[^>]*>', r'</\1>', document, flags=re.I)
    document = re.sub(r'src="素材/vendor/gsap\.min\.js"', 'src="assets/gsap.min.js"', document, flags=re.I)
    return re.sub(r'(<script\b[^>]*?)\bdata-src="([^"]+)"',
                  lambda match: f'{match.group(1).rstrip()} src="assets/gsap.min.js"', document, flags=re.I)


def normalize_audio_roles(document: str) -> str:
    for role, element_id, source in (
        ("voiceover", "voiceover-track", "media/voice.mp3"),
        ("background-music", "bgm-track", "media/bgm.mp3"),
    ):
        role_pattern = re.compile(rf'<audio\b(?![^>]*\bsrc=)[^>]*\bdata-audio-role="{re.escape(role)}"[^>]*>\s*</audio>', re.I)
        role_match = role_pattern.search(document)
        if not role_match:
            continue
        source_pattern = re.compile(rf'<audio\b[^>]*(?<![\w-])id="{re.escape(element_id)}"[^>]*>', re.I)
        source_match = source_pattern.search(document)
        if source_match:
            source_tag = set_attribute(source_match.group(0), "data-audio-role", role)
            document = document[:source_match.start()] + source_tag + document[source_match.end():]
            role_match = role_pattern.search(document)
            if role_match:
                document = document[:role_match.start()] + document[role_match.end():]
        else:
            combined = role_match.group(0)
            opening_match = re.match(r'<audio\b[^>]*>', combined, flags=re.I)
            if not opening_match:
                continue
            role_tag = set_attribute(opening_match.group(0), "id", element_id)
            role_tag = set_attribute(role_tag, "src", source)
            repaired = role_tag + combined[opening_match.end():]
            document = document[:role_match.start()] + repaired + document[role_match.end():]
    return document


def normalize_timeline_registration(document: str) -> str:
    """Register the paused timeline under the literal composition ID."""
    root_match = re.search(r'\bdata-composition-id="([^"]+)"', document)
    composition_id = root_match.group(1) if root_match else "composition"
    registration = (
        'window.__timelines = window.__timelines || {}; '
        f'window.__timelines["{composition_id}"] = timeline;'
    )
    document = re.sub(
        r'window\.__timelines\s*=\s*window\.__timelines\s*\|\|\s*(?:\{\s*\}|\[\s*\])\s*;\s*'
        r'(?:window\.__timelines(?:\.push\([^;]+\)|\[[^;]+?=\s*[^;]+;)\s*;?)?',
        registration,
        document,
        count=1,
        flags=re.I,
    )
    if 'window.__timelines[' not in document:
        raise SystemExit("无法恢复 window.__timelines 字面量注册")
    return document


def scene_timeline_span(document: str) -> float:
    pattern = re.compile(r'<(?:section|div)\b(?=[^>]*\bclass="[^"]*\bscene\b)[^>]*>', re.I)
    end = 0.0
    for tag in pattern.findall(document):
        start_match = re.search(r'\bdata-start="([0-9.]+)"', tag)
        duration_match = re.search(r'\bdata-duration="([0-9.]+)"', tag)
        if start_match and duration_match:
            end = max(end, float(start_match.group(1)) + float(duration_match.group(1)))
    return end


def scale_scene_timings(document: str, factor: float) -> str:
    pattern = re.compile(r'<(?:section|div)\b(?=[^>]*\bclass="[^"]*\bscene\b)[^>]*>', re.I)

    def scale_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        for name in ("data-start", "data-duration"):
            found = re.search(rf'\s{name}="([0-9.]+)"', tag)
            if found:
                tag = set_attribute(tag, name, f"{float(found.group(1)) * factor:.3f}")
        return tag

    return pattern.sub(scale_tag, document)


def align_scenes_to_caption_cues(document: str, cues: list[dict], duration: float) -> str:
    """Anchor each scene transition to the first real speech cue it represents."""
    if not cues:
        return document
    scene_pattern = re.compile(r'<(?:section|div)\b(?=[^>]*\bclass="[^"]*\bscene\b)[^>]*>', re.I)
    matches = list(scene_pattern.finditer(document))
    if not matches:
        return document
    cue_ids = [f"s{index:02d}" for index in range(1, len(cues) + 1)]
    cue_index = {cue_id: index for index, cue_id in enumerate(cue_ids)}
    scene_cue_indices: list[int] = []
    for scene_index, match in enumerate(matches, 1):
        tag = match.group(0)
        refs = re.search(r'\bdata-sentence-ids="([^"]+)"', tag)
        candidates = re.findall(r's\d+', refs.group(1), flags=re.I) if refs else []
        if not candidates:
            scene_match = re.search(r'\bdata-scene="s(\d+)"', tag, flags=re.I)
            candidates = [f"s{int(scene_match.group(1)):02d}"] if scene_match else []
        indices = [cue_index[item.lower()] for item in candidates if item.lower() in cue_index]
        scene_cue_indices.append(min(indices) if indices else min(scene_index - 1, len(cues) - 1))

    replacements: list[tuple[re.Match[str], str]] = []
    for scene_index, match in enumerate(matches):
        cue_start_index = scene_cue_indices[scene_index]
        next_scene_index = scene_cue_indices[scene_index + 1] if scene_index + 1 < len(matches) else len(cues)
        start = 0.0 if scene_index == 0 else float(cues[cue_start_index]["start"])
        end = duration if scene_index + 1 == len(matches) else float(cues[next_scene_index]["start"])
        tag = match.group(0)
        scene_name_match = re.search(r'\bdata-scene="([^"]+)"', tag)
        scene_name = scene_name_match.group(1) if scene_name_match else f"{scene_index:02d}"
        tag = set_attribute(tag, "id", f"scene-{scene_name}")
        if not re.search(r'\bdata-sentence-ids="[^"]+"', tag):
            tag = set_attribute(tag, "data-sentence-ids", cue_ids[cue_start_index])
        tag = set_attribute(tag, "data-start", f"{start:.3f}")
        tag = set_attribute(tag, "data-duration", f"{max(0.2, end - start):.3f}")
        replacements.append((match, tag))
    for match, tag in reversed(replacements):
        document = document[:match.start()] + tag + document[match.end():]
    return document


def set_attribute(tag: str, name: str, value: str) -> str:
    pattern = rf'\s{name}="[^"]*"'
    replacement = f' {name}="{value}"'
    return re.sub(pattern, replacement, tag, count=1) if re.search(pattern, tag) else tag[:-1].rstrip() + replacement + ">"


def set_media_duration(document: str, element_id: str, duration: float) -> str:
    pattern = re.compile(rf'<(video|audio)\b[^>]*\bid="{re.escape(element_id)}"[^>]*>', re.I)
    match = pattern.search(document)
    if not match:
        raise SystemExit(f"HTML 缺少媒体元素 #{element_id}")
    tag = set_attribute(match.group(0), "data-start", "0")
    tag = set_attribute(tag, "data-duration", f"{duration:.3f}")
    return document[:match.start()] + tag + document[match.end():]


def set_role_duration(document: str, media_type: str, role: str, duration: float, allow_missing: bool = False) -> str:
    role_attr = "data-video-role" if media_type == "video" else "data-audio-role"
    pattern = re.compile(rf'<{media_type}\b[^>]*\b{role_attr}="{re.escape(role)}"[^>]*>', re.I)
    match = pattern.search(document)
    if not match:
        if allow_missing:
            return document
        return set_media_duration(document, {
            ("video", "avatar"): "heygen-video",
            ("audio", "voiceover"): "heygen-voice",
            ("audio", "background-music"): "background-music",
        }.get((media_type, role), role), duration)
    tag = set_attribute(match.group(0), "data-start", "0")
    tag = set_attribute(tag, "data-duration", f"{duration:.3f}")
    return document[:match.start()] + tag + document[match.end():]


def extract_html_captions(document: str) -> list[dict]:
    pattern = re.compile(r'<div\b[^>]*class="[^"]*caption[^"]*"[^>]*data-start="([0-9.]+)"[^>]*data-duration="([0-9.]+)"[^>]*>(.*?)</div>', re.I | re.S)
    cues = []
    for start, duration, body in pattern.findall(document):
        text = clean_text(re.sub(r"<[^>]+>", "", body))
        if text:
            cues.append({"text": text, "start": float(start), "end": float(start) + float(duration)})
    return cues


def caption_block(cues: list[dict]) -> str:
    rows = []
    for index, cue in enumerate(cues, 1):
        duration = max(0.2, cue["end"] - cue["start"])
        rows.append(f'    <div id="caption-{index}" class="clip caption" data-sentence-id="s{index:02d}" data-start="{cue["start"]:.3f}" '
                    f'data-duration="{duration:.3f}" data-track-index="4" data-layout-allow-occlusion>'
                    f'{html.escape(cue["text"], quote=False)}</div>')
    return CAPTION_START + "\n" + "\n".join(rows) + "\n    " + CAPTION_END


FIT_ROOT_RUNTIME_SCRIPT = """
<script id="fit-root-runtime">
(function(){
  function fitRootToViewport(){
    var stage=document.getElementById('stage');
    if(!stage)return;
    var W=1080,H=1920;
    var scale=Math.min(window.innerWidth/W,window.innerHeight/H);
    stage.style.transform='scale('+scale+')';
    document.body.style.width=(W*scale)+'px';
    document.body.style.height=(H*scale)+'px';
  }
  window.fitRootToViewport=fitRootToViewport;
  window.addEventListener('resize',fitRootToViewport);
  document.addEventListener('DOMContentLoaded',fitRootToViewport);
})();
</script>
"""


def unwrap_div_by_id(document: str, element_id: str) -> str:
    opening = re.search(rf'<div\b(?=[^>]*(?<![\w-])id=["\']{re.escape(element_id)}["\'])[^>]*>', document, re.I)
    if not opening:
        return document
    depth = 0
    for tag in re.finditer(r'<div\b[^>]*>|</div\s*>', document[opening.end():], flags=re.I):
        if tag.group(0).lower().startswith('</'):
            depth -= 1
            if depth == 0:
                close_start = opening.end() + tag.start()
                close_end = opening.end() + tag.end()
                return document[:opening.start()] + document[opening.end():close_start] + document[close_end:]
        else:
            depth += 1
    raise SystemExit(f"无法安全移除包装节点 #{element_id}")


def enforce_production_layout(document: str, avatar_required: bool = True) -> str:
    document = re.sub(
        r'<div\b([^>]*\bid=["\']viewport["\'][^>]*)>',
        lambda match: '<div' + set_attribute(match.group(1), "id", "stage-shell") + '>',
        document,
        count=1,
        flags=re.I,
    )
    document = unwrap_div_by_id(document, "stage-shell")
    document = re.sub(r'<html\b([^>]*)>', lambda match: '<html' + set_attribute(match.group(1), "lang", "zh-CN") + '>', document, count=1, flags=re.I)
    layout_css = PRODUCTION_LAYOUT_CSS
    if not avatar_required:
        layout_css = layout_css.replace('  video[data-video-role="avatar"]{object-fit:cover!important;}\n', '')
    if re.search(r'<style\b[^>]*id="production-layout-contract"[^>]*>.*?</style>', document, re.I | re.S):
        document = re.sub(
            r'<style\b[^>]*id="production-layout-contract"[^>]*>.*?</style>',
            lambda _: layout_css.strip(),
            document, count=1, flags=re.I | re.S,
        )
    else:
        if not re.search(r'</head\s*>', document, re.I):
            raise SystemExit("HTML 缺少 </head>，无法注入生产排版约束")
        document = re.sub(r'</head\s*>', PRODUCTION_LAYOUT_CSS + '\n</head>', document, count=1, flags=re.I)
    if 'function fitRootToViewport' not in document:
        document = re.sub(r'</head\s*>', FIT_ROOT_RUNTIME_SCRIPT + '\n</head>', document, count=1, flags=re.I)
    return document


def ensure_root_composition(document: str, target_duration: float) -> str:
    root_pattern = re.compile(r'<div\b[^>]*\bdata-composition-id="[^"]+"[^>]*>', re.I)
    if root_pattern.search(document):
        return document
    stage_pattern = re.compile(r'<div\b[^>]*\bid="stage"[^>]*>', re.I)
    match = stage_pattern.search(document)
    if not match:
        raise SystemExit("HTML 缺少 #stage 根画布")
    id_match = re.search(r"setAttribute\(\s*['\"]data-composition-id['\"]\s*,\s*['\"]([^'\"]+)['\"]", document)
    composition_id = id_match.group(1) if id_match else "recovered-dify-composition"
    tag = match.group(0)
    for name, value in (
        ("data-composition-id", composition_id),
        ("data-width", "1080"),
        ("data-height", "1920"),
        ("data-duration", f"{target_duration:.3f}"),
        ("data-caption-sync", "transcript-required"),
    ):
        tag = set_attribute(tag, name, value)
    return document[:match.start()] + tag + document[match.end():]


def normalize_wall_clock_controller(document: str) -> str:
    wall_clock = re.compile(
        r"\bperformance\s*\.\s*now\s*\(|\brequestAnimationFrame\s*\(|\bcancelAnimationFrame\s*\(",
        re.I,
    )
    if not wall_clock.search(document):
        return document

    document = document.replace("runSceneMotion(idx);", "void idx;")
    marker_matches = [
        match for match in re.finditer(r"/\*.*?\*/", document, flags=re.I | re.S)
        if re.search(r"\bplayback[\s_-]*driver\b", match.group(0), flags=re.I)
    ]
    if marker_matches:
        start = marker_matches[0].start()
        script_end = document.lower().rfind("</script>", start)
        if script_end > start and re.search(r"\bconst\s+tl\s*=|\btl\s*=", document[:start]):
            return document[:start] + DETERMINISTIC_CONTROLLER_JS + "\n" + document[script_end:]

    # Fallback for renamed/minified/missing playback-driver comments. Keep all
    # composition setup intact, neutralize wall-clock calls, and install the
    # deterministic controller last so it owns __seekTo.
    document = re.sub(r"\bperformance\s*\.\s*now\s*\(", "__hfTimelineNowMs(", document, flags=re.I)
    document = re.sub(r"\brequestAnimationFrame\s*\(", "__hfSchedulePlaybackFrame(", document, flags=re.I)
    document = re.sub(r"\bcancelAnimationFrame\s*\(", "__hfCancelPlaybackFrame(", document, flags=re.I)
    helpers = r"""
  function __hfTimelineNowMs(){return Number((tl && tl.time) ? tl.time()*1000 : 0);}
  function __hfSchedulePlaybackFrame(){return 0;}
  function __hfCancelPlaybackFrame(){}
"""
    document = re.sub(
        r"window\.__seekTo\s*=\s*function\s*\(\s*sec\s*\)\s*\{\s*driveTime\s*\(\s*sec\s*\)\s*;?\s*\}\s*;?",
        "",
        document,
        flags=re.I,
    )
    controller_marker = "deterministic HyperFrames controller"
    if controller_marker not in document:
        script_end = document.lower().rfind("</script>")
        if script_end < 0:
            raise SystemExit("检测到墙钟驱动，但 HTML 缺少 script 结尾，无法安装 playback driver")
        document = document[:script_end] + helpers + DETERMINISTIC_CONTROLLER_JS + "\n" + document[script_end:]
    else:
        controller_at = document.find(controller_marker)
        document = document[:controller_at] + helpers + "\n" + document[controller_at:]
    if wall_clock.search(document):
        raise SystemExit("墙钟驱动改写后仍有残留，无法安全生成 preview")
    return document


def normalize_scaled_scene_positions(document: str) -> str:
    """Use real-time anchors with scaled authoring-relative motion offsets."""
    document = re.sub(r"\bat\(\s*start\s*\)", "Number(start)", document)
    document = re.sub(r"\bat\(\s*start\s*\+\s*([^()]*)\)", r"Number(start)+at(\1)", document)
    document = re.sub(r"\bat\(\s*end\s*-\s*([0-9.]+)\s*\)", r"Number(end)-\1", document)
    document = re.sub(r"\bat\(\s*dur\s*\)", "Number(dur)", document)
    document = re.sub(r"tl\.seek\(at\(Number\(sec\)\|\|0\)\)", "tl.seek(Number(sec)||0)", document)
    return document


def set_timeline_scale(document: str, factor: float, duration: float) -> str:
    document = re.sub(
        r"\b(var|let|const)\s+timelineScale\s*=\s*[^;]+;",
        rf"\1 timelineScale = {factor:.9f};",
        document,
        count=1,
    )
    # The progress tween is a real-time composition-duration tween.
    document = re.sub(
        r'''(duration\s*:\s*)at\([^)]*\)(\s*,\s*\n\s*width\s*:\s*["']100%["'])''',
        rf"\g<1>{duration:.3f}\g<2>",
        document,
        count=1,
    )
    return document


STATE_CONTROLLER_MARKER = "deterministic media-clock state controller"
STATE_CONTROLLER_JS = r"""
  /* ---------- deterministic media-clock state controller ---------- */
  (function(){
    var root=document.querySelector('[data-composition-id]');
    if(!root||!window.__hfRenderState){
      window.__hfRenderState=function(t){
        var time=Math.max(0,Number(t)||0);
        var scenes=Array.prototype.slice.call(document.querySelectorAll('.scene.clip'));
        var captions=Array.prototype.slice.call(document.querySelectorAll('.caption'));
        scenes.forEach(function(scene){
          var start=Number(scene.getAttribute('data-start')||0);
          var end=start+Number(scene.getAttribute('data-duration')||0);
          var active=time>=start&&time<end;
          scene.classList.toggle('is-active',active);
          scene.classList.toggle('active',active);
          scene.style.visibility=active?'visible':'hidden';
        });
        captions.forEach(function(cap){
          var start=Number(cap.getAttribute('data-start')||0);
          var end=start+Number(cap.getAttribute('data-duration')||0);
          var active=time>=start&&time<end;
          cap.classList.toggle('show',active);
          cap.style.visibility=active?'visible':'hidden';
        });
      };
    }
    var entries=Object.values(window.__timelines||{});
    var tl=entries.find(function(item){return item&&typeof item.time==='function';});
    if(tl&&typeof tl.to==='function'){
      tl.to({__hfState:0},{__hfState:1,duration:Math.max(0.01,Number(root.getAttribute('data-duration'))||0.01),ease:'none',
        onUpdate:function(){window.__hfRenderState(tl.time());}},0);
      var prior=window.__seekTo;
      window.__seekTo=function(sec){if(prior)prior(sec);else if(tl.seek)tl.seek(Number(sec)||0);window.__hfRenderState(tl.time());};
      window.__hfRenderState(tl.time());
    }
  })();
"""


def install_state_controller(document: str) -> str:
    if STATE_CONTROLLER_MARKER in document:
        return document
    script_end = document.lower().rfind("</script>")
    if script_end < 0:
        raise SystemExit("HTML 缺少 script 结尾，无法安装媒体主时钟状态控制器")
    return document[:script_end] + STATE_CONTROLLER_JS + "\n" + document[script_end:]



def rewrite_html(path: Path, cues: list[dict], target_duration: float, transcript_path: Path, avatar_required: bool = True) -> None:
    document = activate_media_placeholders(path.read_text(encoding="utf-8"), black_frame=not avatar_required)
    document = normalize_audio_roles(document)
    if not avatar_required:
        document = sanitize_no_avatar_composition(document)
    document = normalize_wall_clock_controller(document)
    document = normalize_timeline_registration(document)
    if CAPTION_START in document and CAPTION_END in document:
        document = re.sub(re.escape(CAPTION_START) + r".*?" + re.escape(CAPTION_END), lambda _: caption_block(cues), document, count=1, flags=re.S)
    else:
        raise SystemExit("HTML 缺少 CAPTIONS_START/CAPTIONS_END 字幕标记")
    authoring_match = re.search(r'\bdata-authoring-duration="([0-9.]+)"', document)
    declared_authoring_duration = float(authoring_match.group(1)) if authoring_match else 30.0
    scene_span = scene_timeline_span(document)
    scaled_match = re.search(r'\bdata-timeline-scaled-duration="([0-9.]+)"', document)
    scene_span_marker = re.search(r'\bdata-timeline-scene-span="([0-9.]+)"', document)
    already_scaled_to = float(scene_span_marker.group(1)) if scene_span_marker else (
        float(scaled_match.group(1)) if scaled_match and abs(scene_span - target_duration) <= 0.05 else None
    )
    prior_scale_match = re.search(r'\bdata-timeline-scale="([0-9.]+)"', document)
    if already_scaled_to is not None and abs(scene_span - target_duration) <= 0.05:
        authoring_duration = declared_authoring_duration
        timeline_factor = float(prior_scale_match.group(1)) if prior_scale_match else 1.0
    else:
        authoring_duration = scene_span if scene_span > 0 else declared_authoring_duration
        timeline_factor = target_duration / authoring_duration if authoring_duration > 0 else 1.0
        document = scale_scene_timings(document, timeline_factor)
    document = normalize_scaled_scene_positions(document)
    document = align_scenes_to_caption_cues(document, cues, target_duration)
    document = set_timeline_scale(document, timeline_factor, target_duration)
    document = set_role_duration(document, "audio", "voiceover", target_duration)
    document = set_role_duration(document, "video", "avatar", target_duration, allow_missing=not avatar_required)
    document = set_role_duration(document, "audio", "background-music", target_duration)
    document = ensure_root_composition(document, target_duration)
    root_pattern = re.compile(r'(<div\b[^>]*\bdata-composition-id="[^"]+"[^>]*>)', re.I)
    root_match = root_pattern.search(document)
    if not root_match:
        raise SystemExit("HTML 缺少根 composition")
    root_tag = set_attribute(root_match.group(0), "data-duration", f"{target_duration:.3f}")
    if not authoring_match:
        root_tag = set_attribute(root_tag, "data-authoring-duration", "30")
    root_tag = set_attribute(root_tag, "data-caption-sync", "real-transcript")
    root_tag = set_attribute(root_tag, "data-timeline-scale", f"{timeline_factor:.9f}")
    root_tag = set_attribute(root_tag, "data-authoring-duration", f"{authoring_duration:.3f}")
    root_tag = set_attribute(root_tag, "data-timeline-scaled-duration", f"{target_duration:.3f}")
    root_tag = set_attribute(root_tag, "data-timeline-scene-span", f"{target_duration:.3f}")
    root_tag = set_attribute(root_tag, "data-caption-source", transcript_path.name)
    document = document[:root_match.start()] + root_tag + document[root_match.end():]
    document = enforce_production_layout(document, avatar_required=avatar_required)
    document = install_state_controller(document)
    path.write_text(document, encoding="utf-8")


def resolve_hyperframes() -> tuple[Path, Path]:
    node_value = os.environ.get("NODE_BIN")
    node = Path(node_value) if node_value else Path("/tmp/node22-runtime/bin/node")
    if not node.is_file():
        candidates = sorted(Path.home().joinpath(".nvm/versions/node").glob("v22*/bin/node"))
        resolved = candidates[-1] if candidates else shutil.which("node")
        node = Path(resolved) if resolved else None
    if node is None or not node.is_file():
        raise SystemExit("缺少 Node.js 22+")
    cli_value = os.environ.get("HYPERFRAMES_CLI")
    cli = Path(cli_value) if cli_value else None
    if cli is None or not cli.is_file():
        candidates = sorted(Path.home().joinpath(".npm/_npx").glob("*/node_modules/hyperframes/bin/hyperframes.mjs"))
        resolved = candidates[-1] if candidates else shutil.which("hyperframes")
        cli = Path(resolved) if resolved else None
    if cli is None or not cli.is_file():
        raise SystemExit("缺少 HyperFrames CLI")
    return node, cli


def transcribe(audio: Path, output: Path, cli: Path, node: Path) -> list[dict]:
    output.parent.mkdir(parents=True, exist_ok=True)
    run([str(node), str(cli), "transcribe", str(audio), "--model", "small", "--language", "zh", "--json",
         "--to", "srt", "--output", str(output)])
    return parse_srt(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", type=Path, default=Path("index.html"))
    parser.add_argument("--voice", type=Path, default=Path("媒体/HeyGen口播.mp3"))
    parser.add_argument("--avatar-video", type=Path)
    parser.add_argument("--black-frame", dest="black_frame", action="store_true", help="无数字人模式：禁止数字人、头像窗口和黑帧占位")
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--auto-transcribe", action="store_true")
    parser.add_argument("--target-duration", type=float, help="兼容参数；最终时钟始终以口播实际时长为准")
    parser.add_argument("--duration-tolerance", type=float, default=0.25)
    parser.add_argument("--reference-script", type=Path, help="已批准口播原文；字幕文字以此为唯一真值")
    parser.add_argument("--skip-media-normalization", action="store_true")
    args = parser.parse_args()
    for path in (args.html, args.voice):
        if not path.exists():
            raise SystemExit(f"缺少文件：{path}")
    if args.avatar_video is not None and not args.avatar_video.exists():
        raise SystemExit(f"缺少文件：{args.avatar_video}")
    if not args.black_frame and args.avatar_video is None:
        raise SystemExit("完整版必须提供 --avatar-video；黑帧模式请使用 --black-frame")
    transcript = args.transcript
    if transcript is None:
        candidates = sorted(Path("字幕").glob("HeyGen转写.*")) + sorted(Path("字幕").glob("口播时间码.json"))
        transcript = candidates[0] if candidates else None
    fallback = False
    if transcript is None and args.auto_transcribe:
        node, cli = resolve_hyperframes()
        transcript = Path("字幕/口播.srt")
        try:
            transcribe(args.voice, transcript, cli, node)
        except Exception as exc:
            print("本地 ASR 不可用，改用 HTML 自带字幕时间码：" + str(exc).splitlines()[0])
            transcript = None
    if transcript is None or not transcript.exists():
        cues = extract_html_captions(args.html.read_text(encoding="utf-8"))
        fallback = True
        if not cues:
            raise SystemExit("缺少 HeyGen transcript，且 HTML 中没有可用字幕时间码。")
    else:
        entries = load_transcript(transcript)
        reference = args.reference_script.read_text(encoding="utf-8") if args.reference_script and args.reference_script.exists() else ""
        cue_level_transcript = bool(entries) and sum(1 for item in entries if visible_length(str(item.get("text", ""))) >= 6) >= max(1, len(entries) // 2)
        if reference.strip():
            Path("字幕/口播文案.txt").write_text(reference.strip() + "\n", encoding="utf-8")
            if cue_level_transcript:
                cues = [{"text": clean_text(str(item.get("text", ""))), "start": float(item.get("start", 0.0)), "end": float(item.get("end", 0.0))} for item in entries if clean_text(str(item.get("text", "")))]
                print("caption_reference_alignment=cue-level")
            else:
                cues, match_ratio = cues_from_reference(reference, entries)
                print(f"caption_reference_alignment={match_ratio:.3f}")
        else:
            cues = group_entries_into_sentences(entries)
    if not cues:
        raise SystemExit("未能从时间码生成字幕")
    voice_actual = media_duration(args.voice)
    avatar_actual = media_duration(args.avatar_video) if args.avatar_video and args.avatar_video.exists() else 0.0
    effective_duration = voice_actual
    cues = fit_cues_to_duration(cues, effective_duration)
    if not args.skip_media_normalization:
        if args.avatar_video and args.avatar_video.exists():
            normalize_media_duration(args.avatar_video, effective_duration)
        for background_music in (Path("媒体/背景音乐.mp3"), Path("media/bgm.mp3")):
            if background_music.exists():
                normalize_media_duration(background_music, effective_duration)
        refresh_media_identity_manifest()
    if abs(media_duration(args.voice) - effective_duration) > 0.03:
        raise SystemExit("口播实际时长在同步后发生变化，拒绝继续渲染")
    write_outputs(cues, Path("字幕/口播时间码.json"), Path("字幕/口播字幕.srt"))
    rewrite_html(
        args.html,
        cues,
        effective_duration,
        Path("字幕/HTML字幕时间码.json" if fallback else "字幕/口播时间码.json"),
        avatar_required=not args.black_frame,
    )
    config_path = Path("hyperframes.json")
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["duration"] = round(effective_duration, 3)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"voice_duration={media_duration(args.voice):.3f}")
    print(f"avatar_duration={avatar_actual:.3f}")
    print(f"caption_cues={len(cues)}")
    print(f"updated={args.html}")


if __name__ == "__main__":
    main()
