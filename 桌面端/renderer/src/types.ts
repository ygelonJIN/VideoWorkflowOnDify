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
  name: string;
  version: string;
  appName: string;
  nodes: WorkflowNode[];
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
  error?: string;
}

export interface RunResult {
  runId: string;
  status: string;
  ms: number;
  nodes: RunNodeRecord[];
  outputs: Record<string, unknown>;
  warnings: string[];
  error?: string;
}

export interface EnvInfo {
  hasKey: boolean;
  baseUrl: string;
  model: string;
  stub?: boolean;
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

export interface RunInputs {
  campaign_brief: string;
  request_id: string;
  tts_provider: string;
  tts_voice: string;
  production_requirements: string;
}

declare global {
  interface Window {
    wfs?: import("./bridge.js").Bridge;
  }
}
