#!/bin/bash
# Electron 二进制准备：优先用本机已有安装，其次从 npmmirror CDN 下载。
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d node_modules/electron/dist ]; then
  echo "已存在 node_modules/electron/dist"
  exit 0
fi
EXISTING="${WF_ELECTRON_SRC:-/Volumes/TUF ESD-T1A Media/NoBoWo/node_modules/electron}"
if [ -d "$EXISTING/dist" ]; then
  echo "从 $EXISTING 复制 Electron 二进制"
  cp -R "$EXISTING/dist" node_modules/electron/dist
  printf "Electron.app/Contents/MacOS/Electron" > node_modules/electron/path.txt
  exit 0
fi
echo "从 npmmirror CDN 下载（约 120MB）"
ELECTRON_MIRROR=https://cdn.npmmirror.com/binaries/electron/ node node_modules/electron/install.js
