#!/bin/bash
# 候选出片：**只落 样片/待筛/<批次>/**，绝不写 全卡审阅。
#
# 为什么单独有这个脚本：候选（还没被任何人看过的新卡）不许出现在 全卡审阅，
# 那是审阅过的样片库。转正时由 add_card.py --batch 把这里的片搬过去。
#
# 用法：
#   bash 能力库/动效库/render_candidates.sh 20261117-magicui2 本批.json
#   JOBS=2 bash 能力库/动效库/render_candidates.sh <批次> <卡定义.json>
#
# 产物：
#   样片/待筛/<批次>/<编号>-<名字>.mp4
#   样片/待筛/<批次>/源/<族>/<编号>/        可重渲工程
#   样片/待筛/<批次>/待筛清单.tsv
set -uo pipefail
LIB="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$LIB/../.." && pwd)"
BATCH="${1:?用法: render_candidates.sh <批次名> <卡定义.json>}"
JSON="${2:?用法: render_candidates.sh <批次名> <卡定义.json>}"
JOBS="${JOBS:-4}"
OUT="$LIB/样片/待筛/$BATCH"
HF="$ROOT/成品/workflow_runtime/vendor/node_modules/hyperframes/bin/hyperframes.mjs"
CHROME="${HYPERFRAMES_BROWSER_PATH:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
N22="$(ls -d "$HOME"/.nvm/versions/node/v22*/bin/node 2>/dev/null | sort -V | tail -1 || true)"
N22="${N22:-$(command -v node)}"

mkdir -p "$OUT"
echo "候选批次：$BATCH（只写待筛，不进全卡审阅）"
mapfile_tsv="$(python3 "$LIB/make_review_reels.py" --cards-json "$JSON" --out "$OUT" --tsv)"
if [ -z "$mapfile_tsv" ]; then echo "没有生成任何候选项"; exit 1; fi

render_one() {
  local line="$1"
  local fam id name dir
  fam="$(printf '%s' "$line" | cut -f1)"
  id="$(printf '%s' "$line" | cut -f2)"
  name="$(printf '%s' "$line" | cut -f3)"
  dir="$(printf '%s' "$line" | cut -f4)"
  local mp4="$OUT/$id-$name.mp4"
  if [ -f "$mp4" ]; then printf "  已有 %s\n" "$id"; return 0; fi
  if ( cd "$dir" && HYPERFRAMES_BROWSER_PATH="$CHROME" \
       HYPERFRAMES_CACHE_DIR="$PWD/.hyperframes/cache" \
       "$N22" "$HF" render . -w 1 -f 30 -q looks \
         --no-browser-gpu --experimental-fast-capture=false -o out.mp4 >/dev/null 2>&1 ); then
    mv "$dir/out.mp4" "$mp4"
    rm -rf "$dir/.hyperframes"
    printf "  ✓ %s-%s\n" "$id" "$name"
  else
    printf "  ✗ %s（工程在 %s）\n" "$id" "$dir"
    echo "$id" >>"$OUT/失败.txt"
  fi
}
export -f render_one
export OUT N22 HF CHROME

printf '%s\n' "$mapfile_tsv" | xargs -P "$JOBS" -n1 bash -c 'render_one "$1"' _

python3 - "$OUT" <<'PY'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
rows = []
for mp4 in sorted(out.glob("*.mp4")):
    cid, name = mp4.stem.split("-", 1)
    rows.append((cid, name, mp4.name))
(out / "待筛清单.tsv").write_text(
    "编号\t名字\t片名\n" + "".join("%s\t%s\t%s\n" % r for r in rows), encoding="utf-8")
print("待筛清单：%d 条" % len(rows))
PY
echo "看片：$OUT"
