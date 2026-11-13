#!/bin/bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="$(cd "$BASE_DIR/.." && pwd)"
PROJECTS_ROOT="$(cd "$BASE_DIR/../.." && pwd)"

normalize_path() {
  local value="$1"
  value="${value#\"}"
  value="${value%\"}"
  value="${value#\'}"
  value="${value%\'}"
  value="${value//\\ / }"
  if [[ "$value" == \~/* ]]; then
    value="$HOME/${value#\~/}"
  fi
  printf '%s' "$value"
}

if [ "$#" -eq 3 ]; then
  PROJECT_NAME="$1"
  HTML_INPUT="$2"
  RESPONSE_INPUT="$3"
else
  echo "用法：bash render_new_project.sh 项目名 /path/to/html_document.html /path/to/heygen_response.json"
  echo "workflow_runtime/ 是通用运行资产目录，不是可复用的项目文件夹。"
  exit 2
fi

HTML_INPUT="$(normalize_path "$HTML_INPUT")"
RESPONSE_INPUT="$(normalize_path "$RESPONSE_INPUT")"

if [[ "$PROJECT_NAME" == *"/path/to/"* || "$HTML_INPUT" == *"/path/to/"* || "$RESPONSE_INPUT" == *"/path/to/"* ]]; then
  echo "检测到示例占位符。请替换成真实项目名和文件路径，或不带参数运行本脚本进入交互模式。"
  exit 2
fi

if [ -z "$PROJECT_NAME" ] || [ "$PROJECT_NAME" = "." ] || [ "$PROJECT_NAME" = ".." ] || [[ "$PROJECT_NAME" == *"/"* ]] || [[ "$PROJECT_NAME" == *\\* ]]; then
  echo "项目名不能为空，也不能包含路径分隔符：$PROJECT_NAME"
  exit 2
fi
if [ ! -f "$HTML_INPUT" ]; then
  echo "找不到 html_document 文件：$HTML_INPUT"
  echo "请先把 Dify 输出的 html_document 保存为该文件，再运行本命令。"
  exit 1
fi
if [ ! -f "$RESPONSE_INPUT" ]; then
  echo "找不到 heygen_response 文件：$RESPONSE_INPUT"
  echo "请先把完成状态的 heygen_response_json 保存为该文件，再运行本命令。"
  exit 1
fi

PROJECT_DIR="$PROJECTS_ROOT/$PROJECT_NAME"
if [ -e "$PROJECT_DIR" ]; then
  echo "项目文件夹已存在，拒绝覆盖：$PROJECT_DIR"
  exit 1
fi

mkdir -p "$PROJECT_DIR/媒体" "$PROJECT_DIR/成片" "$PROJECT_DIR/字幕"
cp "$TEMPLATE_DIR/hyperframes.json" "$PROJECT_DIR/"
cp "$TEMPLATE_DIR/render.sh" "$PROJECT_DIR/"
cp -R "$TEMPLATE_DIR/scripts" "$PROJECT_DIR/脚本"
cp -R "$TEMPLATE_DIR/assets" "$PROJECT_DIR/素材"
cp "$TEMPLATE_DIR/docs/视频说明.md" "$PROJECT_DIR/"
cp "$TEMPLATE_DIR/docs/项目说明.md" "$PROJECT_DIR/"
cp "$HTML_INPUT" "$PROJECT_DIR/index.html"
cp "$RESPONSE_INPUT" "$PROJECT_DIR/heygen_response.json"
if [ -f "$(dirname "$HTML_INPUT")/voiceover_script.txt" ]; then
  cp "$(dirname "$HTML_INPUT")/voiceover_script.txt" "$PROJECT_DIR/口播文案.txt"
fi

echo "已创建独立项目：$PROJECT_DIR"
if [ "${SKIP_RENDER:-0}" = "1" ]; then
  echo "SKIP_RENDER=1，跳过渲染。"
  exit 0
fi

cd "$PROJECT_DIR"
bash render.sh
