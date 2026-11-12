import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "./Canvas.js";
import { Inspector } from "./Inspector.js";
import { Terminal } from "./Terminal.js";
import { Artifacts } from "./Artifacts.js";
import { InputPanel } from "./InputPanel.js";
import { Select } from "./Select.js";
import { Settings } from "./Settings.js";
import { Produce } from "./Produce.js";
import { ReviewPanel } from "./ReviewPanel.js";
import type { SelectOption } from "./Select.js";
import { bridge } from "./bridge.js";
import type { EnvInfo, RunInputs, RunResult, TraceEvent, WorkflowInfo } from "./types.js";

const api = bridge();

type Tab = "run" | "terminal";
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
    const slim: RunResult = {
      ...result,
      nodes: result.nodes.map((node) => ({ ...node, inputs: undefined, outputs: undefined })),
      outputsByNode: undefined,
    };
    localStorage.setItem(LAST_RUN_KEY, JSON.stringify({ path, at: Date.now(), result: slim }));
  } catch {
    /* 容量不够就放弃恢复，不影响本次运行 */
  }
}

const PENDING_REVIEW_KEY = "studio.pendingReview";

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

export function App() {
  const [workflows, setWorkflows] = useState<Array<{ name: string; path: string }>>([]);
  const [graph, setGraph] = useState<WorkflowInfo | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [tab, setTab] = useState<Tab>("run");
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
  const [runningNodeId, setRunningNodeId] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [reviewGate, setReviewGate] = useState(() => localStorage.getItem("studio.reviewGate") !== "0");
  const [review, setReview] = useState<PendingReview | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [reviewNotes, setReviewNotes] = useState("");
  const runClientId = useRef<string | null>(null);
  // 闸门停在 a07：口播一出来就审，不等到 A17 烧完分镜/动效/合规
  const canReview = Boolean(graph?.nodes.some((node) => node.id === "a07"));

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
      setStatuses({});
      setEvents([]);
      setResult(null);
      setError(null);
      // 换工作流时，待审阅的那份只属于它自己的流程：同一条路径就恢复成收起状态，顶栏能点开
      const pending = readPendingReview();
      if (pending && pending.path === path) {
        setReview(pending);
        setReviewOpen(false);
        setReviewNotes("");
        setNotice("有一份待审阅的文案已恢复：点顶栏「文案待审阅」继续看。");
      } else {
        setReview(null);
        setReviewOpen(false);
      }
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
    localStorage.setItem("studio.reviewGate", reviewGate ? "1" : "0");
  }, [reviewGate]);

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

  const run = useCallback(async (overrides?: { inputs?: RunInputs; precomputed?: Record<string, Record<string, unknown>> }) => {
    if (!graph || running) return;
    const effectiveInputs = overrides?.inputs ?? inputs;
    const gate = reviewGate && canReview && !overrides?.precomputed;
    const clientId = crypto.randomUUID();
    runClientId.current = clientId;
    setRunning(true);
    setStatuses({});
    setEvents([]);
    setResult(null);
    setError(null);
    setNotice(null);
    setRunningNodeId(null);
    setTab("run");
    const unsubscribe = api.onEvent((event) => {
      setEvents((previous) => [...previous, event]);
      if (event.nodeId) {
        setStatuses((previous) => ({
          ...previous,
          [event.nodeId as string]:
            event.type === "node_start" ? "running" : event.type === "node_end" ? "success" : (event.status ?? "error"),
        }));
        if (event.type === "node_start") {
          setRunningNodeId(event.nodeId);
          setSelectedId(event.nodeId);
        }
      }
      if (event.type === "run_end") setRunningNodeId(null);
    });
    try {
      const runResult = await api.run({
        path: graph.path,
        clientId,
        inputs: effectiveInputs,
        ...(gate ? { until: "a07" } : {}),
        ...(overrides?.precomputed ? { precomputed: overrides.precomputed } : {}),
      });
      if (gate && runResult.status === "stopped" && runResult.outputsByNode?.["a07"]) {
        const pending: PendingReview = { path: graph.path, at: Date.now(), result: runResult, inputs: effectiveInputs };
        setReview(pending);
        setReviewOpen(true);
        setReviewNotes("");
        savePendingReview(pending);
        setNotice("口播已生成，先审阅：重跑文案 / 继续生成画面 / 放弃这次运行");
        return;
      }
      setResult(runResult);
      // 只记成功的结果：重跑失败时别把上一次能出片的运行覆盖掉
      if (runResult.status === "success") saveLastRun(graph.path, runResult);
      const produced =
        typeof runResult.outputs.html_document === "string" && typeof runResult.outputs.voiceover_script === "string";
      if (runResult.status === "success" && produced) {
        setView("produce");
        setNotice("运行完成，接着按「准备项目 → 复制提示词 → 放图 → 渲染成片」走");
      }
      if (runResult.status === "error" && runResult.error) setError(runResult.error);
      if (runResult.status !== "success" && runResult.error) setNotice(runResult.error);
    } catch (runError) {
      setError((runError as Error).message);
    } finally {
      unsubscribe();
      runClientId.current = null;
      setRunning(false);
    }
  }, [graph, running, inputs, reviewGate, canReview]);

  const stop = useCallback(async () => {
    const clientId = runClientId.current;
    if (!clientId) return;
    setNotice("正在停止…");
    try {
      await api.cancel(clientId);
    } catch (cause) {
      setNotice(`停止失败：${(cause as Error).message}`);
    }
  }, []);

  const continueFromReview = useCallback(() => {
    if (!review) return;
    const precomputed: Record<string, Record<string, unknown>> = {};
    for (const node of review.result.nodes) {
      if ((node.type === "llm" || node.type === "code") && node.status === "success" && node.outputs) {
        precomputed[node.nodeId] = node.outputs;
      }
    }
    const next = review;
    clearPendingReview();
    setReview(null);
    setReviewOpen(false);
    void run({ inputs: next.inputs, precomputed });
  }, [review, run]);

  const rerunFromReview = useCallback((notes: string) => {
    if (!review) return;
    const base = review.inputs;
    const next: RunInputs = { ...base };
    const note = notes.trim();
    if (note) {
      next.creative_preferences = [base.creative_preferences, "修改意见：" + note].filter(Boolean).join("\n");
    }
    setInputs(next);
    clearPendingReview();
    setReview(null);
    setReviewOpen(false);
    void run({ inputs: next });
  }, [review, run]);

  /** 只把卡片收起来：这次 A 段结果留着，顶栏有入口点回来。 */
  const collapseReview = useCallback(() => {
    setReviewOpen(false);
    setNotice("审阅卡已收起：文案还在，点顶栏「文案待审阅」可以点回来。");
  }, []);

  /** 真的放弃这次运行：丢掉 A 段结果和本地备份。 */
  const discardReview = useCallback(() => {
    clearPendingReview();
    setReview(null);
    setReviewOpen(false);
    setResult(null);
    setNotice("已放弃这次运行，未生成画面；改完输入可以重新运行。");
  }, []);

  useEffect(() => {
    if (!graph || result || running || review) return;
    const saved = readLastRun();
    if (!saved || saved.path !== graph.path) return;
    setResult(saved.result);
    const when = saved.at ? new Date(saved.at).toLocaleString() : "";
    setNotice(`已恢复上次运行结果${when ? `（${when}）` : ""}，可直接去「出片」接着做`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph?.path, result, running, review]);

  // 别的脚本（sync_prompts_to_yaml.py 等）改了 YAML 时，窗口重新获得焦点就同步一次
  const syncExternal = useCallback(async () => {
    if (!graph || running) return;
    try {
      const { rev } = await api.rev(graph.path);
      if (!rev || rev === graph.rev) return;
      const loaded = await api.load(graph.path);
      setGraph(loaded);
      setError(null);
      setNotice("检测到外部修改，已重新载入 YAML");
    } catch {
      /* 文件暂时读不到：不打断当前操作，下一次编辑/运行会给出具体错误 */
    }
  }, [graph, running]);

  useEffect(() => {
    const onFocus = () => {
      void syncExternal();
    };
    window.addEventListener("focus", onFocus);
    return () => window.removeEventListener("focus", onFocus);
  }, [syncExternal]);

  const selected = useMemo(() => graph?.nodes.find((node) => node.id === selectedId) ?? null, [graph, selectedId]);

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

  function applyUpdate(result: { graph: WorkflowInfo; canUndo?: boolean; canRedo?: boolean; mirrorWarning?: string }) {
    setGraph(result.graph);
    if (typeof result.canUndo === "boolean") setCanUndo(result.canUndo);
    if (typeof result.canRedo === "boolean") setCanRedo(result.canRedo);
    setError(null);
    if (result.mirrorWarning) setNotice(result.mirrorWarning);
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

  return (
    <div className="app">
      <header className="topbar card">
        <Select
          value={graph?.path ?? ""}
          width={260}
          options={[
            ...workflows.map((workflow) => ({ value: workflow.path, label: workflow.name })),
            ...(graph && !workflows.some((workflow) => workflow.path === graph.path)
              ? [{ value: graph.path, label: graph.name }]
              : []),
          ]}
          onChange={(path) => void open(path)}
          placeholder="选择工作流"
        />
        <button className="btn" onClick={() => void pickWorkflow()}>打开文件…</button>
        <span className="spacer" />
        <Select value={addType} width={150} options={ADD_TYPE_OPTIONS} onChange={setAddType} />
        <button className="btn" onClick={() => void addNode()} disabled={!graph}>添加节点</button>
        <button
          className={`btn ${connecting ? "primary" : ""}`}
          onClick={() => {
            setConnecting((value) => !value);
            setConnectFrom(null);
          }}
          disabled={!graph}
        >
          {connecting ? (connectFrom ? "选目标…" : "选起点…") : "连线"}
        </button>
        <button className="btn" onClick={() => setShowInput(true)}>输入</button>
        {review && !reviewOpen && (
          <button
            className="btn pending"
            onClick={() => {
              setReviewOpen(true);
              setNotice(null);
            }}
            title="回到 A07 口播审阅卡：重跑文案 / 继续生成画面 / 放弃这次运行"
          >
            文案待审阅 · 点开
          </button>
        )}
        {running ? (
          <button className="btn danger" onClick={() => void stop()}>停止</button>
        ) : (
          <button className="btn primary" onClick={() => setShowInput(true)} disabled={!graph}>运行</button>
        )}
        <button
          className="btn ghost"
          onClick={() => setInspectorOpen((value) => !value)}
          disabled={view !== "canvas"}
        >
          {inspectorOpen ? "收起详情" : "展开详情"}
        </button>
      </header>

      <aside className="rail card">
        <div className="brand">
          <span className="name">视频工作流</span>
          <span className="sub">Studio</span>
        </div>
        <nav className="nav">
          <button className={`tool ${view === "canvas" ? "on" : ""}`} onClick={() => setView("canvas")}>画布</button>
          <button
            className={`tool ${view === "produce" ? "on" : ""}`}
            onClick={() => setView("produce")}
            title="运行完成后：准备项目 → 出图提示词 → 放图 → 渲染成片"
          >
            出片
          </button>
          <button className={`tool ${view === "artifacts" ? "on" : ""}`} onClick={() => setView("artifacts")}>产物</button>
        </nav>
        <div className="rail-foot">
          <button className="btn sm rail-settings" onClick={() => setShowSettings(true)}>设置</button>
          <div className="rail-actions">
            <button className="btn sm" onClick={() => void undo()} disabled={!canUndo}>撤销</button>
            <button className="btn sm" onClick={() => void redo()} disabled={!canRedo}>重做</button>
          </div>
        </div>
      </aside>

      <div className="work">
        <div className={`main ${!inspectorOpen || view !== "canvas" ? "no-inspector" : ""}`}>
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
              />
            ) : (
              <section className="canvas-wrap card">
                <div className="hint-text" style={{ padding: 16 }}>载入中…</div>
              </section>
            )
          ) : null}
          {view === "canvas" && inspectorOpen && graph ? (
            <Inspector
              graph={graph}
              node={selected}
              result={result}
              status={selectedId ? (statuses[selectedId] ?? "") : ""}
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
              onProduce={() => setView("produce")}
            />
          ) : null}
          <div className="produce-layer" hidden={view !== "produce"}>
            <Produce
              result={result}
              inputs={inputs}
              onRun={() => setShowInput(true)}
              onArtifacts={() => setView("artifacts")}
              onNotice={setNotice}
            />
          </div>
        </div>

        <footer className={`bottom card ${consoleOpen ? "" : "collapsed"}`}>
          <div className="tabs">
            <span className={`tab ${tab === "run" ? "on" : ""}`} onClick={() => setTab("run")}>运行台</span>
            <span className={`tab ${tab === "terminal" ? "on" : ""}`} onClick={() => setTab("terminal")}>终端</span>
            <span className="right">
              <span className="meta" title={graph?.path ?? ""}>
                {graph ? `${graph.name} · ${graph.nodes.length} 节点` : "未载入"}
                {env ? ` · ${env.model}` : ""}
                {env?.hasKey ? " · key 已配置" : " · 无 key"}
              </span>
              <span>{result ? `${result.status === "stopped" ? (result.error ? "已停止" : "已完成") : result.status} · ${(result.ms / 1000).toFixed(2)}s` : running ? "运行中" : "就绪"}</span>
            </span>
            <button className="btn sm ghost toggle" onClick={() => setConsoleOpen((value) => !value)}>
              {consoleOpen ? "收起" : "展开"}
            </button>
          </div>
          <div className={`pane ${tab === "run" ? "" : "hidden"}`}>
            <div className="log">
              {result && result.status === "success" && typeof result.outputs.html_document === "string" && (
                <div className="run-next">
                  <span>运行完成 · {result.nodes.length} 节点 · {(result.ms / 1000).toFixed(1)}s</span>
                  <span className="spacer" />
                  <button className="btn sm primary" onClick={() => setView("produce")}>下一步：去出片</button>
                </div>
              )}
              {error && <div className="err">{error}</div>}
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
              {events.length === 0 && !result && <div className="dim">点右上「运行」开始；会真实调用模型（先在左栏「设置」里配 Key）。</div>}
              {events.length === 0 && result && <div className="dim">逐节点事件没有保留（应用重启过）；End 输出已恢复，可直接去「出片」。</div>}
              {result && Object.keys(result.outputs).length > 0 && (
                <div className="dim">产物：{Object.keys(result.outputs).join("、")}</div>
              )}
            </div>
          </div>
          <div className={`pane term-pane ${tab === "terminal" ? "" : "hidden"}`}>
            <Terminal />
          </div>
        </footer>
      </div>

      {showInput && (
        <InputPanel
          inputs={inputs}
          variables={graph?.startVariables ?? []}
          running={running}
          onChange={(patch) => setInputs((previous) => ({ ...previous, ...patch }))}
          hasKey={Boolean(env?.hasKey)}
          reviewGate={reviewGate}
          canReview={canReview}
          onReviewGateChange={setReviewGate}
          onRun={() => {
            setShowInput(false);
            if (review) {
              // 新跑一轮会顶掉那份待审阅的文案：先问一句，别像点遮罩那样悄悄丢掉
              if (!window.confirm("还有一份待审阅的文案没处理，重新运行会把它丢掉。继续？")) return;
              discardReview();
            }
            void run();
          }}
          onClose={() => setShowInput(false)}
        />
      )}

      {review && reviewOpen && (
        <ReviewPanel
          result={review.result}
          busy={running}
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
