#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""组件 / 动效的能力契约（唯一词汇表）。

组件卡写 `provides`：它对外暴露哪些可动锚点，值是「相对组件根的 CSS 选择器」。
动效卡写 `needs`（能力词 + 锚点）与 `target`：

    target = "root"       直接动组件根（sel 就是组件本身）
    target = "items"      sel = 组件根 + 锚点选择器，逐个动锚点元素（如柱、标签、节点）
    target = "container"  sel = 组件根，{{child}} / {{head}} 用锚点选择器在内部找

`needs` 里除锚点外还允许放 ui / text / block / img / media / photo / svg 这类粗能力词，
它们不参与锚点匹配，只作为卡片对环境的声明。

兼容矩阵是算出来的：动效 needs 里的每个锚点都必须在组件的 provides 里；items /
container 还要求选择器非空（root 型允许空串表示组件根自己）。
"""
from __future__ import annotations

ANCHORS = {
    "card", "row", "cell", "bar", "tag", "node", "path", "head",
    "line", "dot", "icon", "badge", "avatar", "pin", "field",
    "bubble", "screen", "num", "flow", "svg",
}

# 只作为环境声明的粗能力词，不是锚点。
CAPABILITY_ONLY = {"ui", "text", "block", "img", "media", "photo", "svg"}

TARGET_MODES = {"root", "items", "container"}


def anchors_of(card: dict) -> list[str]:
    return [str(n) for n in (card.get("needs") or []) if str(n) in ANCHORS]


def provides_of(component: dict) -> dict[str, str]:
    raw = component.get("provides")
    if not isinstance(raw, dict):
        return {}
    return {str(k): str(v) for k, v in raw.items() if str(k) in ANCHORS}


def target_mode(card: dict) -> str:
    mode = str(card.get("target") or "").strip().lower()
    return mode if mode in TARGET_MODES else "container"


def compatible(motion: dict, component: dict) -> bool:
    """这张组件动效能不能挂到这个组件上。"""
    needs = anchors_of(motion)
    if not needs:
        return False
    provides = provides_of(component)
    mode = target_mode(motion)
    for anchor in needs:
        if anchor not in provides:
            return False
        # items / container 要在组件内部找元素；空选择器说明这个锚点就是根，
        # 只允许 root 型卡片使用。
        if mode != "root" and not provides[anchor].strip():
            return False
    return True


def component_motions(cards: list[dict]) -> dict[str, list[str]]:
    """组件编号 → 可用组件动效编号（按 id 排序）。"""
    motions = [c for c in cards if c.get("role") == "component_motion" and c.get("status") == "ready"]
    out = {}
    for comp in cards:
        if comp.get("role") != "component":
            continue
        if not provides_of(comp):
            continue
        out[comp["id"]] = sorted(m["id"] for m in motions if compatible(m, comp))
    return out
