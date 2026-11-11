import { useCallback, useEffect, useMemo, useState } from "react";
import { Canvas } from "./Canvas.js";
import { Inspector } from "./Inspector.js";
import { Terminal } from "./Terminal.js";
import { Artifacts } from "./Artifacts.js";
import { InputPanel } from "./InputPanel.js";
import { bridge } from "./bridge.js";
import type { EnvInfo, RunInputs, RunResult, TraceEvent, WorkflowInfo } from "./types.js";

const api = bridge();

type Tab = "run" | "terminal" | "artifacts";

const EMPTY_INPUTS: RunInputs = {
  campaign_brief: "",
  request_id: "",
  tts_provider: "mimo",
  tts_voice: "mimo_default",
  production_requirements: "",
};

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

  useEffect(() => {
    let alive = true;
    Promise.all([api.workflows(), api.env(), api.inputs()]).then(([list, envInfo, defaults]) => {
      if (!alive) return;
      setWorkflows(list);
      setEnv(envInfo);
      setInputs({
        campaign_brief: String(defaults.campaign_brief ?? ""),
        request_id: String(defaults.request_id ?? ""),
        tts_provider: String(defaults.tts_provider ?? "mimo"),
        tts_voice: String(defaults.tts_voice ?? "mimo_default"),
        production_requirements: String(defaults.production_requirements ?? ""),
      });
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
    setRunning(true);
    setStatuses({});
    setEvents([]);
    setResult(null);
    setError(null);
    setTab("run");
    const unsubscribe = api.onEvent((event) => {
      setEvents((previous) => [...previous, event]);
      if (event.nodeId) {
        setStatuses((previous) => ({
          ...previous,
          [event.nodeId as string]:
            event.type === "node_start" ? "running" : event.type === "node_end" ? "success" : "error",
        }));
      }
    });
    try {
      const runResult = await api.run({
        path: graph.path,
        stub,
        ...(until ? { until } : {}),
        inputs,
      });
      setResult(runResult);
      if (runResult.status === "error" && runResult.error) setError(runResult.error);
    } catch (runError) {
      setError((runError as Error).message);
    } finally {
      unsubscribe();
      setRunning(false);
    }
  }, [graph, running, stub, until, inputs]);

  const selected = useMemo(() => graph?.nodes.find((node) => node.id === selectedId) ?? null, [graph, selectedId]);

  const fail = (cause: unknown) => setError((cause as Error).message);

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
    try {
      applyUpdate(await api.moveNode({ path: graph.path, nodeId, position }));
    } catch (cause) {
      fail(cause);
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
      <header className="topbar">
        <div className="brand"><span className="mark">V</span>视频工作流 · Studio</div>
        <select className="select" value={graph?.path ?? ""} onChange={(event) => void open(event.target.value)}>
          {workflows.map((workflow) => (
            <option key={workflow.path} value={workflow.path}>{workflow.name}</option>
          ))}
        </select>
        <span className="spacer" />
        {graph && <span className="pill">{graph.version || "DSL"}</span>}
        {env && <span className="pill">{env.model}</span>}
        <span className={`pill ${env?.hasKey ? "ok" : ""}`}>{env?.hasKey ? "key 已配置" : "无 key"}</span>
        <label className="toggle">
          <input type="checkbox" checked={stub} onChange={(event) => setStub(event.target.checked)} />
          stub
        </label>
        <select className="select narrow" value={until} onChange={(event) => setUntil(event.target.value)}>
          <option value="a03">停在 a03</option>
          <option value="">跑全程</option>
        </select>
        <button className="btn" onClick={() => void undo()} disabled={!canUndo} title="撤销 ⌘Z">↶</button>
        <button className="btn" onClick={() => void redo()} disabled={!canRedo} title="重做 ⇧⌘Z">↷</button>
        <select className="select narrow" value={addType} onChange={(event) => setAddType(event.target.value)}>
          <option value="code">Code</option>
          <option value="llm">LLM</option>
          <option value="if-else">if-else</option>
          <option value="template-transform">模板</option>
          <option value="http-request">HTTP</option>
          <option value="end">End</option>
        </select>
        <button className="btn" onClick={() => void addNode()} disabled={!graph}>＋ 节点</button>
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
        <button className="btn primary" onClick={() => void run()} disabled={running || !graph}>
          {running ? "运行中…" : "▶ 运行"}
        </button>
      </header>

      <div className="main">
        <nav className="rail">
          <span className="tool on" title="画布">▤</span>
          <span className="tool" title="提示词">✎</span>
          <span className="tool" title="产物">▣</span>
          <span className="sep" />
          <span className="tool" title="终端">⌘</span>
        </nav>
        {graph ? (
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
          <section className="canvas-wrap"><div className="empty">载入中…</div></section>
        )}
        {graph ? (
          <Inspector
            graph={graph}
            node={selected}
            result={result}
            status={selectedId ? (statuses[selectedId] ?? "") : ""}
            onUpdate={async (field, value) => {
              if (!selected) return;
              const updated = await api.updateNode({ path: graph.path, nodeId: selected.id, field, value });
              applyUpdate(updated);
            }}
            onDelete={() => void deleteNode()}
          />
        ) : (
          <aside className="inspector" />
        )}
      </div>

      <footer className="bottom">
        <div className="tabs">
          <span className={`tab ${tab === "run" ? "on" : ""}`} onClick={() => setTab("run")}>运行台</span>
          <span className={`tab ${tab === "terminal" ? "on" : ""}`} onClick={() => setTab("terminal")}>终端</span>
          <span className={`tab ${tab === "artifacts" ? "on" : ""}`} onClick={() => setTab("artifacts")}>产物</span>
          <span className="right">
            {result ? `${result.status} · ${(result.ms / 1000).toFixed(2)}s` : running ? "运行中" : "就绪"}
          </span>
        </div>
        <div className={`pane ${tab === "run" ? "" : "hidden"}`}>
          <div className="log">
            {error && <div className="err">{error}</div>}
            {events.filter((event) => event.type !== "node_start").map((event) => (
              <div key={event.seq}>
                <span className="t">{timeOf(event.at)}</span>{" "}
                <span className={event.type === "node_error" ? "err" : event.type === "run_end" ? "ok" : "dim"}>
                  {event.type === "node_end" ? "✓" : event.type === "node_error" ? "✗" : "·"}
                </span>{" "}
                {event.title ?? event.type}
                {event.ms !== undefined && <span className="dim"> · {event.ms}ms</span>}
                {event.error && <span className="err"> · {event.error}</span>}
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
        <div className={`pane ${tab === "artifacts" ? "" : "hidden"}`}>
          <Artifacts result={result} />
        </div>
      </footer>

      {showInput && (
        <InputPanel
          inputs={inputs}
          running={running}
          onChange={(patch) => setInputs((previous) => ({ ...previous, ...patch }))}
          onRun={() => {
            setShowInput(false);
            void run();
          }}
          onClose={() => setShowInput(false)}
        />
      )}
    </div>
  );
}
