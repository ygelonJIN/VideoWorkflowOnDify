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

export interface SettingsInfo {
  path: string;
  baseUrl: string;
  model: string;
  protocol: string;
  hasKey: boolean;
  keyHint: string;
  inProcessEnv?: boolean;
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

export interface TermEvent {
  kind: "data" | "done";
  id: string;
  stream?: "out" | "err";
  text?: string;
  code?: number;
  ms?: number;
  output?: string;
  error?: string;
}

export interface TermPreset {
  id: string;
  label: string;
  cmd: string;
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
  projectDir: string;
  inputPath: string;
  expectedIds: string[];
  hasMimoKey: boolean;
}

export interface BuildRequest {
  action: "prepare" | "render";
  projectName: string;
  outputs: Record<string, unknown>;
  tts?: { provider?: string; baseUrl?: string; model?: string; voice?: string };
  allowMissing?: boolean;
}

export interface BuildEvent {
  kind: "data" | "done";
  runId: string;
  action: "prepare" | "render";
  stream?: "out" | "err";
  text?: string;
  code?: number;
  ms?: number;
  projectDir?: string;
  expectedIds?: string[];
  error?: string;
}
