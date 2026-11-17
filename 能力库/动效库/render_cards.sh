#!/bin/bash
# 批量出确认片：并发跑 render_card.sh，默认 4 路。
#
# 用法：
#   bash 能力库/动效库/render_cards.sh T27 K40 U65          # 点名渲
#   bash 能力库/动效库/render_cards.sh --missing            # 只渲表里还缺片的
#   JOBS=2 bash 能力库/动效库/render_cards.sh --missing     # 限并发（浅底片用 2）
#
# 为什么要有这个：add_card.py --render 是一张一张串行等，15 张要 4 分钟。
# 转正按批做的时候，先一次写完表（秒级），再一条命令并行补片；
# 返工只点名重渲改过的那几张。
set -uo pipefail
LIB="$(cd "$(dirname "$0")" && pwd)"
JOBS="${JOBS:-4}"
export LIB

if [ "$#" -eq 0 ]; then
  echo "用法: render_cards.sh <编号...> | --missing   （JOBS=4 控制并发）"
  exit 2
fi

ids=()
if [ "${1:-}" = "--missing" ]; then
  # macOS 自带 bash 3.2 没有 mapfile，用 while read 兜住
  while IFS= read -r _id; do
    [ -n "$_id" ] && ids+=("$_id")
  done < <(python3 - "$LIB" <<'PY'
import json, pathlib, sys
lib = pathlib.Path(sys.argv[1])
cards = json.loads((lib / "presets.json").read_text(encoding="utf-8"))["presets"]
root = lib / "样片" / "全卡审阅"
for c in cards:
    if c.get("status") != "ready":
        continue
    if c.get("role") in ("none", "archive", "special_dom", "page_transition"):
        continue
    fam = c.get("family") or "其他"
    if list((root / fam).glob(c["id"] + "-*.mp4")):
        continue
    print(c["id"])
PY
  )
else
  ids=("$@")
fi

if [ "${#ids[@]}" -eq 0 ]; then
  echo "没有缺片：表里每张 ready 卡都有确认片。"
  exit 0
fi

tmp="$(mktemp -d)"
export tmp
run() {
  local id="$1" log="$tmp/$id.log"
  if bash "$LIB/render_card.sh" "$id" >"$log" 2>&1; then
    printf "  ✓ %s\n" "$id"
  else
    printf "  ✗ %s\n" "$id"
    tail -4 "$log" | sed 's/^/      /'
    echo "$id" >>"$tmp/failed"
  fi
}
export -f run

echo "批量渲片：${#ids[@]} 张，并发 $JOBS"
printf '%s\n' "${ids[@]}" | xargs -P "$JOBS" -n1 bash -c 'run "$1"' _

fail=0
[ -f "$tmp/failed" ] && fail=$(wc -l <"$tmp/failed" | tr -d ' ')
echo "完成：成功 $(( ${#ids[@]} - fail ))，失败 $fail"
if [ "$fail" -gt 0 ]; then
  echo "失败清单在 $tmp/failed，日志同目录。重试样例：JOBS=1 bash 能力库/动效库/render_cards.sh $(tr '\n' ' ' <"$tmp/failed")"
  exit 1
fi
rm -rf "$tmp"
