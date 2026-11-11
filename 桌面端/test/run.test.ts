import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { providerFromEnv } from "../src/engine/config.js";
import { fileStubSource, runWorkflowFile } from "../src/engine/run.js";
import { loadWorkflow, parseWorkflow } from "../src/engine/dsl.js";
import { runGraph } from "../src/engine/scheduler.js";
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

const CANCEL_YAML = `
version: "0.7.0"
kind: app
app:
  name: 取消测试
  mode: workflow
workflow:
  graph:
    nodes:
      - id: s
        type: custom
        data:
          type: start
          title: S
          variables: []
      - id: slow
        type: custom
        data:
          type: code
          title: Slow
          variables: []
          outputs:
            - variable: ok
              value_type: boolean
          code: |
            def main() -> dict:
                import time
                time.sleep(8)
                return {"ok": True}
      - id: e
        type: custom
        data:
          type: end
          title: E
          outputs: []
    edges:
      - {id: e1, source: s, target: slow}
      - {id: e2, source: slow, target: e}
`;

describe("手动停止", () => {
  it("中断 signal 后运行立刻结束，节点标记为 stopped", async () => {
    const workflow = parseWorkflow(CANCEL_YAML, "<cancel>");
    const controller = new AbortController();
    const started = Date.now();
    setTimeout(() => controller.abort(), 200);
    const result = await runGraph(workflow, {
      inputs: {},
      provider: providerFromEnv({ WF_STUB: "1" }),
      signal: controller.signal,
    });
    assert.equal(result.status, "stopped");
    assert.equal(result.error, "已停止");
    assert.equal(result.nodes.find((node) => node.nodeId === "slow")?.status, "stopped");
    assert.ok(Date.now() - started < 5000, "停止后不应等 Code 节点的 8 秒跑完");
  });

  it("启动前已中断的 signal 不执行任何节点", async () => {
    const workflow = parseWorkflow(CANCEL_YAML, "<cancel>");
    const controller = new AbortController();
    controller.abort();
    const result = await runGraph(workflow, {
      inputs: {},
      provider: providerFromEnv({ WF_STUB: "1" }),
      signal: controller.signal,
    });
    assert.equal(result.status, "stopped");
    assert.equal(result.nodes.length, 0);
  });
});

const INPUTS_YAML = `
version: "0.7.0"
kind: app
app:
  name: 输入采集
  mode: workflow
workflow:
  graph:
    nodes:
      - id: s
        type: custom
        data:
          type: start
          title: S
          variables:
            - variable: topic
              type: text-input
              required: true
      - id: c
        type: custom
        data:
          type: code
          title: C
          variables:
            - variable: text
              value_selector: [s, topic]
          outputs:
            - variable: out
              value_type: string
          code: |
            def main(text: str) -> dict:
                return {"out": text.upper()}
      - id: e
        type: custom
        data:
          type: end
          title: E
          outputs:
            - variable: result
              value_selector: [c, out]
    edges:
      - {id: e1, source: s, target: c}
      - {id: e2, source: c, target: e}
`;

describe("节点输入值", () => {
  it("运行记录里带上该节点解析后的输入", async () => {
    const workflow = parseWorkflow(INPUTS_YAML, "<inputs>");
    const result = await runGraph(workflow, {
      inputs: { topic: "hello" },
      provider: providerFromEnv({ WF_STUB: "1" }),
    });
    assert.equal(result.status, "success");
    const record = result.nodes.find((node) => node.nodeId === "c");
    assert.equal(record?.inputs?.["s.topic"], "hello");
    assert.equal(result.outputs["result"], "HELLO");
  });
});
