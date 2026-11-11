import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parse } from "yaml";
import { loadWorkflow, startVariables } from "../src/engine/dsl.js";

import { WORKFLOW } from "./paths.js";

interface RawGraph {
  workflow: {
    graph: {
      nodes: Array<{ id: string; data: { type: string } }>;
      edges: Array<{ source: string; target: string }>;
    };
  };
}

/** 节点/连线数量以 YAML 本身为准：以前写死 49/51，04 一加节点测试就整片红。 */
function rawGraph(): RawGraph["workflow"]["graph"] {
  return (parse(readFileSync(WORKFLOW, "utf8")) as RawGraph).workflow.graph;
}

describe("DSL 读取", () => {
  it("读出的节点、连线与 YAML 完全一致", () => {
    const raw = rawGraph();
    const workflow = loadWorkflow(WORKFLOW);
    assert.equal(workflow.doc.version, "0.7.0");
    assert.equal(workflow.nodes.size, raw.nodes.length);
    assert.equal(workflow.edges.length, raw.edges.length);
    assert.deepEqual([...workflow.nodes.keys()].sort(), raw.nodes.map((node) => node.id).sort());
    for (const edge of workflow.edges) {
      assert.ok(workflow.nodes.has(edge.source), `连线起点不存在：${edge.source}`);
      assert.ok(workflow.nodes.has(edge.target), `连线终点不存在：${edge.target}`);
    }
    assert.deepEqual(workflow.warnings, []);
  });

  it("节点类型分布与 YAML 一致", () => {
    const raw = rawGraph();
    const expected: Record<string, number> = {};
    for (const node of raw.nodes) expected[node.data.type] = (expected[node.data.type] ?? 0) + 1;

    const workflow = loadWorkflow(WORKFLOW);
    const counts: Record<string, number> = {};
    for (const node of workflow.nodes.values()) counts[node.data.type] = (counts[node.data.type] ?? 0) + 1;
    assert.deepEqual(counts, expected);

    // 关键节点按 id 定位，04 增删其它节点时不会误伤
    assert.equal(workflow.nodes.get("a00")?.data.type, "start");
    assert.equal(workflow.nodes.get("h00")?.data.type, "code");
    assert.equal(workflow.nodes.get("h02i")?.data.type, "iteration");
    assert.equal(workflow.nodes.get("h02s")?.data.type, "llm");
    assert.equal(workflow.nodes.get("h02sk")?.data.type, "code");
  });

  it("start 节点声明了必填输入", () => {
    const workflow = loadWorkflow(WORKFLOW);
    const start = [...workflow.nodes.values()].find((node) => node.data.type === "start");
    assert.ok(start);
    const variables = startVariables(start);
    assert.deepEqual(variables.filter((item) => item.required).map((item) => item.variable), ["campaign_brief", "request_id"]);
    assert.ok(variables.find((item) => item.variable === "tts_voice")?.options?.includes("mimo_default"));
  });
});
