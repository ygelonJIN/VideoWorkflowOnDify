import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { loadWorkflow } from "../src/engine/dsl.js";
import { VariablePool } from "../src/engine/vars.js";
import { executeNode } from "../src/engine/executors.js";
import { providerFromEnv } from "../src/engine/config.js";

import { WORKFLOW, INPUT, STUB_DIR, A01_STUB } from "./paths.js";
const STUB = A01_STUB;

describe("Code 节点", () => {
  it("a03 能把 a01 的 JSON 文本解析成 brief", async () => {
    // A02 在 2026-11-18 并进 A03，解析逻辑还在，节点 id 变了
    const workflow = loadWorkflow(WORKFLOW);
    const node = workflow.nodes.get("a03");
    assert.ok(node);

    const pool = new VariablePool({}, {});
    pool.setNodeOutputs("a01", { text: readFileSync(STUB, "utf8") });

    const result = await executeNode({ node, pool, provider: providerFromEnv({}) });
    const brief = JSON.parse(String(result.outputs["brief_json"])) as Record<string, unknown>;
    assert.ok(String(brief["topic"]).includes("纪念逝者"));
    assert.equal(brief["argument_count"], 3);
    assert.equal(result.outputs["validation_ok"], true);
    assert.ok(Number(result.outputs["target_duration_seconds"]) > 0);
    assert.ok(result.ms !== undefined && result.ms >= 0);
  });
});
