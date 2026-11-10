#!/usr/bin/env python3
"""预览图片对号：按修改时间从早到晚对应有图屏（跳过 role=html），不改文件名。

出片时构建脚本用同一套规则映射，所以这里只做检查，不动文件。

用法：
    python3 ingest_images.py                     # 看怎么对号、缺哪张
    python3 ingest_images.py --order name        # 按文件名里的数字排
    python3 ingest_images.py --from ~/Downloads  # 先把下载目录里的图搬进来
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def load_ids(plan_path: Path) -> list[str]:
    if not plan_path.exists():
        raise SystemExit("找不到图像计划：%s（先跑一次 --prepare）" % plan_path)
    data = json.loads(plan_path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "image_plan_json" in data:
        inner = data["image_plan_json"]
        data = json.loads(inner) if isinstance(inner, str) else inner
    images = data.get("images") if isinstance(data, dict) and isinstance(data.get("images"), list) else []
    ids = [str(item.get("id")) for item in images
           if isinstance(item, dict) and str(item.get("id") or "").strip()
           and str(item.get("role") or "").lower() != "html"]
    if not ids:
        raise SystemExit("图像计划里没有 images：先跑一次 --prepare")
    return ids


def sort_key(item: Path, order: str):
    if order == "name":
        numbers = [int(part) for part in re.findall(r"\d+", item.stem)]
        return (0, numbers, item.name) if numbers else (1, [], item.name)
    return (0, [item.stat().st_mtime], item.name)


def main() -> None:
    parser = argparse.ArgumentParser(description="预览手动出图的图片怎么对号（不改文件名）")
    parser.add_argument("--plan", type=Path, default=Path("媒体/图片计划.json"))
    parser.add_argument("--dir", type=Path, default=Path("媒体/图片"))
    parser.add_argument("--from", dest="source", type=Path, default=None, help="先把这里的图片搬进图片目录（保持原名）")
    parser.add_argument("--move", action="store_true", help="配合 --from：搬移而不是复制")
    parser.add_argument("--order", choices=("mtime", "name"), default="mtime",
                        help="排序依据：mtime=修改时间从早到晚（默认），name=文件名里的数字")
    args = parser.parse_args()

    ids = load_ids(args.plan)
    args.dir.mkdir(parents=True, exist_ok=True)

    if args.source:
        if not args.source.exists():
            raise SystemExit("来源目录不存在：" + str(args.source))
        incoming = [item for item in args.source.iterdir()
                    if item.is_file() and item.suffix.lower() in EXTS]
        incoming.sort(key=lambda item: (item.stat().st_mtime, item.name))
        if not incoming:
            raise SystemExit("来源目录里没有图片：" + str(args.source))
        print("从 %s 搬入 %d 张（保持原名）" % (args.source, len(incoming)))
        for item in incoming:
            target = args.dir / item.name
            suffix = 1
            while target.exists():
                target = args.dir / ("%s_%d%s" % (item.stem, suffix, item.suffix))
                suffix += 1
            if args.move:
                shutil.move(str(item), str(target))
            else:
                shutil.copy2(str(item), str(target))

    files = [item for item in args.dir.iterdir()
             if item.is_file() and item.suffix.lower() in EXTS and not item.name.startswith("_")]
    by_id = {item.stem: item for item in files if item.stem in ids}
    unnamed = [item for item in files if item.stem not in ids]
    unnamed.sort(key=lambda item: sort_key(item, args.order))

    print("图片目录：%d 个文件 | 已按 id 命名 %d | 其余 %d | 计划共 %d 张" % (
        len(files), len(by_id), len(unnamed), len(ids)))

    mapping = {}
    cursor = 0
    for image_id in ids:
        if image_id in by_id:
            mapping[image_id] = by_id[image_id]
        elif cursor < len(unnamed):
            mapping[image_id] = unnamed[cursor]
            cursor += 1

    print("")
    print("对号（按修改时间从早到晚，文件名不动）：")
    for image_id in ids:
        item = mapping.get(image_id)
        print("  %-6s ← %s" % (image_id, item.name if item else "（还没放）"))

    extra = unnamed[len([i for i in ids if i not in by_id]):]
    if extra:
        print("")
        print("多出来的文件（不会用）：")
        for item in extra:
            print("  " + item.name)

    missing = [image_id for image_id in ids if image_id not in mapping]
    if missing:
        print("")
        print("还缺 %d 张：%s" % (len(missing), "、".join(missing)))
        return
    print("")
    print("齐了，可以出片。")


if __name__ == "__main__":
    main()
