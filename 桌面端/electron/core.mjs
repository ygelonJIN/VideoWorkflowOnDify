/** Electron 主进程与浏览器调试壳共用的本地能力。 */
import { chmod, mkdir, readdir, readFile, rename, stat, utimes, writeFile } from "node:fs/promises";
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

const ENV_PATH = path.join(desktopDir, ".env");

function parseEnvText(text) {
  const values = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const index = trimmed.indexOf("=");
    if (index <= 0) continue;
    const key = trimmed.slice(0, index).trim();
    let value = trimmed.slice(index + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (key) values[key] = value;
  }
  return values;
}

function upsertEnv(text, key, value) {
  const lines = text ? text.replace(/\n$/, "").split("\n") : [];
  let found = false;
  const next = [];
  for (const line of lines) {
    if (new RegExp(`^${key}\\s*=`).test(line)) {
      found = true;
      if (value !== undefined && value !== "") next.push(`${key}=${value}`);
      continue;
    }
    next.push(line);
  }
  if (!found && value !== undefined && value !== "") next.push(`${key}=${value}`);
  return next.length > 0 ? `${next.join("\n")}\n` : "";
}

/** 设置面板读取：只回是否已配置和末四位，绝不把 Key 送回渲染层。 */
export async function getSettings() {
  const raw = await readFile(ENV_PATH, "utf8").catch(() => "");
  const file = parseEnvText(raw);
  const keyValue = file.WF_API_KEY ?? process.env.WF_API_KEY ?? "";
  return {
    path: path.join("桌面端", ".env"),
    baseUrl: file.WF_BASE_URL ?? process.env.WF_BASE_URL ?? "https://opencode.ai/zen/go/v1",
    model: file.WF_MODEL ?? process.env.WF_MODEL ?? "gpt-6-luna",
    protocol: file.WF_PROTOCOL ?? "",
    hasKey: keyValue.trim().length > 0,
    keyHint: keyValue.trim() ? `末四位 ${keyValue.trim().slice(-4)}` : "",
    inProcessEnv: Boolean(process.env.WF_API_KEY) && !file.WF_API_KEY,
  };
}

export async function saveSettings({ baseUrl, model, protocol, apiKey, clearKey } = {}) {
  const protocols = new Set(["", "chat", "responses", "anthropic"]);
  if (protocol !== undefined && !protocols.has(String(protocol))) throw new Error(`不支持的协议：${protocol}`);
  if (baseUrl !== undefined && String(baseUrl).trim() && !/^https?:\/\//.test(String(baseUrl).trim())) {
    throw new Error("Base URL 必须以 http:// 或 https:// 开头");
  }
  for (const [name, value] of [["Base URL", baseUrl], ["模型", model], ["API Key", apiKey]]) {
    if (value !== undefined && /[\r\n]/.test(String(value))) throw new Error(`${name} 不能包含换行`);
  }
  let text = await readFile(ENV_PATH, "utf8").catch(() => "");
  text = upsertEnv(text, "WF_BASE_URL", baseUrl === undefined ? undefined : String(baseUrl).trim());
  text = upsertEnv(text, "WF_MODEL", model === undefined ? undefined : String(model).trim());
  text = upsertEnv(text, "WF_PROTOCOL", protocol === undefined ? undefined : String(protocol).trim());
  if (clearKey) text = upsertEnv(text, "WF_API_KEY", undefined);
  else if (apiKey !== undefined && String(apiKey).trim()) text = upsertEnv(text, "WF_API_KEY", String(apiKey).trim());
  await writeFile(ENV_PATH, text, { mode: 0o600 });
  await chmod(ENV_PATH, 0o600).catch(() => {});
  return getSettings();
}

export async function envInfo() {
  const { config } = await engine();
  const env = { ...config.loadEnvFile(path.join(desktopDir, ".env")), ...process.env };
  return {
    hasKey: Boolean(env.WF_API_KEY),
    baseUrl: env.WF_BASE_URL ?? "https://opencode.ai/zen/go/v1",
    model: env.WF_MODEL ?? "gpt-6-luna",
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

export async function runWorkflow({ path: workflowPath, inputs = {}, until, precomputed, clientId, onEvent }) {
  const { config, runner } = await engine();
  const env = { ...config.loadEnvFile(path.join(desktopDir, ".env")), ...process.env };
  const provider = config.providerFromEnv(env, { stub: false });
  // 不再用 fixtures 兜底：留空的字段就是空，不把示例文案偷偷带进真实运行
  const merged = Object.fromEntries(Object.entries(inputs).filter(([, value]) => value !== undefined));
  const controller = clientId ? new AbortController() : null;
  if (clientId && controller) activeRuns.set(String(clientId), controller);
  try {
    const result = await runner.runWorkflowFile({
      workflowPath,
      inputs: merged,
      provider,
      ...(until ? { until } : {}),
      ...(precomputed ? { precomputed } : {}),
      ...(controller ? { signal: controller.signal } : {}),
      ...(onEvent ? { onEvent } : {}),
    });
    const { trace, ...rest } = result;
    return rest;
  } finally {
    if (clientId) activeRuns.delete(String(clientId));
  }
}

const BUILD_SCRIPT = path.join(workspaceDir, "HTML视频项目", "workflow_runtime", "tools", "build_black_frame_project.py");
let mimoKeyCache;

/** TTS 的 MIMO_API_KEY：优先进程环境，其次从登录 zsh（~/.zshrc）里读，不落盘、不回传渲染层。 */
export async function resolveMimoKey() {
  if (process.env.MIMO_API_KEY) return process.env.MIMO_API_KEY;
  if (mimoKeyCache !== undefined) return mimoKeyCache;
  mimoKeyCache = await new Promise((resolve) => {
    let output = "";
    // .zshrc 只在交互/显式 source 时加载；只取 printenv 的结果，别把 rc 的输出混进来
    const child = spawn("zsh", ["-lc", "source ~/.zshrc >/dev/null 2>&1; printenv MIMO_API_KEY"], { stdio: ["ignore", "pipe", "ignore"] });
    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk) => { output += chunk; });
    child.on("error", () => resolve(""));
    child.on("close", () => resolve(output.trim()));
  });
  return mimoKeyCache;
}

export async function mimoKeyStatus() {
  const key = await resolveMimoKey();
  return { hasKey: Boolean(key), hint: key ? `从终端读取（末四位 ${key.slice(-4)}）` : "没找到 MIMO_API_KEY" };
}

function imageIdsFromOutputs(outputs) {
  const raw = outputs?.image_plan_json;
  if (typeof raw !== "string") return [];
  try {
    const plan = JSON.parse(raw);
    // role=html 的屏不生成照片，期望图片只数真正要出图的
    return (plan.images || [])
      .filter((item) => String(item?.role ?? "").toLowerCase() !== "html")
      .map((item) => String(item?.id ?? ""))
      .filter(Boolean);
  } catch {
    return [];
  }
}

/** 准备项目 / 渲染成片：把本次运行的 End 输出写成 build 脚本认识的输入，再流式跑 Python。 */
export async function startBuild({ kind, action, projectName, outputs, tts = {}, allowMissing = false, replace = false, onData, onExit } = {}) {
  kind = kind ?? action;
  if (kind !== "prepare" && kind !== "render") throw new Error(`未知的构建动作：${kind}`);
  const name = String(projectName ?? "").trim();
  if (!/^[A-Za-z0-9._-]+$/.test(name)) throw new Error("项目名只能包含字母、数字、点、下划线、横线");
  const html = outputs?.html_document;
  const voiceover = outputs?.voiceover_script;
  if (typeof html !== "string" || !html.trim()) throw new Error("这次运行没有 html_document，先跑完整条链路");
  if (typeof voiceover !== "string" || !voiceover.trim()) throw new Error("这次运行没有 voiceover_script");

  // TTS 的 Base 地址在开始节点是中文选项，真正 URL 由 A16 写进 approved_package_json
  let approvedTts = {};
  try {
    const approved = outputs?.approved_package_json;
    if (typeof approved === "string") approvedTts = JSON.parse(approved)?.tts_config ?? {};
  } catch {
    approvedTts = {};
  }
  const text = (value) => String(value ?? "").trim();
  const inputBase = text(tts.baseUrl);
  const ttsResolved = {
    provider: text(tts.provider) || text(approvedTts.provider) || "mimo",
    base_url: /^https?:\/\//i.test(inputBase) ? inputBase : text(approvedTts.base_url),
    model: text(tts.model) || text(approvedTts.model),
    voice: text(tts.voice) || text(approvedTts.voice) || "mimo_default",
  };

  const payload = {
    build_package_json: {
      html_document: html,
      voiceover_script: voiceover,
      ...(outputs?.image_plan_json ? { image_plan_json: outputs.image_plan_json } : {}),
      ...(outputs?.approved_package_json ? { approved_package_json: outputs.approved_package_json } : {}),
      tts_config: {
        provider: ttsResolved.provider,
        base_url: ttsResolved.base_url,
        model: ttsResolved.model,
        voice: ttsResolved.voice,
      },
    },
  };
  const inputDir = path.join(workspaceDir, "HTML视频项目", "Dify输出");
  await mkdir(inputDir, { recursive: true });
  const inputPath = path.join(inputDir, `${name}-blackframe-input.json`);
  await writeFile(inputPath, JSON.stringify(payload, null, 2), "utf8");

  const args = [BUILD_SCRIPT, name, "--input-file", inputPath, "--no-open"];
  if (kind === "prepare") args.push("--prepare");
  else {
    args.push("--skip-images");
    if (allowMissing) args.push("--allow-missing-images");
    if (replace) args.push("--replace");
  }
  if (ttsResolved.provider) args.push("--tts-provider", ttsResolved.provider);
  if (ttsResolved.base_url) args.push("--tts-base-url", ttsResolved.base_url);
  if (ttsResolved.model) args.push("--tts-model", ttsResolved.model);
  if (ttsResolved.voice) args.push("--voice-name", ttsResolved.voice);

  const env = { ...process.env };
  const mimoKey = await resolveMimoKey();
  if (mimoKey) env.MIMO_API_KEY = mimoKey;

  const projectDir = path.join(workspaceDir, "HTML视频项目", name);
  const expectedIds = imageIdsFromOutputs(outputs);
  const runId = `build-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
  const started = Date.now();
  const child = spawn("python3", args, {
    cwd: path.join(workspaceDir, "HTML视频项目", "workflow_runtime"),
    env,
    stdio: ["ignore", "pipe", "pipe"],
  });
  const emit = (stream, text) => onData?.({ runId, action: kind, stream, text });
  child.stdout.setEncoding("utf8");
  child.stderr.setEncoding("utf8");
  child.stdout.on("data", (chunk) => emit("out", chunk));
  child.stderr.on("data", (chunk) => emit("err", chunk));
  let exited = false;
  const done = (code, extra = {}) => {
    if (exited) return;
    exited = true;
    onExit?.({ runId, action: kind, code, ms: Date.now() - started, projectDir, expectedIds, ...extra });
  };
  child.on("error", (error) => {
    emit("err", String(error.message));
    done(-1, { error: String(error.message) });
  });
  child.on("close", (code) => done(code ?? -1));
  return { runId, projectDir, inputPath, expectedIds, hasMimoKey: Boolean(mimoKey) };
}

/** 运行输入不再预填示例正文；只保留 TTS 这类配置默认值，request_id 每次自动生成。 */
export async function inputDefaults() {
  const fixture = JSON.parse(await readFile(path.join(desktopDir, "fixtures", "input.json"), "utf8"));
  const defaults = {};
  for (const key of ["tts_provider", "tts_model", "tts_base_url", "tts_voice"]) {
    if (typeof fixture[key] === "string") defaults[key] = fixture[key];
  }
  const stamp = new Date().toISOString().replace(/[-:.TZ]/g, "").slice(0, 14);
  defaults.request_id = `studio-${stamp}`;
  return defaults;
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

const IMAGE_EXT = new Set([".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"]);

function safeImageName(name) {
  const base = path.basename(String(name ?? "")).replace(/[\u0000-\u001f]/g, "").trim();
  const cleaned = base.replace(/[\\/:*?"<>|]/g, "_").replace(/^\.+/, "");
  return (cleaned || `image-${Date.now()}.png`).slice(0, 120);
}

/** 项目里的媒体目录：提示词在 媒体/出图，成图在 媒体/图片（_resolved 是渲染用的安全文件名副本）。 */
export function projectMediaPath(projectPath, sub) {
  return path.join(safePath(projectPath), "媒体", sub);
}

export async function listProjectImages({ projectPath } = {}) {
  const dir = projectMediaPath(projectPath, "图片");
  await mkdir(dir, { recursive: true });
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (!entry.isFile() || entry.name.startsWith(".")) continue;
    if (!IMAGE_EXT.has(path.extname(entry.name).toLowerCase())) continue;
    const full = path.join(dir, entry.name);
    const info = await stat(full).catch(() => null);
    files.push({ name: entry.name, path: full, size: info?.size ?? 0, mtime: info?.mtimeMs ?? 0 });
  }
  return { dir, files: files.sort((left, right) => right.mtime - left.mtime) };
}

/** 图片直接落到当前项目的 媒体/图片/：保留原文件名（s02.png 就能按 id 对上）和原修改时间（按出图时间对号）。 */
export async function saveProjectImage({ projectPath, name, base64, mtime } = {}) {
  if (typeof base64 !== "string" || !base64) throw new Error("没有收到图片数据");
  const buffer = Buffer.from(base64, "base64");
  if (buffer.length === 0) throw new Error("图片内容为空");
  if (buffer.length > 40 * 1024 * 1024) throw new Error("单张图片超过 40MB");
  const safeName = safeImageName(name);
  const ext = path.extname(safeName).toLowerCase();
  if (!IMAGE_EXT.has(ext)) throw new Error("只接受图片文件（png / jpg / jpeg / webp / gif）");
  const dir = projectMediaPath(projectPath, "图片");
  await mkdir(dir, { recursive: true });
  const target = path.join(dir, safeName);
  await writeFile(target, buffer);
  // 用图片自己的修改时间覆盖落盘时间：拖进来的先后顺序不参与对号
  const when = new Date(Number(mtime));
  if (Number.isFinite(when.getTime()) && when.getTime() > 0) {
    await utimes(target, when, when).catch(() => {});
  }
  const info = await stat(target).catch(() => null);
  return { path: target, name: path.basename(target), size: buffer.length, mtime: info?.mtimeMs ?? Date.now() };
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

/* 旧流程（run_dify_output.sh → TextEdit 贴 Dify 文本）已经不用；终端只保留自由命令。 */
const TERM_PRESETS = [];

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
