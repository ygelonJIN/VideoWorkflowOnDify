/** Dify App DSL 0.7.0 里我们会用到的结构。未列出的字段一律保留。 */
export interface DslPosition { x: number; y: number }

export interface DslNodeData {
  type: string;
  title?: string;
  [key: string]: unknown;
}

export interface DslNode {
  id: string;
  type: string;
  data: DslNodeData;
  position?: DslPosition;
  positionAbsolute?: DslPosition;
  width?: number;
  height?: number;
  [key: string]: unknown;
}

export interface DslEdge {
  id: string;
  source: string;
  target: string;
  sourceHandle?: string;
  targetHandle?: string;
  data?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface WorkflowGraph {
  nodes: DslNode[];
  edges: DslEdge[];
}

export interface EnvironmentVariable {
  name: string;
  value?: unknown;
  value_type?: string;
  description?: string;
}

export interface DslWorkflow {
  graph?: WorkflowGraph;
  environment_variables?: EnvironmentVariable[];
  conversation_variables?: unknown[];
  features?: unknown;
  [key: string]: unknown;
}

export interface DslDocument {
  version?: string;
  kind?: string;
  app?: Record<string, unknown>;
  dependencies?: unknown[];
  workflow?: DslWorkflow;
  [key: string]: unknown;
}

export type Selector = string[];

export interface VariableDefinition {
  variable: string;
  value_selector?: Selector;
  value_type?: string;
  label?: string;
  required?: boolean;
}

export interface OutputDefinition {
  variable: string;
  value_selector: Selector;
  value_type?: string;
}

export type NodeStatus = "pending" | "running" | "success" | "error" | "skipped" | "unimplemented";

export interface TokenUsage {
  input_tokens?: number;
  output_tokens?: number;
  total_tokens?: number;
}
