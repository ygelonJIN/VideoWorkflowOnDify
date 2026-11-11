import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { providerFromEnv } from "../src/engine/config.js";
import { fileStubSource, runWorkflowFile } from "../src/engine/run.js";
import { loadWorkflow } from "../src/engine/dsl.js";
import { VariablePool } from "../src/engine/vars.js";
import { executeNode, NodeNotImplementedError } from "../src/engine/executors.js";

import { WORKFLOW, INPUT, STUB_DIR, A01_STUB } from "./paths.js";

describe("端到端（stub 模型）", () => {
  it("a00 → a01 → a02 → a03 跑通，并产出 brief", async () => {
    const inputs = JSON.parse(readFileSync(INPUT, "utf8")) as Record<string, unknown>;
    const result = await runWorkflowFile({
      workflowPath: WORKFLOW,
      inputs,
      provider: providerFromEnv({ WF_STUB: "1" }),
      stub: fileStubSource(STUB_DIR),
      until: "a03",
    });

    assert.equal(result.status, "stopped");
    assert.deepEqual(result.nodes.map((node) => node.nodeId), ["a00", "a01", "a02", "a03"]);
    assert.ok(result.nodes.every((node) => node.status === "success"));

    const brief = JSON.parse(String(result.outputs["brief_json"])) as Record<string, unknown>;
    assert.ok(String(brief["topic"]).includes("纪念逝者"));
    assert.equal(brief["argument_count"], 3);
    assert.equal(result.outputs["validation_ok"], true);
    assert.equal(result.trace.filter((event) => event.type === "node_end").length, 4);
  });

  it("遇到未实现节点会明确报错", async () => {
    const workflow = loadWorkflow(WORKFLOW);
    const node = workflow.nodes.get("h02i");
    assert.ok(node);
    const pool = new VariablePool({}, {});
    await assert.rejects(
      () => executeNode({ node, pool, provider: providerFromEnv({}) }),
      (error: unknown) => error instanceof NodeNotImplementedError,
    );
  });
});
