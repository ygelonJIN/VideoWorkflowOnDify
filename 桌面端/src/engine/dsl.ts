import { readFileSync } from "node:fs";
import { parse } from "yaml";
import type { DslDocument, DslEdge, DslNode, WorkflowGraph } from "./types.js";

export interface LoadedWorkflow {
  path: string;
  raw: string;
  doc: DslDocument;
  graph: WorkflowGraph;
  nodes: Map<string, DslNode>;
  edges: DslEdge[];
  warnings: string[];
}

export class DslError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DslError";
  }
}

export function loadWorkflow(path: string): LoadedWorkflow {
  const raw = readFileSync(path, "utf8");
  return parseWorkflow(raw, path);
}

export function parseWorkflow(raw: string, path = "<memory>"): LoadedWorkflow {
  let doc: unknown;
  try {
    doc = parse(raw);
  } catch (error) {
    throw new DslError(`YAML 解析失败：${(error as Error).message}`);
  }
  if (!doc || typeof doc !== "object" || Array.isArray(doc)) {
    throw new DslError("YAML 顶层不是对象");
  }
  const dsl = doc as DslDocument;
  const graph = dsl.workflow?.graph;
  if (!graph || !Array.isArray(graph.nodes) || !Array.isArray(graph.edges)) {
    throw new DslError("缺少 workflow.graph.nodes / workflow.graph.edges（本引擎只支持 DSL 0.7 结构）");
  }

  const warnings: string[] = [];
  const nodes = new Map<string, DslNode>();
  for (const node of graph.nodes) {
    if (!node || typeof node.id !== "string" || !node.data || typeof node.data.type !== "string") {
      throw new DslError(`节点结构不合法：${JSON.stringify(node)?.slice(0, 120)}`);
    }
    if (nodes.has(node.id)) throw new DslError(`节点 ID 重复：${node.id}`);
    nodes.set(node.id, node);
  }

  for (const edge of graph.edges) {
    if (!nodes.has(edge.source)) warnings.push(`边 ${edge.id} 的 source 不存在：${edge.source}`);
    if (!nodes.has(edge.target)) warnings.push(`边 ${edge.id} 的 target 不存在：${edge.target}`);
  }

  const starts = [...nodes.values()].filter((node) => node.data.type === "start");
  if (starts.length !== 1) warnings.push(`start 节点数量应为 1，实际 ${starts.length}`);

  return { path, raw, doc: dsl, graph, nodes, edges: graph.edges, warnings };
}

export function nodeType(node: DslNode): string {
  return node.data.type;
}

export function nodeTitle(node: DslNode): string {
  return typeof node.data.title === "string" && node.data.title.length > 0 ? node.data.title : node.id;
}

export function startNode(workflow: LoadedWorkflow): DslNode {
  const node = [...workflow.nodes.values()].find((item) => item.data.type === "start");
  if (!node) throw new DslError("找不到 start 节点");
  return node;
}

export function outgoingEdges(workflow: LoadedWorkflow, nodeId: string, handle?: string): DslEdge[] {
  return workflow.edges.filter((edge) => {
    if (edge.source !== nodeId) return false;
    if (handle === undefined) return true;
    const edgeHandle = edge.sourceHandle ?? "";
    return edgeHandle === handle;
  });
}

export function endNodes(workflow: LoadedWorkflow): DslNode[] {
  return [...workflow.nodes.values()].filter((node) => node.data.type === "end");
}

export function environmentValues(workflow: LoadedWorkflow, overrides: Record<string, string> = {}): Record<string, string> {
  const values: Record<string, string> = {};
  for (const variable of workflow.doc.workflow?.environment_variables ?? []) {
    if (typeof variable.name !== "string") continue;
    values[variable.name] = typeof variable.value === "string" ? variable.value : String(variable.value ?? "");
  }
  for (const [key, value] of Object.entries(overrides)) {
    if (value !== undefined) values[key] = value;
  }
  return values;
}

/** 节点声明的必填输入（start 节点专用）。 */
export function startVariables(node: DslNode): Array<{
  variable: string;
  label?: string;
  type?: string;
  required: boolean;
  options?: string[];
}> {
  const list = Array.isArray(node.data.variables) ? (node.data.variables as Record<string, unknown>[]) : [];
  return list
    .filter((item) => typeof item["variable"] === "string")
    .map((item) => {
      const options = Array.isArray(item["options"])
        ? (item["options"] as unknown[]).map((option) =>
            typeof option === "string" ? option : String((option as Record<string, unknown>)?.["value"] ?? ""),
          )
        : undefined;
      return {
        variable: String(item["variable"]),
        label: typeof item["label"] === "string" ? item["label"] : undefined,
        type: typeof item["type"] === "string" ? item["type"] : undefined,
        required: item["required"] === true,
        options,
      };
    });
}
