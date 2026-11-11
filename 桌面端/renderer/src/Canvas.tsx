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
}

interface View {
  scale: number;
  x: number;
  y: number;
}

const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

export function Canvas({ graph, selectedId, connectSource, statuses, onSelect, onEdgeClick, onMoveNode }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 900, height: 600 });
  const [view, setView] = useState<View>({ scale: 0.4, x: 40, y: 40 });
  const drag = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);
  const [dragging, setDragging] = useState<{ id: string; startX: number; startY: number; originX: number; originY: number; x: number; y: number } | null>(null);
  const viewRef = useRef(view);
  viewRef.current = view;

  const bounds = useMemo(() => {
    let maxX = 1200;
    let maxY = 700;
    for (const node of graph.nodes) {
      maxX = Math.max(maxX, node.position.x + node.width + 200);
      maxY = Math.max(maxY, node.position.y + Math.max(node.height, 120) + 200);
    }
    return { width: maxX, height: maxY };
  }, [graph]);

  const fit = () => {
    const nodeWidth = Math.max(...graph.nodes.map((node) => node.position.x + node.width)) + 120;
    const nodeHeight = Math.max(...graph.nodes.map((node) => node.position.y + node.height)) + 120;
    const scale = clamp(Math.min((size.width - 90) / nodeWidth, (size.height - 90) / nodeHeight), 0.1, 1.1);
    const minX = Math.min(...graph.nodes.map((node) => node.position.x));
    const minY = Math.min(...graph.nodes.map((node) => node.position.y));
    setView({ scale, x: 45 - minX * scale, y: 45 - minY * scale });
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

  useEffect(() => {
    if (graph.nodes.length > 0) fit();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [graph, size.width, size.height]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = element.getBoundingClientRect();
      const px = event.clientX - rect.left;
      const py = event.clientY - rect.top;
      const current = viewRef.current;
      const factor = Math.exp(-event.deltaY * 0.0015);
      const scale = clamp(current.scale * factor, 0.08, 2.5);
      const ratio = scale / current.scale;
      setView({ scale, x: px - (px - current.x) * ratio, y: py - (py - current.y) * ratio });
    };
    element.addEventListener("wheel", onWheel, { passive: false });
    return () => element.removeEventListener("wheel", onWheel);
  }, []);

  function onPointerDown(event: React.PointerEvent) {
    if ((event.target as HTMLElement).closest(".node")) return;
    drag.current = { startX: event.clientX, startY: event.clientY, originX: view.x, originY: view.y };
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
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

  function onPointerUp() {
    drag.current = null;
  }

  return (
    <section
      className={`canvas-wrap ${connectSource ? "connecting" : ""}`}
      ref={ref}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
    >
      <div className="canvas-hint">
        画布 · {graph.nodes.length} 节点 · {graph.edges.length} 连线 · {Math.round(view.scale * 100)}%
      </div>
      <div
        className="canvas-stage"
        ref={stage}
        style={{ transform: `translate(${view.x}px, ${view.y}px) scale(${view.scale})` }}
      >
        <svg className="canvas-edges" width={bounds.width} height={bounds.height} viewBox={`0 0 ${bounds.width} ${bounds.height}`}>
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M0 0L10 5L0 10z" fill="var(--edge)" />
            </marker>
          </defs>
          {graph.edges.map((edge) => {
            const from = graph.nodes.find((node) => node.id === edge.source);
            const to = graph.nodes.find((node) => node.id === edge.target);
            if (!from || !to) return null;
            const x1 = from.position.x + from.width;
            const y1 = from.position.y + Math.min(from.height, 120) / 2;
            const x2 = to.position.x;
            const y2 = to.position.y + Math.min(to.height, 120) / 2;
            const dx = Math.max(40, (x2 - x1) / 2);
            const path = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
            return (
              <g key={edge.id}>
                <path d={path} fill="none" stroke="var(--edge)" strokeWidth={1.4} markerEnd="url(#arrow)" />
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
              className={`node ${selectedId === node.id ? "sel" : ""} ${connectSource === node.id ? "connect-source" : ""} ${active ? "dragging" : ""} ${status === "error" ? "failed" : ""}`}
              style={{ left: x, top: y, width: node.width, minHeight: 74 }}
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
                setDragging({
                  ...dragging,
                  x: dragging.originX + (event.clientX - dragging.startX),
                  y: dragging.originY + (event.clientY - dragging.startY),
                });
              }}
              onPointerUp={(event) => {
                if (!dragging || dragging.id !== node.id) return;
                event.stopPropagation();
                const position = { x: Math.round(dragging.x), y: Math.round(dragging.y) };
                setDragging(null);
                onMoveNode(node.id, position);
              }}
            >
              <i className="h in" />
              <i className="h out" />
              <div className="node-head">
                <i className={`dot ${status}`} />
                <span className="node-title">{node.title}</span>
              </div>
              <div className="node-kind">{node.type}</div>
              <div className="node-meta">{node.model ?? node.id}</div>
            </div>
          );
        })}
      </div>
      <div className="canvas-tools">
        <button onClick={() => setView((current) => ({ ...current, scale: clamp(current.scale * 1.2, 0.08, 2.5) }))}>＋</button>
        <button onClick={() => setView((current) => ({ ...current, scale: clamp(current.scale / 1.2, 0.08, 2.5) }))}>−</button>
        <button onClick={fit}>⤢</button>
      </div>
    </section>
  );
}
