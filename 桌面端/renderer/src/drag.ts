import type { PointerEvent as ReactPointerEvent } from "react";

export interface DragSpec {
  /** 横向拖动改宽度，纵向拖动改高度。 */
  axis: "x" | "y";
  /** 按下时的起始尺寸。 */
  from: number;
  min: number;
  max: number;
  onMove: (value: number) => void;
  onEnd?: () => void;
}

/**
 * 分割条拖动：往回拖（左 / 上）尺寸变大，和"面板贴着边缘"的直觉一致。
 * 用 window 上的 pointermove 而不是元素自身，鼠标拖出分割条也不会断。
 */
export function startDrag(event: ReactPointerEvent<HTMLElement>, spec: DragSpec): void {
  if (event.button !== 0) return;
  event.preventDefault();
  const origin = spec.axis === "x" ? event.clientX : event.clientY;
  const limit = Math.max(spec.min, spec.max);

  const move = (moveEvent: PointerEvent) => {
    const position = spec.axis === "x" ? moveEvent.clientX : moveEvent.clientY;
    const next = Math.min(Math.max(spec.from + (origin - position), spec.min), limit);
    spec.onMove(next);
  };
  const end = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", end);
    window.removeEventListener("pointercancel", end);
    spec.onEnd?.();
  };

  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", end);
  window.addEventListener("pointercancel", end);
}

/** 读一个持久化的尺寸；没有或越界就返回 fallback。 */
export function readSize(key: string, fallback: number, min = 0): number {
  const saved = Number(localStorage.getItem(key));
  return Number.isFinite(saved) && saved >= min ? saved : fallback;
}
