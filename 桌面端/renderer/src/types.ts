export interface WorkflowNode {
  id: string;
  type: string;
  title: string;
  position: { x: number; y: number };
  width: number;
  height: number;
  inputs: Array<{ variable: string; selector?: string[]; valueType?: string }>;
  outputs: string[];
  prompt?: string;
  code?: string;
  conditions?: unknown;
  model?: string;
  promptSections?: PromptSection[];
  /** 所属迭代/循环容器；顶层节点为 null。容器内的节点不能单独重跑。 */
  containerId?: string | null;
}

export interface WorkflowEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle: string;
  targetHandle: string;
}

export interface WorkflowInfo {
  path: string;
  rev: string;
  name: string;
  version: string;
  appName: string;
  nodes: WorkflowNode[];
  startVariables: StartVariable[];
  edges: WorkflowEdge[];
  warnings: string[];
}

export interface TraceEvent {
  seq: number;
  /** 哪一条运行发出的；界面同时跑多条时按它分流。 */
  clientId?: string;
  at: string;
  type: "run_start" | "node_start" | "node_end" | "node_error" | "run_end";
  nodeId?: string;
  title?: string;
  status?: string;
  ms?: number;
  error?: string;
}

export interface RunNodeRecord {
  nodeId: string;
  type: string;
  title: string;
  status: string;
  ms: number;
  inputs?: Record<string, string>;
  outputs?: Record<string, unknown>;
  usage?: { input_tokens?: number; output_tokens?: number; total_tokens?: number };
  error?: string;
}

export interface RunResult {
  runId: string;
  status: string;
  ms: number;
  nodes: RunNodeRecord[];
  outputs: Record<string, unknown>;
  outputsByNode?: Record<string, Record<string, unknown>>;
  warnings: string[];
  error?: string;
}

export type RunStatus = "queued" | "running" | "review" | "ready" | "incomplete" | "error" | "stopped";

/** 界面里的一条运行：单条就是一条，批量就是一批。画布、运行台、出片都读当前选中的这条。 */
export interface RunItem {
  id: string;
  /** 这条的原始需求；单条运行可以是空串。 */
  topic: string;
  /** 批量时自动生成的项目名；单条留空，出片页自己取时间戳。 */
  name: string;
  status: RunStatus;
  /** 本次运行的 clientId：事件按它分流，停止也按它。 */
  clientId?: string;
  nodeTitle?: string;
  runningNodeId?: string | null;
  events: TraceEvent[];
  statuses: Record<string, string>;
  result?: RunResult;
  /** 这次运行用的输入快照；审阅续跑、从节点重跑都按它来。 */
  inputs?: RunInputs;
  /** 这条已经渲染过成片：界面上不再是「可出片」，而是「已出片」。 */
  produced?: { dir: string; at: number };
  error?: string;
}

export interface SettingsInfo {
  path: string;
  baseUrl: string;
  model: string;
  protocol: string;
  hasKey: boolean;
  keyHint: string;
  inProcessEnv?: boolean;
  imageBaseUrl: string;
  imageModel: string;
  hasImageKey: boolean;
  imageKeyHint: string;
  imageInProcessEnv?: boolean;
}

export interface EnvInfo {
  hasKey: boolean;
  baseUrl: string;
  model: string;
}

export interface InboxFile {
  name: string;
  path: string;
  size: number;
  mtime: number;
}

export interface Project {
  name: string;
  path: string;
  mtime: number;
}

export interface FileEntry {
  name: string;
  path: string;
  type: "file" | "dir";
  size?: number;
  mtime?: number;
  depth: number;
}

export type RunInputs = Record<string, string>;

export interface StartVariable {
  variable: string;
  label: string;
  type: string;
  required: boolean;
  options: string[];
  maxLength?: number;
}

export interface PromptSection {
  id: string;
  role: string;
  text: string;
}

declare global {
  interface Window {
    wfs?: import("./bridge.js").Bridge;
  }
}

export interface BuildStarted {
  runId: string;
  /** 调用方自己带的构建 id：多个构建并行时用它把事件对上号。 */
  jobId?: string;
  projectDir: string;
  inputPath: string;
  expectedIds: string[];
  hasMimoKey: boolean;
}

export interface BuildRequest {
  action: "prepare" | "render";
  jobId?: string;
  projectName: string;
  outputs: Record<string, unknown>;
  tts?: { provider?: string; baseUrl?: string; model?: string; voice?: string };
  allowMissing?: boolean;
  replace?: boolean;
}

export interface BuildEvent {
  kind: "data" | "done";
  runId: string;
  jobId?: string;
  action: "prepare" | "render";
  stream?: "out" | "err";
  text?: string;
  code?: number;
  ms?: number;
  projectDir?: string;
  expectedIds?: string[];
  error?: string;
}
