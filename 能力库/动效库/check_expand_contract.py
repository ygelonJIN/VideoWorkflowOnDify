#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""展开契约回归探针：在本地把 S2N → R1 跑一遍，验证"坏规格进不去 HTML"。

用法：
    python3 能力库/动效库/check_expand_contract.py

为什么要有：状态卡的落点规则（改写文字的卡只能落文字、触发卡必须配 then、
deco/out 的落点）写在 `gen_catalog.py` 派生的 `state_meta` 里，由 S2N 和 R1
各执行一次。这两处的判据不在任何一份静态文档里，改提示词或改 Code 节点时
很容易把它们改回原样——这个脚本就是那条回归线。

只报告，不写文件，不阻塞任何东西：把节点的 `main()` 取出来直接调，
断言"该丢的丢了、该留的留了"。

口径提醒：这里验证的是**结构**（卡落没落对目标、有没有结果），不评内容好不好。
"""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent.parent
YAML = REPO / "Dify工作流" / "04_黑帧口播_分组生成.yml"

sys.path.insert(0, str(HERE))
import yaml_nodes  # noqa: E402


def load_main(node_id: str):
    env: dict = {}
    exec(compile(yaml_nodes.get_code(node_id, YAML), node_id, "exec"), env)
    return env["main"]


PKG = {"storyboard": {"scenes": [
    {"scene_id": "s01", "voiceover_text": "第一屏口播",
     "estimated_start_seconds": 0, "estimated_end_seconds": 6},
]}}
BASE_COPY = [{"role": "title", "text": "天然制造贫富", "beat": "天然", "motion": {"preset": "T01"}}]
METRICS = {"id": "U54", "anim": "metrics",
           "texts": ["富豪", "财富集中", "中产", "并不稳定", "贫民", "被动下沉"],
           "motion": {"preset": "UA22"}}
ROWS = {"id": "U05", "anim": "rows", "texts": ["猎人", "多份", "不劳动者", "少份"],
        "motion": {"preset": "UA02"}}
CARDS = {"id": "U55", "anim": "cards",
         "texts": ["付出可量化", "获得有对应", "差别被承认", "货币被肯定"],
         "motion": {"preset": "UA37"}}


class Probe:
    def __init__(self) -> None:
        self.catalog = json.loads(load_main("h00")()["catalog_json"])
        self.catalog_json = json.dumps(self.catalog, ensure_ascii=False)
        self.s2n = load_main("s2n")
        self.r1 = load_main("h02sx")
        self.failed = 0

    # --- 走完整链路：规格 → S2N → R1 ---
    def via_spec(self, name: str, scene: dict, expect: list[tuple[str, bool]]) -> None:
        spec = {"scenes": [dict({"scene_id": "s01", "bg": "B36", "copy": BASE_COPY,
                                 "components": [], "transition": None}, **scene)]}
        s2 = self.s2n(json.dumps(spec, ensure_ascii=False), json.dumps(PKG, ensure_ascii=False),
                      self.catalog_json)
        out = self.r1(s2["specs_json"], self.catalog_json)
        self._check(name, out, expect, json.loads(s2["s2_warnings_json"]))

    # --- 多屏：测全片配额 ---
    def via_many(self, name: str, n: int, extra: dict, expect_warn: str) -> None:
        scenes = []
        for i in range(1, n + 1):
            scene = {"scene_id": "s%02d" % i, "bg": "B36",
                     "copy": BASE_COPY + [{"role": "body", "text": "钱把成果量化"}],
                     "components": [], "transition": None}
            scene.update(extra)
            scenes.append(scene)
        s2 = self.s2n(json.dumps({"scenes": scenes}, ensure_ascii=False),
                      json.dumps({"storyboard": {"scenes": [
                          {"scene_id": "s%02d" % i, "voiceover_text": "口播%d" % i,
                           "estimated_start_seconds": (i - 1) * 6,
                           "estimated_end_seconds": i * 6} for i in range(1, n + 1)]}},
                          ensure_ascii=False), self.catalog_json)
        warns = json.loads(s2["s2_warnings_json"])
        hit = any(expect_warn in w for w in warns)
        self.failed += 0 if hit else 1
        print("%s %s" % ("PASS" if hit else "FAIL", name))
        for line in warns:
            print("     s2:", line)

    # --- 绕开 S2N，直喂 R1（最后一道关也要挡得住）---
    def via_r1(self, name: str, motions: list, expect: list[tuple[str, bool]],
               components: list | None = None) -> None:
        specs = [{"scene_id": "s01", "bg": "B36", "visual": "html", "media": None,
                  "copy": [{"role": "title", "text": "天然制造贫富", "beat": "天然"}],
                  "components": components or [], "motions": motions, "transition": None}]
        self._check(name, self.r1(json.dumps(specs, ensure_ascii=False), self.catalog_json),
                    expect, [])

    def _check(self, name, out, expect, warnings) -> None:
        scripts = json.loads(out["scripts_json"])
        report = json.loads(out["motion_report_json"])
        body = scripts.get("s01") or ""
        bad = [(needle, want) for needle, want in expect if (needle in body) != want]
        ok = not bad
        self.failed += 0 if ok else 1
        print("%s %s" % ("PASS" if ok else "FAIL", name))
        print("     used=%s skipped=%s" % (report["used"].get("s01"), report["skipped"].get("s01")))
        for line in warnings:
            print("     s2:", line)
        for needle, want in bad:
            print("     → %r 应该%s，实际%s" % (needle, "出现" if want else "被丢弃",
                                                "出现" if needle in body else "被丢弃"))

    def run(self) -> int:
        # 1) 改写文字的状态卡落在组件根上：会把组件内容清空重写（s05 的 16px）
        self.via_spec("内容型状态卡落组件根 → 丢弃",
                      {"components": [METRICS],
                       "state": {"preset": "S24", "target": "metrics", "word": "富豪"}},
                      [("preset: S24", False), ("preset: UA22", True)])
        # 2) 触发卡没有 then：只有动作没有结果
        self.via_spec("触发卡缺 then → 丢弃",
                      {"components": [ROWS], "state": {"preset": "S04", "target": "rows", "word": "猎人"}},
                      [("preset: S04", False)])
        # 3) 触发卡 + then：两条都留，且落在同一目标
        self.via_spec("触发卡带 then → 保留两条",
                      {"components": [ROWS],
                       "state": {"preset": "S04", "target": "rows", "word": "猎人",
                                 "then": {"preset": "S07", "target": "rows", "word": "猎人"}}},
                      [("preset: S04", True), ("preset: S07", True)])
        # 4) then 落在别的目标上：结果不是这个动作的结果
        self.via_spec("then 换个目标 → 丢弃",
                      {"components": [ROWS, CARDS],
                       "state": {"preset": "S04", "target": "rows", "word": "猎人",
                                 "then": {"preset": "S07", "target": "cards", "word": "猎人"}}},
                      [("preset: S04", False)])
        # 5) deco：标注不许落在标题上（标题已经最大，再标就是糊住它）
        self.via_spec("deco 落标题 → 丢弃",
                      {"components": [], "deco": {"preset": "K45", "target": "title"}},
                      [("preset: K45", False)])
        self.via_spec("deco 落正文 → 保留",
                      {"components": [],
                       "copy": BASE_COPY + [{"role": "body", "text": "钱把成果量化"}],
                       "deco": {"preset": "K48", "target": "body"}},
                      [("preset: K48", True)])
        # 6) 比例条要真实数字（S02/S18 的 avoid）
        self.via_spec("比例条落在没有数字的屏 → 丢弃",
                      {"components": [ROWS], "state": {"preset": "S18", "target": "rows", "word": "猎人"}},
                      [("preset: S18", False)])
        self.via_spec("比例条落在有数字的屏 → 保留",
                      {"components": [{"id": "U05", "anim": "rows",
                                       "texts": ["猎人", "3份", "不劳动者", "0份"],
                                       "motion": {"preset": "UA02"}}],
                       "state": {"preset": "S18", "target": "rows", "word": "猎人"}},
                      [("preset: S18", True)])
        # 6) out：离场卡固定在切点前，不占内容槽位
        self.via_spec("out 落组件 → 保留且按切点定位",
                      {"components": [CARDS], "out": {"preset": "X03", "target": "cards"}},
                      [("preset: X03", True), ("__cueWindows", True)])
        # 7) out 不许动标题
        self.via_spec("out 落标题 → 丢弃",
                      {"components": [], "out": {"preset": "X03", "target": "title"}},
                      [("preset: X03", False)])
        # 8) 老路径回归：普通入场 + 锚点状态卡
        self.via_spec("回归：入场 + 锚点状态卡",
                      {"components": [METRICS],
                       "state": {"preset": "S36", "target": "metrics", "word": "富豪"}},
                      [("preset: T01", True), ("preset: UA22", True), ("preset: S36", True)])
        # 9–11) R1 直喂：S2N 被绕开时，最后一道关仍然有效
        self.via_r1("R1 直喂：内容卡落组件根 → 丢弃",
                    [{"preset": "S24", "target": "comp-1", "role": "state"}],
                    [("preset: S24", False)])
        self.via_r1("R1 直喂：触发卡没有结果 → 丢弃",
                    [{"preset": "S04", "target": "rows", "role": "state"}],
                    [("preset: S04", False)], components=[ROWS])
        self.via_r1("R1 直喂：deco 只落文字的卡落在组件上 → 丢弃",
                    [{"preset": "K45", "target": "comp-1", "role": "deco"}],
                    [("preset: K45", False)])
        # 12) 全片配额：deco 超过 ⌈屏数÷3⌉ 要点名
        self.via_many("deco 超配额 → 点名", 3, {"deco": {"preset": "K48", "target": "body"}}, "上限")
        print()
        if self.failed:
            print("展开契约回归：%d 条不过（判据在 gen_catalog.state_meta 与 S2N/R1）" % self.failed)
            return 1
        print("展开契约回归：全过。")
        return 0


if __name__ == "__main__":
    sys.exit(Probe().run())
