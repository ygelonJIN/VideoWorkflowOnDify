import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { loadWorkflow, startVariables } from "../src/engine/dsl.js";

import { WORKFLOW, INPUT, STUB_DIR, A01_STUB } from "./paths.js";

describe("DSL 读取", () => {
  it("能读 04 的节点、连线与版本", () => {
    const workflow = loadWorkflow(WORKFLOW);
    assert.equal(workflow.doc.version, "0.7.0");
    assert.equal(workflow.nodes.size, 49);
    assert.equal(workflow.edges.length, 51);
    assert.deepEqual(workflow.warnings, []);
  });

  it("节点类型分布与画布一致", () => {
    const workflow = loadWorkflow(WORKFLOW);
    const counts: Record<string, number> = {};
    for (const node of workflow.nodes.values()) counts[node.data.type] = (counts[node.data.type] ?? 0) + 1;
    assert.equal(counts["start"], 1);
    assert.equal(counts["llm"], 16);
    assert.equal(counts["code"], 20);
    assert.equal(counts["if-else"], 6);
    assert.equal(counts["iteration"], 1);
    assert.equal(counts["iteration-start"], 1);
    assert.equal(counts["template-transform"], 1);
    assert.equal(counts["end"], 3);
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
