import type { DslNode, Selector, TokenUsage } from "./types.js";

/** 节点输出里跟 Dify 一样会出现的元字段。 */
export interface NodeOutputs {
  [key: string]: unknown;
}

export interface NodeResultMeta {
  usage?: TokenUsage;
  ms?: number;
  protocol?: string;
}

export class VariablePool {
  private readonly outputs = new Map<string, NodeOutputs>();
  private readonly sys: Record<string, unknown>;

  constructor(
    private readonly env: Record<string, string> = {},
    sys: Record<string, unknown> = {},
  ) {
    this.sys = { ...sys };
  }

  setNodeOutputs(nodeId: string, outputs: NodeOutputs): void {
    this.outputs.set(nodeId, { ...outputs });
  }

  mergeNodeOutputs(nodeId: string, patch: NodeOutputs): void {
    this.outputs.set(nodeId, { ...(this.outputs.get(nodeId) ?? {}), ...patch });
  }

  getNodeOutputs(nodeId: string): NodeOutputs | undefined {
    return this.outputs.get(nodeId);
  }

  get(selector: Selector | undefined): unknown {
    if (!selector || selector.length < 2) return undefined;
    const [scope, field] = selector as [string, string];
    if (scope === "sys") return this.sys[field];
    if (scope === "env") return this.env[field];
    return this.outputs.get(scope)?.[field];
  }

  has(selector: Selector | undefined): boolean {
    if (!selector || selector.length < 2) return false;
    const [scope, field] = selector as [string, string];
    if (scope === "sys") return field in this.sys;
    if (scope === "env") return field in this.env;
    const node = this.outputs.get(scope);
    return node !== undefined && field in node;
  }

  sysValue(name: string): unknown {
    return this.sys[name];
  }

  clone(): VariablePool {
    const copy = new VariablePool(this.env, this.sys);
    for (const [key, value] of this.outputs) copy.outputs.set(key, { ...value });
    return copy;
  }

  snapshot(): Record<string, NodeOutputs> {
    return Object.fromEntries([...this.outputs.entries()].map(([id, outputs]) => [id, { ...outputs }]));
  }
}

/** Dify 把非字符串值转成字符串的规则：null/undefined → 空，对象 → JSON，布尔 → true/false。 */
export function stringValue(value: unknown): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") return String(value);
  if (Array.isArray(value) || typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

/** 按节点变量声明的 value_type 做一次宽松的类型还原。 */
export function coerceByType(value: unknown, valueType: string | undefined, fallback: unknown = value): unknown {
  switch (valueType) {
    case "string":
      return stringValue(value);
    case "number": {
      const num = typeof value === "number" ? value : Number(stringValue(value));
      return Number.isFinite(num) ? num : 0;
    }
    case "boolean": {
      if (typeof value === "boolean") return value;
      const text = stringValue(value).trim().toLowerCase();
      return text === "true" || text === "1";
    }
    case "object":
      return value ?? {};
    case "array":
      return Array.isArray(value) ? value : [];
    default: {
      const type = String(valueType ?? "");
      if (type.startsWith("array")) return Array.isArray(value) ? value : [];
      if (type.startsWith("object")) return value ?? {};
      return value ?? fallback;
    }
  }
}

export function collectNodeOutputs(node: DslNode, values: Record<string, unknown>): NodeOutputs {
  const definitions = node.data.outputs;
  if (!Array.isArray(definitions)) return values;
  const result: NodeOutputs = {};
  for (const definition of definitions as Record<string, unknown>[]) {
    const name = typeof definition["variable"] === "string" ? definition["variable"] : undefined;
    if (!name) continue;
    if (name in values) result[name] = values[name];
  }
  return result;
}
