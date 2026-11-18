#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""候选片自检：每张片取两帧，量"墨量"（非背景像素占比）和帧间差异。

用途：出完候选片先自己看一遍有没有整屏空白 / 只有标题没有主体 / 完全没动。
只读，不改任何文件；结论打到 stdout，可重跑。

用法：
    python3 qa_batch.py 20261117-mermaid
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parents[2]          # 能力库/动效库
BATCH_ROOT = HERE / "样片" / "待筛"
W, H = 270, 480

INK_MIN = 0.004      # 主体至少要占 0.4% 的非背景像素
DIFF_MIN = 0.0015    # 两帧之间至少要有 0.15% 的像素变化（证明在动）


def gray(mp4: pathlib.Path, t: float) -> bytes:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "%.2f" % t, "-i", str(mp4), "-frames:v", "1",
         "-vf", "scale=%d:%d" % (W, H), "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    return r.stdout if len(r.stdout) >= W * H else b""


def ink(px: bytes) -> float:
    if not px:
        return 0.0
    hot = sum(1 for v in px if v > 48)
    return hot / float(W * H)


def diff(a: bytes, b: bytes) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    return sum(1 for i in range(n) if abs(a[i] - b[i]) > 22) / float(n)


def main() -> int:
    batch = sys.argv[1] if len(sys.argv) > 1 else ""
    d = BATCH_ROOT / batch
    if not d.is_dir():
        print("没有这个批次：" + str(d))
        return 1
    rows, weak = [], []
    for mp4 in sorted(d.glob("*.mp4")):
        f1, f2 = gray(mp4, 0.6), gray(mp4, 2.4)
        if not f1 or not f2:
            rows.append((mp4.stem, -1, -1, "解码失败"))
            weak.append((mp4.stem, "解码失败", 0, 0))
            continue
        i1, i2 = ink(f1), ink(f2)
        dv = diff(f1, f2)
        body = max(i1, i2) - 0.002          # 扣掉左上角标题行本身的墨
        flag = ""
        if body < INK_MIN:
            flag = "主体太空"
        elif dv < DIFF_MIN:
            flag = "几乎没动"
        rows.append((mp4.stem, i1, i2, flag or "ok"))
        if flag:
            weak.append((mp4.stem, flag, round(body, 4), round(dv, 4)))
    ok = sum(1 for r in rows if r[3] == "ok")
    print("批次 %s：%d 条，ok %d，需处理 %d" % (batch, len(rows), ok, len(weak)))
    for name, flag, body, dv in weak:
        print("  ! %-30s %s  主体%.4f 变化%.4f" % (name, flag, body, dv))
    out = d / "自检.json"
    out.write_text(json.dumps(
        [{"片": r[0], "墨量1": round(r[1], 4), "墨量2": round(r[2], 4), "结论": r[3]} for r in rows],
        ensure_ascii=False, indent=1), encoding="utf-8")
    print("明细：" + str(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
