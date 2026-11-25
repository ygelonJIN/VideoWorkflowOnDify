import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "./Canvas.js";
import { Inspector } from "./Inspector.js";
import { Artifacts } from "./Artifacts.js";
import { InputPanel } from "./InputPanel.js";
import { Select } from "./Select.js";
import { Settings } from "./Settings.js";
import { Produce } from "./Produce.js";
import { RunSwitch } from "./RunSwitch.js";
import { ReviewPanel } from "./ReviewPanel.js";
import type { SelectOption } from "./Select.js";
import { bridge } from "./bridge.js";
import {
  autoProjectName,
  cleanRequirements,
  hasProducibleOutput,
  precomputedFrom,
  primaryVariable,
  startableCount,
  uniqueProjectName,
} from "../../src/batch/model.js";
import type { EnvInfo, RunInputs, RunItem, RunResult, RunStatus, TraceEvent, WorkflowInfo } from "./types.js";

const api = bridge();

type View = "canvas" | "produce" | "artifacts";

const EMPTY_INPUTS: RunInputs = {};

const ADD_TYPE_OPTIONS: SelectOption[] = [
  { value: "code", label: "Code" },
  { value: "llm", label: "LLM" },
  { value: "if-else", label: "if-else" },
  { value: "template-transform", label: "模板" },
  { value: "http-request", label: "HTTP" },
  { value: "end", label: "End" },
  { value: "iteration", label: "迭代", hint: "暂不支持新建", disabled: true },
  { value: "loop", label: "循环", hint: "暂不支持新建", disabled: true },
  { value: "question-classifier", label: "问题分类", hint: "引擎未实现", disabled: true },
  { value: "variable-aggregator", label: "变量聚合", hint: "引擎未实现", disabled: true },
];

function timeOf(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toTimeString().slice(0, 8);
}

const LAST_RUN_KEY = "studio.lastRun";
const RESUME_KEY = "studio.resumeRun";
const PENDING_REVIEW_KEY = "studio.pendingReview";
const RUNS_KEY = "studio.batchRuns";
const RUN_CAP_KEY = "studio.batchRunCap";

function slimResult(result: RunResult): RunResult {
  return {
    ...result,
    nodes: result.nodes.map((node) => ({ ...node, inputs: undefined, outputs: undefined })),
    outputsByNode: undefined,
  };
}

/** 重启应用后还能接着出片：只存 End 输出和节点状态，不存每个节点的大段输入输出。 */
function readLastRun(): { path: string; at: number; result: RunResult } | null {
  try {
    const raw = localStorage.getItem(LAST_RUN_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { path?: string; at?: number; result?: RunResult };
    if (!saved?.result || typeof saved.result.outputs !== "object" || !saved.result.outputs) return null;
    return { path: saved.path ?? "", at: saved.at ?? 0, result: saved.result };
  } catch {
    return null;
  }
}

function saveLastRun(path: string, result: RunResult): void {
  try {
    localStorage.setItem(LAST_RUN_KEY, JSON.stringify({ path, at: Date.now(), result: slimResult(result) }));
  } catch {
    /* 容量不够就放弃恢复，不影响本次运行 */
  }
}

function clearLastRun(): void {
  try {
    localStorage.removeItem(LAST_RUN_KEY);
    localStorage.removeItem(RESUME_KEY);
  } catch {
    /* 忽略 */
  }
}

/**
 * 中断/失败的运行也要留一份快照：重启应用后「从选中节点重跑」靠它复用前面节点的输出。
 * 和 lastRun 不同，这里要保留 outputs——没有输出就没法复用，等于只能从头跑。
 */
function readResumeRun(): { path: string; at: number; result: RunResult; inputs: RunInputs } | null {
  try {
    const raw = localStorage.getItem(RESUME_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { path?: string; at?: number; result?: RunResult; inputs?: RunInputs };
    if (!saved?.result || !Array.isArray(saved.result.nodes)) return null;
    return { path: saved.path ?? "", at: saved.at ?? 0, result: saved.result, inputs: saved.inputs ?? {} };
  } catch {
    return null;
  }
}

function saveResumeRun(next: { path: string; at: number; result: RunResult; inputs: RunInputs }): void {
  try {
    localStorage.setItem(RESUME_KEY, JSON.stringify(next));
  } catch {
    /* 太大存不下：内存里那份照样能重跑，只是重启后回不来 */
  }
}

function clearResumeRun(): void {
  try {
    localStorage.removeItem(RESUME_KEY);
  } catch {
    /* 忽略 */
  }
}

/** 待审阅的这次运行：停在 A07，结果只在内存里等于迟早会丢，所以单独存一份。 */
interface PendingReview {
  path: string;
  at: number;
  result: RunResult;
  inputs: RunInputs;
}

function readPendingReview(): PendingReview | null {
  try {
    const raw = localStorage.getItem(PENDING_REVIEW_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as Partial<PendingReview>;
    if (!saved?.result || !Array.isArray(saved.result.nodes)) return null;
    return { path: saved.path ?? "", at: saved.at ?? 0, result: saved.result, inputs: saved.inputs ?? {} };
  } catch {
    return null;
  }
}

function savePendingReview(next: PendingReview): void {
  try {
    localStorage.setItem(PENDING_REVIEW_KEY, JSON.stringify(next));
  } catch {
    /* 结果太大存不下：内存里那份照常能审阅，只是重启后回不来 */
  }
}

function clearPendingReview(): void {
  try {
    localStorage.removeItem(PENDING_REVIEW_KEY);
  } catch {
    /* 忽略 */
  }
}

/**
 * 重启后恢复整批的运行视图：只留能接着出片的东西（结果、输入、项目名），
 * 逐节点事件和节点输出不落盘。停在审阅里的那条恢复成「已停止」，要接着跑就重跑。
 */
function readStoredRuns(): { path: string; activeId: string; runs: RunItem[] } | null {
  try {
    const raw = localStorage.getItem(RUNS_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as {
      path?: string;
      activeId?: string;
      runs?: Array<{
        id?: string;
        topic?: string;
        name?: string;
        status?: string;
        result?: RunResult;
        inputs?: RunInputs;
        error?: string;
      }>;
    };
    if (!Array.isArray(saved.runs) || saved.runs.length < 2) return null;
    const allowed: RunStatus[] = ["ready", "incomplete", "error", "stopped"];
    const runs: RunItem[] = saved.runs.map((item) => {
      const status = allowed.includes(item.status as RunStatus) ? (item.status as RunStatus) : "stopped";
      return {
        id: item.id || crypto.randomUUID(),
        topic: item.topic ?? "",
        name: item.name ?? "",
        status,
        events: [],
        statuses: {},
        ...(item.result ? { result: item.result } : {}),
        ...(item.inputs ? { inputs: item.inputs } : {}),
        ...(item.error ? { error: item.error } : {}),
      };
    });
    return { path: saved.path ?? "", activeId: saved.activeId ?? "", runs };
  } catch {
    return null;
  }
}

function readRunCap(): number {
  const parsed = Number(localStorage.getItem(RUN_CAP_KEY));
  if (!Number.isFinite(parsed) || parsed < 1) return 2;
  return Math.min(4, Math.floor(parsed));
}

export function App() {
  const [workflows, setWorkflows] = useState<Array<{ name: string; path: string }>>([]);
  const [graph, setGraph] = useState<WorkflowInfo | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunItem[]>([]);
  const [activeRunId, setActiveRunId] = useState("");
  const [env, setEnv] = useState<EnvInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inputs, setInputs] = useState<RunInputs>(EMPTY_INPUTS);
  const [showInput, setShowInput] = useState(false);
  const [addType, setAddType] = useState("code");
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);
  const [view, setView] = useState<View>("canvas");
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [consoleOpen, setConsoleOpen] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [runCap, setRunCap] = useState(readRunCap);
  const [reviewGate, setReviewGate] = useState(() => localStorage.getItem("studio.reviewGate") !== "0");
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");

  const runsRef = useRef(runs);
  runsRef.current = runs;
  const inputsRef = useRef(inputs);
  inputsRef.current = inputs;
  const launching = useRef(new Set<string>());
  const restoredPath = useRef<string | null>(null);

  const activeRun = runs.find((run) => run.id === activeRunId) ?? runs[0] ?? null;
  const activeIndex = activeRun ? runs.findIndex((run) => run.id === activeRun.id) : -1;
  const result = activeRun?.result ?? null;
  const statuses = activeRun?.statuses ?? {};
  const events = activeRun?.events ?? [];
  const runningNodeId = activeRun?.runningNodeId ?? null;
  const busy = runs.some((run) => run.status === "running" || run.status === "queued");
  const batch = runs.length > 1;
  const runStateText: Record<RunStatus, string> = {
    queued: "排队中",
    running: "运行中",
    review: "待审阅",
    ready: "可出片",
    incomplete: "无成片",
    error: "失败",
    stopped: "已停止",
  };

  // 闸门停在 a07：口播一出来就审，不等到 A17 烧完分镜/动效/合规
  const canReview = Boolean(graph?.nodes.some((node) => node.id === "a07"));

  /** 当前选中的这条如果停在 A07，审阅卡就是它的。 */
  const review = useMemo<PendingReview | null>(() => {
    if (!graph || !activeRun || activeRun.status !== "review" || !activeRun.result) return null;
    return { path: graph.path, at: 0, result: activeRun.result, inputs: activeRun.inputs ?? {} };
  }, [graph, activeRun]);

  useEffect(() => {
    localStorage.setItem(RUN_CAP_KEY, String(runCap));
  }, [runCap]);

  useEffect(() => {
    localStorage.setItem("studio.reviewGate", reviewGate ? "1" : "0");
  }, [reviewGate]);

  const open = useCallback(async (path: string) => {
    try {
      const loaded = await api.load(path);
      setGraph(loaded);
      setSelectedId(null);
      setConnecting(false);
      setConnectFrom(null);
      api.history({ path }).then((state) => {
        setCanUndo(state.canUndo);
        setCanRedo(state.canRedo);
      }).catch(() => {
        setCanUndo(false);
        setCanRedo(false);
      });
      setRuns([]);
      setActiveRunId("");
      setReviewOpen(false);
      setError(null);
      restoredPath.current = null;
    } catch (loadError) {
      setError((loadError as Error).message);
    }
  }, []);

  const pickWorkflow = useCallback(async () => {
    try {
      const picked = await api.pickWorkflow();
      if (!picked) return;
      setWorkflows((previous) =>
        previous.some((item) => item.path === picked)
          ? previous
          : [...previous, { name: picked.split("/").pop() ?? picked, path: picked }],
      );
      await open(picked);
    } catch (cause) {
      fail(cause);
    }
  }, [open]);

  useEffect(() => {
    let alive = true;
    Promise.all([api.workflows(), api.env(), api.inputs()]).then(([list, envInfo, defaults]) => {
      if (!alive) return;
      setWorkflows(list);
      setEnv(envInfo);
      const initialInputs: RunInputs = {};
      for (const [key, value] of Object.entries(defaults)) initialInputs[key] = typeof value === "string" ? value : String(value ?? "");
      setInputs(initialInputs);
      const preferred = list.find((item) => item.name.startsWith("04")) ?? list[0];
      if (preferred) void open(preferred.path);
    }).catch((cause: Error) => {
      setError(`初始化失败：${cause.message}（检查 preload 或重新 npm run app）`);
    });
    return () => {
      alive = false;
    };
  }, [open]);

  /** 恢复上次的视图：待审阅 → 整批 → 上次成功 → 上次中断，只认当前这条 YAML。 */
  useEffect(() => {
    if (!graph || restoredPath.current === graph.path) return;
    restoredPath.current = graph.path;
    const pending = readPendingReview();
    if (pending && pending.path === graph.path) {
      const id = crypto.randomUUID();
      setRuns([{ id, topic: "", name: "", status: "review", events: [], statuses: {}, result: pending.result, inputs: pending.inputs }]);
      setActiveRunId(id);
      setReviewOpen(false);
      setNotice("有一份待审阅的文案已恢复：点顶栏「文案待审阅」继续看。");
      return;
    }
    const stored = readStoredRuns();
    if (stored && stored.path === graph.path) {
      setRuns(stored.runs);
      setActiveRunId(stored.runs.some((run) => run.id === stored.activeId) ? stored.activeId : stored.runs[0]?.id ?? "");
      setNotice(`已恢复上次批量运行（${stored.runs.length} 条）`);
      return;
    }
    const saved = readLastRun();
    if (saved && saved.path === graph.path) {
      const id = crypto.randomUUID();
      setRuns([{
        id,
        topic: "",
        name: "",
        status: hasProducibleOutput(saved.result.outputs) ? "ready" : "incomplete",
        events: [],
        statuses: {},
        result: saved.result,
      }]);
      setActiveRunId(id);
      const when = saved.at ? new Date(saved.at).toLocaleString() : "";
      setNotice(`已恢复上次运行结果${when ? `（${when}）` : ""}，可直接去「出片」接着做`);
      return;
    }
    const resume = readResumeRun();
    if (resume && resume.path === graph.path) {
      const id = crypto.randomUUID();
      setRuns([{
        id,
        topic: "",
        name: "",
        status: "stopped",
        events: [],
        statuses: {},
        result: resume.result,
        inputs: resume.inputs,
      }]);
      setActiveRunId(id);
      const when = resume.at ? new Date(resume.at).toLocaleString() : "";
      setNotice(`已恢复上次中断的运行${when ? `（${when}）` : ""}：选中节点后可在右侧「从此节点重跑」`);
    }
  }, [graph?.path]);

  /** 整批只落盘能接着出片的东西；单条仍走 lastRun / resumeRun。 */
  useEffect(() => {
    if (!graph) return;
    // 空列表是「刚打开工作流、正在恢复」或数量恢复之后的状态：
    // 清空动作由 clearRuns 自己删 key，这里不抢在恢复 effect 之前把它删掉。
    if (runs.length === 0) return;
    if (runs.length === 1) {
      try {
        localStorage.removeItem(RUNS_KEY);
      } catch {
        /* 忽略 */
      }
      return;
    }
    const timer = setTimeout(() => {
      try {
        const payload = {
          path: graph.path,
          at: Date.now(),
          activeId: activeRun?.id ?? "",
          runs: runs.map((run) => ({
            id: run.id,
            topic: run.topic,
            name: run.name,
            // 停在审阅里的那条恢复后没法续跑（节点输出没落盘）：按已停止恢复，想继续就重跑
            status: run.status === "review" ? "stopped" : run.status,
            ...(run.result ? { result: slimResult(run.result) } : {}),
            ...(run.inputs ? { inputs: run.inputs } : {}),
            ...(run.error ? { error: run.error } : {}),
          })),
        };
        localStorage.setItem(RUNS_KEY, JSON.stringify(payload));
      } catch {
        /* 存不下就放弃整批恢复，不影响本次批量 */
      }
    }, 600);
    return () => clearTimeout(timer);
  }, [runs, activeRun?.id, graph?.path]);

  /**
   * 跑一条。批量只是把多条依次丢进这里，由队列闸门控制同时跑几条。
   * overrides.inputs 用于审阅续跑 / 从节点重跑；overrides.precomputed 有值时跳过闸门。
   */
  const launchRun = useCallback(async (
    runId: string,
    overrides?: { inputs?: RunInputs; precomputed?: Record<string, Record<string, unknown>> },
  ) => {
    const item = runsRef.current.find((run) => run.id === runId);
    if (!item || !graph || item.status === "running") return;
    const clientId = crypto.randomUUID();
    const nextInputs = overrides?.inputs ?? item.inputs ?? inputsRef.current;
    const gate = reviewGate && canReview && !overrides?.precomputed;
    setRuns((previous) =>
      previous.map((run) =>
        run.id === runId
          ? {
              ...run,
              status: "running",
              clientId,
              nodeTitle: "启动中…",
              runningNodeId: null,
              events: [],
              statuses: {},
              error: undefined,
              inputs: nextInputs,
            }
          : run,
      ),
    );
    const off = api.onEvent((event: TraceEvent) => {
      // 批量里同时跑着别的链路：事件带 clientId，只改发出它的那条
      if (event.clientId && event.clientId !== clientId) return;
      setRuns((previous) =>
        previous.map((run) => {
          if (run.id !== runId || run.clientId !== clientId) return run;
          if (event.type === "run_end") {
            return { ...run, events: [...run.events, event], runningNodeId: null, nodeTitle: "" };
          }
          if (!event.nodeId) return { ...run, events: [...run.events, event] };
          const status =
            event.type === "node_start" ? "running" : event.type === "node_end" ? "success" : (event.status ?? "error");
          return {
            ...run,
            events: [...run.events, event],
            statuses: { ...run.statuses, [event.nodeId]: status },
            runningNodeId: event.type === "node_start" ? event.nodeId : run.runningNodeId,
            nodeTitle: event.type === "node_start" ? (event.title ?? event.nodeId) : "",
          };
        }),
      );
    });
    try {
      const runResult = await api.run({
        path: graph.path,
        clientId,
        inputs: nextInputs,
        ...(gate ? { until: "a07" } : {}),
        ...(overrides?.precomputed ? { precomputed: overrides.precomputed } : {}),
      });
      setRuns((previous) =>
        previous.map((run) => {
          // 停止后马上重跑时，旧那次的收尾不能再覆盖新那次（clientId 已经换了）
          if (run.id !== runId || run.clientId !== clientId) return run;
          if (gate && runResult.status === "stopped" && runResult.outputsByNode?.["a07"]) {
            return { ...run, status: "review", result: runResult, nodeTitle: "口播待审阅" };
          }
          if (runResult.status === "success") {
            const producible = hasProducibleOutput(runResult.outputs);
            return {
              ...run,
              status: producible ? "ready" : "incomplete",
              result: runResult,
              nodeTitle: "",
              ...(producible ? {} : { error: "运行成功，但没有 html_document / voiceover_script：这条链没走到出片口径。" }),
            };
          }
          return {
            ...run,
            status: runResult.status === "stopped" ? "stopped" : "error",
            result: runResult,
            nodeTitle: "",
            error: runResult.error ?? (runResult.status === "stopped" ? "已停止" : undefined),
          };
        }),
      );

      const single = runsRef.current.length === 1;
      if (gate && runResult.status === "stopped" && runResult.outputsByNode?.["a07"]) {
        const pending: PendingReview = { path: graph.path, at: Date.now(), result: runResult, inputs: nextInputs };
        // 整批的待审阅逐条留在 runs 里，不走单条的恢复快照：否则重启后会丢批次、只剩一条
        if (single) savePendingReview(pending);
        if (single) {
          setReviewOpen(true);
          setReviewNotes("");
          setNotice("口播已生成，先审阅：重跑文案 / 继续生成画面 / 放弃这次运行");
        } else {
          setNotice("有口播待审阅：在上方切换条里点「待审阅」那条逐条审。");
        }
        return;
      }
      const producible = runResult.status === "success" && hasProducibleOutput(runResult.outputs);
      if (single) {
        if (runResult.status === "success") {
          saveLastRun(graph.path, runResult);
          clearResumeRun();
          clearPendingReview();
        } else {
          // 失败/停止也留一份：重启后能「从选中节点重跑」，不必把前面几十分钟再烧一遍
          saveResumeRun({ path: graph.path, at: Date.now(), result: runResult, inputs: nextInputs });
        }
        if (producible) {
          setView("produce");
          setNotice("运行完成，接着按「准备项目 → 复制提示词 → 放图 → 渲染成片」走");
        }
        if (runResult.status === "error" && runResult.error) setError(runResult.error);
        if (runResult.status !== "success" && runResult.error) setNotice(runResult.error);
      } else {
        if (producible) setNotice("这一条跑完了：在上方切换条里逐条去出片。");
        else if (runResult.status === "error") setNotice(runResult.error ?? "有一条运行失败，点切换条看它的日志。");
      }
    } catch (cause) {
      setRuns((previous) =>
        previous.map((run) =>
          run.id === runId && run.clientId === clientId
            ? { ...run, status: "error", error: (cause as Error).message, nodeTitle: "", runningNodeId: null }
            : run,
        ),
      );
      if (runsRef.current.length === 1) setError((cause as Error).message);
      else setNotice((cause as Error).message);
    } finally {
      off();
    }
  }, [graph, reviewGate, canReview]);

  // 运行闸门：排队的行按上限放行
  useEffect(() => {
    const active = runs.filter((run) => run.status === "running").length;
    const queued = runs.filter((run) => run.status === "queued" && !launching.current.has(run.id));
    const count = startableCount(queued.length, active, runCap);
    if (count <= 0) return;
    for (const run of queued.slice(0, count)) {
      launching.current.add(run.id);
      void launchRun(run.id).finally(() => launching.current.delete(run.id));
    }
  }, [runs, runCap, launchRun]);

  /** 单条运行：清掉上一批的切换条，只留这一条。 */
  const startSingle = useCallback(() => {
    if (!graph) return;
    if (runsRef.current.some((run) => run.status === "review")) {
      if (!window.confirm("还有一份待审阅的文案没处理，重新运行会把它丢掉。继续？")) return;
    }
    const replacingBatch = runsRef.current.length > 1;
    setShowInput(false);
    clearPendingReview();
    clearLastRun();
    const target = primaryVariable(graph.startVariables);
    const topic = target ? (inputsRef.current[target] ?? "") : "";
    const id = crypto.randomUUID();
    setRuns([{
      id,
      topic,
      name: "",
      status: "queued",
      events: [],
      statuses: {},
      inputs: { ...inputsRef.current },
    }]);
    setActiveRunId(id);
    setReviewOpen(false);
    setReviewNotes("");
    setView("canvas");
    setInspectorOpen(true);
    setError(null);
    setNotice(replacingBatch ? "已切到单条运行；上一批的切换条收起了，项目和成片还在「产物」里。" : null);
  }, [graph]);

  /** 批量：只换主需求，其余输入全批共用；项目名按主题 + 时间戳自动避开已有目录。 */
  const startBatch = useCallback(async (topics: string[], cap: number) => {
    if (!graph) return;
    if (runsRef.current.some((run) => run.status === "review")) {
      if (!window.confirm("还有待审阅的文案没处理，重新运行会把它丢掉。继续？")) return;
    }
    const clean = cleanRequirements(topics);
    if (clean.length === 0) {
      setNotice("先写至少一条原始需求。");
      return;
    }
    setShowInput(false);
    clearPendingReview();
    clearLastRun();
    const projects = await api.projects().catch(() => []);
    const taken = new Set(projects.map((project) => project.name));
    const target = primaryVariable(graph.startVariables);
    const now = new Date();
    const items: RunItem[] = clean.map((topic, index) => {
      const name = uniqueProjectName(autoProjectName(topic, index, now), taken);
      taken.add(name);
      const nextInputs: RunInputs = { ...inputsRef.current, ...(target ? { [target]: topic } : {}) };
      if ("request_id" in nextInputs || graph.startVariables.some((variable) => variable.variable === "request_id")) {
        nextInputs.request_id = name;
      }
      return {
        id: crypto.randomUUID(),
        topic,
        name,
        status: "queued",
        events: [],
        statuses: {},
        inputs: nextInputs,
      };
    });
    setRunCap(cap);
    setRuns(items);
    setActiveRunId(items[0]?.id ?? "");
    setReviewOpen(false);
    setReviewNotes("");
    setView("canvas");
    setInspectorOpen(true);
    setError(null);
    setNotice(`批量已开始：${items.length} 条，同时跑 ${Math.min(cap, items.length)} 条`);
  }, [graph]);

  const stopAll = useCallback(async () => {
    const live = runsRef.current.filter((run) => run.status === "running" && run.clientId);
    if (live.length === 0 && !runsRef.current.some((run) => run.status === "queued")) return;
    setNotice("正在停止…");
    setRuns((previous) =>
      previous.map((run) =>
        run.status === "running" || run.status === "queued"
          ? { ...run, status: "stopped", nodeTitle: "", runningNodeId: null }
          : run,
      ),
    );
    await Promise.all(live.map((run) => api.cancel(run.clientId as string).catch(() => undefined)));
  }, []);

  const selectRun = useCallback((id: string) => {
    const run = runsRef.current.find((item) => item.id === id);
    setActiveRunId(id);
    setReviewNotes("");
    setReviewOpen(run?.status === "review");
    if (run?.status === "review") setNotice(null);
  }, []);

  const continueFromReview = useCallback(() => {
    if (!review || !activeRun) return;
    const precomputed = precomputedFrom(review.result);
    clearPendingReview();
    setReviewOpen(false);
    void launchRun(activeRun.id, { inputs: review.inputs, precomputed });
  }, [review, activeRun, launchRun]);

  const rerunFromReview = useCallback((notes: string) => {
    if (!review || !activeRun) return;
    const base = review.inputs;
    const next: RunInputs = { ...base };
    const note = notes.trim();
    if (note) {
      next.creative_preferences = [base.creative_preferences, "修改意见：" + note].filter(Boolean).join("\n");
    }
    // 单条时把修改意见写回共用输入，下次运行也带着；批量只影响这一条
    if (!batch) setInputs(next);
    clearPendingReview();
    setReviewOpen(false);
    void launchRun(activeRun.id, { inputs: next });
  }, [review, activeRun, batch, launchRun]);

  /** 只把卡片收起来：这次 A 段结果留着，顶栏有入口点回来。 */
  const collapseReview = useCallback(() => {
    setReviewOpen(false);
    setNotice("审阅卡已收起：文案还在，点顶栏「文案待审阅」可以点回来。");
  }, []);

  /** 真的放弃这次运行：丢掉 A 段结果和本地备份。 */
  const discardReview = useCallback(() => {
    clearPendingReview();
    setRuns((previous) =>
      previous.map((run) =>
        run.id === activeRun?.id ? { ...run, status: "stopped", result: undefined, nodeTitle: "" } : run,
      ),
    );
    setReviewOpen(false);
    setNotice("已放弃这次运行，未生成画面；改完输入可以重新运行。");
  }, [activeRun?.id]);

  const clearRuns = useCallback(() => {
    setRuns([]);
    setActiveRunId("");
    setReviewOpen(false);
    try {
      localStorage.removeItem(RUNS_KEY);
    } catch {
      /* 忽略 */
    }
    setNotice("已收起这一批的切换条；已经生成的项目和成片还在「产物」里。");
  }, []);

  const reloadGraph = useCallback(async (force: boolean) => {
    if (!graph || busy) return;
    try {
      if (!force) {
        const { rev } = await api.rev(graph.path);
        if (!rev || rev === graph.rev) return;
      }
      const loaded = await api.load(graph.path);
      setGraph(loaded);
      setError(null);
      setNotice(force ? `已重载 YAML（rev ${loaded.rev.slice(0, 8)}）` : "检测到外部修改，已重新载入 YAML");
    } catch (cause) {
      // 非强制那次是后台同步：文件暂时读不到就不打断当前操作，下一次编辑/运行会给出具体错误
      if (force) setError((cause as Error).message);
    }
  }, [graph, busy]);

  // 别的脚本改了 YAML 时，窗口重新获得焦点就比对 sha1 并同步一次
  const syncExternal = useCallback(async () => {
    await reloadGraph(false);
  }, [reloadGraph]);

  useEffect(() => {
    const onFocus = () => {
      void syncExternal();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [syncExternal]);

  const selected = useMemo(() => graph?.nodes.find((node) => node.id === selectedId) ?? null, [graph, selectedId]);

  /** 有可出片结果时顶栏「出片」亮一个点。数量在步骤条里，这里只回答「有没有东西可做」。 */
  const produced = runs.some((run) => run.result && hasProducibleOutput(run.result.outputs));

  useEffect(() => {
    const prevent = (event: DragEvent) => event.preventDefault();
    window.addEventListener("dragover", prevent);
    window.addEventListener("drop", prevent);
    return () => {
      window.removeEventListener("dragover", prevent);
      window.removeEventListener("drop", prevent);
    };
  }, []);

  const fail = (cause: unknown) => setError((cause as Error).message);

  /**
   * 从选中节点重跑：把该节点**之前**已经成功的 LLM/代码节点输出原样喂回去，跳过它们。
   * 调度器只复用顶层 LLM/代码节点（`precomputed`），所以：
   * - 容器节点（迭代/循环）本身可以当起点，容器内部节点不行；
   * - 起点之前的 LLM/代码节点不重新请求，省掉重跑最贵的那一段；
   * - 上次运行没跑过该节点时，前面能复用的照样复用。
   */
  const runFromNode = useCallback((nodeId: string) => {
    if (!graph || busy || !activeRun) return;
    const target = graph.nodes.find((node) => node.id === nodeId) ?? null;
    if (!result) {
      setNotice("还没有可复用的运行结果：先完整跑一次，之后才能从中途重跑。");
      return;
    }
    if (target?.containerId) {
      setNotice("这个节点在迭代/循环容器里，容器内部不能单独重跑：选中容器节点本身（例如 H02I）再重跑。");
      return;
    }
    const precomputed: Record<string, Record<string, unknown>> = {};
    // 只收顶层节点：容器内部的记录调度器根本不会命中，传过去只是白搬几 MB 的每屏 HTML
    const topLevel = new Set(graph.nodes.filter((node) => !node.containerId).map((node) => node.id));
    for (const record of result.nodes) {
      if (record.nodeId === nodeId) break;
      if (!topLevel.has(record.nodeId)) continue;
      if ((record.type === "llm" || record.type === "code") && record.status === "success" && record.outputs) {
        precomputed[record.nodeId] = record.outputs;
      }
    }
    const reused = Object.keys(precomputed).length;
    // 一个都复用时等于整跑，闸门照旧生效，所以不传空的 precomputed
    void launchRun(activeRun.id, {
      inputs: activeRun.inputs ?? inputs,
      ...(reused > 0 ? { precomputed } : {}),
    });
  }, [graph, busy, activeRun, result, inputs, launchRun]);

  function applyUpdate(result: { graph: WorkflowInfo; canUndo?: boolean; canRedo?: boolean }) {
    setGraph(result.graph);
    if (typeof result.canUndo === "boolean") setCanUndo(result.canUndo);
    if (typeof result.canRedo === "boolean") setCanRedo(result.canRedo);
    setError(null);
  }

  async function undo() {
    if (!graph) return;
    try {
      applyUpdate(await api.undo({ path: graph.path }));
      setSelectedId(null);
    } catch (cause) {
      fail(cause);
    }
  }

  async function redo() {
    if (!graph) return;
    try {
      applyUpdate(await api.redo({ path: graph.path }));
      setSelectedId(null);
    } catch (cause) {
      fail(cause);
    }
  }

  async function moveNode(nodeId: string, position: { x: number; y: number }) {
    if (!graph) return;
    const path = graph.path;
    // 先本地落位，松手瞬间不闪回；写盘在后台完成，成功不再用返回的图覆盖画面
    setGraph((previous) =>
      previous
        ? { ...previous, nodes: previous.nodes.map((node) => (node.id === nodeId ? { ...node, position } : node)) }
        : previous,
    );
    try {
      const result = await api.moveNode({ path, nodeId, position });
      if (typeof result.canUndo === "boolean") setCanUndo(result.canUndo);
      if (typeof result.canRedo === "boolean") setCanRedo(result.canRedo);
      setError(null);
    } catch (cause) {
      fail(cause);
      try {
        setGraph(await api.load(path));
      } catch {
        /* 保持当前画面，错误已经提示 */
      }
    }
  }

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "z") return;
      event.preventDefault();
      if (event.shiftKey) void redo();
      else void undo();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function addNode() {
    if (!graph) return;
    const source = selected ?? graph.nodes.find((node) => node.type === "start") ?? null;
    const position = source
      ? { x: source.position.x + source.width + 70, y: source.position.y }
      : { x: 120, y: 120 };
    try {
      const result = await api.addNode({
        path: graph.path,
        type: addType,
        title: `新 ${addType}`,
        position,
        sourceId: source?.id ?? null,
      });
      applyUpdate(result);
      setSelectedId(result.nodeId);
    } catch (cause) {
      fail(cause);
    }
  }

  function handleNodeClick(id: string) {
    if (!connecting || !graph) {
      setSelectedId(id);
      return;
    }
    if (!connectFrom) {
      setConnectFrom(id);
      return;
    }
    if (connectFrom === id) {
      setConnectFrom(null);
      return;
    }
    api.connect({ path: graph.path, source: connectFrom, target: id })
      .then((result) => {
        applyUpdate(result);
        setConnecting(false);
        setConnectFrom(null);
      })
      .catch(fail);
  }

  async function handleEdgeClick(edgeId: string) {
    if (!graph) return;
    if (!window.confirm("删除这条连线？")) return;
    try {
      const result = await api.removeEdge({ path: graph.path, edgeId });
      applyUpdate(result);
    } catch (cause) {
      fail(cause);
    }
  }

  async function deleteNode() {
    if (!graph || !selected) return;
    if (!window.confirm(`删除节点「${selected.title}」？相关连线会一起删掉；一进一出时会自动接上。`)) return;
    try {
      const result = await api.removeNode({ path: graph.path, nodeId: selected.id });
      applyUpdate(result);
      setSelectedId(null);
    } catch (cause) {
      fail(cause);
    }
  }

  const showRunsBar = runs.length > 1 && view !== "artifacts";

  return (
    <div className={`app ${showRunsBar ? "has-runs" : ""}`}>
      <header className="topbar card">
        <div className="brand">
          <span className="name">视频工作流</span>
          <span className="sub">Studio</span>
        </div>
        <span className="vline" />
        <Select
          value={graph?.path ?? ""}
          width={240}
          options={[
            ...workflows.map((workflow) => ({ value: workflow.path, label: workflow.name })),
            ...(graph && !workflows.some((workflow) => workflow.path === graph.path)
              ? [{ value: graph.path, label: graph.name }]
              : []),
          ]}
          onChange={(path) => void open(path)}
          placeholder="选择工作流"
        />
        <button className="btn sm ghost" onClick={() => void pickWorkflow()}>打开…</button>
        <button
          className="btn sm ghost"
          onClick={() => void reloadGraph(true)}
          disabled={!graph || busy}
          title="重新读取磁盘上的 YAML（外部改过就用这个，不必切窗口触发同步）"
        >
          重载
        </button>

        <span className="spacer" />

        <div className="seg" role="tablist" aria-label="视图">
          <button
            role="tab"
            aria-selected={view === "canvas"}
            className={view === "canvas" ? "on" : ""}
            onClick={() => setView("canvas")}
          >
            画布
          </button>
          <button
            role="tab"
            aria-selected={view === "produce"}
            className={view === "produce" ? "on" : ""}
            onClick={() => setView("produce")}
            title="运行完成后：准备项目 → 出图提示词 → 放图 → 渲染成片"
          >
            出片{produced && view !== "produce" && <span className="dot" />}
          </button>
          <button
            role="tab"
            aria-selected={view === "artifacts"}
            className={view === "artifacts" ? "on" : ""}
            onClick={() => setView("artifacts")}
          >
            产物
          </button>
        </div>

        <span className="spacer" />

        <span className="topbar-meta" title={graph?.path ?? ""}>
          {graph ? `${graph.nodes.length} 节点` : "未载入"}
          {env ? ` · ${env.model}` : ""}
          {env?.hasKey ? " · key 已配置" : " · 无 key"}
        </span>
        {/* 撤销/重做/运行/设置是一组：换行时整组一起换，不拆散 */}
        <div className="topbar-actions">
          <button
            className="btn sm ghost"
            onClick={() => void undo()}
            disabled={!canUndo || view !== "canvas"}
            title="撤销（⌘Z）"
          >
            撤销
          </button>
          <button
            className="btn sm ghost"
            onClick={() => void redo()}
            disabled={!canRedo || view !== "canvas"}
            title="重做（⇧⌘Z）"
          >
            重做
          </button>
          <span className="vline" />
          {busy ? (
            <button className="btn sm danger stop" onClick={() => void stopAll()} title="停止这一批里所有在跑和排队的条目">
              停止
            </button>
          ) : (
            <button
              className="btn primary run"
              onClick={() => setShowInput(true)}
              disabled={!graph}
              title="打开运行输入：单条，或一次批量跑同一工作流的多条需求"
            >
              运行
            </button>
          )}
          <button className="btn sm ghost" onClick={() => setShowSettings(true)}>设置</button>
          {review && !reviewOpen && (
            <button
              className="btn sm pending"
              onClick={() => {
                setReviewOpen(true);
                setNotice(null);
              }}
              title="回到 A07 口播审阅卡：重跑文案 / 继续生成画面 / 放弃这次运行"
            >
              文案待审阅 · 点开
            </button>
          )}
        </div>
      </header>

      {showRunsBar && (
        <RunSwitch runs={runs} activeId={activeRun?.id ?? ""} busy={busy} onSelect={selectRun} onClear={clearRuns} />
      )}

      <div className={`work ${view === "canvas" && inspectorOpen && graph ? "" : "solo"}`}>
        <div className="main">
          {view === "artifacts" ? (
            <Artifacts result={result} />
          ) : view === "canvas" ? (
            graph ? (
              <Canvas
                graph={graph}
                selectedId={selectedId}
                connectSource={connectFrom}
                statuses={statuses}
                onSelect={handleNodeClick}
                onEdgeClick={(edgeId) => void handleEdgeClick(edgeId)}
                onMoveNode={(nodeId, position) => void moveNode(nodeId, position)}
                runningNodeId={runningNodeId}
                toolbar={
                  <>
                    <Select value={addType} options={ADD_TYPE_OPTIONS} onChange={setAddType} />
                    <button className="btn sm" onClick={() => void addNode()}>添加节点</button>
                    <button
                      className={`btn sm ${connecting ? "primary" : ""}`}
                      onClick={() => {
                        setConnecting((value) => !value);
                        setConnectFrom(null);
                      }}
                    >
                      {connecting ? (connectFrom ? "选目标…" : "选起点…") : "连线"}
                    </button>
                    <span className="dock-sep" />
                    <button
                      className={`btn sm insp-toggle ${inspectorOpen ? "on" : ""}`}
                      onClick={() => setInspectorOpen((value) => !value)}
                      title={inspectorOpen ? "收起右侧详情和运行台" : "展开右侧详情和运行台"}
                    >
                      详情
                    </button>
                  </>
                }
              />
            ) : (
              <section className="canvas-wrap card">
                <div className="hint-text" style={{ padding: 16 }}>载入中…</div>
              </section>
            )
          ) : null}
          <div className="produce-layer" hidden={view !== "produce"}>
            <Produce
              result={result}
              inputs={activeRun?.inputs ?? inputs}
              defaultName={activeRun?.name ?? ""}
              batch={batch && activeRun ? { index: activeIndex, total: runs.length, topic: activeRun.topic } : null}
              onRun={() => setShowInput(true)}
              onArtifacts={() => setView("artifacts")}
              onNotice={setNotice}
            />
          </div>
        </div>

        {view === "canvas" && inspectorOpen && graph ? (
          <div className="side">
            <Inspector
              graph={graph}
              node={selected}
              result={result}
              status={selectedId ? (statuses[selectedId] ?? "") : ""}
              runtimeModel={env?.model}
              onUpdate={async (field, value, messageIndex) => {
                if (!selected) return;
                const updated = await api.updateNode({
                  path: graph.path,
                  nodeId: selected.id,
                  field,
                  value,
                  ...(messageIndex !== undefined ? { messageIndex } : {}),
                });
                applyUpdate(updated);
              }}
              onDelete={() => void deleteNode()}
              onRerun={runFromNode}
              onProduce={() => setView("produce")}
            />
            <footer className={`bottom card ${consoleOpen ? "" : "collapsed"}`}>
              <div className="console-head">
                <span className="console-title">运行台</span>
                {batch && activeRun && (
                  <span className="console-run">第 {activeIndex + 1}/{runs.length} 条</span>
                )}
                <span className="right">
                  <span className="elapsed">
                    {activeRun
                      ? `${runStateText[activeRun.status]}${result ? ` · ${(result.ms / 1000).toFixed(2)}s` : ""}`
                      : "就绪"}
                  </span>
                </span>
                <button className="btn sm ghost toggle" onClick={() => setConsoleOpen((value) => !value)}>
                  {consoleOpen ? "收起" : "展开"}
                </button>
              </div>
              <div className="pane">
                <div className="log">
                  {result && result.status === "success" && typeof result.outputs.html_document === "string" && (
                    <div className="run-next">
                      <span>运行完成 · {result.nodes.length} 节点 · {(result.ms / 1000).toFixed(1)}s</span>
                      <span className="spacer" />
                      <button className="btn sm primary" onClick={() => setView("produce")}>下一步：去出片</button>
                    </div>
                  )}
                  {error && <div className="err">{error}</div>}
                  {activeRun?.error && activeRun.status !== "review" && <div className="err">{activeRun.error}</div>}
                  {[...events].reverse().filter((event) => event.type !== "node_start").slice(0, 300).map((event) => (
                    <div key={event.seq}>
                      <span className="t">{timeOf(event.at)}</span>
                      <span className={event.type === "node_error" ? "err" : event.type === "run_end" ? "ok" : "dim"}>
                        {event.type === "node_end" ? "完成" : event.type === "node_error" ? "失败" : "事件"}
                      </span>
                      <span>{event.title ?? event.type}</span>
                      {event.ms !== undefined && <span className="dim">{event.ms}ms</span>}
                      {event.error && <span className="err">{event.error}</span>}
                    </div>
                  ))}
                  {events.length === 0 && !result && activeRun?.status !== "running" && (
                    <div className="dim">点右上「运行」开始；可以在里面选单条或批量。会真实调用模型（先在顶栏「设置」里配 Key）。</div>
                  )}
                  {events.length === 0 && result && <div className="dim">逐节点事件没有保留（应用重启过）；End 输出已恢复，可直接去「出片」。</div>}
                  {result && Object.keys(result.outputs).length > 0 && (
                    <div className="dim">产物：{Object.keys(result.outputs).join("、")}</div>
                  )}
                </div>
              </div>
            </footer>
          </div>
        ) : null}
      </div>

      {showInput && (
        <InputPanel
          inputs={inputs}
          variables={graph?.startVariables ?? []}
          running={busy}
          onChange={(patch) => setInputs((previous) => ({ ...previous, ...patch }))}
          hasKey={Boolean(env?.hasKey)}
          reviewGate={reviewGate}
          canReview={canReview}
          onReviewGateChange={setReviewGate}
          onRun={startSingle}
          onRunBatch={(topics, cap) => void startBatch(topics, cap)}
          runCap={runCap}
          onRunCapChange={setRunCap}
          onClose={() => setShowInput(false)}
        />
      )}

      {review && reviewOpen && (
        <ReviewPanel
          result={review.result}
          busy={activeRun?.status === "running" || activeRun?.status === "queued"}
          notes={reviewNotes}
          onNotesChange={setReviewNotes}
          onContinue={continueFromReview}
          onRerun={rerunFromReview}
          onCollapse={collapseReview}
          onDiscard={discardReview}
        />
      )}

      {showSettings && (
        <Settings
          onClose={() => setShowSettings(false)}
          onSaved={(next) => {
            api.env().then(setEnv).catch(() => {});
            setNotice(next.hasKey ? "设置已保存" : "设置已保存（还没有 Key）");
          }}
        />
      )}

      {notice && (
        <div className="toast" role="status">
          <span>{notice}</span>
          <button className="btn sm ghost" onClick={() => setNotice(null)}>知道了</button>
        </div>
      )}
    </div>
  );
}
