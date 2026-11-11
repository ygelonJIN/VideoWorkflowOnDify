import { readFileSync } from "node:fs";

export type LlmProtocol = "chat" | "responses" | "anthropic";

export interface ProviderConfig {
  protocol: LlmProtocol;
  baseUrl: string;
  apiKey: string;
  model: string;
  sessionId: string;
  maxOutputTokens?: number;
  temperature?: number;
  timeoutMs: number;
  extraHeaders: Record<string, string>;
  stub: boolean;
}

const DEFAULT_BASE = "https://opencode.ai/zen/go/v1";
const DEFAULT_MODEL = "gpt-6-luna";

export function parseEnvFile(text: string): Record<string, string> {
  const values: Record<string, string> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    values[key] = value;
  }
  return values;
}

export function loadEnvFile(path: string): Record<string, string> {
  try {
    return parseEnvFile(readFileSync(path, "utf8"));
  } catch {
    return {};
  }
}

export function protocolForModel(model: string): LlmProtocol {
  if (/luna|grok-4\.[67]|muse-spark/i.test(model)) return "responses";
  if (/minimax-m2|claude-haiku-5-5/i.test(model)) return "anthropic";
  return "chat";
}

export function providerFromEnv(
  env: Record<string, string | undefined>,
  overrides: Partial<ProviderConfig> = {},
): ProviderConfig {
  const model = overrides.model ?? env.WF_MODEL ?? DEFAULT_MODEL;
  const protocol = overrides.protocol ?? (env.WF_PROTOCOL as LlmProtocol | undefined) ?? protocolForModel(model);
  const baseUrl = (overrides.baseUrl ?? env.WF_BASE_URL ?? DEFAULT_BASE).replace(/\/+$/, "");
  const stub = overrides.stub ?? env.WF_STUB === "1";
  return {
    protocol,
    baseUrl,
    apiKey: overrides.apiKey ?? env.WF_API_KEY ?? "",
    model,
    sessionId: overrides.sessionId ?? env.WF_SESSION ?? `wfs-${Date.now().toString(36)}`,
    maxOutputTokens: overrides.maxOutputTokens ?? (env.WF_MAX_OUTPUT_TOKENS ? Number(env.WF_MAX_OUTPUT_TOKENS) : undefined),
    temperature: overrides.temperature ?? (env.WF_TEMPERATURE ? Number(env.WF_TEMPERATURE) : undefined),
    timeoutMs: overrides.timeoutMs ?? Number(env.WF_TIMEOUT_MS ?? 600000),
    extraHeaders: { ...(overrides.extraHeaders ?? {}) },
    stub,
  };
}
