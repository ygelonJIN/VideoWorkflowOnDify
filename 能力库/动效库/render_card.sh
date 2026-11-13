#!/bin/bash
# 出一张卡的 3 秒样片：生成工程 → 渲染 → 落到 样片/全卡审阅/<族>/<编号>-<名字>.mp4
# 用法：bash 能力库/动效库/render_card.sh T01
set -euo pipefail
ID="${1:?用法: render_card.sh <编号>，例如 T01}"

LIB="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$LIB/../.." && pwd)"
OUT="$ROOT/能力库/动效库/样片/全卡审阅"
HF="$ROOT/成品/workflow_runtime/vendor/node_modules/hyperframes/bin/hyperframes.mjs"
CHROME="${HYPERFRAMES_BROWSER_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
N22="$(ls -d "$HOME"/.nvm/versions/node/v22*/bin/node 2>/dev/null | sort -V | tail -1 || true)"
N22="${N22:-$(command -v node)}"

LINE="$(python3 "$LIB/make_review_reels.py" --only "$ID" --tsv)"
FAM="$(printf '%s' "$LINE" | cut -f1)"
NAME="$(printf '%s' "$LINE" | cut -f3)"
DIR="$(printf '%s' "$LINE" | cut -f4)"
mkdir -p "$OUT/$FAM"

( cd "$DIR" && HYPERFRAMES_BROWSER_PATH="$CHROME" \
    HYPERFRAMES_CACHE_DIR="$PWD/.hyperframes/cache" \
    "$N22" "$HF" render . -w 1 -f 30 -q looks \
      --no-browser-gpu --experimental-fast-capture=false -o out.mp4 >/dev/null )
mv "$DIR/out.mp4" "$OUT/$FAM/$ID-$NAME.mp4"
rm -rf "$DIR/.hyperframes"
echo "✓ $OUT/$FAM/$ID-$NAME.mp4"
