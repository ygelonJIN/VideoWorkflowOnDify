#!/usr/bin/env python3
"""把图像计划（image_plan）渲染成真实图片：GPT Image API。

计划来自 Dify 的 H01P 节点，落到项目 `媒体/图片计划.json`。本脚本只做执行：
读计划 → 逐张调用 `/v1/images/generations` → 写 `媒体/图片/<id>.png` → 记录哈希做缓存。

用法：
    python3 generate_images.py --plan 媒体/图片计划.json --out 媒体/图片
    python3 generate_images.py --plan 媒体/图片计划.json --only s01 --force
    python3 generate_images.py --plan 媒体/图片计划.json --dry-run     # 出占位图，跑通链路

环境变量：
    IMAGE_API_KEY / OPENAI_API_KEY   必填（dry-run 不需要）
    IMAGE_API_BASE                   默认 https://api.openai.com/v1
    IMAGE_MODEL                      默认 gpt-image-1
    IMAGE_SIZE                       默认 1024x1536
    IMAGE_QUALITY                    默认 medium
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DEFAULT_BASE = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-1"
DEFAULT_SIZE = "1024x1536"
DEFAULT_QUALITY = "medium"
SUPPORTED_SIZES = {"1024x1024", "1536x1024", "1024x1536", "1080x1920", "auto"}

# 火山方舟（即梦同源 Seedream 模型）：Base 必须带 /api/v3
VOLC_BASE = "https://ark.cn-beijing.volces.com/api/v3"
VOLC_MODEL = "doubao-seedream-4-0-250828"
# Seedream 3.0 只认固定尺寸；把 OpenAI 那套尺寸映射过去，4.0 也能接受这些值
VOLC_SIZE_MAP = {
    "1024x1536": "832x1248",
    "1536x1024": "1248x832",
    "1024x1024": "1024x1024",
    "1080x1920": "720x1280",
    "auto": "1024x1024",
}


def detect_provider(base_url: str) -> str:
    lowered = (base_url or "").lower()
    if "volces.com" in lowered or "ark.cn" in lowered or "volcengine" in lowered:
        return "volcengine"
    return "openai"


def provider_defaults(provider: str) -> tuple[str, str]:
    if provider == "volcengine":
        return VOLC_BASE, VOLC_MODEL
    return DEFAULT_BASE, DEFAULT_MODEL


def map_size(size: str, provider: str) -> str:
    if provider != "volcengine":
        return size
    return VOLC_SIZE_MAP.get(size, size)
PRINT_LOCK = threading.Lock()


def log(message: str) -> None:
    with PRINT_LOCK:
        print(message, flush=True)


def env(name: str, fallback: str = "") -> str:
    return str(os.environ.get(name, fallback)).strip()


def resolve_key() -> str:
    key = env("IMAGE_API_KEY") or env("OPENAI_API_KEY") or env("ARK_API_KEY")
    if key:
        return key
    key_file = env("IMAGE_API_KEY_FILE")
    if key_file and Path(key_file).exists():
        return Path(key_file).read_text(encoding="utf-8").strip()
    return ""


def load_plan(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise SystemExit(f"图像计划不是合法 JSON：{exc}") from exc
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception as exc:
            raise SystemExit(f"图像计划是字符串但不是合法 JSON：{exc}") from exc
    if isinstance(data, dict) and "image_plan_json" in data:
        inner = data["image_plan_json"]
        data = json.loads(inner) if isinstance(inner, str) else inner
    if not isinstance(data, dict):
        raise SystemExit("图像计划必须是 JSON 对象")
    return data


def style_prefix(plan: dict) -> str:
    explicit = str(plan.get("prompt_prefix") or "").strip()
    if explicit:
        return explicit
    bible = plan.get("style_bible")
    if not isinstance(bible, dict):
        return ""
    parts = []
    for key in ("medium", "look", "lighting", "composition", "palette"):
        value = bible.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())
    rules = bible.get("consistency_rules")
    if isinstance(rules, list):
        parts.extend(str(item).strip() for item in rules if str(item).strip())
    return "\n".join(parts)


def normalize_items(plan: dict) -> list[dict]:
    raw = plan.get("images") or plan.get("items") or []
    if not isinstance(raw, list):
        return []
    items = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        image_id = str(item.get("id") or item.get("scene_id") or "").strip()
        if not image_id:
            image_id = "img%02d" % (index + 1)
        image_id = re.sub(r"[^A-Za-z0-9_-]", "", image_id) or "img%02d" % (index + 1)
        subject = str(item.get("subject") or "").strip()
        prompt = str(item.get("prompt") or "").strip()
        if not prompt:
            prompt = subject
        entry = {
            "id": image_id,
            "scene_id": str(item.get("scene_id") or image_id).strip(),
            "role": str(item.get("role") or "full").strip(),
            "subject": subject,
            "prompt": prompt,
            "prompt_zh": str(item.get("prompt_zh") or "").strip(),
            "negative": str(item.get("negative") or "").strip(),
            "size": str(item.get("size") or item.get("aspect") or "").strip(),
            "quality": str(item.get("quality") or "").strip(),
            "text_safe_zone": str(item.get("text_safe_zone") or "").strip(),
            "motion_hint": str(item.get("motion_hint") or "").strip(),
        }
        items.append(entry)
    return items


def build_prompt(item: dict, prefix: str) -> str:
    chunks = []
    if prefix:
        chunks.append(prefix)
    chunks.append(item["prompt"])
    if item.get("text_safe_zone"):
        chunks.append("Composition: keep the " + item["text_safe_zone"] + " side visually calm and uncluttered for overlaid type.")
    chunks.append(
        "No text, no letters, no numbers, no logos, no watermarks, no UI chrome, no collage, no illustration, no cartoon. "
        "Photographic, single coherent frame, natural depth of field, film grain."
    )
    if item.get("negative"):
        chunks.append("Avoid: " + item["negative"])
    return "\n\n".join(chunks)


def cache_hash(item: dict, model: str, size: str, quality: str, prompt: str) -> str:
    payload = json.dumps({
        "prompt": prompt, "model": model, "size": size, "quality": quality,
    }, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def decode_image(payload: dict) -> bytes:
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RuntimeError("响应缺少 data 数组")
    first = data[0]
    b64 = first.get("b64_json")
    if b64:
        return base64.b64decode(b64)
    url = first.get("url")
    if url:
        with urllib.request.urlopen(url, timeout=120) as response:
            return response.read()
    raise RuntimeError("响应既没有 b64_json 也没有 url")


def call_api(prompt: str, model: str, size: str, quality: str, base_url: str, api_key: str) -> bytes:
    provider = detect_provider(base_url)
    endpoint = base_url.rstrip("/") + "/images/generations"
    if provider == "volcengine":
        # 火山方舟：默认返回 url；watermark 必须关，否则图上有"AI生成"水印
        body = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "response_format": "url",
            "watermark": False,
        }
    else:
        body = {"model": model, "prompt": prompt, "n": 1, "size": size}
        if "gpt-image" in model.lower():
            body["quality"] = quality
            body["output_format"] = "png"
        else:
            # dall-e 系列不认 output_format，quality 只有 standard/hd
            body["quality"] = "hd" if quality == "high" else "standard"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return decode_image(payload)


def placeholder_png(path: Path, image_id: str, size: str) -> None:
    from PIL import Image, ImageDraw

    width, height = (int(part) for part in size.split("x")) if re.fullmatch(r"\d+x\d+", size) else (1024, 1536)
    image = Image.new("RGB", (width, height), (18, 20, 26))
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        draw.line([(0, y), (width, y)], fill=(int(18 + 40 * ratio), int(20 + 34 * ratio), int(26 + 30 * ratio)))
    box_w, box_h = int(width * 0.62), int(height * 0.2)
    left, top = (width - box_w) // 2, (height - box_h) // 2
    draw.rectangle([left, top, left + box_w, top + box_h], outline=(120, 132, 150), width=3)
    draw.text((left + 24, top + 20), "PLACEHOLDER", fill=(190, 200, 214))
    draw.text((left + 24, top + 52), image_id, fill=(150, 160, 176))
    draw.text((left + 24, top + 84), size, fill=(110, 120, 136))
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


ZONE_ZH = {"top": "上", "bottom": "下", "left": "左", "right": "右", "center": "中"}


def zh_prompt(item: dict, prefix: str = "") -> str:
    """中文提示词：模型给的正文 + 统一的中文约束，手动出图直接整段复制。"""
    zone = ZONE_ZH.get(str(item.get("text_safe_zone") or ""), "")
    tail = "画面里不要出现文字、字母、数字、logo、水印、界面元素；不要可识别的真人正脸；单一光源、真实摄影质感。"
    if zone:
        tail += "构图给%s侧留出干净的空白，后期要压文字。" % zone
    base = str(item.get("prompt_zh") or "").strip()
    if base:
        return (base + "\n\n" + tail).strip()
    # 没有中文版时不要把一句 subject 当提示词：直接给英文全文，那才是能出图的东西
    return "（本张没有中文版，直接复制下面这段英文）\n" + build_prompt(item, prefix) + "\n\n" + tail


def write_sheet(plan: dict, items: list[dict], out_path: Path, project: str) -> Path:
    """生成给人用的出图清单：每张图一条 prompt，点一下全选，粘进即梦即可。"""
    import html as html_lib

    prefix = style_prefix(plan)
    cards = []
    for item in items:
        english = build_prompt(item, prefix)
        cards.append(
            '<section class="card">'
            '<div class="head"><b>%s</b><span>%s · 文字留白 %s · 镜头 %s</span></div>'
            '<p class="sub">%s</p>'
            '<textarea readonly onclick="this.focus();this.select()">%s</textarea>'
            '<details><summary>英文提示词（可选）</summary>'
            '<textarea readonly onclick="this.focus();this.select()">%s</textarea></details>'
            '<div class="foot">保存为 <code>%s.png</code></div>'
            '</section>' % (
                html_lib.escape(item["id"]), html_lib.escape(item["role"]),
                html_lib.escape(item["text_safe_zone"]), html_lib.escape(item["motion_hint"]),
                html_lib.escape(item["subject"] or ""),
                html_lib.escape(zh_prompt(item, prefix)), html_lib.escape(english), html_lib.escape(item["id"]),
            )
        )
    page = """<!doctype html>
<html lang="zh"><meta charset="utf-8">
<title>出图清单 - %s</title>
<style>
:root{color-scheme:dark}
body{margin:0;padding:32px;background:#11141a;color:#e6e8ee;font:14px/1.6 -apple-system,"PingFang SC",sans-serif}
h1{font-size:20px;margin:0 0 6px}
.tip{color:#9aa3b2;margin:0 0 24px}
.card{background:#181c24;border:1px solid #262c38;border-radius:10px;padding:16px;margin-bottom:14px}
.head{display:flex;gap:10px;align-items:baseline}
.head b{font-size:15px;color:#7dd3fc}
.head span{color:#9aa3b2;font-size:12px}
.sub{margin:6px 0 10px;color:#c8cedb}
textarea{width:100%%;min-height:110px;box-sizing:border-box;background:#0d1015;color:#d6dae3;border:1px solid #2a313d;border-radius:8px;padding:10px;font:12px/1.55 ui-monospace,Menlo,monospace;resize:vertical}
textarea:focus{outline:1px solid #3b82f6}
.foot{margin-top:8px;color:#8b93a3;font-size:12px}
code{background:#0d1015;padding:1px 5px;border-radius:4px;color:#a5b4fc}
</style>
<h1>出图清单 · %s</h1>
<p class="tip">点一下文本框全选 → 复制 → 粘进即梦 → 出图 → 下载后按下面的文件名保存进 <code>媒体/图片/</code>。全部放好后构建时加 <code>--skip-images</code>。</p>
%s
</html>""" % (html_lib.escape(project), html_lib.escape(project), "\n".join(cards))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


def write_prompt_pack(plan: dict, items: list[dict], out_dir: Path, project: str) -> Path:
    """每张图一份 txt，另附 README：复制哪段、存成什么名字、放哪。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = style_prefix(plan)
    rows = []
    for item in items:
        english = build_prompt(item, prefix)
        body = [
            "【%s】%s · 文字留白 %s · 镜头 %s" % (
                item["id"], item["role"], item["text_safe_zone"], item["motion_hint"]),
            "",
            "这张画什么：" + (item.get("subject") or "（未写）"),
            "",
            "—— 中文提示词（复制这一段）——",
            zh_prompt(item, prefix),
            "",
            "—— 英文提示词（可选，模型更吃英文）——",
            english,
            "",
            "出图后保存为：%s.png" % item["id"],
            "放进：媒体/图片/",
        ]
        (out_dir / (item["id"] + ".txt")).write_text("\n".join(body) + "\n", encoding="utf-8")
        rows.append("  %-6s →  %s.png" % (item["id"] + ".txt", item["id"]))

    targets = "\n".join("  媒体/图片/%s.png" % item["id"] for item in items)
    pairs = "\n".join(rows)
    readme = """手动出图包 · %s
共 %d 张

一、怎么出图
  1. 打开即梦（或任何文生图工具），比例选 9:16，其次 2:3。
  2. 打开本目录里的 s01.txt、s02.txt…，复制「中文提示词」那一段粘进去。
  3. 每张出图后下载，重命名成 <id>.png。

二、放哪
  全部放进项目的  媒体/图片/ ：

%s

三、齐了之后
  回到项目根目录，跑构建并跳过生图：

  python3 tools/build_black_frame_project.py 项目名 --input-file ../../Dify输出/xxx.json --skip-images

  缺哪张会直接点名；文件名不对也会报出来。

四、注意
  - 文件名必须是 id 本身（s01、s02…），不要加后缀说明。
  - 支持 .png / .jpg / .jpeg / .webp。
  - 尺寸 1080x1920 最好，832x1248（2:3）也可以，渲染时按 9:16 裁左右。
  - 画面里不要有文字，文字由 HTML 叠上去。

文件对照：
%s
""" % (project, len(items), targets, pairs)
    readme_path = out_dir / "README.txt"
    readme_path.write_text(readme, encoding="utf-8")

    # 合集：所有提示词放一个文件，分隔线切开，整份复制也不会混
    blocks = [
        "%s · 全部图片提示词" % project,
        "共 %d 张，按顺序对应 %s" % (len(items), "、".join(item["id"] + ".png" for item in items)),
        "",
    ]
    for item in items:
        blocks.append("═" * 46)
        blocks.append("%s ｜ %s · 文字留白 %s · 镜头 %s" % (
            item["id"], item["role"], item["text_safe_zone"], item["motion_hint"]))
        blocks.append("═" * 46)
        blocks.append(zh_prompt(item, prefix))
        blocks.append("")
    (out_dir / "全部提示词.txt").write_text("\n".join(blocks), encoding="utf-8")
    return readme_path


def verify_image(path: Path, expected_size: str) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size
    if width < 512 or height < 512:
        raise RuntimeError(f"图片尺寸异常：{width}x{height}")
    return width, height


def main() -> None:
    parser = argparse.ArgumentParser(description="用 GPT Image API 把图像计划渲染成真实图片")
    parser.add_argument("--plan", type=Path, required=True, help="图像计划 JSON")
    parser.add_argument("--out", type=Path, default=Path("媒体/图片"))
    parser.add_argument("--only", default="", help="只生成这些 id，逗号分隔")
    parser.add_argument("--skip", default="", help="跳过这些 id，逗号分隔")
    parser.add_argument("--force", action="store_true", help="忽略缓存，重新生成")
    parser.add_argument("--dry-run", action="store_true", help="生成占位图，不调用 API")
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--model", default=None, help="留空按 Base 地址自动选（OpenAI: gpt-image-1 / 火山方舟: doubao-seedream-4-0）")
    parser.add_argument("--size", default=None)
    parser.add_argument("--quality", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--list", action="store_true", help="只列出计划里的 id")
    parser.add_argument("--sheet", nargs="?", const="__default__", default=None,
                        help="生成给人用的出图清单 HTML（手动出图时用），可选路径")
    args = parser.parse_args()

    base_url = args.base_url or env("IMAGE_API_BASE", "")
    provider = detect_provider(base_url) if base_url else "openai"
    default_base, default_model = provider_defaults(provider)
    base_url = base_url or default_base
    model = args.model or env("IMAGE_MODEL", "") or default_model
    size_override = args.size or env("IMAGE_SIZE", "") or DEFAULT_SIZE
    quality = args.quality or env("IMAGE_QUALITY", "") or DEFAULT_QUALITY

    plan = load_plan(args.plan)
    items = normalize_items(plan)
    if not items:
        raise SystemExit("图像计划里没有 images")

    if args.list:
        for item in items:
            print(item["id"], item["role"], len(item["prompt"]))
        return

    if args.sheet:
        default_path = Path("媒体/出图清单.html")
        target = default_path if args.sheet == "__default__" else Path(args.sheet)
        written = write_sheet(plan, items, target, Path.cwd().name)
        pack_dir = Path("媒体/出图")
        readme = write_prompt_pack(plan, items, pack_dir, Path.cwd().name)
        print("出图清单：" + str(written.resolve()))
        print("提示词包：" + str(pack_dir.resolve()) + "（%d 份 txt + README.txt）" % len(items))
        print("复制中文提示词出图，按 id 命名放回 媒体/图片/，然后 --skip-images 构建")
        return

    only = {part.strip() for part in args.only.split(",") if part.strip()}
    skip = {part.strip() for part in args.skip.split(",") if part.strip()}
    if only:
        items = [item for item in items if item["id"] in only]
    if skip:
        items = [item for item in items if item["id"] not in skip]
    if not items:
        print("没有需要生成的图片")
        return

    missing_prompt = [item["id"] for item in items if not item["prompt"]]
    if missing_prompt:
        raise SystemExit("这些图片没有 prompt：" + "、".join(missing_prompt))

    args.out.mkdir(parents=True, exist_ok=True)
    record_path = args.out / "_生成记录.json"
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            record = {}
    except Exception:
        record = {}

    api_key = resolve_key()
    if not args.dry_run and not api_key:
        raise SystemExit("缺少 IMAGE_API_KEY / OPENAI_API_KEY：设置环境变量后重跑，或加 --dry-run 只出占位图")
    if not args.dry_run and not re.fullmatch(r"\d+x\d+", size_override):
        raise SystemExit("IMAGE_SIZE 必须形如 1024x1536")
    if not args.dry_run and size_override not in SUPPORTED_SIZES:
        log("提示：%s 不在常见尺寸列表 %s 内，按原样发送" % (size_override, sorted(SUPPORTED_SIZES)))

    prefix = style_prefix(plan)
    log("image_plan: %d 张 | provider=%s model=%s size=%s%s" % (
        len(items), provider, model, size_override, " | DRY-RUN" if args.dry_run else "",
    ))
    if provider == "volcengine":
        log("火山方舟模式：尺寸会映射到 Seedream 可接受的值（%s → %s），watermark 已关闭" % (
            size_override, map_size(size_override, provider)))

    failures: list[str] = []
    done: list[str] = []
    reused: list[str] = []

    def work(item: dict) -> tuple[str, str]:
        image_id = item["id"]
        raw_size = item["size"] if re.fullmatch(r"\d+x\d+", item.get("size") or "") else size_override
        size = map_size(raw_size, provider)
        item_quality = item.get("quality") or quality
        prompt = build_prompt(item, prefix)
        digest = cache_hash(item, model, size, item_quality, prompt)
        target = args.out / (image_id + ".png")
        previous = record.get(image_id) if isinstance(record.get(image_id), dict) else {}
        if target.exists() and not args.force and previous.get("hash") == digest and target.stat().st_size > 20000:
            return image_id, "reuse"
        if args.dry_run:
            placeholder_png(target, image_id, size)
            record[image_id] = {
                "hash": digest, "file": target.name, "model": "placeholder",
                "size": size, "quality": item_quality, "prompt": item["prompt"][:400],
                "role": item["role"], "scene_id": item["scene_id"],
                "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            return image_id, "placeholder"
        last_error = ""
        for attempt in range(args.retries + 1):
            try:
                data = call_api(prompt, model, size, item_quality, base_url, api_key)
                if len(data) < 20000:
                    raise RuntimeError("返回图片过小（%d bytes）" % len(data))
                target.write_bytes(data)
                width, height = verify_image(target, size)
                record[image_id] = {
                    "hash": digest, "file": target.name, "model": model,
                    "size": "%dx%d" % (width, height), "quality": item_quality,
                    "prompt": item["prompt"][:400], "role": item["role"],
                    "scene_id": item["scene_id"], "bytes": target.stat().st_size,
                    "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
                }
                return image_id, "ok:%dx%d" % (width, height)
            except urllib.error.HTTPError as exc:
                detail = ""
                try:
                    detail = exc.read().decode("utf-8", "ignore")[:300]
                except Exception:
                    pass
                last_error = "HTTP %s %s" % (exc.code, detail)
                if exc.code in (400, 401, 403):
                    raise RuntimeError(last_error) from exc
                time.sleep(3 + attempt * 5)
            except Exception as exc:  # noqa: BLE001
                last_error = "%s: %s" % (type(exc).__name__, exc)
                time.sleep(3 + attempt * 5)
        raise RuntimeError(last_error or "未知错误")

    started = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        futures = {pool.submit(work, item): item["id"] for item in items}
        for future in as_completed(futures):
            image_id = futures[future]
            try:
                _, status = future.result()
            except Exception as exc:  # noqa: BLE001
                failures.append(image_id)
                log("image %s FAIL %s" % (image_id, exc))
                continue
            if status == "reuse":
                reused.append(image_id)
                log("image %s reuse" % image_id)
            else:
                done.append(image_id)
                log("image %s %s" % (image_id, status))

    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log("完成：生成 %d、复用 %d、失败 %d，用时 %.1fs" % (len(done), len(reused), len(failures), time.time() - started))
    if failures:
        log("失败清单：" + "、".join(sorted(failures)))
        log("修法：单独重跑 --only " + ",".join(sorted(failures)))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
