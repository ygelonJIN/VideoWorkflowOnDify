#!/usr/bin/env python3
"""Activate media placeholders and align captions to real speech timestamps."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
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
  html,body{width:100%;height:100%;margin:0;padding:0;overflow:hidden;background:#000;}
  #stage{position:relative!important;width:1080px!important;height:1920px!important;min-height:1920px!important;overflow:hidden!important;}
  [data-composition-id]{position:absolute!important;inset:0!important;width:1080px!important;height:1920px!important;min-height:1920px!important;overflow:hidden!important;}
  [data-coverage="full"]{box-sizing:border-box!important;width:1080px!important;height:1920px!important;min-height:1920px!important;
    display:flex!important;flex-direction:column!important;align-items:stretch!important;justify-content:center!important;overflow:hidden!important;}
  [data-coverage="full"] > .topbar{position:absolute!important;top:0!important;left:0!important;right:0!important;flex:0 0 auto!important;}
  [data-coverage="full"] > .head,[data-coverage="full"] > .body{flex:0 1 auto!important;}
  [data-coverage="full"] .scene-inner,[data-coverage="full"] > .scene-main,[data-coverage="full"] > main,
  [data-coverage="full"] > .main-content,[data-coverage="full"] > .content,[data-coverage="full"] > .hero,
  [data-coverage="full"] > .stage-content,[data-coverage="full"] > .hero-main,[data-coverage="full"] > .cta-main,
  [data-coverage="full"] > .frag-wrap,[data-coverage="full"] > .flow-wrap,[data-coverage="full"] > .pain-top,
  [data-coverage="full"] > .sol-top{flex:0 1 auto!important;justify-content:center!important;}
  .avatar-zone::after{content:""!important;}
  .avatar-window,.avatar-window.pip{position:absolute!important;top:96px!important;right:48px!important;left:auto!important;bottom:auto!important;
    width:214px!important;height:380px!important;min-width:214px!important;min-height:380px!important;max-width:214px!important;max-height:380px!important;
    z-index:80!important;border-radius:22px!important;overflow:hidden!important;border:2px solid rgba(255,255,255,.18)!important;
    background:#050914!important;box-shadow:0 18px 48px rgba(0,0,0,.42)!important;}
  .avatar-zone .avatar-window{position:absolute!important;top:0!important;right:0!important;bottom:0!important;left:0!important;
    width:100%!important;height:100%!important;min-width:0!important;min-height:0!important;max-width:none!important;max-height:none!important;
    border:0!important;border-radius:0!important;box-shadow:none!important;background:transparent!important;}
  .avatar-window video,.avatar-window video[data-video-role="avatar"]{position:absolute!important;top:0!important;right:0!important;bottom:0!important;left:0!important;
    width:100%!important;height:100%!important;min-width:0!important;min-height:0!important;max-width:none!important;max-height:none!important;
    object-fit:cover!important;object-position:center center!important;z-index:1!important;border-radius:0!important;border:0!important;background:transparent!important;box-shadow:none!important;}
  .avatar-tag{display:none!important;}
  video[data-video-role="avatar"],#heygen_avatar,#heygen-avatar,.avatar-video{z-index:80!important;}
  .caption-layer{position:absolute!important;left:0!important;right:0!important;bottom:24%!important;top:auto!important;width:auto!important;
    z-index:70!important;display:flex!important;justify-content:center!important;align-items:flex-end!important;pointer-events:none!important;}
  .clip.caption,.caption{box-sizing:border-box!important;display:none!important;max-width:66%!important;width:max-content!important;
    background:rgba(6,10,20,.78)!important;border:1px solid rgba(255,255,255,.12)!important;border-radius:14px!important;
    padding:14px 22px!important;font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif!important;
    font-size:37px!important;line-height:1.35!important;color:#eaf1ff!important;text-align:center!important;white-space:normal!important;}
  .clip.caption.show,.caption.show{display:block!important;}
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
  scenes.forEach((scene)=>{
    const start=Number(scene.getAttribute('data-start')||0);
    const items=[...scene.querySelectorAll('.kicker,.headline,.subhead,.panel,.pipe,.tiles,.dash,.benefits,.deal,.chips,.cta-btn,.card,.flow,.metrics,.cmp-list,.cmp-item,.tools-grid,.tool,.metric,.step,.cta-bar')];
    if(items.length) tl.fromTo(items,{y:26,opacity:0},{y:0,opacity:1,duration:at(.5),stagger:at(.06),ease:'power3.out'},Number(start));
  });
  tl.eventCallback('onUpdate',()=>syncVisuals(tl.time()));
  syncVisuals(0);
  window.__seekTo=function(sec){tl.seek(Number(sec)||0);syncVisuals(tl.time());};
"""


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=True, text=True, capture_output=True)


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


def split_long_cue(text: str, start: float, end: float, max_chars: int) -> list[dict]:
    text = clean_text(text)
    if not text:
        return []
    if visible_length(text) <= max_chars:
        return [{"text": text, "start": start, "end": end}]
    chunks, current = [], ""
    for char in text:
        current += char
        if (char in PUNCTUATION and visible_length(current) >= max(6, max_chars // 2)) or visible_length(current) >= max_chars:
            chunks.append(current.strip())
            current = ""
    if current.strip():
        chunks.append(current.strip())
    weights = [max(1, visible_length(chunk)) for chunk in chunks]
    total, cursor, duration = sum(weights), start, max(0.2, end - start)
    cues = []
    for index, (chunk, weight) in enumerate(zip(chunks, weights)):
        chunk_end = end if index == len(chunks) - 1 else cursor + duration * weight / total
        cues.append({"text": chunk, "start": round(cursor, 3), "end": round(chunk_end, 3)})
        cursor = chunk_end
    return cues


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


def group_entries(entries: list[dict], max_chars: int) -> list[dict]:
    word_level = len(entries) >= 8 and all(visible_length(item["text"]) <= 6 for item in entries)
    if not word_level:
        return [cue for item in entries for cue in split_long_cue(item["text"], item["start"], item["end"], max_chars)]
    cues, text, start, end = [], "", 0.0, 0.0
    for item in entries:
        candidate = (text + item["text"]).strip()
        if text and (visible_length(candidate) > max_chars or item["start"] - end > 0.35 or text[-1:] in PUNCTUATION):
            cues.extend(split_long_cue(text, start, end, max_chars))
            text = ""
        if not text:
            start = item["start"]
        text, end = candidate, item["end"]
    if text:
        cues.extend(split_long_cue(text, start, end, max_chars))
    return cues


def format_srt_time(seconds: float) -> str:
    ms = max(0, round(seconds * 1000))
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def scale_cues(cues: list[dict], factor: float) -> list[dict]:
    return [{"text": c["text"], "start": round(c["start"] * factor, 3), "end": round(c["end"] * factor, 3)} for c in cues]


def write_outputs(cues: list[dict], json_path: Path, srt_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(cues, ensure_ascii=False, indent=2), encoding="utf-8")
    blocks = [f"{i}\n{format_srt_time(c['start'])} --> {format_srt_time(c['end'])}\n{c['text']}\n"
              for i, c in enumerate(cues, 1)]
    srt_path.write_text("\n".join(blocks), encoding="utf-8")


def activate_media_placeholders(document: str) -> str:
    pattern = re.compile(r'<template\b(?P<attrs>[^>]*\bdata-media-type="(?:video|audio)"[^>]*)>\s*</template>', re.I)

    def replace(match: re.Match[str]) -> str:
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', match.group("attrs")))
        kind = attrs.get("data-media-type", "").lower()
        element_id = attrs.get("data-media-id", "")
        role = attrs.get("data-video-role") or attrs.get("data-audio-role") or ""
        source = {
            ("video", "avatar"): "媒体/HeyGen数字人.mp4",
            ("audio", "voiceover"): "媒体/HeyGen口播.mp3",
            ("audio", "background-music"): "媒体/背景音乐.mp3",
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
    return re.sub(r'(<script\b[^>]*?)\bdata-src="([^"]+)"',
                  lambda match: f'{match.group(1).rstrip()} src="素材/vendor/gsap.min.js"', document, flags=re.I)


def scale_scene_timings(document: str, factor: float) -> str:
    pattern = re.compile(r'<(?:section|div)\b[^>]*data-coverage="full"[^>]*>', re.I)

    def scale_tag(match: re.Match[str]) -> str:
        tag = match.group(0)
        for name in ("data-start", "data-duration"):
            found = re.search(rf'\s{name}="([0-9.]+)"', tag)
            if found:
                tag = set_attribute(tag, name, f"{float(found.group(1)) * factor:.3f}")
        return tag

    return pattern.sub(scale_tag, document)


def set_attribute(tag: str, name: str, value: str) -> str:
    pattern = rf'\s{name}="[^"]*"'
    replacement = f' {name}="{value}"'
    return re.sub(pattern, replacement, tag, count=1) if re.search(pattern, tag) else tag[:-1].rstrip() + replacement + ">"


def set_media_duration(document: str, element_id: str, duration: float) -> str:
    pattern = re.compile(rf'<(video|audio)\b[^>]*\bid="{re.escape(element_id)}"[^>]*>', re.I)
    match = pattern.search(document)
    if not match:
        raise SystemExit(f"HTML 缺少媒体元素 #{element_id}")
    return document[:match.start()] + set_attribute(match.group(0), "data-duration", f"{duration:.3f}") + document[match.end():]


def set_role_duration(document: str, media_type: str, role: str, duration: float) -> str:
    role_attr = "data-video-role" if media_type == "video" else "data-audio-role"
    pattern = re.compile(rf'<{media_type}\b[^>]*\b{role_attr}="{re.escape(role)}"[^>]*>', re.I)
    match = pattern.search(document)
    if not match:
        return set_media_duration(document, {
            ("video", "avatar"): "heygen-video",
            ("audio", "voiceover"): "heygen-voice",
            ("audio", "background-music"): "background-music",
        }.get((media_type, role), role), duration)
    return document[:match.start()] + set_attribute(match.group(0), "data-duration", f"{duration:.3f}") + document[match.end():]


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
        rows.append(f'    <div id="caption-{index}" class="clip caption" data-start="{cue["start"]:.3f}" '
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


def enforce_production_layout(document: str) -> str:
    document = re.sub(r'<html\b([^>]*)>', lambda match: '<html' + set_attribute(match.group(1), "lang", "zh-CN") + '>', document, count=1, flags=re.I)
    if re.search(r'<style\b[^>]*id="production-layout-contract"[^>]*>.*?</style>', document, re.I | re.S):
        document = re.sub(
            r'<style\b[^>]*id="production-layout-contract"[^>]*>.*?</style>',
            lambda _: PRODUCTION_LAYOUT_CSS.strip(),
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
    """Avoid applying timelineScale twice to already-scaled scene start times."""
    document = re.sub(r"\bat\(\s*start\s*\)", "Number(start)", document)
    document = re.sub(r"\bat\(\s*start\s*\+\s*([^()]*)\)", r"Number(start)+at(\1)", document)
    document = re.sub(r"tl\.seek\(at\(Number\(sec\)\|\|0\)\)", "tl.seek(Number(sec)||0)", document)
    return document


def rewrite_html(path: Path, cues: list[dict], target_duration: float, transcript_path: Path) -> None:
    document = activate_media_placeholders(path.read_text(encoding="utf-8"))
    document = normalize_wall_clock_controller(document)
    if CAPTION_START in document and CAPTION_END in document:
        document = re.sub(re.escape(CAPTION_START) + r".*?" + re.escape(CAPTION_END), lambda _: caption_block(cues), document, count=1, flags=re.S)
    else:
        raise SystemExit("HTML 缺少 CAPTIONS_START/CAPTIONS_END 字幕标记")
    authoring_match = re.search(r'\bdata-authoring-duration="([0-9.]+)"', document)
    authoring_duration = float(authoring_match.group(1)) if authoring_match else 30.0
    timeline_factor = target_duration / authoring_duration if authoring_duration > 0 else 1.0
    scaled_match = re.search(r'\bdata-timeline-scaled-duration="([0-9.]+)"', document)
    already_scaled_to = float(scaled_match.group(1)) if scaled_match else None
    if already_scaled_to is None or abs(already_scaled_to - target_duration) > 0.05:
        document = scale_scene_timings(document, timeline_factor)
    document = normalize_scaled_scene_positions(document)
    document = set_role_duration(document, "audio", "voiceover", target_duration)
    document = set_role_duration(document, "video", "avatar", target_duration)
    document = set_role_duration(document, "audio", "background-music", target_duration)
    document = ensure_root_composition(document, target_duration)
    root_pattern = re.compile(r'(<div\b[^>]*\bdata-composition-id="[^"]+"[^>]*>)', re.I)
    root_match = root_pattern.search(document)
    if not root_match:
        raise SystemExit("HTML 缺少根 composition")
    root_tag = set_attribute(root_match.group(0), "data-duration", f"{target_duration:.3f}")
    root_tag = set_attribute(root_tag, "data-caption-sync", "real-transcript")
    root_tag = set_attribute(root_tag, "data-timeline-scale", f"{timeline_factor:.6f}")
    root_tag = set_attribute(root_tag, "data-timeline-scaled-duration", f"{target_duration:.3f}")
    root_tag = set_attribute(root_tag, "data-caption-source", transcript_path.name)
    document = document[:root_match.start()] + root_tag + document[root_match.end():]
    document = enforce_production_layout(document)
    path.write_text(document, encoding="utf-8")


def resolve_hyperframes() -> tuple[Path, Path]:
    node = Path(os.environ.get("NODE_BIN", "/tmp/node22-runtime/bin/node"))
    if not node.exists():
        resolved = shutil.which("node")
        if not resolved:
            raise SystemExit("缺少 Node.js")
        node = Path(resolved)
    cli = Path(os.environ.get("HYPERFRAMES_CLI", "/Users/jinfeiqing/.npm/_npx/7ba6bcc82b4b0196/node_modules/hyperframes/bin/hyperframes.mjs"))
    if not cli.exists():
        resolved = shutil.which("hyperframes")
        if not resolved:
            raise SystemExit("缺少 HyperFrames CLI")
        cli = Path(resolved)
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
    parser.add_argument("--avatar-video", type=Path, default=Path("媒体/HeyGen数字人.mp4"))
    parser.add_argument("--transcript", type=Path)
    parser.add_argument("--auto-transcribe", action="store_true")
    parser.add_argument("--target-duration", type=float, default=30.0)
    parser.add_argument("--duration-tolerance", type=float, default=0.25)
    parser.add_argument("--max-caption-chars", type=int, default=16)
    parser.add_argument("--skip-media-normalization", action="store_true")
    args = parser.parse_args()
    for path in (args.html, args.voice, args.avatar_video):
        if not path.exists():
            raise SystemExit(f"缺少文件：{path}")
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
        cues = group_entries(load_transcript(transcript), args.max_caption_chars)
    if not cues:
        raise SystemExit("未能从时间码生成字幕")
    voice_actual = media_duration(args.voice)
    avatar_actual = media_duration(args.avatar_video)
    natural_duration = max(voice_actual, avatar_actual)
    if fallback and cues and cues[-1]["end"] > 0:
        cues = scale_cues(cues, natural_duration / cues[-1]["end"])
    elif cues[-1]["end"] > natural_duration + max(0.5, args.duration_tolerance):
        raise SystemExit("字幕时间码明显长于实际口播，请检查是否选错音频或时间码")
    effective_duration = (
        args.target_duration
        if abs(natural_duration - args.target_duration) <= args.duration_tolerance
        else natural_duration
    )
    if not args.skip_media_normalization:
        normalize_media_duration(args.voice, effective_duration)
        normalize_media_duration(args.avatar_video, effective_duration)
        background_music = Path("媒体/背景音乐.mp3")
        if background_music.exists():
            normalize_media_duration(background_music, effective_duration)
        effective_duration = max(media_duration(args.voice), media_duration(args.avatar_video))
    write_outputs(cues, Path("字幕/口播时间码.json"), Path("字幕/口播字幕.srt"))
    rewrite_html(args.html, cues, effective_duration, Path("字幕/HTML字幕时间码.json" if fallback else "字幕/口播时间码.json"))
    config_path = Path("hyperframes.json")
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["duration"] = round(effective_duration, 3)
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"voice_duration={media_duration(args.voice):.3f}")
    print(f"avatar_duration={media_duration(args.avatar_video):.3f}")
    print(f"caption_cues={len(cues)}")
    print(f"updated={args.html}")


if __name__ == "__main__":
    main()
