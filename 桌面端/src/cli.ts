#!/usr/bin/env node
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { loadWorkflow, startVariables } from "./engine/dsl.js";
import { providerFromEnv, loadEnvFile } from "./engine/config.js";
import type { LlmProtocol, ProviderConfig } from "./engine/config.js";
import { runWorkflowFile } from "./engine/run.js";
import { fileStubSource } from "./engine/run.js";
import type { RunResult } from "./engine/scheduler.js";
import { nodeTitle, nodeType } from "./engine/dsl.js";

interface CliArgs {
  workflowPath?: string;
  input?: string;
  brief?: string;
  requestId?: string;
  stub: boolean;
  stubDir: string;
  until?: string;
  trace?: string;
  json: boolean;
  list: boolean;
  model?: string;
  baseUrl?: string;
  protocol?: LlmProtocol;
  apiKey?: string;
  session?: string;
  envFile?: string;
  maxOutputTokens?: number;
  help: boolean;
}

const USAGE = `视频工作流引擎 · M0

用法：
  npm run cli -- <workflow.yml> [选项]

选项：
  --input <file>          输入变量 JSON（start 节点的变量表）
  --brief <text>          直接给 campaign_brief（覆盖 --input 里的）
  --request-id <text>     覆盖 request_id
  --until <nodeId>        跑到该节点后停止（例如 a03）
  --stub                  模型节点用 fixtures/stub/<nodeId>.txt 的固定输出
  --stub-dir <dir>        stub 目录，默认 fixtures/stub
  --trace <file>          把 trace 写成 JSONL
  --json                  输出完整结果 JSON
  --list                  只列出节点
  --model <name>          覆盖模型，默认环境变量或 gpt-6-luna
  --base-url <url>        覆盖 base URL
  --protocol <p>          chat | responses | anthropic
  --api-key <key>         覆盖 API Key
  --env-file <file>       额外读取的 .env（默认读当前目录 .env）
`;

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = { stub: false, stubDir: "fixtures/stub", json: false, list: false, help: false };
  const take = (index: number, name: string): string => {
    const value = argv[index];
    if (value === undefined || value.startsWith("--")) throw new Error(`${name} 缺少参数值`);
    return value;
  };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === undefined) continue;
    switch (arg) {
      case "--input": args.input = take(++i, arg); break;
      case "--brief": args.brief = take(++i, arg); break;
      case "--request-id": args.requestId = take(++i, arg); break;
      case "--stub": args.stub = true; break;
      case "--stub-dir": args.stubDir = take(++i, arg); break;
      case "--until": args.until = take(++i, arg); break;
      case "--trace": args.trace = take(++i, arg); break;
      case "--json": args.json = true; break;
      case "--list": args.list = true; break;
      case "--model": args.model = take(++i, arg); break;
      case "--base-url": args.baseUrl = take(++i, arg); break;
      case "--protocol": {
        const value = take(++i, arg);
        if (value !== "chat" && value !== "responses" && value !== "anthropic") throw new Error(`未知协议：${value}`);
        args.protocol = value;
        break;
      }
      case "--api-key": args.apiKey = take(++i, arg); break;
      case "--session": args.session = take(++i, arg); break;
      case "--env-file": args.envFile = take(++i, arg); break;
      case "--max-output-tokens": args.maxOutputTokens = Number(take(++i, arg)); break;
      case "--help": case "-h": args.help = true; break;
      default:
        if (arg.startsWith("--")) throw new Error(`未知选项：${arg}`);
        if (!args.workflowPath) args.workflowPath = arg;
        else throw new Error(`多余的参数：${arg}`);
    }
  }
  return args;
}

const useColor = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code: string) => (text: string) => (useColor ? `\u001b[${code}m${text}\u001b[0m` : text);
const c = { dim: paint("2"), green: paint("32"), red: paint("31"), yellow: paint("33"), blue: paint("34"), bold: paint("1") };

function short(value: unknown, max = 220): string {
  const text = typeof value === "string" ? value : JSON.stringify(value);
  if (text === undefined) return "";
  return text.length > max ? `${text.slice(0, max)}…（${text.length} 字符）` : text;
}

function printRun(result: RunResult, workflowPath: string): void {
  console.log("");
  console.log(`${c.bold("▶")} ${workflowPath}`);
  console.log(`  ${c.dim(`${result.nodes.length} 个节点执行 · ${(result.ms / 1000).toFixed(2)}s · ${result.status}`)}`);
  console.log("");
  for (const node of result.nodes) {
    const mark =
      node.status === "success" ? c.green("✓")
      : node.status === "running" ? c.blue("…")
      : node.status === "unimplemented" ? c.yellow("⊘")
      : c.red("✗");
    const usage = node.usage?.total_tokens ? c.dim(` · ${node.usage.total_tokens} tok`) : "";
    console.log(`  ${mark} ${node.title.padEnd(28, " ")} ${String(node.ms).padStart(6, " ")}ms${usage}`);
    if (node.error) console.log(`      ${c.red(node.error)}`);
  }
  console.log("");
  if (result.error) console.log(`${c.red("错误：")}${result.error}`);
  const keys = Object.keys(result.outputs);
  if (keys.length > 0 && (result.status === "success" || result.status === "stopped")) {
    console.log(c.bold("输出："));
    for (const key of keys) {
      const value = result.outputs[key];
      console.log(`  ${c.dim(key.padEnd(24, " "))} ${short(value)}`);
    }
  } else if (result.status !== "success" && result.status !== "stopped") {
    console.log(c.dim("未列产物：运行没有正常结束，前面节点的结果保留在 trace 里。"));
  }
  if (result.warnings.length > 0) {
    console.log("");
    console.log(c.yellow("YAML 警告："));
    for (const warning of result.warnings) console.log(`  - ${warning}`);
  }
}

async function main(): Promise<void> {
  let args: CliArgs;
  try {
    args = parseArgs(process.argv.slice(2));
  } catch (error) {
    console.error(`${c.red("参数错误：")}${(error as Error).message}`);
    console.log(USAGE);
    process.exit(2);
  }
  if (args.help || !args.workflowPath) {
    console.log(USAGE);
    process.exit(args.help ? 0 : 2);
  }

  const workflowPath = resolve(args.workflowPath);
  const workflow = loadWorkflow(workflowPath);

  if (args.list) {
    console.log(`${workflowPath}\n${workflow.nodes.size} 节点 / ${workflow.edges.length} 连线\n`);
    for (const node of workflow.nodes.values()) {
      console.log(`  ${node.id.padEnd(22, " ")} ${nodeType(node).padEnd(18, " ")} ${nodeTitle(node)}`);
    }
    return;
  }

  const envFile = args.envFile ?? resolve(".env");
  const fileEnv = existsSync(envFile) ? loadEnvFile(envFile) : {};
  const env: Record<string, string | undefined> = { ...fileEnv, ...process.env };

  const provider: ProviderConfig = providerFromEnv(env, {
    ...(args.model ? { model: args.model } : {}),
    ...(args.baseUrl ? { baseUrl: args.baseUrl } : {}),
    ...(args.protocol ? { protocol: args.protocol } : {}),
    ...(args.apiKey ? { apiKey: args.apiKey } : {}),
    ...(args.session ? { sessionId: args.session } : {}),
    ...(args.maxOutputTokens ? { maxOutputTokens: args.maxOutputTokens } : {}),
    stub: args.stub || env.WF_STUB === "1",
  });

  const inputs: Record<string, unknown> = {};
  if (args.input) {
    const parsed = JSON.parse(readFileSync(resolve(args.input), "utf8")) as Record<string, unknown>;
    for (const [key, value] of Object.entries(parsed)) inputs[key] = value;
  }
  const start = [...workflow.nodes.values()].find((node) => node.data.type === "start");
  if (!start) throw new Error("工作流没有 start 节点");
  for (const item of startVariables(start)) {
    if (!(item.variable in inputs)) {
      if (item.options && item.options.length > 0) inputs[item.variable] = item.options[0];
      else inputs[item.variable] = "";
    }
  }
  if (args.brief !== undefined) inputs["campaign_brief"] = args.brief;
  if (args.requestId !== undefined) inputs["request_id"] = args.requestId;
  if (!String(inputs["request_id"] ?? "").trim()) inputs["request_id"] = `cli-${Date.now()}`;

  const stubDir = resolve(args.stubDir);
  const result = await runWorkflowFile({
    workflowPath,
    inputs,
    provider,
    ...(args.stub ? { stub: fileStubSource(stubDir) } : {}),
    ...(args.until ? { until: args.until } : {}),
    ...(args.trace ? { tracePath: resolve(args.trace) } : {}),
  });

  if (args.json) {
    const { trace, ...rest } = result;
    console.log(JSON.stringify(rest, null, 2));
  } else {
    printRun(result, workflowPath);
  }
  process.exit(result.status === "success" || result.status === "stopped" ? 0 : 1);
}

main().catch((error) => {
  console.error(`${c.red("运行失败：")}${(error as Error).message}`);
  process.exit(1);
});
