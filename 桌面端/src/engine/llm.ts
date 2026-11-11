import type { ProviderConfig } from "./config.js";
import type { TokenUsage } from "./types.js";

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface LlmResult {
  text: string;
  usage?: TokenUsage;
  protocol: string;
  status: number;
  raw: unknown;
}

export class LlmError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly body?: string,
  ) {
    super(message);
    this.name = "LlmError";
  }
}

const RETRY_STATUS = new Set([408, 429, 500, 502, 503, 504, 529]);

function extractChatText(body: unknown): string {
  const choices = (body as { choices?: Array<{ message?: { content?: unknown } }> })?.choices;
  const content = choices?.[0]?.message?.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => (part && typeof part === "object" && "text" in part ? String((part as { text?: unknown }).text ?? "") : ""))
      .join("");
  }
  return "";
}

function extractResponsesText(body: unknown): string {
  const typed = body as {
    output_text?: unknown;
    output?: Array<{ type?: string; content?: Array<{ type?: string; text?: unknown }> }>;
  };
  if (typeof typed.output_text === "string") return typed.output_text;
  const pieces: string[] = [];
  for (const item of typed.output ?? []) {
    for (const part of item.content ?? []) {
      if (typeof part.text === "string") pieces.push(part.text);
    }
  }
  return pieces.join("");
}

function extractAnthropicText(body: unknown): string {
  const content = (body as { content?: Array<{ type?: string; text?: unknown }> })?.content ?? [];
  return content.filter((part) => part.type === "text" || typeof part.text === "string").map((part) => String(part.text ?? "")).join("");
}

function usageOf(body: unknown): TokenUsage | undefined {
  const usage = (body as { usage?: Record<string, unknown> })?.usage;
  if (!usage || typeof usage !== "object") return undefined;
  const num = (value: unknown): number | undefined => (typeof value === "number" ? value : undefined);
  const input = num(usage["input_tokens"]) ?? num(usage["prompt_tokens"]);
  const output = num(usage["output_tokens"]) ?? num(usage["completion_tokens"]);
  const total = num(usage["total_tokens"]) ?? (input !== undefined && output !== undefined ? input + output : undefined);
  if (input === undefined && output === undefined && total === undefined) return undefined;
  return { input_tokens: input, output_tokens: output, total_tokens: total };
}

function headersFor(provider: ProviderConfig): Record<string, string> {
  const base: Record<string, string> = {
    "content-type": "application/json",
    "user-agent": "video-workflow-studio/0.1",
    ...provider.extraHeaders,
  };
  if (provider.protocol === "anthropic") {
    base["x-api-key"] = provider.apiKey;
    base["anthropic-version"] = "2023-06-01";
  } else {
    base["authorization"] = `Bearer ${provider.apiKey}`;
  }
  if (provider.baseUrl.includes("opencode.ai")) {
    base["x-opencode-session"] = provider.sessionId;
  }
  return base;
}

function requestBody(provider: ProviderConfig, messages: ChatMessage[]): { url: string; body: Record<string, unknown> } {
  const base = provider.baseUrl;
  if (provider.protocol === "anthropic") {
    const system = messages.filter((m) => m.role === "system").map((m) => m.content).join("\n\n");
    return {
      url: `${base}/messages`,
      body: {
        model: provider.model,
        max_tokens: provider.maxOutputTokens ?? 8192,
        ...(system ? { system } : {}),
        messages: messages.filter((m) => m.role !== "system").map((m) => ({ role: m.role, content: m.content })),
        ...(provider.temperature !== undefined ? { temperature: provider.temperature } : {}),
      },
    };
  }
  if (provider.protocol === "responses") {
    const system = messages.filter((m) => m.role === "system").map((m) => m.content).join("\n\n");
    return {
      url: `${base}/responses`,
      body: {
        model: provider.model,
        input: messages
          .filter((m) => m.role !== "system")
          .map((m) => ({ role: m.role, content: m.content })),
        ...(system ? { instructions: system } : {}),
        ...(provider.maxOutputTokens ? { max_output_tokens: provider.maxOutputTokens } : {}),
        ...(provider.temperature !== undefined ? { temperature: provider.temperature } : {}),
      },
    };
  }
  return {
    url: `${base}/chat/completions`,
    body: {
      model: provider.model,
      messages,
      stream: false,
      ...(provider.maxOutputTokens ? { max_tokens: provider.maxOutputTokens } : {}),
      ...(provider.temperature !== undefined ? { temperature: provider.temperature } : {}),
    },
  };
}

export interface CompleteOptions {
  maxTokens?: number;
  temperature?: number;
  signal?: AbortSignal;
}

export async function complete(provider: ProviderConfig, messages: ChatMessage[], options: CompleteOptions = {}): Promise<LlmResult> {
  if (!provider.apiKey) {
    throw new LlmError("缺少 API Key：设置 WF_API_KEY，或用 --stub 走固定输出");
  }
  const { url, body } = requestBody(provider, messages);
  if (options.maxTokens) {
    if (provider.protocol === "anthropic") body["max_tokens"] = options.maxTokens;
    else if (provider.protocol === "responses") body["max_output_tokens"] = options.maxTokens;
    else body["max_tokens"] = options.maxTokens;
  }
  if (options.temperature !== undefined) body["temperature"] = options.temperature;

  const attempts = 3;
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    if (options.signal?.aborted) throw new LlmError("已停止");
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), provider.timeoutMs);
    // 外部 signal（手动停止）与单次请求超时要同时生效；以前传了 signal 就把超时丢了
    const signal = options.signal ? AbortSignal.any([options.signal, controller.signal]) : controller.signal;
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: headersFor(provider),
        body: JSON.stringify(body),
        signal,
      });
      const text = await response.text();
      if (!response.ok) {
        if (RETRY_STATUS.has(response.status) && attempt < attempts - 1) {
          await new Promise((resolve) => setTimeout(resolve, 800 * 2 ** attempt));
          continue;
        }
        throw new LlmError(`模型请求失败 ${response.status}：${text.slice(0, 300)}`, response.status, text);
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(text);
      } catch {
        throw new LlmError(`模型返回不是 JSON：${text.slice(0, 200)}`, response.status, text);
      }
      const output =
        provider.protocol === "anthropic"
          ? extractAnthropicText(parsed)
          : provider.protocol === "responses"
            ? extractResponsesText(parsed)
            : extractChatText(parsed);
      return {
        text: output,
        usage: usageOf(parsed),
        protocol: provider.protocol,
        status: response.status,
        raw: parsed,
      };
    } catch (error) {
      lastError = error;
      if (options.signal?.aborted) throw new LlmError("已停止");
      if (error instanceof LlmError) throw error;
      if (attempt < attempts - 1) {
        await new Promise((resolve) => setTimeout(resolve, 800 * 2 ** attempt));
        continue;
      }
    } finally {
      clearTimeout(timer);
    }
  }
  throw lastError instanceof Error ? lastError : new LlmError(String(lastError));
}
