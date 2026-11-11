import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parse } from "yaml";
import { addNode, connect, moveNode, removeEdge, removeNode, updateNodeField, YamlEditError } from "../src/engine/yamlEdit.js";
import { WORKFLOW } from "./paths.js";

const RAW = readFileSync(WORKFLOW, "utf8");

function nodeData(raw: string, id: string): Record<string, unknown> {
  const doc = parse(raw) as { workflow: { graph: { nodes: Array<{ id: string; data: Record<string, unknown> }> } } };
  return doc.workflow.graph.nodes.find((node) => node.id === id)?.data as Record<string, unknown>;
}

describe("YAML 写回", () => {
  it("改提示词只动那一行，注释和结构不变", () => {
    const prompt = '新提示词：保留 "引号" 与换行\n第二行';
    const next = updateNodeField(RAW, "a01", "prompt", prompt);
    const template = nodeData(next, "a01")["prompt_template"] as Array<{ text: string }>;
    assert.equal(template[0]?.text, prompt);
    assert.equal(nodeData(RAW, "a01")["title"], nodeData(next, "a01")["title"]);
    assert.ok(next.startsWith(RAW.split("\n").slice(0, 2).join("\n")), "文件头注释应原样保留");
    assert.equal(next.split("\n").length, RAW.split("\n").length, "单行替换不应改变行数");
    assert.equal((parse(next) as { workflow: { graph: { nodes: unknown[] } } }).workflow.graph.nodes.length, 49);
  });

  it("改代码与标题", () => {
    const code = "def main(x: str) -> dict:\n    return {\"ok\": x}\n";
    const withCode = updateNodeField(RAW, "a02", "code", code);
    assert.equal(nodeData(withCode, "a02")["code"], code);
    const withTitle = updateNodeField(withCode, "a03", "title", "A03 新标题");
    assert.equal(nodeData(withTitle, "a03")["title"], "A03 新标题");
  });

  it("未知节点直接报错，不写坏文件", () => {
    assert.throws(() => updateNodeField(RAW, "nope", "title", "x"), YamlEditError);
  });

  it("加节点会自动连一条边，删除后恢复原状", () => {
    const added = addNode(RAW, { type: "code", title: "新 Code", position: { x: 10, y: 20 }, sourceId: "a03" });
    const withNode = parse(added.raw) as { workflow: { graph: { nodes: Array<{ id: string; data: Record<string, unknown> }>; edges: Array<{ source: string; target: string }> } } };
    assert.equal(withNode.workflow.graph.nodes.length, 50);
    const node = withNode.workflow.graph.nodes.find((item) => item.id === added.nodeId);
    assert.equal(node?.data["type"], "code");
    assert.ok(withNode.workflow.graph.edges.some((edge) => edge.source === "a03" && edge.target === added.nodeId));

    const removed = removeNode(added.raw, added.nodeId);
    const restored = parse(removed) as { workflow: { graph: { nodes: unknown[]; edges: Array<{ source: string; target: string }> } } };
    assert.equal(restored.workflow.graph.nodes.length, 49);
    assert.equal(restored.workflow.graph.edges.length, 51);
    assert.ok(!restored.workflow.graph.edges.some((edge) => edge.source === added.nodeId || edge.target === added.nodeId));
  });

  it("删除中间节点会把前后接上", () => {
    const removed = removeNode(RAW, "a02");
    const graph = (parse(removed) as { workflow: { graph: { nodes: unknown[]; edges: Array<{ source: string; target: string }> } } }).workflow.graph;
    assert.equal(graph.nodes.length, 48);
    assert.ok(graph.edges.some((edge) => edge.source === "a01" && edge.target === "a03"));
  });

  it("连线与断开", () => {
    const connected = connect(RAW, { source: "a03", target: "a04" });
    const after = (parse(connected) as { workflow: { graph: { edges: Array<{ id: string; source: string; target: string }> } } }).workflow.graph;
    const edge = after.edges.find((item) => item.source === "a03" && item.target === "a04");
    assert.ok(edge);
    const removed = removeEdge(connected, edge.id);
    const final = (parse(removed) as { workflow: { graph: { edges: unknown[] } } }).workflow.graph;
    assert.equal(final.edges.length, 51);
  });

  it("移动节点只改 position 四行", () => {
    const moved = moveNode(RAW, "a03", { x: 123, y: 456 });
    const graph = (parse(moved) as { workflow: { graph: { nodes: Array<{ id: string; position: { x: number; y: number }; positionAbsolute: { x: number; y: number } }> } } }).workflow.graph;
    const node = graph.nodes.find((item) => item.id === "a03");
    assert.deepEqual(node?.position, { x: 123, y: 456 });
    assert.deepEqual(node?.positionAbsolute, { x: 123, y: 456 });
    assert.equal(moved.split("\n").length, RAW.split("\n").length);
  });

  it("新加 if-else 会按来源节点的输出生成默认条件", () => {
    const added = addNode(RAW, { type: "if-else", title: "新门禁", position: { x: 0, y: 0 }, sourceId: "a03" });
    const graph = (parse(added.raw) as { workflow: { graph: { nodes: Array<{ id: string; data: Record<string, unknown> }> } } }).workflow.graph;
    const node = graph.nodes.find((item) => item.id === added.nodeId);
    const cases = node?.data["cases"] as Array<{ conditions: Array<{ variable_selector: string[]; comparison_operator: string }> }>;
    assert.equal(cases?.[0]?.conditions[0]?.variable_selector[0], "a03");
    assert.equal(cases?.[0]?.conditions[0]?.comparison_operator, "is not empty");
  });

  it("不能删 start 节点", () => {
    assert.throws(() => removeNode(RAW, "a00"), YamlEditError);
  });
});
