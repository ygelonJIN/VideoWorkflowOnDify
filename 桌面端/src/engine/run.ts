import { loadWorkflow } from "./dsl.js";
import type { LoadedWorkflow } from "./dsl.js";
import { runGraph } from "./scheduler.js";
import type { RunOptions, RunResult } from "./scheduler.js";
import { TraceRecorder } from "./trace.js";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join } from "node:path";
import type { StubSource } from "./executors.js";

export function fileStubSource(dir: string): StubSource {
  const cache = new Map<string, string | null>();
  return {
    get(nodeId: string): string | undefined {
      if (!cache.has(nodeId)) {
        const candidates = [`${nodeId}.txt`, `${nodeId}.json`, `${nodeId}.md`];
        let found: string | null = null;
        for (const name of candidates) {
          const path = join(dir, name);
          if (existsSync(path)) {
            found = readFileSync(path, "utf8");
            break;
          }
        }
        cache.set(nodeId, found);
      }
      const value = cache.get(nodeId);
      return value === null ? undefined : (value ?? undefined);
    },
  };
}

export interface RunFileOptions extends Omit<RunOptions, "inputs"> {
  workflowPath: string;
  inputs: Record<string, unknown>;
  tracePath?: string;
}

export interface RunFileResult extends RunResult {
  workflow: LoadedWorkflow;
}

export async function runWorkflowFile(options: RunFileOptions): Promise<RunFileResult> {
  const workflow = loadWorkflow(options.workflowPath);
  const result = await runGraph(workflow, options);
  if (options.tracePath) {
    const recorder = new TraceRecorder();
    for (const event of result.trace) recorder.events.push(event);
    recorder.writeJsonl(options.tracePath);
  }
  return { ...result, workflow };
}
