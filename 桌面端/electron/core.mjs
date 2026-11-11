/** Electron 主进程与浏览器调试壳共用的本地能力。 */
import { readdir, readFile, rename, stat, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const desktopDir = path.resolve(here, "..");
export const workspaceDir = path.resolve(desktopDir, "..");
const engineDir = path.join(desktopDir, "dist", "src", "engine");
const workflowDir = path.join(workspaceDir, "Dify工作流");
const projectsDir = path.join(workspaceDir, "HTML视频项目");

let engineCache = null;
export async function engine() {
  if (!engineCache) {
    engineCache = {
      dsl: await import(pathToFileURL(path.join(engineDir, "dsl.js")).href),
      config: await import(pathToFileURL(path.join(engineDir, "config.js")).href),
      runner: await import(pathToFileURL(path.join(engineDir, "run.js")).href),
      yamlEdit: await import(pathToFileURL(path.join(engineDir, "yamlEdit.js")).href),
      mirrors: await import(pathToFileURL(path.join(engineDir, "mirrors.js")).href),
    };
  }
  return engineCache;
}

export async function listWorkflows() {
  if (!existsSync(workflowDir)) return [];
  const names = (await readdir(workflowDir)).filter((name) => name.endsWith(".yml") || name.endsWith(".yaml")).sort();
  return names.map((name) => ({ name, path: path.join(workflowDir, name) }));
}

export async function envInfo() {
  const { config } = await engine();
  const env = { ...config.loadEnvFile(path.join(desktopDir, ".env")), ...process.env };
  return {
    hasKey: Boolean(env.WF_API_KEY),
    baseUrl: env.WF_BASE_URL ?? "https://opencode.ai/zen/go/v1",
    model: env.WF_MODEL ?? "gpt-6-luna",
    stub: env.WF_STUB === "1",
  };
}

async function revisionOf(filePath) {
  const data = await readFile(filePath);
  return createHash("sha1").update(data).digest("hex").slice(0, 12);
}

/** 供界面判断磁盘上的 YAML 是否被别的进程改过。 */
export async function fileRevision(filePath) {
  return { rev: await revisionOf(safePath(filePath)) };
}

export async function loadGraph(filePath) {
  const { dsl } = await engine();
  const workflow = dsl.loadWorkflow(filePath);
  const nodes = [...workflow.nodes.values()].map((node) => {
    const data = node.data ?? {};
    return {
      id: node.id,
      type: data.type,
      title: data.title ?? node.id,
      position: node.positionAbsolute ?? node.position ?? { x: 0, y: 0 },
      width: node.width ?? 244,
      height: node.height ?? 110,
      inputs: Array.isArray(data.variables)
        ? data.variables.map((item) => ({ variable: item.variable, selector: item.value_selector, valueType: item.value_type }))
        : [],
      outputs: Array.isArray(data.outputs) ? data.outputs.map((item) => (typeof item === "string" ? item : item.variable)) : [],
      prompt: Array.isArray(data.prompt_template) ? data.prompt_template.map((item) => item.text).join("\n\n") : undefined,
      promptSections: Array.isArray(data.prompt_template)
        ? data.prompt_template.map((item, index) => ({
            id: String(item.id ?? `${node.id}-${index}`),
            role: String(item.role ?? "user"),
            text: String(item.text ?? ""),
          }))
        : undefined,
      code: typeof data.code === "string" ? data.code : undefined,
      conditions: data.cases ?? data.conditions ?? undefined,
      model: data.model?.name ?? undefined,
    };
  });
  const start = [...workflow.nodes.values()].find((node) => node.data?.type === "start");
  const startVariables = Array.isArray(start?.data.variables)
    ? start.data.variables.map((item) => ({
        variable: String(item.variable ?? ""),
        label: String(item.label ?? item.variable ?? ""),
        type: String(item.type ?? "text-input"),
        required: item.required === true,
        options: Array.isArray(item.options) ? item.options.map((option) => String(option)) : [],
        ...(item.max_length !== undefined ? { maxLength: Number(item.max_length) } : {}),
      }))
    : [];
  return {
    path: filePath,
    rev: await revisionOf(filePath),
    name: path.basename(filePath),
    version: workflow.doc.version ?? "",
    appName: workflow.doc.app?.name ?? "",
    nodes,
    startVariables,
    edges: workflow.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? "",
      targetHandle: edge.targetHandle ?? "",
    })),
    warnings: workflow.warnings,
  };
}

const activeRuns = new Map();

/** 手动停止：按渲染层传来的 clientId 中断对应运行（Electron IPC 与 HTTP 壳共用）。 */
export function cancelRun(clientId) {
  const controller = activeRuns.get(String(clientId ?? ""));
  if (!controller) return { ok: false, error: "运行已结束或不存在" };
  controller.abort();
  return { ok: true };
}

export async function runWorkflow({ path: workflowPath, inputs = {}, stub = false, until, clientId, onEvent }) {
  const { config, runner } = await engine();
  const env = { ...config.loadEnvFile(path.join(desktopDir, ".env")), ...process.env };
  const provider = config.providerFromEnv(env, { stub });
  const defaults = JSON.parse(await readFile(path.join(desktopDir, "fixtures", "input.json"), "utf8"));
  const provided = Object.fromEntries(Object.entries(inputs).filter(([, value]) => value !== "" && value !== undefined));
  const merged = { ...defaults, ...provided };
  const stubSource = stub ? runner.fileStubSource(path.join(desktopDir, "fixtures", "stub")) : undefined;
  const controller = clientId ? new AbortController() : null;
  if (clientId && controller) activeRuns.set(String(clientId), controller);
  try {
    const result = await runner.runWorkflowFile({
      workflowPath,
      inputs: merged,
      provider,
      ...(stubSource ? { stub: stubSource } : {}),
      ...(until ? { until } : {}),
      ...(controller ? { signal: controller.signal } : {}),
      ...(onEvent ? { onEvent } : {}),
    });
    const { trace, ...rest } = result;
    return rest;
  } finally {
    if (clientId) activeRuns.delete(String(clientId));
  }
}

export async function inputDefaults() {
  return JSON.parse(await readFile(path.join(desktopDir, "fixtures", "input.json"), "utf8"));
}

const MIRROR_TOOL = path.join(workspaceDir, "HTML视频项目", "workflow_runtime", "tools", "sync_prompts_to_yaml.py");

/** 改 YAML 里的提示词/代码/标题；04 的提示词和代码节点同步写回 保留资料/ 镜像。 */
export async function updateNode({ path: yamlPath, nodeId, field, value, messageIndex }) {
  const safe = safePath(yamlPath);
  const { yamlEdit, mirrors } = await engine();
  const raw = await readFile(safe, "utf8");
  const next = yamlEdit.updateNodeField(raw, nodeId, field, String(value ?? ""), messageIndex);
  recordHistory(safe, raw);
  await writeAtomic(safe, next);

  let mirror = null;
  let mirrorWarning;
  if (path.basename(safe).startsWith("04") && (field === "prompt" || field === "code")) {
    const maps = await mirrors.loadMirrorMaps(MIRROR_TOOL);
    if (maps.warning) mirrorWarning = maps.warning;
    const name = field === "prompt" ? maps.prompts[nodeId] : maps.codes[nodeId];
    if (name) {
      const dir = field === "prompt" ? "保留资料/工作流提示词" : "保留资料/工作流代码节点";
      const target = path.join(workspaceDir, dir, name);
      if (existsSync(target)) {
        const mirrorText = field === "prompt" ? yamlEdit.promptTextOf(next, nodeId) : String(value ?? "");
        await writeFile(target, mirrorText, "utf8");
        mirror = path.relative(workspaceDir, target);
      } else {
        mirrorWarning = `映射表里有 ${nodeId} → ${name}，但镜像文件不存在，保留资料/ 未同步`;
      }
    }
  }
  return { ok: true, path: safe, mirror, ...(mirrorWarning ? { mirrorWarning } : {}), ...historyFlags(safe) };
}

const HISTORY_LIMIT = 50;
const history = new Map();

function historyOf(filePath) {
  if (!history.has(filePath)) history.set(filePath, { undo: [], redo: [] });
  return history.get(filePath);
}

function historyFlags(filePath) {
  const entry = historyOf(filePath);
  return { canUndo: entry.undo.length > 0, canRedo: entry.redo.length > 0 };
}

function recordHistory(filePath, raw) {
  const entry = historyOf(filePath);
  entry.undo.push(raw);
  if (entry.undo.length > HISTORY_LIMIT) entry.undo.shift();
  entry.redo.length = 0;
}

export async function historyStatus(payload) {
  return historyFlags(safePath(payload.path));
}

export async function undo(payload) {
  const safe = safePath(payload.path);
  const entry = historyOf(safe);
  if (entry.undo.length === 0) throw new Error("没有可撤销的修改");
  const current = await readFile(safe, "utf8");
  const previous = entry.undo.pop();
  entry.redo.push(current);
  await writeAtomic(safe, previous);
  return { graph: await loadGraph(safe), ...historyFlags(safe) };
}

export async function redo(payload) {
  const safe = safePath(payload.path);
  const entry = historyOf(safe);
  if (entry.redo.length === 0) throw new Error("没有可重做的修改");
  const current = await readFile(safe, "utf8");
  const next = entry.redo.pop();
  entry.undo.push(current);
  await writeAtomic(safe, next);
  return { graph: await loadGraph(safe), ...historyFlags(safe) };
}

async function writeAtomic(target, content) {
  const tmp = `${target}.tmp-${process.pid}`;
  await writeFile(tmp, content, "utf8");
  await rename(tmp, target);
}

async function editYaml(filePath, mutate) {
  const safe = safePath(filePath);
  const { yamlEdit } = await engine();
  const raw = await readFile(safe, "utf8");
  const result = mutate(raw, yamlEdit);
  const next = typeof result === "string" ? result : result.raw;
  recordHistory(safe, raw);
  await writeAtomic(safe, next);
  return { ...(typeof result === "string" ? {} : result), graph: await loadGraph(safe), ...historyFlags(safe) };
}

export async function moveNode(payload) {
  return editYaml(payload.path, (raw, yamlEdit) => yamlEdit.moveNode(raw, payload.nodeId, payload.position));
}

export async function addNode(payload) {
  return editYaml(payload.path, (raw, yamlEdit) =>
    yamlEdit.addNode(raw, {
      type: payload.type,
      title: payload.title ?? `新 ${payload.type}`,
      position: payload.position ?? { x: 100, y: 100 },
      ...(payload.sourceId ? { sourceId: payload.sourceId } : {}),
    }),
  );
}

export async function removeNode(payload) {
  return editYaml(payload.path, (raw, yamlEdit) => yamlEdit.removeNode(raw, payload.nodeId));
}

export async function connectNodes(payload) {
  return editYaml(payload.path, (raw, yamlEdit) =>
    yamlEdit.connect(raw, {
      source: payload.source,
      target: payload.target,
      ...(payload.sourceHandle ? { sourceHandle: payload.sourceHandle } : {}),
    }),
  );
}

export async function removeEdge(payload) {
  return editYaml(payload.path, (raw, yamlEdit) => yamlEdit.removeEdge(raw, payload.edgeId));
}

export async function listProjects() {
  if (!existsSync(projectsDir)) return [];
  const entries = await readdir(projectsDir, { withFileTypes: true });
  const projects = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".") || entry.name === "workflow_runtime") continue;
    const full = path.join(projectsDir, entry.name);
    const info = await stat(full).catch(() => null);
    projects.push({ name: entry.name, path: full, mtime: info?.mtimeMs ?? 0 });
  }
  return projects.sort((a, b) => b.mtime - a.mtime);
}

const SKIP_DIRS = new Set(["node_modules", "vendor", ".hyperframes", ".git", "__pycache__"]);

export async function listFiles(dirPath, depth = 0) {
  const safe = safePath(dirPath);
  const entries = await readdir(safe, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.name.startsWith(".") || SKIP_DIRS.has(entry.name)) continue;
    const full = path.join(safe, entry.name);
    if (entry.isDirectory()) {
      if (depth < 2) files.push({ name: entry.name, path: full, type: "dir", depth });
      continue;
    }
    const info = await stat(full).catch(() => null);
    files.push({ name: entry.name, path: full, type: "file", size: info?.size ?? 0, mtime: info?.mtimeMs ?? 0, depth });
  }
  return files;
}

export function safePath(candidate) {
  const resolved = path.resolve(candidate);
  if (!resolved.startsWith(workspaceDir + path.sep) && resolved !== workspaceDir) {
    throw new Error(`路径不在工作区内：${candidate}`);
  }
  return resolved;
}

export async function fileUrl(filePath) {
  const safe = safePath(filePath);
  return pathToFileURL(safe).href;
}

export async function readText(filePath, limit = 200_000) {
  const safe = safePath(filePath);
  const data = await readFile(safe);
  return { path: safe, text: data.subarray(0, limit).toString("utf8"), truncated: data.length > limit };
}

const TERM_PRESETS = [
  {
    id: "prepare",
    label: "准备（--prepare）",
    cmd: "bash HTML视频项目/workflow_runtime/tools/run_dify_output.sh --prepare",
  },
  { id: "render", label: "出片（--skip-images）", cmd: "bash HTML视频项目/workflow_runtime/tools/run_dify_output.sh --skip-images" },
  { id: "images", label: "只出图", cmd: "bash HTML视频项目/workflow_runtime/tools/run_dify_output.sh --images-only" },
];

export function termPresets() {
  return TERM_PRESETS;
}

let termSeq = 0;

/** 跑一条本地命令，stdout/stderr 逐行回传。 */
export function startCommand({ cmd, cwd, onData, onExit }) {
  const working = cwd ? safePath(cwd) : workspaceDir;
  const id = `term-${Date.now().toString(36)}-${++termSeq}`;
  const child = spawn("bash", ["-lc", cmd], {
    cwd: working,
    env: { ...process.env, FORCE_COLOR: "0" },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const started = Date.now();
  let output = "";
  const emit = (stream, text) => {
    output += text;
    onData?.({ id, stream, text });
  };
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => emit("out", String(chunk)));
  child.stderr.on("data", (chunk) => emit("err", String(chunk)));
  const done = new Promise((resolve) => {
    child.on("error", (error) => {
      const ms = Date.now() - started;
      onExit?.({ id, code: -1, ms, output, error: String(error) });
      resolve({ code: -1, ms, output, error: String(error) });
    });
    child.on("close", (code) => {
      const ms = Date.now() - started;
      onExit?.({ id, code: code ?? -1, ms, output });
      resolve({ code: code ?? -1, ms, output });
    });
  });
  return { id, done, kill: () => child.kill("SIGTERM") };
}
