import { parse } from "yaml";

export type EditableField = "title" | "prompt" | "code" | "template";

export class YamlEditError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "YamlEditError";
  }
}

/** YAML 双引号标量：JSON 字符串是合法子集，换行/引号/反斜杠都能安全承载。 */
function quote(value: string): string {
  return JSON.stringify(value);
}

function leadingSpaces(line: string): number {
  return line.length - line.trimStart().length;
}

function nodeBlockRange(lines: string[], nodeId: string): { start: number; end: number } {
  const start = lines.findIndex((line) => {
    const match = /^(\s*)- id:\s*(.+?)\s*$/.exec(line);
    if (!match) return false;
    return String(match[2]).replace(/^["']|["']$/g, "") === nodeId;
  });
  if (start < 0) throw new YamlEditError(`找不到节点 ${nodeId}`);
  const indent = leadingSpaces(lines[start] as string);
  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    const line = lines[index] as string;
    const nextNode = /^(\s*)- id:\s*/.exec(line);
    if (nextNode && leadingSpaces(line) <= indent) {
      end = index;
      break;
    }
    if (/^\s*edges:\s*$/.test(line) && leadingSpaces(line) <= indent) {
      end = index;
      break;
    }
  }
  return { start, end };
}

function findKeyLine(lines: string[], from: number, to: number, key: string, section?: string): number {
  let begin = from;
  if (section) {
    const sectionIndex = lines.findIndex((line, index) => index >= from && index < to && new RegExp(`^\\s*${section}:`).test(line));
    if (sectionIndex < 0) throw new YamlEditError(`节点里没有 ${section}`);
    begin = sectionIndex;
  }
  for (let index = begin; index < to; index += 1) {
    if (new RegExp(`^(\\s*)${key}:`).test(lines[index] as string)) return index;
  }
  throw new YamlEditError(`节点里没有 ${key}`);
}

function replaceScalar(lines: string[], index: number, key: string, value: string): void {
  const line = lines[index] as string;
  const indent = " ".repeat(leadingSpaces(line));
  const inline = line.slice(line.indexOf(`${key}:`) + key.length + 1).trim();
  lines[index] = `${indent}${key}: ${quote(value)}`;
  // 块标量（|、>）后面跟着缩进内容，一并去掉，避免残留成孤立文本
  if (/^[|>][-+]?\s*$/.test(inline)) {
    let cursor = index + 1;
    while (cursor < lines.length) {
      const next = lines[cursor] as string;
      if (next.trim() === "" || leadingSpaces(next) > indent.length) {
        lines.splice(cursor, 1);
        continue;
      }
      break;
    }
  }
}

function nodeById(doc: unknown, nodeId: string): Record<string, unknown> | undefined {
  const graph = (doc as { workflow?: { graph?: { nodes?: Array<{ id?: string; data?: Record<string, unknown> }> } } })?.workflow?.graph;
  return graph?.nodes?.find((node) => node.id === nodeId)?.data;
}

function readField(document: Record<string, unknown> | undefined, field: EditableField): unknown {
  if (!document) return undefined;
  if (field === "title") return document["title"];
  if (field === "code") return document["code"];
  if (field === "template") return document["template"];
  const template = document["prompt_template"];
  if (!Array.isArray(template) || template.length === 0) return undefined;
  return (template[0] as { text?: unknown })?.text;
}

/**
 * 只替换指定节点的单个字段值，其余行原样保留（注释、缩进、长单行都不动）。
 * 写完立刻重新解析校验：节点数、节点 id 顺序、目标字段都必须对得上。
 */
export function updateNodeField(raw: string, nodeId: string, field: EditableField, value: string): string {
  const lines = raw.split("\n");
  const before = parse(raw) as unknown;
  const beforeData = nodeById(before, nodeId);
  if (!beforeData) throw new YamlEditError(`找不到节点 ${nodeId}`);
  const beforeCount = (before as { workflow: { graph: { nodes: unknown[] } } }).workflow.graph.nodes.length;

  const { start, end } = nodeBlockRange(lines, nodeId);
  let index: number;
  let key: string;
  switch (field) {
    case "title":
      index = findKeyLine(lines, start + 1, end, "title");
      key = "title";
      break;
    case "code":
      index = findKeyLine(lines, start + 1, end, "code");
      key = "code";
      break;
    case "template":
      index = findKeyLine(lines, start + 1, end, "template");
      key = "template";
      break;
    case "prompt":
      index = findKeyLine(lines, start + 1, end, "text", "prompt_template");
      key = "text";
      break;
    default:
      throw new YamlEditError(`不支持的字段：${String(field)}`);
  }
  replaceScalar(lines, index, key, value);
  const next = lines.join("\n");

  const after = parse(next) as unknown;
  const afterData = nodeById(after, nodeId);
  if (!afterData) throw new YamlEditError("写回后找不到节点");
  const afterCount = (after as { workflow: { graph: { nodes: unknown[] } } }).workflow.graph.nodes.length;
  if (afterCount !== beforeCount) throw new YamlEditError(`写回后节点数变化：${beforeCount} → ${afterCount}`);
  const afterValue = readField(afterData, field);
  if (afterValue !== value) {
    throw new YamlEditError(`写回校验失败：期望 ${value.length} 字符，实际 ${String(afterValue ?? "").length}`);
  }
  return next;
}

// ---------------------------------------------------------------------------
// 结构编辑：加/删节点、加/删连线
// ---------------------------------------------------------------------------

export interface NodeSpec {
  id?: string;
  type: "code" | "llm" | "if-else" | "template-transform" | "http-request" | "end";
  title: string;
  position: { x: number; y: number };
  sourceId?: string;
}

export interface EdgeSpec {
  source: string;
  target: string;
  sourceHandle?: string;
}

function sectionRange(lines: string[], name: "nodes" | "edges"): { start: number; end: number; indent: number } {
  const start = lines.findIndex((line) => new RegExp(`^(\\s*)${name}:\\s*$`).test(line));
  if (start < 0) throw new YamlEditError(`找不到 ${name}: 段`);
  const indent = leadingSpaces(lines[start] as string);
  let end = lines.length;
  for (let index = start + 1; index < lines.length; index += 1) {
    const line = lines[index] as string;
    const match = new RegExp(`^(\\s*)([a-z_]+):\\s*$`).exec(line);
    if (match && leadingSpaces(line) <= indent && String(match[2]) !== name) {
      end = index;
      break;
    }
  }
  return { start, end, indent };
}

function itemIndent(lines: string[], section: { start: number; end: number; indent: number }): number {
  for (let index = section.start + 1; index < section.end; index += 1) {
    if (/^\s*- id:\s*/.test(lines[index] as string)) return leadingSpaces(lines[index] as string);
  }
  return section.indent + 2;
}

function itemRange(lines: string[], start: number, endExclusive: number, indent: number): { start: number; end: number } {
  let end = endExclusive;
  for (let index = start + 1; index < endExclusive; index += 1) {
    if (leadingSpaces(lines[index] as string) === indent && /^\s*- id:\s*/.test(lines[index] as string)) {
      end = index;
      break;
    }
  }
  return { start, end };
}

function quoteValue(value: string): string {
  return JSON.stringify(value);
}

function graphOf(doc: unknown): {
  nodes: Array<{ id: string; data: Record<string, unknown> }>;
  edges: Array<{ id: string; source: string; target: string; sourceHandle?: string }>;
} {
  const graph = (doc as { workflow?: { graph?: { nodes?: unknown[]; edges?: unknown[] } } })?.workflow?.graph;
  return {
    nodes: (graph?.nodes ?? []) as Array<{ id: string; data: Record<string, unknown> }>,
    edges: (graph?.edges ?? []) as Array<{ id: string; source: string; target: string; sourceHandle?: string }>,
  };
}

function flatten(data: Record<string, unknown>): Record<string, unknown> {
  return data ?? {};
}

function nodeFlags(source: Record<string, unknown> | undefined): { isInIteration: boolean; iterationId?: string; isInLoop: boolean; loopId?: string; sourceIdForCondition?: string } {
  if (!source) return { isInIteration: false, isInLoop: false };
  const iterationId = typeof source["iteration_id"] === "string" ? String(source["iteration_id"]) : undefined;
  const loopId = typeof source["loop_id"] === "string" ? String(source["loop_id"]) : undefined;
  return { isInIteration: Boolean(iterationId), iterationId, isInLoop: Boolean(loopId), loopId };
}

function outputNames(data: Record<string, unknown>): string[] {
  const outputs = data["outputs"];
  if (Array.isArray(outputs)) {
    return outputs.map((item) => (typeof item === "string" ? item : String((item as Record<string, unknown>)?.["variable"] ?? ""))).filter(Boolean);
  }
  if (outputs && typeof outputs === "object") return Object.keys(outputs as Record<string, unknown>);
  return [];
}

function nodeLines(id: string, indent: number, spec: NodeSpec, flags: ReturnType<typeof nodeFlags>, sourceOutputNames?: string[]): string[] {
  const pad = " ".repeat(indent);
  const field = " ".repeat(indent + 2);
  const data = " ".repeat(indent + 4);
  const deep = " ".repeat(indent + 6);
  const lines: string[] = [
    `${pad}- id: ${id}`,
    `${field}type: custom`,
    `${field}data:`,
    `${data}type: ${spec.type}`,
    `${data}title: ${quoteValue(spec.title)}`,
  ];
  if (flags.isInIteration) {
    lines.push(`${data}isInIteration: true`, `${data}iteration_id: ${flags.iterationId}`);
  }
  if (flags.isInLoop) {
    lines.push(`${data}isInLoop: true`, `${data}loop_id: ${flags.loopId}`);
  }

  switch (spec.type) {
    case "code":
      lines.push(
        `${data}code_language: python3`,
        `${data}variables: []`,
        `${data}outputs:`,
        `${deep}text:`,
        `${deep}  type: string`,
        `${data}code: ${quoteValue('def main() -> dict:\n    return {"text": ""}')}`,
      );
      break;
    case "llm":
      lines.push(
        `${data}model:`,
        `${deep}provider: langgenius/opencode_go/opencode_go`,
        `${deep}name: gpt-6-luna`,
        `${deep}mode: chat`,
        `${deep}completion_params:`,
        `${deep}  max_tokens: 8192`,
        `${data}prompt_template:`,
        `${deep}- role: system`,
        `${deep}  text: ${quoteValue("你是一个助手。")}`,
        `${data}context:`,
        `${deep}enabled: false`,
        `${deep}variable_selector: []`,
        `${data}vision:`,
        `${deep}enabled: false`,
      );
      break;
    case "if-else": {
      const sourceOutputs = Array.isArray(sourceOutputNames) ? sourceOutputNames : [];
      const output = sourceOutputs[0];
      lines.push(
        `${data}cases:`,
        `${deep}- id: valid`,
        `${deep}  case_id: valid`,
        `${deep}  logical_operator: and`,
        `${deep}  conditions:`,
      );
      if (output) {
        lines.push(
          `${deep}  - id: valid-condition`,
          `${deep}    variable_selector:`,
          `${deep}    - ${flags.sourceIdForCondition}`,
          `${deep}    - ${output}`,
          `${deep}    comparison_operator: is not empty`,
          `${deep}    value: ""`,
          `${deep}    varType: string`,
        );
      } else {
        lines.push(`${deep}  []`);
      }
      break;
    }
    case "template-transform":
      lines.push(`${data}template: ${quoteValue("{{ input }}")}`, `${data}variables: []`);
      break;
    case "http-request":
      lines.push(
        `${data}method: get`,
        `${data}url: ${quoteValue("https://example.com")}`,
        `${data}headers: ""`,
        `${data}params: ""`,
        `${data}body:`,
        `${deep}type: none`,
        `${deep}data: []`,
        `${data}authorization:`,
        `${deep}type: no-auth`,
        `${deep}config: null`,
        `${data}timeout:`,
        `${deep}max_connect_timeout: 10`,
        `${deep}max_read_timeout: 60`,
        `${deep}max_write_timeout: 30`,
      );
      break;
    case "end":
      lines.push(`${data}outputs: []`);
      break;
  }

  lines.push(
    `${field}position:`,
    `${field}  x: ${Math.round(spec.position.x)}`,
    `${field}  y: ${Math.round(spec.position.y)}`,
    `${field}positionAbsolute:`,
    `${field}  x: ${Math.round(spec.position.x)}`,
    `${field}  y: ${Math.round(spec.position.y)}`,
    `${field}sourcePosition: right`,
    `${field}targetPosition: left`,
    `${field}width: 244`,
    `${field}height: ${spec.type === "end" ? 96 : 110}`,
  );
  return lines;
}

function edgeLines(edge: { id: string; source: string; sourceHandle: string; target: string; targetHandle: string; sourceType: string; targetType: string; flags: ReturnType<typeof nodeFlags> }, indent: number): string[] {
  const pad = " ".repeat(indent);
  const field = " ".repeat(indent + 2);
  const data = " ".repeat(indent + 4);
  return [
    `${pad}- id: ${edge.id}`,
    `${field}source: ${edge.source}`,
    `${field}sourceHandle: ${edge.sourceHandle}`,
    `${field}target: ${edge.target}`,
    `${field}targetHandle: ${edge.targetHandle}`,
    `${field}type: custom`,
    `${field}data:`,
    `${data}sourceType: ${edge.sourceType}`,
    `${data}targetType: ${edge.targetType}`,
    `${data}isInIteration: ${edge.flags.isInIteration}`,
    `${data}isInLoop: ${edge.flags.isInLoop}`,
    ...(edge.flags.isInIteration ? [`${data}iteration_id: ${edge.flags.iterationId}`] : []),
    ...(edge.flags.isInLoop ? [`${data}loop_id: ${edge.flags.loopId}`] : []),
  ];
}

function uniqueEdgeId(edges: Array<{ id: string }>, base: string): string {
  let id = base;
  let suffix = 2;
  while (edges.some((edge) => edge.id === id)) {
    id = `${base}-${suffix}`;
    suffix += 1;
  }
  return id;
}

function insertEdge(lines: string[], edge: Parameters<typeof edgeLines>[0], indent: number): void {
  const block = edgeLines(edge, indent);
  const section = sectionRange(lines, "edges");
  let insertAt = lines.length;
  if (lines[lines.length - 1] === "") insertAt = lines.length - 1;
  // 找到 edges 段最后一行（跳过末尾空行）
  for (let index = section.start + 1; index < lines.length; index += 1) {
    if ((lines[index] as string).trim() === "") continue;
    insertAt = index + 1;
  }
  lines.splice(insertAt, 0, ...block);
}

/** 在选中节点后面插一个新节点，并自动连一条边。 */
export function addNode(raw: string, spec: NodeSpec): { raw: string; nodeId: string; edgeId?: string } {
  const doc = parse(raw) as unknown;
  const graph = graphOf(doc);
  const baseId = (spec.id ?? `${spec.type}_${Math.random().toString(36).slice(2, 6)}`).replace(/[^A-Za-z0-9_]/g, "_");
  if (!/^[A-Za-z0-9_]/.test(baseId)) throw new YamlEditError(`节点 id 不合法：${baseId}`);
  if (graph.nodes.some((node) => node.id === baseId)) throw new YamlEditError(`节点 id 已存在：${baseId}`);

  const source = spec.sourceId ? graph.nodes.find((node) => node.id === spec.sourceId) : undefined;
  const flags = nodeFlags(source ? flatten(source.data) : undefined);

  const lines = raw.split("\n");
  const nodesSection = sectionRange(lines, "nodes");
  const indent = itemIndent(lines, nodesSection);
  const sourceOutputs = source ? outputNames(flatten(source.data)) : [];
  const block = nodeLines(baseId, indent, spec, { ...flags, sourceIdForCondition: source?.id }, sourceOutputs);
  lines.splice(nodesSection.end, 0, ...block);

  let edgeId: string | undefined;
  if (source) {
    const edgesSection = sectionRange(lines, "edges");
    const edgeIndent = itemIndent(lines, edgesSection);
    const sourceType = String(flatten(source.data)["type"] ?? "custom");
    const sourceHandle = sourceType === "if-else" ? "false" : "source";
    edgeId = uniqueEdgeId(graph.edges, `${source.id}-${sourceHandle}-${baseId}`);
    insertEdge(lines, {
      id: edgeId,
      source: source.id,
      sourceHandle,
      target: baseId,
      targetHandle: "target",
      sourceType,
      targetType: spec.type,
      flags,
    }, edgeIndent);
  }

  const next = lines.join("\n");
  const after = graphOf(parse(next) as unknown);
  if (!after.nodes.some((node) => node.id === baseId)) throw new YamlEditError("新增节点写回失败");
  if (edgeId && !after.edges.some((edge) => edge.id === edgeId)) throw new YamlEditError("新增连线写回失败");
  return { raw: next, nodeId: baseId, ...(edgeId ? { edgeId } : {}) };
}

/** 删一个节点，连同它的所有连线；恰好一进一出时自动接上。 */
export function removeNode(raw: string, nodeId: string): string {
  const doc = parse(raw) as unknown;
  const graph = graphOf(doc);
  const node = graph.nodes.find((item) => item.id === nodeId);
  if (!node) throw new YamlEditError(`找不到节点 ${nodeId}`);
  if (flatten(node.data)["type"] === "start") throw new YamlEditError("不能删除 start 节点");

  const incoming = graph.edges.filter((edge) => edge.target === nodeId);
  const outgoing = graph.edges.filter((edge) => edge.source === nodeId);

  const lines = raw.split("\n");
  const nodesSection = sectionRange(lines, "nodes");
  const nIndent = itemIndent(lines, nodesSection);
  const nodeIndex = lines.findIndex((line) => leadingSpaces(line) === nIndent && new RegExp(`- id:\\s*${nodeId}\\s*$`).test(line));
  if (nodeIndex < 0) throw new YamlEditError("找不到节点块");
  const nodeRange = itemRange(lines, nodeIndex, nodesSection.end, nIndent);
  lines.splice(nodeRange.start, nodeRange.end - nodeRange.start);

  // 删边：从后往前删，避免行号漂移
  const sections = sectionRange(lines, "edges");
  const eIndent = itemIndent(lines, sections);
  const edgeStarts: number[] = [];
  for (let index = sections.start + 1; index < sections.end; index += 1) {
    if (leadingSpaces(lines[index] as string) === eIndent && /^\s*- id:\s*/.test(lines[index] as string)) edgeStarts.push(index);
  }
  const toRemove: Array<{ start: number; end: number }> = [];
  for (const start of edgeStarts) {
    const end = itemRange(lines, start, sections.end, eIndent).end;
    const block = lines.slice(start, end).join("\n");
    const idMatch = /- id:\s*(\S+)/.exec(block);
    const edge = idMatch ? graph.edges.find((item) => item.id === idMatch[1]) : undefined;
    if (edge && (edge.source === nodeId || edge.target === nodeId)) toRemove.push({ start, end });
  }
  toRemove.sort((a, b) => b.start - a.start);
  for (const range of toRemove) lines.splice(range.start, range.end - range.start);

  let next = lines.join("\n");

  if (incoming.length === 1 && outgoing.length === 1) {
    const before = incoming[0];
    const after = outgoing[0];
    if (before && after && before.source !== after.target) {
      try {
        next = connect(next, { source: before.source, target: after.target, sourceHandle: before.sourceHandle });
      } catch {
        /* 接不上就保留断开的图，交给用户手动连 */
      }
    }
  }

  const result = graphOf(parse(next) as unknown);
  if (result.nodes.some((item) => item.id === nodeId)) throw new YamlEditError("删除节点写回失败");
  if (result.edges.some((edge) => edge.source === nodeId || edge.target === nodeId)) throw new YamlEditError("删除连线写回失败");
  return next;
}

/** 连一条边；if-else 默认走 false 分支。 */
export function connect(raw: string, spec: EdgeSpec): string {
  const doc = parse(raw) as unknown;
  const graph = graphOf(doc);
  const source = graph.nodes.find((node) => node.id === spec.source);
  const target = graph.nodes.find((node) => node.id === spec.target);
  if (!source || !target) throw new YamlEditError("连线端点不存在");
  if (source.id === target.id) throw new YamlEditError("不能连自己");
  const sourceType = String(flatten(source.data)["type"] ?? "custom");
  const targetType = String(flatten(target.data)["type"] ?? "custom");
  const sourceHandle = spec.sourceHandle ?? (sourceType === "if-else" ? "false" : "source");
  if (graph.edges.some((edge) => edge.source === source.id && edge.target === target.id && (edge.sourceHandle ?? "") === sourceHandle)) {
    throw new YamlEditError("这条线已经存在");
  }

  const flags = nodeFlags(flatten(source.data));
  const lines = raw.split("\n");
  const edgesSection = sectionRange(lines, "edges");
  const indent = itemIndent(lines, edgesSection);
  const id = uniqueEdgeId(graph.edges, `${source.id}-${sourceHandle}-${target.id}`);
  insertEdge(lines, {
    id,
    source: source.id,
    sourceHandle,
    target: target.id,
    targetHandle: "target",
    sourceType,
    targetType,
    flags,
  }, indent);
  const next = lines.join("\n");
  const after = graphOf(parse(next) as unknown);
  if (!after.edges.some((edge) => edge.id === id)) throw new YamlEditError("连线写回失败");
  return next;
}

/** 删一条边。 */
export function removeEdge(raw: string, edgeId: string): string {
  const doc = parse(raw) as unknown;
  const graph = graphOf(doc);
  if (!graph.edges.some((edge) => edge.id === edgeId)) throw new YamlEditError(`找不到连线 ${edgeId}`);
  const lines = raw.split("\n");
  const section = sectionRange(lines, "edges");
  const indent = itemIndent(lines, section);
  const starts: number[] = [];
  for (let index = section.start + 1; index < section.end; index += 1) {
    if (leadingSpaces(lines[index] as string) === indent && /^\s*- id:\s*/.test(lines[index] as string)) starts.push(index);
  }
  for (const start of starts) {
    const end = itemRange(lines, start, section.end, indent).end;
    if (/^\s*- id:\s*(\S+)/.exec(lines[start] as string)?.[1] === edgeId) {
      lines.splice(start, end - start);
      break;
    }
  }
  const next = lines.join("\n");
  if (graphOf(parse(next) as unknown).edges.some((edge) => edge.id === edgeId)) throw new YamlEditError("删除连线写回失败");
  return next;
}

/** 移动节点：只改 position / positionAbsolute 的 x、y 四行。 */
export function moveNode(raw: string, nodeId: string, position: { x: number; y: number }): string {
  const lines = raw.split("\n");
  const { start, end } = nodeBlockRange(lines, nodeId);
  let changed = 0;
  for (let index = start; index < end; index += 1) {
    if (!/^\s*(position|positionAbsolute):\s*$/.test(lines[index] as string)) continue;
    for (let cursor = index + 1; cursor < Math.min(index + 4, end); cursor += 1) {
      const line = lines[cursor] as string;
      const match = /^(\s*)(x|y):\s*(-?[\d.]+)\s*$/.exec(line);
      if (!match) continue;
      lines[cursor] = `${match[1]}${match[2]}: ${match[2] === "x" ? Math.round(position.x) : Math.round(position.y)}`;
      changed += 1;
    }
  }
  if (changed < 2) throw new YamlEditError(`节点 ${nodeId} 没有可写的 position`);
  const next = lines.join("\n");
  const after = parse(next) as { workflow: { graph: { nodes: Array<{ id: string; position?: { x: number; y: number } }> } } };
  const node = after.workflow.graph.nodes.find((item) => item.id === nodeId);
  if (!node?.position || Math.round(node.position.x) !== Math.round(position.x) || Math.round(node.position.y) !== Math.round(position.y)) {
    throw new YamlEditError("位置写回校验失败");
  }
  return next;
}
