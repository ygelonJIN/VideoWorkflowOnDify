#!/bin/bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECTS_ROOT="$(cd "$BASE_DIR/../.." && pwd)"
if [ "$#" -gt 0 ]; then
  NAME="$1"
  shift
else
  NAME="dify-output-$(date +%Y%m%d-%H%M%S)"
fi

echo "同一条命令自动识别：仅 HTML → 预览；无数字人口播 → 本地 TTS/提供音频并生成 MP4；全合一 → HeyGen 并生成 MP4。"
echo "默认打开 TextEdit；请把 Dify 输出粘贴到 TextEdit，不要粘贴到终端。"
exec python3 "$BASE_DIR/process_dify_output.py" "$NAME" "$@"
