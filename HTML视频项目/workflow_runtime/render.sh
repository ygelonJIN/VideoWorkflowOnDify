#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

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
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  HF_CLI="$(find "$HOME/.npm/_npx" -path '*/node_modules/hyperframes/bin/hyperframes.mjs' -type f 2>/dev/null | sort | tail -1 || true)"
fi
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  HF_CLI="$(command -v hyperframes || true)"
fi
if [ -z "$HF_CLI" ] || [ ! -f "$HF_CLI" ]; then
  echo "缺少 HyperFrames CLI。请安装 Node.js 22+ 后运行 npx hyperframes --version。"
  exit 1
fi
if [ ! -x "$CHROME_BIN" ]; then
  echo "缺少 Chrome：$CHROME_BIN"
  exit 1
fi

if grep -q 'data-render-mode="black-frame"' index.html; then
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

echo "同步真实口播时间码并校准音画时长..."
if [ -f 口播文案.txt ] && [ -s 字幕/口播时间码.json ]; then
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
if grep -q 'data-render-mode="black-frame"' index.html; then
  SYNC_ARGS+=(--black-frame)
else
  SYNC_ARGS+=(--avatar-video 媒体/HeyGen数字人.mp4)
fi
if [ -f 口播文案.txt ]; then
  SYNC_ARGS+=(--reference-script 口播文案.txt)
fi
python3 脚本/sync_video.py "${SYNC_ARGS[@]}" "${TRANSCRIPT_ARG[@]}"

echo "检查生产排版/内容密度/音画同步契约..."
python3 脚本/check_html_contract.py index.html
echo "检查真实 DOM 的组件重叠、垂直构图和字幕规格..."
HYPERFRAMES_CLI="$HF_CLI" HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" 脚本/check_html_layout.mjs index.html

if [ "${RUN_HYPERFRAMES_CHECK:-0}" = "1" ]; then
  echo "检查 HTML 组合..."
  HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" "$HF_CLI" check . --no-browser-gpu || true
else
  echo "跳过交互式 HyperFrames check；生产契约已由 check_html_contract.py 验证。"
fi

echo "渲染最终 MP4..."
HYPERFRAMES_BROWSER_PATH="$CHROME_BIN" "$NODE_BIN" "$HF_CLI" render . \
  --quality delivery \
  --no-browser-gpu \
  --experimental-fast-capture=false \
  -o ./成片/最终视频.mp4

echo "标准化最终 MP4 响度..."
python3 脚本/normalize_final_audio.py --video ./成片/最终视频.mp4

echo "检查最终 MP4 的媒体主时钟与无数字人契约..."
python3 脚本/check_final_video.py   --video ./成片/最终视频.mp4   --voice "$VOICE_FILE"   --html index.html

echo "完成：$PROJECT_DIR/成片/最终视频.mp4"
