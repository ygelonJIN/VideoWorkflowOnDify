import { useEffect, useMemo, useRef, useState } from "react";
import type { WorkflowInfo } from "./types.js";

interface Props {
  graph: WorkflowInfo;
  selectedId: string | null;
  connectSource: string | null;
  statuses: Record<string, string>;
  onSelect: (id: string) => void;
  onEdgeClick: (edgeId: string) => void;
  onMoveNode: (id: string, position: { x: number; y: number }) => void;
  runningNodeId?: string | null;
}

interface View {
  scale: number;
  x: number;
  y: number;
}

const MAX_SCALE = 3;
const WHEEL_FACTOR = 0.006;   // 同样滑动距离，缩放幅度是上一版的两倍
const BUTTON_STEP = 1.35;
const INITIAL_SCALE = 0.6;    // 打开工作流时的可视比例
const MIN_RATIO = 0.4;        // 缩放下限 = 全图适配比例 × 0.4，不写死百分比

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

const STATE_TEXT: Record<string, string> = { success: "成功", running: "运行中", error: "失败", stopped: "已停止" };
const STATE_CLASS: Record<string, string> = { success: "ok", running: "run", error: "err", stopped: "stop" };

export function Canvas({ graph, selectedId, connectSource, statuses, onSelect, onEdgeClick, onMoveNode, runningNodeId }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 900, height: 600 });
  const [view, setView] = useState<View>({ scale: 0.5, x: 40, y: 40 });
  const drag = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);
  const [dragging, setDragging] = useState<{ id: string; startX: number; startY: number; originX: number; originY: number; x: number; y: number } | null>(null);
  const [query, setQuery] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);
  const viewRef = useRef(view);
  viewRef.current = view;
  const fittedPath = useRef<string | null>(null);

  const matches = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    if (!keyword) return [];
    return graph.nodes
      .filter((node) => node.title.toLowerCase().includes(keyword) || node.id.toLowerCase().includes(keyword))
      .slice(0, 8);
  }, [query, graph]);

  /** 拖动中的节点用预览坐标，连线也要跟着走，不能只用图里的旧坐标。 */
  const positionOf = (node: WorkflowInfo["nodes"][number]) =>
    dragging?.id === node.id ? { x: dragging.x, y: dragging.y } : node.position;

  const centerOn = (node: WorkflowInfo["nodes"][number], scale = viewRef.current.scale) => {
    const next = clamp(Math.max(scale, minScaleRef.current), minScaleRef.current, 1.2);
    const centerX = node.position.x + node.width / 2;
    const centerY = node.position.y + node.height / 2;
    setView({ scale: next, x: size.width / 2 - centerX * next, y: size.height / 2 - centerY * next });
  };

  const focusNode = (id: string) => {
    const node = graph.nodes.find((item) => item.id === id);
    if (!node) return;
    onSelect(id);
    centerOn(node, Math.max(viewRef.current.scale, 0.5));
    setQuery("");
  };

  /* 运行中的节点走到哪，镜头跟到哪（运行时由 App 传进来） */
  useEffect(() => {
    if (!runningNodeId) return;
    if (size.width < 40 || size.height < 40) return;
    const node = graph.nodes.find((item) => item.id === runningNodeId);
    if (!node) return;
    centerOn(node, Math.max(viewRef.current.scale, 0.6));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runningNodeId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "f") {
        event.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const bounds = useMemo(() => {
    let maxX = 1200;
    let maxY = 700;
    for (const node of graph.nodes) {
      maxX = Math.max(maxX, node.position.x + node.width + 200);
      maxY = Math.max(maxY, node.position.y + Math.max(node.height, 120) + 200);
    }
    return { width: maxX, height: maxY };
  }, [graph]);

  /* 全图适配比例：缩放上下限和「适应」都从它推，不写死 20% */
  const fitScale = useMemo(() => {
    if (graph.nodes.length === 0 || size.width < 40 || size.height < 40) return 1;
    const minX = Math.min(...graph.nodes.map((node) => node.position.x));
    const minY = Math.min(...graph.nodes.map((node) => node.position.y));
    const maxX = Math.max(...graph.nodes.map((node) => node.position.x + node.width));
    const maxY = Math.max(...graph.nodes.map((node) => node.position.y + node.height));
    return Math.min((size.width - 90) / (maxX - minX), (size.height - 90) / (maxY - minY));
  }, [graph, size.width, size.height]);

  const minScale = clamp(fitScale * MIN_RATIO, 0.03, 0.5);
  const minScaleRef = useRef(minScale);
  minScaleRef.current = minScale;

  const fitView = (anchor: "start" | "bbox", floor = 0) => {
    if (graph.nodes.length === 0) return;
    const minX = Math.min(...graph.nodes.map((node) => node.position.x));
    const minY = Math.min(...graph.nodes.map((node) => node.position.y));
    const maxX = Math.max(...graph.nodes.map((node) => node.position.x + node.width));
    const maxY = Math.max(...graph.nodes.map((node) => node.position.y + node.height));
    const scale = clamp(fitScale, Math.max(minScaleRef.current, floor), 1.2);
    const entry = graph.nodes.find((node) => node.type === "start") ?? graph.nodes[0];
    const focusX = anchor === "start" && entry ? entry.position.x + entry.width / 2 : (minX + maxX) / 2;
    const focusY = anchor === "start" && entry ? entry.position.y + entry.height / 2 : (minY + maxY) / 2;
    setView({ scale, x: size.width / 2 - focusX * scale, y: size.height / 2 - focusY * scale });
  };

  const zoomAt = (clientX: number, clientY: number, factor: number) => {
    const element = ref.current;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    const current = viewRef.current;
    const next = clamp(current.scale * factor, minScaleRef.current, MAX_SCALE);
    const ratio = next / current.scale;
    setView({ scale: next, x: px - (px - current.x) * ratio, y: py - (py - current.y) * ratio });
  };

  const zoomCenter = (factor: number) => {
    const element = ref.current;
    if (!element) return;
    const rect = element.getBoundingClientRect();
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, factor);
  };

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const box = entries[0]?.contentRect;
      if (box) setSize({ width: box.width, height: box.height });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  /* 只在换工作流时适配一次：选中节点、拖动节点、撤销重做都不再重置缩放 */
  useEffect(() => {
    if (graph.nodes.length === 0) return;
    if (size.width < 40 || size.height < 40) return;
    if (fittedPath.current === graph.path) return;
    fittedPath.current = graph.path;
    /* 首次打开先给一个能看清文字的比例；要看全图按「适应」 */
    fitView("start", INITIAL_SCALE);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph.path, graph.nodes.length, size.width, size.height]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const delta = event.deltaMode === 1 ? event.deltaY * 16 : event.deltaY;
      zoomAt(event.clientX, event.clientY, Math.exp(-delta * WHEEL_FACTOR));
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, []);

  function onPointerDown(event: React.PointerEvent) {
    if ((event.target as HTMLElement).closest(".node, .canvas-tools")) return;
    drag.current = { startX: event.clientX, startY: event.clientY, originX: view.x, originY: view.y };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
    (event.currentTarget as HTMLElement).classList.add("panning");
  }

  function onPointerMove(event: React.PointerEvent) {
    const current = drag.current;
    if (!current) return;
    setView({
      ...view,
      x: current.originX + (event.clientX - current.startX),
      y: current.originY + (event.clientY - current.startY),
    });
  }

  function onPointerUp(event: React.PointerEvent) {
    drag.current = null;
    (event.currentTarget as HTMLElement).classList.remove("panning");
  }

  return (
    <section
      className={`canvas-wrap card ${connectSource ? "connecting" : ""}`}
      ref={ref}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div className="canvas-hud">
        <span>{graph.nodes.length} 节点 · {graph.edges.length} 连线</span>
        <span className="zoom">{Math.round(view.scale * 100)}%</span>
        <span className="hint">滚轮缩放 · 拖空白平移 · 点节点看详情</span>
      </div>
      <div className="canvas-search">
        <input
          ref={searchRef}
          value={query}
          placeholder="搜索节点（⌘F）"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && matches[0]) {
              event.preventDefault();
              focusNode(matches[0].id);
            } else if (event.key === "Escape") {
              setQuery("");
              searchRef.current?.blur();
            }
          }}
        />
        {matches.length > 0 && (
          <ul className="search-results">
            {matches.map((node) => (
              <li key={node.id} onMouseDown={(event) => { event.preventDefault(); focusNode(node.id); }}>
                <span>{node.title}</span>
                <span className="dim">{node.id}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div
        className="stage"
        style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
      >
        <svg className="canvas-edges" width={bounds.width} height={bounds.height} viewBox={`0 0 ${bounds.width} ${bounds.height}`}>
          {graph.edges.map((edge) => {
            const from = graph.nodes.find((node) => node.id === edge.source);
            const to = graph.nodes.find((node) => node.id === edge.target);
            if (!from || !to) return null;
            const fromPos = positionOf(from);
            const toPos = positionOf(to);
            const x1 = fromPos.x + from.width;
            const y1 = fromPos.y + Math.min(from.height, 120) / 2;
            const x2 = toPos.x;
            const y2 = toPos.y + Math.min(to.height, 120) / 2;
            const dx = Math.max(40, (x2 - x1) / 2);
            const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
            return (
              <g key={edge.id}>
                <path d={path} />
                <path
                  d={path}
                  fill="none"
                  stroke="transparent"
                  strokeWidth={14}
                  style={{ cursor: "pointer", pointerEvents: "stroke" }}
                  onClick={(event) => {
                    event.stopPropagation();
                    onEdgeClick(edge.id);
                  }}
                />
              </g>
            );
          })}
        </svg>
        {graph.nodes.map((node) => {
          const status = statuses[node.id] ?? "";
          const active = dragging?.id === node.id ? dragging : null;
          const x = active ? active.x : node.position.x;
          const y = active ? active.y : node.position.y;
          return (
            <div
              key={node.id}
              className={`node ${selectedId === node.id ? "sel" : ""} ${connectSource === node.id ? "connect-source" : ""} ${active ? "dragging" : ""} ${status === "error" ? "failed" : ""} ${status ? `st-${status}` : ""}`}
              style={{ left: x, top: y, width: node.width, minHeight: 96 }}
              onClick={() => onSelect(node.id)}
              onPointerDown={(event) => {
                if (connectSource) return;
                event.stopPropagation();
                (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
                setDragging({
                  id: node.id,
                  startX: event.clientX,
                  startY: event.clientY,
                  originX: node.position.x,
                  originY: node.position.y,
                  x: node.position.x,
                  y: node.position.y,
                });
              }}
              onPointerMove={(event) => {
                if (!dragging || dragging.id !== node.id) return;
                event.stopPropagation();
                // 指针位移是屏幕像素，节点坐标是画布像素：要除以缩放，否则缩放后不跟手。
                // 用函数式更新，避免高频 pointermove 拿到旧的 dragging。
                const scale = viewRef.current.scale || 1;
                setDragging((previous) =>
                  previous
                    ? {
                        ...previous,
                        x: previous.originX + (event.clientX - previous.startX) / scale,
                        y: previous.originY + (event.clientY - previous.startY) / scale,
                      }
                    : previous,
                );
              }}
              onPointerUp={(event) => {
                if (!dragging || dragging.id !== node.id) return;
                event.stopPropagation();
                const position = { x: Math.round(dragging.x), y: Math.round(dragging.y) };
                const moved = position.x !== node.position.x || position.y !== node.position.y;
                setDragging(null);
                if (moved) onMoveNode(node.id, position);
              }}
            >
              <div className="node-head">
                <span className="node-title">{node.title}</span>
              </div>
              <div className="node-kind">{node.type}</div>
              <div className="node-meta">{node.model ?? node.id}</div>
              {STATE_TEXT[status] && (
                <span className={`node-state ${STATE_CLASS[status]}`}>{STATE_TEXT[status]}</span>
              )}
            </div>
          );
        })}
      </div>
      <div className="canvas-tools">
        <button onClick={() => zoomCenter(1 / BUTTON_STEP)}>缩小</button>
        <button onClick={() => zoomCenter(1 / view.scale)}>100%</button>
        <button onClick={() => zoomCenter(BUTTON_STEP)}>放大</button>
        <button onClick={() => fitView("bbox")}>适应</button>
      </div>
    </section>
  );
}
