import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseWorkflow } from "../src/engine/dsl.js";
import { runGraph } from "../src/engine/scheduler.js";
import { providerFromEnv } from "../src/engine/config.js";
import { parse, stringify } from "yaml";
import { WORKFLOW } from "./paths.js";

const ITERATION_YAML = `
version: "0.7.0"
kind: app
app:
  name: 迭代测试
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
            - variable: items
              type: array
              required: true
      - id: it
        type: custom
        data:
          type: iteration
          title: IT
          iterator_selector: [s, items]
          output_selector: [inner, text]
          is_parallel: false
          parallel_nums: 10
          error_handle_mode: terminated
          start_node_id: it_start
          width: 500
          height: 200
      - id: it_start
        type: custom
        data:
          type: iteration-start
          title: ""
          iteration_id: it
      - id: inner
        type: custom
        data:
          type: code
          title: INNER
          isInIteration: true
          iteration_id: it
          variables:
            - variable: item
              value_selector: [it, item]
              value_type: string
          outputs:
            text:
              type: string
          code: |
            def main(item: str) -> dict:
                return {"text": str(item).upper()}
      - id: e
        type: custom
        data:
          type: end
          title: E
          outputs:
            - variable: result
              value_selector: [it, output]
              value_type: array
    edges:
      - {id: e1, source: s, target: it}
      - {id: e2, source: it_start, target: inner}
      - {id: e3, source: it, target: e}
`;

const LOOP_YAML = `
version: "0.7.0"
kind: app
app:
  name: 循环测试
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
            - variable: seed
              type: text-input
              required: true
      - id: lp
        type: custom
        data:
          type: loop
          title: LP
          loop_count: 3
          logical_operator: and
          loop_variables:
            - id: seen
              label: seen
              value: ""
              value_type: constant
              var_type: string
          break_conditions:
            - id: never
              variable_selector: [inner, done]
              comparison_operator: is
              value: "true"
              varType: boolean
          start_node_id: lp_start
      - id: lp_start
        type: custom
        data:
          type: loop-start
          title: ""
          loop_id: lp
      - id: inner
        type: custom
        data:
          type: code
          title: INNER
          isInLoop: true
          loop_id: lp
          variables:
            - variable: seed
              value_selector: [s, seed]
              value_type: string
          outputs:
            value:
              type: string
            done:
              type: boolean
          code: |
            def main(seed: str) -> dict:
                return {"value": seed + "!", "done": False}
      - id: setit
        type: custom
        data:
          type: assigner
          title: SET
          isInLoop: true
          loop_id: lp
          version: "2"
          items:
            - variable_selector: [lp, seen]
              input_type: variable
              operation: over-write
              value: [inner, value]
              write_mode: over-write
      - id: e
        type: custom
        data:
          type: end
          title: E
          outputs:
            - variable: seen
              value_selector: [lp, seen]
              value_type: string
            - variable: rounds
              value_selector: [lp, loop_round]
              value_type: number
    edges:
      - {id: e1, source: s, target: lp}
      - {id: e2, source: lp_start, target: inner}
      - {id: e3, source: inner, target: setit}
      - {id: e4, source: lp, target: e}
`;

describe("容器节点", () => {
  it("iteration 逐项执行并把结果收成数组", async () => {
    const workflow = parseWorkflow(ITERATION_YAML, "<iteration>");
    const result = await runGraph(workflow, {
      inputs: { items: ["a", "b", "c"] },
      provider: providerFromEnv({ WF_STUB: "1" }),
    });
    assert.equal(result.status, "success");
    assert.deepEqual(result.outputs["result"], ["A", "B", "C"]);
    const innerRuns = result.nodes.filter((node) => node.nodeId === "inner");
    assert.equal(innerRuns.length, 3);
  });

  it("04 的真实 H02I 迭代（逐屏 → 动效 → 合并）能跑通", async () => {
    // 从当前 YAML 里抓 H02I 的整个子图：h02i_start + 所有 parentId=h02i 的节点。
    // 以前这里写死 h02i_start→h02s→h02j，04 加上 h02sm/h02sk 后测试就假红了。
    const doc = parse(readFileSync(WORKFLOW, "utf8")) as {
      workflow: { graph: { nodes: Array<Record<string, any>>; edges: Array<Record<string, any>> } };
    };
    const rawNodes = doc.workflow.graph.nodes;
    const rawEdges = doc.workflow.graph.edges;
    const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

    const iteration = clone(rawNodes.find((node) => node.id === "h02i"));
    assert.ok(iteration, "04 里找不到 h02i");
    iteration.data.iterator_selector = ["s", "scene_payloads"];

    const body = rawNodes.filter((node) => node.parentId === "h02i");
    assert.ok(body.some((node) => node.id === "h02i_start"), "H02I 缺少入口节点");
    assert.ok(body.some((node) => node.id === "h02sk"), "H02I 里缺少 H02SK 合并节点");
    const bodyIds = new Set(body.map((node) => String(node.id)));

    const nodes = [
      { id: "s", type: "custom", data: { type: "start", title: "S", variables: [{ variable: "scene_payloads", type: "array", required: true }] } },
      iteration,
      ...body.map(clone),
      { id: "e", type: "custom", data: { type: "end", title: "E", outputs: [{ variable: "scenes", value_selector: ["h02i", "output"] }] } },
    ];
    const edges = rawEdges
      .filter((edge) => bodyIds.has(String(edge.source)) && bodyIds.has(String(edge.target)))
      .map(clone)
      .concat([
        { id: "slice-s-i", source: "s", target: "h02i" },
        { id: "slice-i-e", source: "h02i", target: "e" },
      ]);

    const workflow = parseWorkflow(stringify({ version: "0.7.0", kind: "app", app: { name: "04 迭代切片", mode: "workflow" }, workflow: { graph: { nodes, edges } } }), "<04-slice>");
    const section = "<section class=\"scene\" data-scene=\"s01\">A</section>";
    // 合并节点内部可能对动效做清洗（h02sx 等），只断言 HTML 仍在，不绑死脚本原文
    const script = "<script>window.__m = 1;</script>";
    const result = await runGraph(workflow, {
      inputs: { scene_payloads: [{ scene_id: "s01" }, { scene_id: "s02" }, { scene_id: "s03" }] },
      provider: providerFromEnv({ WF_STUB: "1" }),
      stub: { get: (nodeId: string) => (nodeId === "h02s" ? section : nodeId === "h02sm" ? script : undefined) },
    });

    assert.equal(result.status, "success");
    assert.equal(result.nodes.filter((node) => node.nodeId === "h02s").length, 3);
    assert.equal(result.nodes.filter((node) => node.nodeId === "h02sm").length, 3);
    assert.equal(result.nodes.filter((node) => node.nodeId === "h02sk").length, 3);

    const scenes = result.outputs["scenes"] as string[];
    assert.equal(scenes.length, 3, "每屏应收集一条合并结果");
    for (const item of scenes) {
      assert.ok(item.startsWith(section), "合并结果应以本屏 HTML 开头");
      assert.ok(item.length >= section.length, "合并结果不能丢内容");
    }
  });

  it("iteration 并行模式结果顺序不变", async () => {
    const parallelYaml = ITERATION_YAML.replace("is_parallel: false", "is_parallel: true").replace("parallel_nums: 10", "parallel_nums: 2");
    const workflow = parseWorkflow(parallelYaml, "<iteration-parallel>");
    const result = await runGraph(workflow, {
      inputs: { items: ["a", "b", "c", "d"] },
      provider: providerFromEnv({ WF_STUB: "1" }),
    });
    assert.equal(result.status, "success");
    assert.deepEqual(result.outputs["result"], ["A", "B", "C", "D"]);
  });

  it("loop 按 loop_count 重复，assigner 写回循环变量", async () => {
    const workflow = parseWorkflow(LOOP_YAML, "<loop>");
    const result = await runGraph(workflow, {
      inputs: { seed: "x" },
      provider: providerFromEnv({ WF_STUB: "1" }),
    });
    assert.equal(result.status, "success");
    assert.equal(result.outputs["seen"], "x!");
    assert.equal(result.outputs["rounds"], 3);
    const innerRuns = result.nodes.filter((node) => node.nodeId === "inner");
    assert.equal(innerRuns.length, 3);
  });
});
