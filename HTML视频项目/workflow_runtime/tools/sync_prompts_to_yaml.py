#!/usr/bin/env python3
"""把 `保留资料/工作流提示词/*.md` 同步进 Dify Workflow YAML。

提示词镜像和 YAML 里的 `text:` 必须逐字一致。手改 YAML 里的超长单行字符串容易
出错，所以以 md 为源：本脚本按节点映射把 md 全文写回 YAML，并校验 YAML 仍可解析。

用法：
    python3 sync_prompts_to_yaml.py --check     # 只报告差异
    python3 sync_prompts_to_yaml.py             # 写回
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

TOOLS_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = TOOLS_DIR.parent
WORKSPACE = RUNTIME_DIR.parent.parent
YAML_PATH = WORKSPACE / "Dify工作流" / "04_黑帧口播_分组生成.yml"
PROMPT_DIR = WORKSPACE / "保留资料" / "工作流提示词"

# node_id -> 提示词镜像文件
MAPPING = {
    "h01d": "视觉定调提示词.md",
    "h01p": "图像计划提示词.md",
    "h01c": "组件语法提示词.md",
    "h01t": "转场设计提示词.md",
    "h01g": "背景系统提示词.md",
    "h01s": "HTML骨架提示词.md",
    "h02a": "场景组A提示词.md",
    "h02b": "场景组B提示词.md",
    "h02c": "场景组C提示词.md",
    "h02d": "场景组D提示词.md",
    "h02m": "动效脚本提示词.md",
    "h02t": "转场脚本提示词.md",
}

# node_id -> Code 节点镜像文件（只覆盖与视觉链路相关的节点）
CODE_MAPPING = {
    "h00": "split_scene_groups_black_frame.py",
    "h01v": "normalize_transition_plan.py",
    "h01pv": "normalize_image_plan.py",
    "h01w": "split_background_spec.py",
    "h02": "validate_html_composition_black_frame.py",
    "h03": "merge_scene_groups_black_frame.py",
}
CODE_DIR = WORKSPACE / "保留资料" / "工作流代码节点"


def node_block_bounds(text: str, node_id: str) -> tuple[int, int] | None:
    start = text.find("\n    - id: %s\n" % node_id)
    if start < 0:
        return None
    start += 1
    following = text.find("\n    - id: ", start + 1)
    edges = text.find("\n    edges:", start + 1)
    candidates = [pos for pos in (following, edges) if pos > 0]
    end = min(candidates) if candidates else len(text)
    return start, end


def read_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    if not path.exists():
        raise SystemExit("找不到提示词镜像：" + str(path))
    return path.read_text(encoding="utf-8")


def read_code(name: str) -> str:
    path = CODE_DIR / name
    if not path.exists():
        raise SystemExit("找不到代码节点镜像：" + str(path))
    return path.read_text(encoding="utf-8")


def current_text(block: str) -> str | None:
    match = re.search(r'^          text: (".*")$', block, re.M)
    if not match:
        return None
    return json.loads(match.group(1))


def current_code(block: str) -> str | None:
    match = re.search(r'^        code: (".*")$', block, re.M)
    if not match:
        return None
    return json.loads(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只报告差异，不写回")
    parser.add_argument("--yaml", type=Path, default=YAML_PATH)
    args = parser.parse_args()

    document = args.yaml.read_text(encoding="utf-8")
    changed = []
    missing = []

    jobs = [(node_id, name, "prompt") for node_id, name in MAPPING.items()]
    jobs += [(node_id, name, "code") for node_id, name in CODE_MAPPING.items()]

    for node_id, asset_name, kind in jobs:
        bounds = node_block_bounds(document, node_id)
        if bounds is None:
            missing.append(node_id)
            continue
        start, end = bounds
        block = document[start:end]
        if kind == "prompt":
            wanted = read_prompt(asset_name)
            have = current_text(block)
            pattern = r'^          text: (".*")$'
            prefix = "          text: "
        else:
            wanted = read_code(asset_name)
            have = current_code(block)
            pattern = r'^        code: (".*")$'
            prefix = "        code: "
        if have == wanted:
            continue
        changed.append((node_id, asset_name, len(have or ""), len(wanted)))
        if args.check:
            continue
        scalar = json.dumps(wanted, ensure_ascii=False)
        new_block, count = re.subn(pattern, lambda _m, _p=prefix, _s=scalar: _p + _s, block, count=1, flags=re.M)
        if count != 1:
            raise SystemExit("节点 %s 的 %s 行没有唯一匹配，拒绝写回" % (node_id, kind))
        document = document[:start] + new_block + document[end:]

    if missing:
        print("YAML 里没有这些节点：" + "、".join(missing))
    if not changed:
        print("提示词镜像与 YAML 一致")
        return
    for node_id, prompt_name, old_len, new_len in changed:
        print("差异 %-5s %-22s %d → %d 字符" % (node_id, prompt_name, old_len, new_len))
    if args.check:
        print("共 %d 个节点不一致（--check 模式，未写回）" % len(changed))
        return

    try:
        parsed = yaml.safe_load(document)
    except Exception as exc:
        raise SystemExit("写回后 YAML 解析失败，已放弃：" + str(exc)) from exc
    nodes = parsed["workflow"]["graph"]["nodes"]
    print("YAML 解析通过，节点数 %d" % len(nodes))
    args.yaml.write_text(document, encoding="utf-8")
    print("已写回 " + str(args.yaml))


if __name__ == "__main__":
    main()
