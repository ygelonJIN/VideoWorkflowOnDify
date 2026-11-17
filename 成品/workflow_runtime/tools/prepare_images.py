#!/usr/bin/env python3
"""数字人版（01）渲染前的图片准备：图像计划 → 生图 → 替换 {{IMG:id}}。

04 黑帧线由 `build_black_frame_project.py` 一起做完这三步；01 走的是
`render_new_project.sh`（有 HeyGen 响应、没有 TTS），原来那条路不碰图片，
于是 04 派生的 HTML 里的 `{{IMG:...}}` 会原样进渲染器。这里把它补齐：

1. 读 `媒体/图像计划.json`（Dify 输出里的 `image_plan_json`）；
2. 缺图就调 `scripts/generate_images.py` 生成到 `媒体/图片/`（有 Key 才调，没有就给出图清单）；
3. 把 `index.html` 里的 `{{IMG:id}}` 换成真实文件路径。

缺图不拦渲染：换不成的那张按约定文件名写进去并打印警告，先出片再补图。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(TOOLS_DIR))

from build_black_frame_project import (  # noqa: E402
    IMAGE_EXTS,
    placeholder_ids,
    replace_image_placeholders,
)


def load_plan(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit("图像计划不是合法 JSON：%s（%s）" % (path, exc)) from exc
    if not isinstance(data, dict):
        raise SystemExit("图像计划必须是 JSON 对象：" + str(path))
    return data


def wanted_ids(plan: dict) -> list[str]:
    items = plan.get("images") if isinstance(plan.get("images"), list) else []
    ids = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        image_id = str(item.get("id") or item.get("scene_id") or "").strip()
        if image_id and role != "html" and image_id not in ids:
            ids.append(image_id)
    return ids


def have_ids(image_dir: Path) -> set[str]:
    if not image_dir.exists():
        return set()
    return {
        item.stem for item in image_dir.iterdir()
        if item.is_file() and item.suffix.lower() in IMAGE_EXTS
        and not item.name.startswith("_") and item.stat().st_size > 10000
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="数字人版渲染前的图片准备")
    parser.add_argument("--html", type=Path, default=Path("index.html"))
    parser.add_argument("--plan", type=Path, default=Path("媒体/图像计划.json"))
    parser.add_argument("--skip-generate", action="store_true", help="只替换占位，不调生图接口（图已手动放好）")
    parser.add_argument("--only", default="", help="只生成这些 id，逗号分隔")
    args = parser.parse_args()

    if not args.html.exists():
        raise SystemExit("找不到 HTML：" + str(args.html))
    html = args.html.read_text(encoding="utf-8")
    refs = placeholder_ids(html)
    if not refs:
        print("HTML 里没有 {{IMG:...}} 占位，跳过图片准备")
        return
    if not args.plan.exists():
        raise SystemExit(
            "HTML 里有 %d 个图片占位，但没有图像计划：%s\n"
            "Dify 输出必须带 image_plan_json（H01P → H01PV），把项目里的 媒体/图像计划.json 补上再跑。"
            % (len(refs), args.plan)
        )

    plan = load_plan(args.plan)
    wanted = wanted_ids(plan)
    if not wanted:
        print("图像计划里没有需要照片的屏（全部 role=html），只替换占位")
    image_dir = Path("媒体/图片")
    missing = [image_id for image_id in wanted if image_id not in have_ids(image_dir)]

    if missing and not args.skip_generate:
        command = [
            sys.executable, str(RUNTIME_DIR / "scripts" / "generate_images.py"),
            "--plan", str(args.plan), "--out", str(image_dir),
        ]
        if args.only:
            command.extend(["--only", args.only])
        print("开始生成图像：缺 %d 张（%s）" % (len(missing), "、".join(missing[:8])))
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError:
            print("⚠️ 生图没有完成（多半缺 IMAGE_API_KEY / ARK_API_KEY）。可以手动出图：")
            print("   python3 %s --plan %s --sheet" % (RUNTIME_DIR / "scripts" / "generate_images.py", args.plan))
            print("   出完按 id 命名放回 媒体/图片/，然后加 --skip-generate 重跑本脚本或直接重渲染")

    still_missing = [image_id for image_id in wanted if image_id not in have_ids(image_dir)]
    html = replace_image_placeholders(
        html, Path.cwd(), refs, allow_missing=True, allow_unnamed=True,
    )
    args.html.write_text(html, encoding="utf-8")
    if still_missing:
        print("⚠️ 这些图片还缺，画面会缺图：" + "、".join(still_missing))
    else:
        print("图片准备完成：%d 张全部就位" % len(wanted))


if __name__ == "__main__":
    main()
