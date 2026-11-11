import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";

export interface CodeRunOptions {
  code: string;
  args: Record<string, unknown>;
  timeoutMs?: number;
  python?: string;
  signal?: AbortSignal;
}

export interface CodeRunResult {
  outputs: Record<string, unknown>;
  stdout: string;
  stderr: string;
  ms: number;
}

const RUNNER = `import json, runpy, sys, traceback
cfg_path, code_path = sys.argv[1], sys.argv[2]
with open(cfg_path, encoding="utf-8") as handle:
    args = json.load(handle)
try:
    module = runpy.run_path(code_path)
    result = module["main"](**args)
    if not isinstance(result, dict):
        raise TypeError("main() 必须返回 dict，实际是 " + type(result).__name__)
    sys.stdout.write("\\n__WF_RESULT__" + json.dumps(result, ensure_ascii=False, default=str) + "\\n")
except Exception:
    traceback.print_exc()
    sys.exit(2)
`;

/** 用系统 python3 跑 Dify Code 节点：代码原样执行，参数走 JSON 文件，结果走 stdout 标记行。 */
export async function runPythonCode(options: CodeRunOptions): Promise<CodeRunResult> {
  const dir = await mkdtemp(join(tmpdir(), "wf-code-"));
  try {
    const codePath = join(dir, "node.py");
    const argsPath = join(dir, "args.json");
    const runnerPath = join(dir, "runner.py");
    await writeFile(codePath, options.code, "utf8");
    await writeFile(argsPath, JSON.stringify(options.args), "utf8");
    await writeFile(runnerPath, RUNNER, "utf8");

    const python = options.python ?? process.env.WF_PYTHON ?? "python3";
    const started = Date.now();
    const result = await new Promise<{ code: number | null; stdout: string; stderr: string; timedOut: boolean; aborted: boolean }>((resolve, reject) => {
      const child = spawn(python, [runnerPath, argsPath, codePath], { stdio: ["ignore", "pipe", "pipe"] });
      let stdout = "";
      let stderr = "";
      let timedOut = false;
      let aborted = false;
      const onAbort = () => {
        aborted = true;
        child.kill("SIGKILL");
      };
      options.signal?.addEventListener("abort", onAbort, { once: true });
      if (options.signal?.aborted) onAbort();
      const cleanup = () => options.signal?.removeEventListener("abort", onAbort);
      const timer = setTimeout(() => {
        timedOut = true;
        child.kill("SIGKILL");
      }, options.timeoutMs ?? 120000);
      child.stdout.setEncoding("utf8");
      child.stderr.setEncoding("utf8");
      child.stdout.on("data", (chunk: string) => {
        stdout += chunk;
        if (stdout.length > 20 * 1024 * 1024) child.kill("SIGKILL");
      });
      child.stderr.on("data", (chunk: string) => {
        stderr += chunk;
        if (stderr.length > 2 * 1024 * 1024) child.kill("SIGKILL");
      });
      child.on("error", (error) => {
        clearTimeout(timer);
        cleanup();
        reject(error);
      });
      child.on("close", (code) => {
        clearTimeout(timer);
        cleanup();
        resolve({ code, stdout, stderr, timedOut, aborted });
      });
    });

    if (result.aborted) throw new Error("已停止");
    if (result.timedOut) throw new Error(`Code 节点超时（${options.timeoutMs ?? 120000}ms）`);
    if (result.code !== 0) throw new Error(`Code 节点失败（exit ${result.code}）：${result.stderr.trim().slice(-1200)}`);
    const markerIndex = result.stdout.lastIndexOf("__WF_RESULT__");
    if (markerIndex < 0) throw new Error(`Code 节点没有返回 __WF_RESULT__：${result.stdout.slice(-500)}`);
    const jsonText = result.stdout.slice(markerIndex + "__WF_RESULT__".length).trim();
    const parsed = JSON.parse(jsonText) as Record<string, unknown>;
    return { outputs: parsed, stdout: result.stdout.slice(0, markerIndex), stderr: result.stderr, ms: Date.now() - started };
  } finally {
    await rm(dir, { recursive: true, force: true });
  }
}
