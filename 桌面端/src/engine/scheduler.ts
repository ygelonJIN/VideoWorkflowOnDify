import type { DslNode, NodeStatus, TokenUsage } from "./types.js";
import type { LoadedWorkflow } from "./dsl.js";
import { environmentValues, nodeTitle, nodeType, startNode, startVariables } from "./dsl.js";
import type { ProviderConfig } from "./config.js";
import { VariablePool } from "./vars.js";
import type { ExecuteResult, StubSource } from "./executors.js";
import { evaluateConditions, executeNode, NodeExecutionError, NodeNotImplementedError } from "./executors.js";
import { TraceRecorder } from "./trace.js";
import type { TraceEvent } from "./trace.js";

export interface RunOptions {
  inputs: Record<string, unknown>;
  provider: ProviderConfig;
  env?: Record<string, string>;
  sys?: Record<string, unknown>;
  stub?: StubSource;
  until?: string;
  maxSteps?: number;
  codeTimeoutMs?: number;
  onEvent?: (event: TraceEvent) => void;
}

export interface NodeRunRecord {
  nodeId: string;
  type: string;
  title: string;
  status: NodeStatus;
  ms: number;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  usage?: TokenUsage;
  nextHandle?: string;
  error?: string;
}

export type RunStatus = "success" | "error" | "unimplemented" | "stopped";

export interface RunResult {
  runId: string;
  status: RunStatus;
  ms: number;
  nodes: NodeRunRecord[];
  outputs: Record<string, unknown>;
  outputsByNode: Record<string, Record<string, unknown>>;
  trace: TraceEvent[];
  warnings: string[];
  error?: string;
}

interface RunContext {
  workflow: LoadedWorkflow;
  pool: VariablePool;
  options: RunOptions;
  records: NodeRunRecord[];
  statuses: Map<string, NodeStatus>;
  outputsByNode: Record<string, Record<string, unknown>>;
  endOutputs: Record<string, unknown>;
  lastExecuted?: string;
  steps: number;
  maxSteps: number;
  emit: (event: Omit<TraceEvent, "seq" | "at">) => void;
}

class StopRun extends Error {
  constructor(
    readonly status: RunStatus,
    message: string,
  ) {
    super(message);
    this.name = "StopRun";
  }
}

function belongsTo(node: DslNode, containerId: string | undefined): boolean {
  const iterationId = node.data["iteration_id"];
  const loopId = node.data["loop_id"];
  if (containerId === undefined) return !iterationId && !loopId;
  return iterationId === containerId || loopId === containerId;
}

function resolveNextNodeIds(
  workflow: LoadedWorkflow,
  nodeId: string,
  handle: string | undefined,
  containerId: string | undefined,
): string[] {
  return workflow.edges
    .filter((edge) => {
      if (edge.source !== nodeId) return false;
      if (handle !== undefined) return (edge.sourceHandle ?? "") === handle;
      const sourceHandle = edge.sourceHandle ?? "";
      return sourceHandle === "" || sourceHandle === "source";
    })
    .map((edge) => edge.target)
    .filter((target) => {
      const node = workflow.nodes.get(target);
      return node !== undefined && belongsTo(node, containerId);
    });
}

async function executeOne(ctx: RunContext, node: DslNode): Promise<ExecuteResult> {
  const record: NodeRunRecord = {
    nodeId: node.id,
    type: nodeType(node),
    title: nodeTitle(node),
    status: "running",
    ms: 0,
  };
  ctx.records.push(record);
  ctx.statuses.set(node.id, "running");
  ctx.emit({ type: "node_start", nodeId: node.id, nodeType: record.type, title: record.title });
  const started = Date.now();

  try {
    let result: ExecuteResult;
    if (node.data.type === "iteration") {
      result = { outputs: await executeIteration(ctx, node) };
    } else if (node.data.type === "loop") {
      result = { outputs: await executeLoop(ctx, node) };
    } else {
      result = await executeNode({
        node,
        pool: ctx.pool,
        provider: ctx.options.provider,
        inputs: ctx.options.inputs,
        ...(ctx.options.stub ? { stub: ctx.options.stub } : {}),
        ...(ctx.options.codeTimeoutMs !== undefined ? { codeTimeoutMs: ctx.options.codeTimeoutMs } : {}),
        ...(ctx.options.env ? { env: ctx.options.env } : {}),
      });
    }

    record.ms = result.ms ?? Date.now() - started;
    record.status = "success";
    record.outputs = result.outputs;
    record.usage = result.usage;
    record.nextHandle = result.nextHandle;
    ctx.statuses.set(node.id, "success");
    ctx.pool.setNodeOutputs(node.id, result.outputs);
    ctx.outputsByNode[node.id] = result.outputs;
    ctx.lastExecuted = node.id;
    ctx.emit({
      type: "node_end",
      nodeId: node.id,
      nodeType: record.type,
      title: record.title,
      status: "success",
      ms: record.ms,
      ...(result.usage ? { usage: result.usage } : {}),
      ...(result.nextHandle !== undefined ? { nextHandle: result.nextHandle } : {}),
    });
    return result;
  } catch (error) {
    record.ms = Date.now() - started;
    if (error instanceof NodeNotImplementedError) {
      record.status = "unimplemented";
      record.error = error.message;
      ctx.statuses.set(node.id, "unimplemented");
      ctx.emit({ type: "node_error", nodeId: node.id, nodeType: record.type, title: record.title, status: "unimplemented", error: record.error });
      throw new StopRun("unimplemented", `${error.message}（节点 ${node.title} / ${node.id}）`);
    }
    record.status = "error";
    record.error = error instanceof NodeExecutionError ? error.message : (error as Error).message;
    ctx.statuses.set(node.id, "error");
    ctx.emit({ type: "node_error", nodeId: node.id, nodeType: record.type, title: record.title, status: "error", error: record.error });
    throw new StopRun("error", `${record.title} 执行失败：${record.error}`);
  }
}

async function executeIteration(ctx: RunContext, node: DslNode): Promise<Record<string, unknown>> {
  const selector = node.data["iterator_selector"];
  const rawItems = ctx.pool.get(Array.isArray(selector) ? (selector as string[]) : undefined);
  let items: unknown[] = [];
  if (Array.isArray(rawItems)) {
    items = rawItems;
  } else if (typeof rawItems === "string") {
    try {
      const parsed: unknown = JSON.parse(rawItems);
      if (Array.isArray(parsed)) items = parsed;
    } catch {
      items = [];
    }
  }
  const startId = String(node.data["start_node_id"] ?? "");
  const outputSelector = Array.isArray(node.data["output_selector"]) ? (node.data["output_selector"] as string[]) : undefined;
  const mode = String(node.data["error_handle_mode"] ?? "terminated");
  const parallel = node.data["is_parallel"] === true;
  const parallelNums = Math.max(1, Number(node.data["parallel_nums"] ?? 10));

  const runItem = async (item: unknown, index: number, pool: VariablePool, sink: RunContext): Promise<unknown> => {
    pool.mergeNodeOutputs(node.id, { item, index });
    try {
      await runContainer(sink, [startId], node.id);
    } catch (error) {
      if (error instanceof StopRun && error.status === "unimplemented") throw error;
      if (mode === "continue-on-error") return null;
      if (mode === "remove-abnormal-output") return undefined;
      throw error;
    }
    return pool.get(outputSelector);
  };

  if (parallel && items.length > 1) {
    const outputs: unknown[] = [];
    for (let offset = 0; offset < items.length; offset += parallelNums) {
      const chunk = items.slice(offset, offset + parallelNums);
      const results = await Promise.all(
        chunk.map(async (item, localIndex) => {
          const index = offset + localIndex;
          const pool = ctx.pool.clone();
          const sink: RunContext = { ...ctx, pool, records: [], statuses: new Map() };
          const value = await runItem(item, index, pool, sink);
          ctx.records.push(...sink.records);
          for (const [key, status] of sink.statuses) ctx.statuses.set(key, status);
          return value;
        }),
      );
      outputs.push(...results.filter((value) => value !== undefined));
    }
    return { output: outputs };
  }

  const outputs: unknown[] = [];
  for (let index = 0; index < items.length; index += 1) {
    const value = await runItem(items[index], index, ctx.pool, ctx);
    if (value !== undefined) outputs.push(value);
  }
  return { output: outputs };
}

async function executeLoop(ctx: RunContext, node: DslNode): Promise<Record<string, unknown>> {
  const variables = Array.isArray(node.data["loop_variables"]) ? (node.data["loop_variables"] as Record<string, unknown>[]) : [];
  const initial: Record<string, unknown> = {};
  for (const variable of variables) {
    const label = String(variable["label"] ?? variable["id"] ?? "");
    if (label) initial[label] = variable["value"] ?? "";
  }
  ctx.pool.mergeNodeOutputs(node.id, initial);

  const startId = String(node.data["start_node_id"] ?? "");
  const loopCount = Math.max(1, Number(node.data["loop_count"] ?? 10));
  const breakConditions = Array.isArray(node.data["break_conditions"])
    ? (node.data["break_conditions"] as Record<string, unknown>[])
    : [];
  const logicalOperator = typeof node.data["logical_operator"] === "string" ? String(node.data["logical_operator"]) : undefined;

  let round = 0;
  for (; round < loopCount; round += 1) {
    await runContainer(ctx, [startId], node.id);
    if (evaluateConditions(breakConditions, ctx.pool, logicalOperator)) {
      round += 1;
      break;
    }
  }
  return { ...(ctx.pool.getNodeOutputs(node.id) ?? {}), loop_round: round };
}

async function runContainer(ctx: RunContext, startIds: string[], containerId: string | undefined): Promise<"done" | "stopped"> {
  const queue = [...startIds];
  const visited = new Set<string>();
  while (queue.length > 0) {
    const nodeId = queue.shift();
    if (!nodeId) break;
    const node = ctx.workflow.nodes.get(nodeId);
    if (!node || !belongsTo(node, containerId)) continue;
    if (visited.has(nodeId)) continue;
    visited.add(nodeId);
    ctx.steps += 1;
    if (ctx.steps > ctx.maxSteps) throw new StopRun("error", `超过最大节点步数 ${ctx.maxSteps}`);
    if (node.data.type === "iteration-start" || node.data.type === "loop-start") {
      // 容器入口占位节点：不执行、不上报，但要把出边接上
      for (const nextId of resolveNextNodeIds(ctx.workflow, nodeId, undefined, containerId)) {
        if (!visited.has(nextId)) queue.push(nextId);
      }
    } else {
      const result = await executeOne(ctx, node);
      if (node.data.type === "end" && containerId === undefined) {
        for (const [key, value] of Object.entries(result.outputs)) ctx.endOutputs[key] = value;
        continue;
      }
      if (containerId === undefined && ctx.options.until === nodeId) return "stopped";
      for (const nextId of resolveNextNodeIds(ctx.workflow, nodeId, result.nextHandle, containerId)) {
        if (!visited.has(nextId)) queue.push(nextId);
      }
    }
  }
  return "done";
}

export async function runGraph(workflow: LoadedWorkflow, options: RunOptions): Promise<RunResult> {
  const started = Date.now();
  const runId = `run-${new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14)}-${Math.random().toString(36).slice(2, 6)}`;
  const trace = new TraceRecorder();
  const emit = (event: Parameters<TraceRecorder["emit"]>[0]) => {
    const full = trace.emit(event);
    options.onEvent?.(full);
  };

  const env = environmentValues(workflow, options.env ?? {});
  const pool = new VariablePool(env, {
    workflow_run_id: runId,
    user_id: options.sys?.["user_id"] ?? "local",
    ...options.sys,
  });

  const start = startNode(workflow);
  const variables = startVariables(start);
  const missing = variables.filter((item) => item.required && !(item.variable in options.inputs));
  if (missing.length > 0) throw new Error(`缺少必填输入：${missing.map((item) => item.variable).join("、")}`);
  for (const item of variables) {
    if (!(item.variable in options.inputs)) options.inputs[item.variable] = "";
  }

  const ctx: RunContext = {
    workflow,
    pool,
    options,
    records: [],
    statuses: new Map(),
    outputsByNode: {},
    endOutputs: {},
    steps: 0,
    maxSteps: options.maxSteps ?? 500,
    emit,
  };

  emit({ type: "run_start", nodeId: start.id, nodeType: "start", title: nodeTitle(start) });

  let status: RunStatus = "success";
  let error: string | undefined;
  try {
    const outcome = await runContainer(ctx, [start.id], undefined);
    if (outcome === "stopped") status = "stopped";
  } catch (stop) {
    if (stop instanceof StopRun) {
      status = stop.status;
      error = stop.message;
    } else {
      status = "error";
      error = (stop as Error).message;
    }
  }

  const ms = Date.now() - started;
  const outputs = Object.keys(ctx.endOutputs).length > 0
    ? ctx.endOutputs
    : ctx.lastExecuted
      ? (ctx.outputsByNode[ctx.lastExecuted] ?? {})
      : {};
  emit({ type: "run_end", status, ms, ...(error ? { error } : {}) });

  return {
    runId,
    status,
    ms,
    nodes: ctx.records,
    outputs,
    outputsByNode: ctx.outputsByNode,
    trace: trace.events,
    warnings: workflow.warnings,
    ...(error ? { error } : {}),
  };
}
