import type { EnvInfo, FileEntry, Project, RunInputs, RunResult, SettingsInfo, TermEvent, TermPreset, TraceEvent, WorkflowInfo } from "./types.js";

export interface Bridge {
  workflows(): Promise<Array<{ name: string; path: string }>>;
  pickWorkflow(): Promise<string | null>;
  load(path: string): Promise<WorkflowInfo>;
  rev(path: string): Promise<{ rev: string }>;
  run(options: { path: string; stub: boolean; until?: string; inputs?: Partial<RunInputs>; clientId?: string }): Promise<RunResult>;
  cancel(clientId: string): Promise<{ ok: boolean; error?: string }>;
  env(): Promise<EnvInfo>;
  settings(): Promise<SettingsInfo>;
  saveSettings(payload: { baseUrl?: string; model?: string; protocol?: string; apiKey?: string; clearKey?: boolean }): Promise<SettingsInfo>;
  inputs(): Promise<Partial<RunInputs>>;
  onEvent(handler: (event: TraceEvent) => void): () => void;
  projects(): Promise<Project[]>;
  updateNode(options: { path: string; nodeId: string; field: "title" | "prompt" | "code"; value: string; messageIndex?: number }): Promise<{ ok: boolean; mirror?: string | null; mirrorWarning?: string; graph: WorkflowInfo }>;
  fileUrl(filePath: string): Promise<string>;
  addNode(options: { path: string; type: string; title?: string; position?: { x: number; y: number }; sourceId?: string | null }): Promise<{ nodeId: string; graph: WorkflowInfo }>;
  removeNode(options: { path: string; nodeId: string }): Promise<{ graph: WorkflowInfo }>;
  connect(options: { path: string; source: string; target: string; sourceHandle?: string }): Promise<{ graph: WorkflowInfo }>;
  removeEdge(options: { path: string; edgeId: string }): Promise<{ graph: WorkflowInfo; canUndo?: boolean; canRedo?: boolean }>;
  moveNode(options: { path: string; nodeId: string; position: { x: number; y: number } }): Promise<{ graph: WorkflowInfo; canUndo?: boolean; canRedo?: boolean }>;
  history(options: { path: string }): Promise<{ canUndo: boolean; canRedo: boolean }>;
  undo(options: { path: string }): Promise<{ graph: WorkflowInfo; canUndo: boolean; canRedo: boolean }>;
  redo(options: { path: string }): Promise<{ graph: WorkflowInfo; canUndo: boolean; canRedo: boolean }>;
  files(dirPath: string): Promise<FileEntry[]>;
  readText(filePath: string): Promise<{ path: string; text: string; truncated: boolean }>;
  open(filePath: string): Promise<{ ok: boolean; error?: string }>;
  presets(): Promise<TermPreset[]>;
  exec(options: { cmd: string; cwd?: string }): Promise<{ id: string }>;
  onTerm(handler: (event: TermEvent) => void): () => void;
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error(`${url} 失败：${response.status}`);
  return response.json() as Promise<T>;
}

const httpBridge: Bridge = {
  workflows: () => fetch("/api/workflows").then((response) => response.json()),
  pickWorkflow: async () => {
    // 浏览器调试壳没有原生文件框，退化成手填绝对路径
    const typed = window.prompt("输入 YAML 的绝对路径");
    return typed && typed.trim() ? typed.trim() : null;
  },
  load: (path) => post<WorkflowInfo>("/api/load", { path }),
  rev: (path) => post<{ rev: string }>("/api/rev", { path }),
  run: (options) => post<RunResult>("/api/run", options),
  cancel: (clientId) => post<{ ok: boolean; error?: string }>("/api/cancel", { clientId }),
  env: () => fetch("/api/env").then((response) => response.json()),
  settings: () => fetch("/api/settings").then((response) => response.json()),
  saveSettings: (payload) => post<SettingsInfo>("/api/save-settings", payload),
  inputs: () => fetch("/api/inputs").then((response) => response.json()),
  projects: () => fetch("/api/projects").then((response) => response.json()),
  updateNode: (options) => post("/api/update-node", options),
  fileUrl: async (filePath) => {
    const result = await post<{ url: string }>("/api/file-url", { path: filePath });
    return result.url;
  },
  addNode: (options) => post("/api/add-node", options),
  removeNode: (options) => post("/api/remove-node", options),
  connect: (options) => post("/api/connect", options),
  removeEdge: (options) => post("/api/remove-edge", options),
  moveNode: (options) => post("/api/move-node", options),
  history: (options) => post("/api/history", options),
  undo: (options) => post("/api/undo", options),
  redo: (options) => post("/api/redo", options),
  files: (dirPath) => post<FileEntry[]>("/api/files", { path: dirPath }),
  readText: (filePath) => post("/api/read", { path: filePath }),
  open: async (filePath) => {
    window.open(`/files?path=${encodeURIComponent(filePath)}`, "_blank");
    return { ok: true };
  },
  presets: () => fetch("/api/presets").then((response) => response.json()),
  exec: (options) => post<{ id: string }>("/api/exec", options),
  onEvent: (handler) => {
    const source = new EventSource("/api/events");
    source.addEventListener("trace", (event) => {
      try {
        handler(JSON.parse(String((event as MessageEvent).data)) as TraceEvent);
      } catch {
        /* ignore */
      }
    });
    return () => source.close();
  },
  onTerm: (handler) => {
    const source = new EventSource("/api/events");
    const listen = (name: string, kind: "data" | "done") => (event: MessageEvent) => {
      try {
        handler({ kind, ...(JSON.parse(String(event.data)) as Omit<TermEvent, "kind">) });
      } catch {
        /* ignore */
      }
    };
    const data = listen("term", "data");
    const done = listen("term-done", "done");
    source.addEventListener("term", data as EventListener);
    source.addEventListener("term-done", done as EventListener);
    return () => {
      source.removeEventListener("term", data as EventListener);
      source.removeEventListener("term-done", done as EventListener);
      source.close();
    };
  },
};

export function bridge(): Bridge {
  return window.wfs ?? httpBridge;
}
