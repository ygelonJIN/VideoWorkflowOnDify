import { writeFileSync } from "node:fs";
import type { TokenUsage } from "./types.js";

export type TraceEventType = "run_start" | "node_start" | "node_end" | "node_error" | "run_end";

export interface TraceEvent {
  seq: number;
  at: string;
  type: TraceEventType;
  nodeId?: string;
  nodeType?: string;
  title?: string;
  status?: string;
  ms?: number;
  usage?: TokenUsage;
  nextHandle?: string;
  error?: string;
}

export class TraceRecorder {
  readonly events: TraceEvent[] = [];

  emit(event: Omit<TraceEvent, "seq" | "at">): TraceEvent {
    const full: TraceEvent = { seq: this.events.length + 1, at: new Date().toISOString(), ...event };
    this.events.push(full);
    return full;
  }

  toJSONL(): string {
    return this.events.map((event) => JSON.stringify(event)).join("\n") + "\n";
  }

  writeJsonl(path: string): void {
    writeFileSync(path, this.toJSONL(), "utf8");
  }
}
