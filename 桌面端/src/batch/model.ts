/**
 * 批量运行里跟界面无关的纯逻辑：并发闸门、项目命名、审阅续跑。
 * 放在 src/ 下是为了能被 node:test 直接覆盖（渲染层不进 dist 的类型检查）。
 */

const INVALID_NAME = /[/\\:*?"<>|\u0000-\u001f]/g;

export interface VariableLike {
  variable: string;
  type?: string;
  required?: boolean;
}

/** 一行批量里「主输入」的变量名：优先 campaign_brief，否则第一个必填文本变量。 */
export function primaryVariable(variables: VariableLike[]): string | null {
  if (!variables.length) return null;
  const brief = variables.find((item) => item.variable === "campaign_brief");
  if (brief) return brief.variable;
  const textLike = (item: VariableLike) => !item.type || item.type === "paragraph" || item.type === "text-input";
  const text = variables.find((item) => item.required && textLike(item)) ?? variables.find(textLike);
  return text?.variable ?? null;
}

/** 主题 → 项目名主干：取第一行、去掉路径字符和空白，限长，避免文件名过长。 */
export function cleanTopicName(topic: string): string {
  const first =
    String(topic ?? "")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .find(Boolean) ?? "";
  return first.replace(INVALID_NAME, "").replace(/\s+/g, "").slice(0, 16);
}

/** 和成品目录现有命名一致：`名字20261125-1056`；没有主题就给序号兜底。 */
export function autoProjectName(topic: string, index: number, when: Date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, "0");
  const stamp = `${when.getFullYear()}${pad(when.getMonth() + 1)}${pad(when.getDate())}-${pad(when.getHours())}${pad(when.getMinutes())}`;
  const base = cleanTopicName(topic) || `批量${pad(index + 1)}`;
  return `${base}${stamp}`;
}

/** 同一批里重名（同名主题、同一分钟）就加 -2/-3；四个 04 同时跑不会撞同一个成品目录。 */
export function uniqueProjectName(base: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  if (!used.has(base)) return base;
  for (let index = 2; index < 1000; index += 1) {
    const candidate = `${base}-${index}`;
    if (!used.has(candidate)) return candidate;
  }
  return `${base}-${Date.now()}`;
}

/** 并发闸门：还能再起几个。active 是正在跑的，limit 是上限（1–4）。 */
export function startableCount(queued: number, active: number, limit: number): number {
  return Math.max(0, Math.min(queued, limit - active));
}

export interface NodeRecordLike {
  nodeId: string;
  type?: string;
  status?: string;
  outputs?: Record<string, unknown>;
}

/** 审阅续跑用：把已经成功的 LLM/代码节点输出喂回去，不再重新请求。 */
export function precomputedFrom(result: { nodes?: NodeRecordLike[] } | null | undefined): Record<string, Record<string, unknown>> {
  const precomputed: Record<string, Record<string, unknown>> = {};
  for (const node of result?.nodes ?? []) {
    if ((node.type === "llm" || node.type === "code") && node.status === "success" && node.outputs) {
      precomputed[node.nodeId] = node.outputs;
    }
  }
  return precomputed;
}

/** 出片需要的两样东西都在，才算「可出片」。 */
export function hasProducibleOutput(outputs: Record<string, unknown> | undefined): boolean {
  return typeof outputs?.html_document === "string" && typeof outputs?.voiceover_script === "string";
}

/** 入口列表清洗：去掉空条目，保持顺序。 */
export function cleanRequirements(items: Iterable<string>): string[] {
  return [...items].map((item) => String(item ?? "").trim()).filter(Boolean);
}
