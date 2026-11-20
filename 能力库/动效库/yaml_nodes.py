#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""读写 04 YAML 里某个节点的 code / prompt_template，不动 YAML 的其它部分。

Dify 的 YAML 把节点代码整段塞进一个 JSON 字符串里，直接 dump 会把缩进、顺序、
注释全部打乱。这里只做一件事：把旧代码按 JSON 转义后在原文里定位，替换成新的。
定位不到或命中多处就报错，不猜。
"""
from __future__ import annotations

import json
import pathlib
import re

REPO = pathlib.Path(__file__).resolve().parent.parent.parent
YAML = REPO / "Dify工作流" / "04_黑帧口播_分组生成.yml"


def read_yaml_text(path=None) -> str:
    path = path or YAML
    return path.read_text(encoding="utf-8")


def write_yaml_text(text: str, path=None) -> None:
    path = path or YAML
    import yaml as _yaml
    _yaml.safe_load(text)          # 写之前先确认整份 YAML 还能解析
    path.write_text(text, encoding="utf-8")


def _node(data: dict, node_id: str) -> dict:
    for node in data["workflow"]["graph"]["nodes"]:
        if node["id"] == node_id:
            return node
    raise SystemExit("找不到节点 " + node_id)


def load_node(node_id: str, path=None) -> dict:
    import yaml as _yaml
    data = _yaml.safe_load(read_yaml_text(path))
    return _node(data, node_id)


def get_code(node_id: str, path=None) -> str:
    return load_node(node_id, path)["data"]["code"]


def get_prompt_text(node_id: str, path=None) -> str:
    """prompt_template 是 [{role, text}]；只改 role=system 那一条的 text。"""
    parts = load_node(node_id, path)["data"]["prompt_template"]
    for part in parts:
        if part.get("role") == "system":
            return part["text"]
    raise SystemExit(node_id + " 没有 system 提示词")


def _replace_once(raw: str, old: str, new: str, what: str, node_id: str = "") -> str:
    """替换目标节点的代码/提示词。

    同一段代码可能在多个节点里一字不差（A07 与 A07R 就是），所以命中多处时按
    "这段文本前面最近的 `id: <node_id>`" 定位到目标节点，不猜第一个。
    """
    esc_old = json.dumps(old, ensure_ascii=False)[1:-1]
    esc_new = json.dumps(new, ensure_ascii=False)[1:-1]
    starts = [i for i in range(len(raw)) if raw.startswith(esc_old, i)]
    if not starts:
        raise SystemExit("%s 定位失败（命中 0 处），未写入" % what)
    if len(starts) == 1:
        return raw[:starts[0]] + esc_new + raw[starts[0] + len(esc_old):]
    if not node_id:
        raise SystemExit("%s 命中 %d 处且没有节点 id，未写入" % (what, len(starts)))
    for start in starts:
        head = raw[max(0, start - 8000):start]
        found = re.findall(r"\bid:\s*([\w-]+)\s*\n", head)
        if found and found[-1] == node_id:
            return raw[:start] + esc_new + raw[start + len(esc_old):]
    raise SystemExit("%s 命中 %d 处，但没有一处属于节点 %s" % (what, len(starts), node_id))


def _roundtrip_set(path, node_id: str, key: str, value: str) -> None:
    """文本定位失败时的兜底写入：整份 YAML 读入、改字段、再 dump。

    2026-11-20 之后两份 YAML 由 yaml.safe_dump 生成，长字符串的转义方式不再
    和 Dify 导出的一致，`_replace_once` 会定位不到；这条路径保证生成器还能写。
    """
    import yaml as _yaml
    data = _yaml.safe_load(read_yaml_text(path))
    node = _node(data, node_id)
    if key == "code":
        node["data"]["code"] = value
    else:
        for part in node["data"]["prompt_template"]:
            if part.get("role") == "system":
                part["text"] = value
                break
    write_yaml_text(_yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100000), path)


def set_code(node_id: str, new_code: str, path=None) -> None:
    raw = read_yaml_text(path)
    old = get_code(node_id, path)
    if old == new_code:
        return
    compile(new_code, node_id, "exec")
    try:
        write_yaml_text(_replace_once(raw, old, new_code, node_id + " 的代码", node_id), path)
    except SystemExit:
        _roundtrip_set(path, node_id, "code", new_code)


def set_prompt_text(node_id: str, new_text: str, path=None) -> None:
    raw = read_yaml_text(path)
    old = get_prompt_text(node_id, path)
    if old == new_text:
        return
    try:
        write_yaml_text(_replace_once(raw, old, new_text, node_id + " 的提示词", node_id), path)
    except SystemExit:
        _roundtrip_set(path, node_id, "prompt", new_text)
