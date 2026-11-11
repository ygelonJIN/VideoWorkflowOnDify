import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "./Canvas.js";
import { Inspector } from "./Inspector.js";
import { Terminal } from "./Terminal.js";
import { Artifacts } from "./Artifacts.js";
import { InputPanel } from "./InputPanel.js";
import { Select } from "./Select.js";
import { Settings } from "./Settings.js";
import type { SelectOption } from "./Select.js";
import { bridge } from "./bridge.js";
import type { EnvInfo, RunInputs, RunResult, TraceEvent, WorkflowInfo } from "./types.js";

const api = bridge();

type Tab = "run" | "terminal";
type View = "canvas" | "artifacts";

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

export function App() {
  const [workflows, setWorkflows] = useState<Array<{ name: string; path: string }>>([]);
  const [graph, setGraph] = useState<WorkflowInfo | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [statuses, setStatuses] = useState<Record<string, string>>({});
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [result, setResult] = useState<RunResult | null>(null);
  const [running, setRunning] = useState(false);
  const [stub, setStub] = useState(true);
  const [until, setUntil] = useState("a03");
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
  const [notice, setNotice] = useState<string | null>(null);
  const runClientId = useRef<string | null>(null);

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

  const run = useCallback(async () => {
    if (!graph || running) return;
    const clientId = crypto.randomUUID();
    runClientId.current = clientId;
    setRunning(true);
    setStatuses({});
    setEvents([]);
    setResult(null);
    setError(null);
    setNotice(null);
    setTab("run");
    const unsubscribe = api.onEvent((event) => {
      setEvents((previous) => [...previous, event]);
      if (event.nodeId) {
        setStatuses((previous) => ({
          ...previous,
          [event.nodeId as string]:
            event.type === "node_start" ? "running" : event.type === "node_end" ? "success" : (event.status ?? "error"),
        }));
      }
    });
    try {
      const runResult = await api.run({
        path: graph.path,
        stub,
        clientId,
        ...(until ? { until } : {}),
        inputs,
      });
      setResult(runResult);
      if (runResult.status === "error" && runResult.error) setError(runResult.error);
      if (runResult.status === "stopped" && runResult.error) setNotice(runResult.error);
      if (runResult.status === "stopped" && !runResult.error && until) {
        setNotice(`已停在 ${until}；要跑全程，在「输入」里把「跑到哪」改成跑全程`);
      }
    } catch (runError) {
      setError((runError as Error).message);
    } finally {
      unsubscribe();
      runClientId.current = null;
      setRunning(false);
    }
  }, [graph, running, stub, until, inputs]);

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
          ) : graph ? (
            <Canvas
              graph={graph}
              selectedId={selectedId}
              connectSource={connectFrom}
              statuses={statuses}
              onSelect={handleNodeClick}
              onEdgeClick={(edgeId) => void handleEdgeClick(edgeId)}
              onMoveNode={(nodeId, position) => void moveNode(nodeId, position)}
            />
          ) : (
            <section className="canvas-wrap card">
              <div className="hint-text" style={{ padding: 16 }}>载入中…</div>
            </section>
          )}
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
            />
          ) : null}
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
                {stub ? " · stub" : ""}
              </span>
              <span>{result ? `${result.status === "stopped" ? (result.error ? "已停止" : "已完成") : result.status} · ${(result.ms / 1000).toFixed(2)}s` : running ? "运行中" : "就绪"}</span>
            </span>
            <button className="btn sm ghost toggle" onClick={() => setConsoleOpen((value) => !value)}>
              {consoleOpen ? "收起" : "展开"}
            </button>
          </div>
          <div className={`pane ${tab === "run" ? "" : "hidden"}`}>
            <div className="log">
              {error && <div className="err">{error}</div>}
              {events.filter((event) => event.type !== "node_start").map((event) => (
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
              {events.length === 0 && <div className="dim">点右上「运行」开始；当前 stub 模式不调用模型。</div>}
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
          stub={stub}
          until={until}
          onChange={(patch) => setInputs((previous) => ({ ...previous, ...patch }))}
          onStubChange={setStub}
          onUntilChange={setUntil}
          onRun={() => {
            setShowInput(false);
            void run();
          }}
          onClose={() => setShowInput(false)}
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
