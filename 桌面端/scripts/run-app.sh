#!/bin/bash
# 从 DSH 终端启动时必须清掉 ELECTRON_RUN_AS_NODE，否则 Electron 会以 Node 模式跑、
# 连 import { app } from "electron" 都会失败（报 does not provide an export named 'BrowserWindow'）。
#
# 关键：必须把应用目录作为参数传给 Electron。不传的话 Electron 会跑它自带的默认应用，
# 只打印 "To run a local app, execute the following on the command line: ... path-to-app"。
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d node_modules/electron/dist ]; then
  echo "缺少 Electron 二进制：node_modules/electron/dist" >&2
  echo "跑 bash scripts/setup-electron.sh 或 npm install electron 后再试" >&2
  exit 1
fi
if [ ! -f renderer/dist/app.js ]; then
  echo "缺少 renderer/dist/app.js，先跑 npm run build:renderer" >&2
  exit 1
fi
if [ "$#" -eq 0 ]; then
  set -- .
elif [ "${1#-}" != "$1" ]; then
  # 传的是选项（--smoke/--version 等）而不是应用目录，补上 "."
  set -- . "$@"
fi
echo "Electron 启动：$PWD  参数：$*" >&2
exec env -u ELECTRON_RUN_AS_NODE ./node_modules/.bin/electron "$@"
