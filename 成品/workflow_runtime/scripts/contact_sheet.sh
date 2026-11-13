#!/bin/sh
# Contact sheet of a video: one frame every STEP seconds, tiled with timestamps.
# usage: sh contact_sheet.sh VIDEO OUT.jpg [STEP_SECONDS=1] [COLUMNS=5] [THUMB_WIDTH=384]
set -e
V=$1; OUT=$2; STEP=${3:-1}; COLS=${4:-5}; TW=${5:-384}
[ -f "$V" ] || { echo "usage: contact_sheet.sh VIDEO OUT.jpg [STEP] [COLS] [THUMB_W]"; exit 1; }
DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$V")
N=$(python3 -c "import math;print(max(1,math.ceil(float('$DUR')/float('$STEP'))))")
ROWS=$(( (N + COLS - 1) / COLS ))
# drawtext 需要 ffmpeg 编译 freetype；没有就退化成不带时间戳的联系表
if ffmpeg -hide_banner -filters 2>/dev/null | grep -q ' drawtext '; then
  VF="fps=1/$STEP,scale=$TW:-2,drawtext=text='%{pts\:hms}':x=6:y=6:fontsize=18:fontcolor=yellow:box=1:boxcolor=black@0.6,tile=${COLS}x${ROWS}:padding=4:color=gray"
else
  VF="fps=1/$STEP,scale=$TW:-2,tile=${COLS}x${ROWS}:padding=4:color=gray"
fi
ffmpeg -v error -y -i "$V" -vf "$VF" -frames:v 1 -q:v 3 "$OUT"
echo "wrote $OUT ($N frames, ${COLS}x${ROWS})"
