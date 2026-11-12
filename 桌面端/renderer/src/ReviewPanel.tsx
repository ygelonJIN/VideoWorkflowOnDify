import { useEffect, useMemo } from "react";
import type { RunResult } from "./types.js";

interface Props {
  result: RunResult;
  busy: boolean;
  onContinue: () => void;
  onRerun: (notes: string) => void;
  /** 修改意见存在 App 里：卡片收起再打开，已经写的内容还在。 */
  notes: string;
  onNotesChange: (value: string) => void;
  /** 收起卡片：文案和这次运行结果都留着，顶栏能点回来。 */
  onCollapse: () => void;
  /** 真正放弃这次运行：丢掉 A 段结果，回到没跑过的状态。 */
  onDiscard: () => void;
}

function parseJson<T>(raw: unknown): T | null {
  if (typeof raw !== "string" || !raw.trim()) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function warningList(raw: unknown): string[] {
  const parsed = parseJson<unknown>(raw);
  return Array.isArray(parsed) ? parsed.map((item) => String(item)).filter(Boolean) : [];
}

/** 口播闸门：A07 整理完、分镜之前停住，先看口播，再决定重跑还是继续。 */
export function ReviewPanel({ result, busy, notes, onNotesChange, onContinue, onRerun, onCollapse, onDiscard }: Props) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCollapse();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCollapse]);
  const data = useMemo(() => {
    const byId = new Map(result.nodes.map((node) => [node.nodeId, node.outputs]));
    // 闸门停在 a07：口播、字数、时长、口播自检都在这里；分镜/动效/合规还没跑，所以不强求
    const a07 = byId.get("a07") ?? {};
    const pkg = parseJson<{
      approved_script?: { voiceover_script?: string };
      storyboard?: { scenes?: unknown[] };
      brief?: { target_duration_seconds?: number };
    }>(byId.get("a16")?.approved_package_json);
    const script =
      String(a07.voiceover_script ?? "").trim() ||
      String(parseJson<{ voiceover_script?: string }>(a07.script_json)?.voiceover_script ?? "").trim() ||
      String(pkg?.approved_script?.voiceover_script ?? "").trim();
    const duration = Number(a07.estimated_duration_seconds ?? pkg?.brief?.target_duration_seconds ?? 0);
    const scenes = Array.isArray(pkg?.storyboard?.scenes)
      ? pkg.storyboard.scenes.length
      : Number(byId.get("a09")?.scene_count ?? 0);
    const warnings = [
      ...warningList(a07.copy_warnings_json),
      ...warningList(byId.get("a09")?.storyboard_warnings_json),
      ...warningList(byId.get("a11")?.motion_warnings_json),
    ];
    const errors = warningList(a07.copy_errors_json);
    const invalid = String(a07.copy_valid ?? "").trim() === "false";
    return { script, duration, scenes, warnings, errors, invalid };
  }, [result]);

  const chars = data.script.replace(/\s/g, "").length;

  return (
    <div className="review-mask" onClick={onCollapse}>
      <section className="review-card card" onClick={(event) => event.stopPropagation()}>
        <header className="review-head">
          <div>
            <h2>口播已生成 · 先审阅</h2>
            <div className="review-sub">分镜、动效、合规、画面都还没跑；改这一版文案不会浪费后面的调用。</div>
          </div>
          <div className="review-head-right">
            <span className="pill ok">已停在 A07</span>
            <button className="review-close" onClick={onCollapse} title="收起，不丢结果（顶栏可以点回来）">✕</button>
          </div>
        </header>

        <div className="review-stats">
          <span>{chars} 字</span>
          {data.duration > 0 && <span>约 {data.duration.toFixed(1)} 秒</span>}
          {data.scenes > 0 && <span>{data.scenes} 屏</span>}
        </div>

        <pre className="review-script">{data.script || "没有读到口播文案：A07 的输出为空。"}</pre>

        {data.invalid && (
          <div className="warn-box">
            <div>口播自检没过（A07 copy_valid=false），下面是要修的点；直接点「重跑文案」带修改意见重写。</div>
            {data.errors.slice(0, 6).map((error) => (
              <div key={error}>{error}</div>
            ))}
            {data.errors.length > 6 && <div>…还有 {data.errors.length - 6} 条，在运行台里。</div>}
          </div>
        )}

        {data.warnings.length > 0 && (
          <div className="warn-box">
            {data.warnings.slice(0, 6).map((warning) => (
              <div key={warning}>{warning}</div>
            ))}
            {data.warnings.length > 6 && <div>…还有 {data.warnings.length - 6} 条，在运行台里。</div>}
          </div>
        )}

        <label className="field">
          <span>修改意见（重跑时带进 A01，可留空）</span>
          <textarea
            rows={3}
            value={notes}
            onChange={(event) => onNotesChange(event.target.value)}
            placeholder="例如：开头别用『人生』这种大词；第二段再具体一点，少一点排比。"
          />
        </label>

        <div className="review-actions">
          <span className="spacer" />
          <button
            className="btn danger"
            onClick={() => {
              if (window.confirm("放弃这次运行？这一版口播和分镜结果会丢掉，要看得重新跑文案。")) onDiscard();
            }}
            disabled={busy}
          >
            放弃这次运行
          </button>
          <button className="btn" onClick={() => onRerun(notes)} disabled={busy}>重跑文案</button>
          <button className="btn primary" onClick={onContinue} disabled={busy}>继续生成画面</button>
        </div>
        <div className="hint-text">继续：复用这版口播，接着跑分镜 → 动效 → 合规 → 画面/HTML，中途不再停。</div>
        <div className="hint-text">这张卡可以随时收起：点卡片外面、按 Esc、点右上角 ✕ 都只是收起，文案还在，顶栏「文案待审阅」能点回来；真要丢掉结果才点「放弃这次运行」。</div>
      </section>
    </div>
  );
}
