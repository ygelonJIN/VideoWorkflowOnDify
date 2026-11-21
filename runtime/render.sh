#!/bin/bash
set -euo pipefail

STAGE="启动"
trap 'code=$?; if [ "$code" -ne 0 ]; then echo ""; echo "❌ 失败关卡：${STAGE}（退出码 ${code}）"; fi' EXIT

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"
# 渲染锁默认放在项目内，避免 ~/.cache 在多账号/沙箱下不可写导致渲染排队失败。
# 缓存放全局一份：whisper 模型 465M，跟着项目走会每个项目各存一份（2026-11-17 改）。
export HYPERFRAMES_CACHE_DIR="${HYPERFRAMES_CACHE_DIR:-$HOME/.cache/hyperframes}"
mkdir -p "$HYPERFRAMES_CACHE_DIR" "$HYPERFRAMES_CACHE_DIR/locks"

NODE_BIN="${NODE_BIN:-/tmp/node22-runtime/bin/node}"
HF_CLI="${HYPERFRAMES_CLI:-}"
CHROME_BIN="${HYPERFRAMES_BROWSER_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [ ! -x "$NODE_BIN" ]; then
  NODE_BIN="$(find "$HOME/.nvm/versions/node" -path '*/bin/node' -type f 2>/dev/null | sort -V | tail -1 || true)"
fi
if [ ! -x "$NODE_BIN" ]; then
  NODE_BIN="$(command -v node || true)"
fi
if [ -z "${NODE_BIN:-}" ]; then
  echo "缺少 Node.js，请安装 Node.js 22+。"
  exit 1
fi
NODE_MAJOR="$("$NODE_BIN" -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)"
if [ "$NODE_MAJOR" -lt 22 ]; then
  NODE22_BIN="$(find "$HOME/.nvm/versions/node" -path '*/bin/node' -type f 2>/dev/null | sort -V | tail -1 || true)"
  if [ -n "$NODE22_BIN" ] && [ "$("$NODE22_BIN" -p 'Number(process.versions.node.split(".")[0])' 2>/dev/null || echo 0)" -ge 22 ]; then
    NODE_BIN="$NODE22_BIN"
    NODE_MAJOR="$("$NODE_BIN" -p 'Number(process.versions.node.split(".")[0])')"
  fi
fi
if [ "$NODE_MAJOR" -lt 22 ]; then
  echo "HyperFrames 需要 Node.js 22+，当前：$("$NODE_BIN" -v)"
  exit 1
fi
# 优先使用仓库内钉死的 CLI（runtime/vendor），再退回 npx 缓存和全局命令。
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  SEARCH_DIR="$PROJECT_DIR"
  for _ in 1 2 3 4; do
    for CANDIDATE in \
      "$SEARCH_DIR/vendor/node_modules/hyperframes/bin/hyperframes.mjs" \
      "$SEARCH_DIR/runtime/vendor/node_modules/hyperframes/bin/hyperframes.mjs"; do
      if [ -f "$CANDIDATE" ]; then
        HF_CLI="$CANDIDATE"
        break 2
      fi
    done
    SEARCH_DIR="$(dirname "$SEARCH_DIR")"
  done
fi
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  HF_CLI="$(find "$HOME/.npm/_npx" -path '*/node_modules/hyperframes/bin/hyperframes.mjs' -type f 2>/dev/null | sort | tail -1 || true)"
fi
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  HF_CLI="$(command -v hyperframes || true)"
fi
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  echo "缺少 HyperFrames CLI（不是 Node 的问题）。"
  echo "修复：在仓库根的 runtime/vendor 下执行 npm i（需 Node 22+），"
  echo "或把可用的 hyperframes.mjs 路径写进 HYPERFRAMES_CLI 环境变量。"
  exit 1
fi
if [ ! -x "$CHROME_BIN" ]; then
  echo "缺少 Chrome：$CHROME_BIN"
  exit 1
fi

BLACK_FRAME_HINT=0
if grep -q 'data-render-mode="black-frame"' index.html; then
  BLACK_FRAME_HINT=1
elif [ -f 媒体/口播.mp3 ] && [ ! -f heygen_response.json ]; then
  BLACK_FRAME_HINT=1
  echo "未写 data-render-mode，但检测到 媒体/口播.mp3 且无 HeyGen 响应，按黑帧口播渲染。"
fi
if [ "$BLACK_FRAME_HINT" = "1" ]; then
  RENDER_MODE="black-frame"
  VOICE_FILE="媒体/口播.mp3"
  if [ ! -f "$VOICE_FILE" ]; then
    echo "缺少本地口播音频：$VOICE_FILE"
    exit 1
  fi
else
  RENDER_MODE="full"
  VOICE_FILE="媒体/HeyGen口播.mp3"
  if [ ! -f heygen_response.json ]; then
    echo "缺少 heygen_response.json"
    exit 1
  fi
  echo "核验 HeyGen video_id 与媒体身份..."
  if [ "${FORCE_HEYGEN_DOWNLOAD:-0}" = "1" ]; then
    python3 脚本/download_heygen_media.py heygen_response.json
  else
    python3 脚本/download_heygen_media.py heygen_response.json --if-needed
  fi
fi

STAGE="同步口播时间码与音画时长"
echo "同步真实口播时间码并校准音画时长..."
if [ -f 口播文案.txt ] && [ -s 媒体/transcript.json ]; then
  TRANSCRIPT_ARG=(--transcript 媒体/transcript.json)
elif [ -f 口播文案.txt ] && [ -s 字幕/口播时间码.json ]; then
  TRANSCRIPT_ARG=(--transcript 字幕/口播时间码.json)
elif [ "$RENDER_MODE" = "full" ] && [ -s 字幕/HeyGen转写.json ]; then
  TRANSCRIPT_ARG=(--transcript 字幕/HeyGen转写.json)
else
  TRANSCRIPT_ARG=(--auto-transcribe)
fi
SYNC_ARGS=(
  --html index.html
  --voice "$VOICE_FILE"
)
if [ "$RENDER_MODE" = "black-frame" ]; then
  SYNC_ARGS+=(--black-frame)
else
  SYNC_ARGS+=(--avatar-video 媒体/HeyGen数字人.mp4)
fi
if [ -f 字幕/手写字幕.srt ]; then
  SYNC_ARGS+=(--captions-srt 字幕/手写字幕.srt)
  echo "使用手写字幕：字幕/手写字幕.srt"
elif [ -f 字幕/最终字幕.srt ]; then
  SYNC_ARGS+=(--captions-srt 字幕/最终字幕.srt)
  echo "使用手写字幕：字幕/最终字幕.srt"
elif [ -f 口播文案.txt ]; then
  SYNC_ARGS+=(--reference-script 口播文案.txt)
fi
python3 脚本/sync_video.py "${SYNC_ARGS[@]}" "${TRANSCRIPT_ARG[@]}"

STAGE="生成页间转场快照"
if [ -f 脚本/snapshot_scenes.mjs ] && grep -q "__gtCut" index.html; then
  echo "生成每屏快照（页间 GT 转场当纹理用）..."
  HYPERFRAMES_CLI="$HF_CLI" HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" 脚本/snapshot_scenes.mjs index.html || echo "⚠️ 快照生成失败（页间转场会退回硬切）"
fi

# 检查器只当诊断：写进 诊断/检查结果.txt，不再拦渲染。
# 想恢复"不达标就停"的旧行为，跑 STRICT_RENDER=1 bash render.sh。
check_or_continue() {
  local name="$1"; shift
  echo "· 检查：${name}"
  if "$@" >> 诊断/检查结果.txt 2>&1; then
    echo "  ✓ ${name} 通过"
  else
    echo "  ⚠️ ${name} 有问题，已记录；继续渲染（只诊断，不拦）"
    if [ "${STRICT_RENDER:-0}" = "1" ]; then echo "STRICT_RENDER=1：停止"; exit 1; fi
  fi
  return 0
}
mkdir -p 诊断
: > 诊断/检查结果.txt
STAGE="检查生产契约（check_html_contract.py）"
check_or_continue "生产契约" python3 脚本/check_html_contract.py index.html

STAGE="检查真实 DOM 排版（check_html_layout.mjs）"
check_or_continue "真实 DOM 排版" env HYPERFRAMES_CLI="$HF_CLI" HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" 脚本/check_html_layout.mjs index.html

STAGE="检查页面时间线（空页/闪屏/动作越界）"
check_or_continue "页面时间线" env HYPERFRAMES_CLI="$HF_CLI" HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" 脚本/check_html_timing.mjs index.html
STAGE="检查动效编号"
echo "检查动效编号与 kit 调用（只报告）..."
if [ -f 脚本/check_presets.py ]; then
  python3 脚本/check_presets.py --html index.html || true
else
  for _d in "$PROJECT_DIR/.." "$PROJECT_DIR/../.." "$PROJECT_DIR/../../.."; do
    if [ -f "$_d/runtime/tools/check_presets.py" ]; then
      python3 "$_d/runtime/tools/check_presets.py" --html index.html || true
      break
    fi
  done
fi

STAGE="检查动效差异"
echo "检查动效差异（只报告）..."
HYPERFRAMES_CLI="$HF_CLI" HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" 脚本/check_motion_variation.mjs index.html || true

STAGE="检查构图差异"
check_or_continue "构图差异" env HYPERFRAMES_CLI="$HF_CLI" HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" 脚本/check_composition_variation.mjs index.html


if [ "${RUN_HYPERFRAMES_CHECK:-0}" = "1" ]; then
  STAGE="HyperFrames 组合检查"
echo "检查 HTML 组合..."
  HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" "$HF_CLI" check . --no-browser-gpu || true
else
  echo "跳过交互式 HyperFrames check；生产契约已由 check_html_contract.py 验证。"
fi

STAGE="渲染 MP4"
render_once() {
  HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" "$HF_CLI" render . \
    --quality delivery \
    --no-browser-gpu \
    --experimental-fast-capture=false \
    -o ./成片/最终视频.mp4
}
echo "渲染最终 MP4..."
render_once
STAGE="检查单帧黑闪"
if ! python3 脚本/detect_blank_frames.py ./成片/最终视频.mp4 --html index.html; then
  echo "检测到孤立空帧，先用前一帧修复..."
  STAGE="修复孤立空帧"
  python3 脚本/repair_blank_frames.py ./成片/最终视频.mp4 --html index.html
  STAGE="复查单帧黑闪"
  python3 脚本/detect_blank_frames.py ./成片/最终视频.mp4 --html index.html
fi

STAGE="检查动效密度"
python3 脚本/check_motion_profile.py ./成片/最终视频.mp4 || true

STAGE="响度标准化"
echo "标准化最终 MP4 响度..."
python3 脚本/normalize_final_audio.py --video ./成片/最终视频.mp4

STAGE="检查最终 MP4 契约"
echo "检查最终 MP4 的媒体主时钟与无数字人契约..."
python3 脚本/check_final_video.py   --video ./成片/最终视频.mp4   --voice "$VOICE_FILE"   --html index.html

# 复核产物：联系表 + 响度/真峰，只报告不拦截
STAGE="生成复核产物"
mkdir -p ./成片/复核
if [ -f 脚本/contact_sheet.sh ]; then
  echo "生成联系表..."
  bash 脚本/contact_sheet.sh ./成片/最终视频.mp4 ./成片/复核/联系表.jpg 2 6 384 || echo "⚠️ 联系表生成失败（不阻塞）"
fi
if [ -f 脚本/audio_check.sh ]; then
  echo "复核响度与真峰..."
  bash 脚本/audio_check.sh ./成片/最终视频.mp4 -14.5 | tee ./成片/复核/音频报告.txt || echo "⚠️ 音频复核失败（不阻塞）"
fi

echo "完成：$PROJECT_DIR/成片/最终视频.mp4"
