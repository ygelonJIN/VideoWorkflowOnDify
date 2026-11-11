import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { parseWorkflow } from "../src/engine/dsl.js";
import { runGraph } from "../src/engine/scheduler.js";
import { providerFromEnv } from "../src/engine/config.js";
import { stringify } from "yaml";
import { loadWorkflow } from "../src/engine/dsl.js";
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

  it("04 的真实 H02I 迭代 + H02S + H02J 拼接能跑通", async () => {
    const source = loadWorkflow(WORKFLOW);
    const pick = (id: string) => JSON.parse(JSON.stringify(source.nodes.get(id))) as Record<string, any>;
    const iteration = pick("h02i");
    iteration.data.iterator_selector = ["s", "scene_payloads"];
    const doc = {
      version: "0.7.0",
      kind: "app",
      app: { name: "04 迭代切片", mode: "workflow" },
      workflow: {
        graph: {
          nodes: [
            { id: "s", type: "custom", data: { type: "start", title: "S", variables: [{ variable: "scene_payloads", type: "array", required: true }] } },
            iteration,
            pick("h02i_start"),
            pick("h02s"),
            pick("h02j"),
            { id: "e", type: "custom", data: { type: "end", title: "E", outputs: [{ variable: "scenes_html", value_selector: ["h02j", "scenes_html"] }] } },
          ],
          edges: [
            { id: "x1", source: "s", target: "h02i" },
            { id: "x2", source: "h02i_start", target: "h02s" },
            { id: "x3", source: "h02i", target: "h02j" },
            { id: "x4", source: "h02j", target: "e" },
          ],
        },
      },
    };
    const workflow = parseWorkflow(stringify(doc), "<04-slice>");
    const result = await runGraph(workflow, {
      inputs: { scene_payloads: [{ scene_id: "s01" }, { scene_id: "s02" }, { scene_id: "s03" }] },
      provider: providerFromEnv({ WF_STUB: "1" }),
      stub: { get: (nodeId: string) => (nodeId === "h02s" ? "<section>S</section>" : undefined) },
    });
    assert.equal(result.status, "success");
    assert.equal(result.outputs["scenes_html"], "<section>S</section>\n\n<section>S</section>\n\n<section>S</section>");
    assert.equal(result.nodes.filter((node) => node.nodeId === "h02s").length, 3);
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
