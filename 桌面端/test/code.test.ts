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
  it("a02 能把 a01 的 JSON 文本解析成四个字段", async () => {
    const workflow = loadWorkflow(WORKFLOW);
    const node = workflow.nodes.get("a02");
    assert.ok(node);

    const pool = new VariablePool({}, {});
    pool.setNodeOutputs("a01", { text: readFileSync(STUB, "utf8") });

    const result = await executeNode({ node, pool, provider: providerFromEnv({}) });
    const campaign = JSON.parse(String(result.outputs["campaign_json"])) as Record<string, unknown>;
    assert.ok(String(campaign["topic"]).includes("纪念逝者"));
    assert.equal(String(result.outputs["history_json"]), "{}");
    assert.ok(result.ms !== undefined && result.ms >= 0);
  });
});
