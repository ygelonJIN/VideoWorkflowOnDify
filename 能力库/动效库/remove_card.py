#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""删卡：一条命令走完，不用记步骤。

用法：
    python3 remove_card.py GT12 GT13          # 真删
    python3 remove_card.py GT12 --dry-run     # 只看会动哪些文件

做四件事，顺序固定：
    1. presets.json 删条目（唯一源）
    2. gen_catalog.py 重生成 能力卡.md / 组件卡.md / H00 目录
    3. 跑同步链：sync_expander.py → check
    4. 删样片（样片/全卡审阅/<族>/）与源工程（样片/全卡审阅/源/<族>/）

编号删后**永久留空，不再复用**：已发布过的编号进过提示词，复用会让旧记录对不上。
删完把编号追加到「已有能力一览.md」的"做过又删了"清单（脚本会提示，不自动写）。
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
WORK = HERE.parent.parent
PRESETS = HERE / "presets.json"
CARDS_MD = HERE / "能力卡.md"
REELS = HERE / "样片" / "全卡审阅"


def run(cmd: list[str]) -> int:
    print("  $", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(WORK)).returncode


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(PRESETS.read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in data["presets"]}
    missing = [i for i in args.ids if i not in by_id]
    if missing:
        raise SystemExit("表里没有：" + " ".join(missing))

    print("将要删除：")
    for i in args.ids:
        c = by_id[i]
        print("  %-6s %-10s 族=%s src=%s" % (i, c["name"], c.get("family"), c.get("src", "")))

    # 1) presets
    keep = [c for c in data["presets"] if c["id"] not in args.ids]
    if args.dry_run:
        print("  · presets.json：%d → %d 张" % (len(by_id), len(keep)))
    else:
        data["presets"] = keep
        data["updated"] = __import__("datetime").date.today().isoformat()
        PRESETS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("✓ presets.json：%d → %d 张" % (len(by_id), len(keep)))

    # 2) 能力卡 / 组件卡 / H00 目录：全是生成物，跑一次生成器即可
    if not args.dry_run:
        if run([sys.executable, str(HERE / "gen_catalog.py")]) != 0:
            raise SystemExit("gen_catalog 失败")
        print("✓ 能力卡.md / 组件卡.md / H00 目录：已按 presets.json 重生成")

    # 3) 同步链
    if not args.dry_run:
        if run([sys.executable, str(HERE / "sync_expander.py")]) != 0:
            raise SystemExit("sync_expander 失败")
        if run([sys.executable, str(HERE / "sync_expander.py"), "--check"]) != 0:
            raise SystemExit("同步检查没过，先看差异再删样片")

    # 4) 样片与源工程
    for i in args.ids:
        fam = by_id[i].get("family", "其他")
        for p in (REELS / fam).glob(i + "-*.mp4"):
            print("  删样片", p.relative_to(WORK))
            if not args.dry_run:
                p.unlink()
        src = REELS / "源" / fam / i
        if src.exists():
            print("  删源工程", src.relative_to(WORK))
            if not args.dry_run:
                shutil.rmtree(src)

    print()
    if args.dry_run:
        print("（dry-run，什么都没动）")
    else:
        print("改完。收尾两件事：")
        print("  1. 把这几个编号追加到 能力库/动效库/来源台账.md 的「删过、不再复用」清单")
        print("  2. 如果它们出现在某条成片的项目里，那条片子要重跑")


if __name__ == "__main__":
    main()
