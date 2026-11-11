import type { DslNode, OutputDefinition, TokenUsage, VariableDefinition } from "./types.js";
import type { ProviderConfig } from "./config.js";
import type { VariablePool } from "./vars.js";
import { coerceByType, stringValue } from "./vars.js";
import { complete } from "./llm.js";
import type { ChatMessage } from "./llm.js";
import { difySelectors, interpolateDify, renderTemplateJinja } from "./template.js";
import { runPythonCode } from "./code.js";

export interface StubSource {
  get(nodeId: string): string | undefined;
}

export interface ExecuteContext {
  node: DslNode;
  pool: VariablePool;
  provider: ProviderConfig;
  inputs?: Record<string, unknown>;
  stub?: StubSource;
  codeTimeoutMs?: number;
  env?: Record<string, string>;
}

export interface ExecuteResult {
  outputs: Record<string, unknown>;
  nextHandle?: string;
  usage?: TokenUsage;
  ms?: number;
  protocol?: string;
}

export class NodeNotImplementedError extends Error {
  constructor(
    readonly nodeType: string,
    readonly nodeId: string,
  ) {
    super(`节点类型未实现：${nodeType}`);
    this.name = "NodeNotImplementedError";
  }
}

export class NodeExecutionError extends Error {
  constructor(
    readonly nodeId: string,
    readonly nodeType: string,
    message: string,
  ) {
    super(message);
    this.name = "NodeExecutionError";
  }
}

/** 节点声明的输入变量 → 按 value_type 从变量池取值。 */
function nodeArguments(node: DslNode, pool: VariablePool): Record<string, unknown> {
  const args: Record<string, unknown> = {};
  const definitions = Array.isArray(node.data.variables) ? (node.data.variables as VariableDefinition[]) : [];
  for (const definition of definitions) {
    if (!definition.variable) continue;
    const raw = pool.get(definition.value_selector);
    args[definition.variable] = coerceByType(raw, definition.value_type, "");
  }
  return args;
}

function declaredOutputType(node: DslNode, name: string): string | undefined {
  const outputs = node.data.outputs;
  if (!Array.isArray(outputs)) return undefined;
  const found = (outputs as Record<string, unknown>[]).find((item) => item["variable"] === name);
  return typeof found?.["value_type"] === "string" ? String(found["value_type"]) : undefined;
}

function llmMessages(node: DslNode, pool: VariablePool): ChatMessage[] {
  const template = Array.isArray(node.data.prompt_template) ? (node.data.prompt_template as Array<Record<string, unknown>>) : [];
  const messages: ChatMessage[] = [];
  for (const item of template) {
    const role = String(item["role"] ?? "user");
    const text = interpolateDify(String(item["text"] ?? ""), pool);
    if (role === "system" || role === "user" || role === "assistant") messages.push({ role, content: text });
  }
  if (messages.length === 0) messages.push({ role: "user", content: "" });
  return messages;
}

function normalizeCompare(value: unknown, varType: string | undefined): unknown {
  if (varType === "boolean") {
    if (typeof value === "boolean") return value;
    const text = stringValue(value).trim().toLowerCase();
    return text === "true" || text === "1";
  }
  if (varType === "number") {
    const num = typeof value === "number" ? value : Number(stringValue(value));
    return Number.isFinite(num) ? num : 0;
  }
  if (varType === "array" || varType === "object") return value;
  return stringValue(value).trim();
}

function looseEqual(left: unknown, right: unknown): boolean {
  if (left === right) return true;
  if (typeof left === "boolean" || typeof right === "boolean") {
    return String(left).toLowerCase() === String(right).toLowerCase();
  }
  if (typeof left === "number" || typeof right === "number") {
    const a = Number(left);
    const b = Number(right);
    return Number.isFinite(a) && Number.isFinite(b) && a === b;
  }
  return stringValue(left) === stringValue(right);
}

export function evaluateCondition(condition: Record<string, unknown>, pool: VariablePool): boolean {
  const selector = condition["variable_selector"];
  if (!Array.isArray(selector)) return false;
  const operator = String(condition["comparison_operator"] ?? "is").trim().toLowerCase();
  const varType = typeof condition["varType"] === "string" ? String(condition["varType"]) : undefined;
  const left = normalizeCompare(pool.get(selector as string[]), varType);
  const rightRaw = condition["value"];
  const right = normalizeCompare(rightRaw, varType);

  switch (operator) {
    case "is":
    case "=":
    case "equals":
      return looseEqual(left, right);
    case "is not":
    case "≠":
    case "not equals":
      return !looseEqual(left, right);
    case "contains":
      return stringValue(left).includes(stringValue(right));
    case "not contains":
      return !stringValue(left).includes(stringValue(right));
    case "start with":
    case "starts with":
      return stringValue(left).startsWith(stringValue(right));
    case "end with":
    case "ends with":
      return stringValue(left).endsWith(stringValue(right));
    case "is empty":
    case "empty":
      return stringValue(left).trim() === "";
    case "is not empty":
    case "not empty":
      return stringValue(left).trim() !== "";
    case "null":
      return left === null || left === undefined;
    case "not null":
      return left !== null && left !== undefined;
    case "in": {
      const list = Array.isArray(rightRaw) ? rightRaw : String(stringValue(rightRaw)).split(",");
      return list.some((item) => looseEqual(left, normalizeCompare(item, varType)));
    }
    case "not in": {
      const list = Array.isArray(rightRaw) ? rightRaw : String(stringValue(rightRaw)).split(",");
      return !list.some((item) => looseEqual(left, normalizeCompare(item, varType)));
    }
    case ">":
      return Number(left) > Number(right);
    case "<":
      return Number(left) < Number(right);
    case "≥":
    case ">=":
      return Number(left) >= Number(right);
    case "≤":
    case "<=":
      return Number(left) <= Number(right);
    default:
      throw new Error(`不支持的条件运算符：${operator}`);
  }
}

export function evaluateConditions(
  conditions: Record<string, unknown>[],
  pool: VariablePool,
  logicalOperator: string | undefined,
): boolean {
  if (conditions.length === 0) return false;
  const results = conditions.map((condition) => evaluateCondition(condition, pool));
  return String(logicalOperator ?? "and").toLowerCase() === "or" ? results.some(Boolean) : results.every(Boolean);
}

function evaluateIfElse(node: DslNode, pool: VariablePool): string {
  const cases = Array.isArray(node.data.cases) ? (node.data.cases as Array<Record<string, unknown>>) : [];
  for (const item of cases) {
    const conditions = Array.isArray(item["conditions"]) ? (item["conditions"] as Record<string, unknown>[]) : [];
    const operator = String(item["logical_operator"] ?? "and").toLowerCase();
    const results = conditions.map((condition) => evaluateCondition(condition, pool));
    const matched = operator === "or" ? results.some(Boolean) : results.every(Boolean);
    if (matched && conditions.length > 0) {
      return String(item["case_id"] ?? item["id"] ?? "");
    }
  }
  return "false";
}

async function executeHttp(node: DslNode, pool: VariablePool): Promise<ExecuteResult> {
  const interpolate = (value: unknown) => (typeof value === "string" ? interpolateDify(value, pool) : value);
  const method = String(node.data["method"] ?? "get").toUpperCase();
  const url = interpolate(node.data["url"]);
  const headers: Record<string, string> = {};
  const headerText = String(node.data["headers"] ?? "");
  for (const line of headerText.split(/\r?\n/)) {
    const index = line.indexOf(":");
    if (index > 0) headers[interpolate(line.slice(0, index).trim()) as string] = interpolate(line.slice(index + 1).trim()) as string;
  }
  const paramsText = String(node.data["params"] ?? "");
  const query = new URLSearchParams();
  for (const line of paramsText.split(/\r?\n/)) {
    const index = line.indexOf(":");
    if (index > 0) query.set(line.slice(0, index).trim(), String(interpolate(line.slice(index + 1).trim())));
  }
  const bodyConfig = node.data["body"] as Record<string, unknown> | undefined;
  let body: string | undefined;
  if (bodyConfig && bodyConfig["type"] === "raw-text") {
    const data = Array.isArray(bodyConfig["data"]) ? (bodyConfig["data"] as Record<string, unknown>[]) : [];
    body = data.map((item) => String(interpolate(item["value"])).trim()).join("\n");
  } else if (bodyConfig && bodyConfig["type"] === "json") {
    const data = Array.isArray(bodyConfig["data"]) ? (bodyConfig["data"] as Record<string, unknown>[]) : [];
    const object: Record<string, unknown> = {};
    for (const item of data) {
      const key = String(item["key"] ?? "");
      if (key) object[key] = interpolate(item["value"]);
    }
    body = JSON.stringify(object);
    headers["content-type"] = headers["content-type"] ?? "application/json";
  }
  const fullUrl = query.size > 0 ? `${String(url)}${String(url).includes("?") ? "&" : "?"}${query.toString()}` : String(url);
  const timeout = Number((node.data["timeout"] as Record<string, unknown> | undefined)?.["max_read_timeout"] ?? 60) * 1000;
  const response = await fetch(fullUrl, { method, headers, body, signal: AbortSignal.timeout(timeout) });
  const text = await response.text();
  return {
    outputs: {
      body: text,
      status_code: response.status,
      headers: Object.fromEntries(response.headers.entries()),
    },
  };
}

export async function executeNode(context: ExecuteContext): Promise<ExecuteResult> {
  const { node, pool, provider } = context;
  const type = node.data.type;

  try {
    switch (type) {
      case "start": {
        const outputs = { ...(context.inputs ?? {}) };
        return { outputs };
      }

      case "llm": {
        const messages = llmMessages(node, pool);
        if (provider.stub) {
          const text = context.stub?.get(node.id);
          if (text === undefined) throw new Error(`--stub 缺少节点 ${node.id} 的输出 fixture`);
          return { outputs: { text, files: [], usage: {} }, protocol: "stub" };
        }
        const params = (node.data["model"] as Record<string, unknown> | undefined)?.["completion_params"] as
          | Record<string, unknown>
          | undefined;
        const maxTokens = params?.["max_tokens"] !== undefined ? Number(params["max_tokens"]) : undefined;
        const started = Date.now();
        const result = await complete(provider, messages, { maxTokens });
        return {
          outputs: { text: result.text, files: [], usage: result.usage ?? {} },
          usage: result.usage,
          ms: Date.now() - started,
          protocol: result.protocol,
        };
      }

      case "code": {
        const args = nodeArguments(node, pool);
        const started = Date.now();
        const result = await runPythonCode({
          code: String(node.data["code"] ?? ""),
          args,
          timeoutMs: context.codeTimeoutMs,
          ...(process.env.WF_PYTHON ? { python: process.env.WF_PYTHON } : {}),
        });
        const outputs: Record<string, unknown> = {};
        for (const [name, value] of Object.entries(result.outputs)) {
          outputs[name] = coerceByType(value, declaredOutputType(node, name), value);
        }
        return { outputs, ms: result.ms || Date.now() - started };
      }

      case "if-else": {
        return { outputs: {}, nextHandle: evaluateIfElse(node, pool) };
      }

      case "template-transform": {
        const variables: Record<string, unknown> = {};
        const definitions = Array.isArray(node.data["variables"]) ? (node.data["variables"] as VariableDefinition[]) : [];
        for (const definition of definitions) {
          if (definition.variable) variables[definition.variable] = pool.get(definition.value_selector);
        }
        const output = renderTemplateJinja(String(node.data["template"] ?? ""), variables);
        return { outputs: { output } };
      }

      case "http-request":
        return await executeHttp(node, pool);

      case "end": {
        const outputs: Record<string, unknown> = {};
        const definitions = Array.isArray(node.data["outputs"]) ? (node.data["outputs"] as OutputDefinition[]) : [];
        for (const definition of definitions) {
          outputs[definition.variable] = coerceByType(
            pool.get(definition.value_selector),
            definition.value_type,
            undefined,
          );
        }
        return { outputs };
      }

      case "iteration-start":
      case "loop-start":
        return { outputs: {} };

      case "assigner": {
        const items = Array.isArray(node.data["items"]) ? (node.data["items"] as Record<string, unknown>[]) : [];
        for (const item of items) {
          const target = item["variable_selector"];
          if (!Array.isArray(target) || target.length < 2) continue;
          const [scope, field] = target as [string, string];
          const inputType = String(item["input_type"] ?? "variable");
          const value =
            inputType === "constant"
              ? item["value"]
              : pool.get(Array.isArray(item["value"]) ? (item["value"] as string[]) : undefined);
          if (item["operation"] === "over-write" || item["operation"] === undefined) {
            pool.mergeNodeOutputs(scope, { [field]: value });
          } else if (item["operation"] === "append") {
            const existing = pool.getNodeOutputs(scope)?.[field];
            const list = Array.isArray(existing) ? existing : [];
            pool.mergeNodeOutputs(scope, { [field]: [...list, value] });
          } else if (item["operation"] === "clear") {
            pool.mergeNodeOutputs(scope, { [field]: [] });
          }
        }
        return { outputs: {} };
      }

      case "iteration":
      case "loop":
        throw new NodeNotImplementedError(type, node.id);

      default:
        throw new NodeNotImplementedError(type, node.id);
    }
  } catch (error) {
    if (error instanceof NodeNotImplementedError) throw error;
    throw new NodeExecutionError(node.id, type, (error as Error).message);
  }
}

export function selectorsUsedBy(node: DslNode): string[][] {
  const text = JSON.stringify(node.data);
  return difySelectors(text);
}
