import type { RunItem, RunStatus } from "./types.js";

interface Props {
  runs: RunItem[];
  activeId: string;
  busy: boolean;
  onSelect: (id: string) => void;
  onClear: () => void;
}

const STATUS_TEXT: Record<RunStatus, string> = {
  queued: "排队中",
  running: "运行中",
  review: "待审阅",
  ready: "可出片",
  incomplete: "无成片",
  error: "失败",
  stopped: "已停止",
};

function stateText(run: RunItem): string {
  if (run.status === "running" && run.nodeTitle) return `运行中 · ${run.nodeTitle}`;
  /* 已经渲出成片的这条不该再提示「可出片」：它这一轮已经走完了 */
  if (run.produced) return "已出片";
  return STATUS_TEXT[run.status];
}

function topicOf(run: RunItem, index: number): string {
  const first = run.topic.split(/\r?\n/).map((line) => line.trim()).find(Boolean);
  return first || run.name || `第 ${index + 1} 条`;
}

/**
 * 画布 / 出片共用的批量切换条。只在真有一条以上运行时出现：
 * 单条运行看不出它，批量时点谁，画布状态、运行台和出片页就跟谁。
 */
export function RunSwitch({ runs, activeId, busy, onSelect, onClear }: Props) {
  return (
    <section className="runs-bar card" aria-label="批量运行">
      <span className="runs-label">批量运行</span>
      <span className="runs-count">{runs.length} 条</span>
      <div className="runs-list" role="tablist" aria-label="选择要查看的运行">
        {runs.map((run, index) => (
          <button
            key={run.id}
            role="tab"
            aria-selected={run.id === activeId}
            className={`run-chip ${run.id === activeId ? "on" : ""} ${run.status}`}
            title={`${topicOf(run, index)}${run.name ? `\n项目：${run.name}` : ""}\n${stateText(run)}`}
            onClick={() => onSelect(run.id)}
          >
            <span className="run-chip-no">{index + 1}</span>
            <span className="run-chip-topic">{topicOf(run, index)}</span>
            <span className="run-chip-state">{stateText(run)}</span>
          </button>
        ))}
      </div>
      <span className="spacer" />
      <button
        className="btn sm ghost"
        onClick={onClear}
        disabled={busy}
        title="收起这一批的切换条；已经生成的项目和成片不受影响"
      >
        清空
      </button>
    </section>
  );
}
