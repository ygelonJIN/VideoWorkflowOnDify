import { useCallback, useEffect, useRef, useState } from "react";
import { bridge } from "./bridge.js";
import { LogBox } from "./Produce.js";
import type { BuildEvent, RunInputs, RunItem } from "./types.js";

const api = bridge();

interface Props {
  runs: RunItem[];
  inputs: Partial<RunInputs>;
  onSelect: (runId: string) => void;
  onProduced: (runId: string, dir: string) => void;
  onNotice: (message: string) => void;
}

type Phase = "running" | "done" | "error";

/** 这条能不能出片：成功跑完且拿到 html_document + voiceover_script。 */
function producible(run: RunItem): boolean {
  const outputs = run.result?.outputs ?? {};
  return typeof outputs.html_document === "string" && typeof outputs.voiceover_script === "string";
}

/**
 * 批量出片：一批多条，逐条串行出，一次只烧一条的图片钱。
 * 单条仍走 Produce 的五步向导；这里是批量的对应页。
 */
export function BatchProduce({ runs, inputs, onSelect, onProduced, onNotice }: Props) {
  const [logs, setLogs] = useState<Record<string, string>>({});
  const [phases, setPhases] = useState<Record<string, Phase>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentId, setCurrentId] = useState("");
  const [busy, setBusy] = useState(false);
  const jobs = useRef(new Map<string, { runId: string; resolve: () => void }>());
  const runsRef = useRef(runs);
  runsRef.current = runs;
  const inputsRef = useRef(inputs);
  inputsRef.current = inputs;
  const onProducedRef = useRef(onProduced);
  onProducedRef.current = onProduced;

  useEffect(() => {
    const off = api.onBuild((event: BuildEvent) => {
      const entry = event.jobId ? jobs.current.get(event.jobId) : undefined;
      if (!entry) return;
      if (event.kind === "data") {
        setLogs((previous) => ({
          ...previous,
          [entry.runId]: ((previous[entry.runId] ?? "") + (event.text ?? "")).slice(-60000),
        }));
        return;
      }
      jobs.current.delete(event.jobId!);
      if (event.code === 0) {
        setPhases((previous) => ({ ...previous, [entry.runId]: "done" }));
        if (event.projectDir) onProducedRef.current(entry.runId, event.projectDir);
      } else {
        setPhases((previous) => ({ ...previous, [entry.runId]: "error" }));
        setErrors((previous) => ({ ...previous, [entry.runId]: event.error ?? `退出码 ${event.code}` }));
      }
      entry.resolve();
    });
    return off;
  }, []);

  const produceOne = useCallback((run: RunItem, replace = false) => {
    return new Promise<void>((resolve) => {
      if (!producible(run)) {
        resolve();
        return;
      }
      const jobId = `batch-produce-${crypto.randomUUID()}`;
      jobs.current.set(jobId, { runId: run.id, resolve });
      setCurrentId(run.id);
      setPhases((previous) => ({ ...previous, [run.id]: "running" }));
      setErrors((previous) => ({ ...previous, [run.id]: "" }));
      void api
        .build({
          jobId,
          action: "render",
          projectName: run.name || `batch-${Date.now()}`,
          outputs: run.result?.outputs ?? {},
          allowMissing: true,
          replace,
          tts: {
            provider: inputsRef.current.tts_provider,
            baseUrl: inputsRef.current.tts_base_url,
            model: inputsRef.current.tts_model,
            voice: inputsRef.current.tts_voice,
          },
        })
        .catch((cause: Error) => {
          jobs.current.delete(jobId);
          setPhases((previous) => ({ ...previous, [run.id]: "error" }));
          setErrors((previous) => ({ ...previous, [run.id]: cause.message }));
          resolve();
        });
    });
  }, []);

  const pending = runs.filter((run) => producible(run) && !run.produced);

  const produceAll = useCallback(async () => {
    if (busy) return;
    const list = runsRef.current.filter((run) => producible(run) && !run.produced);
    if (list.length === 0) {
      onNotice("这批都已经出过片了；要重出就点单条的「重新出片」。");
      return;
    }
    setBusy(true);
    onNotice(`开始批量出片：${list.length} 条，逐条串行`);
    for (const run of list) {
      await produceOne(run);
    }
    setBusy(false);
    onNotice(`批量出片结束：${list.length} 条 · 列表里点「查看成片」看`);
  }, [busy, onNotice, produceOne]);

  /* 全自动：一批全部跑完时自动逐条出片（设置面板里可关）。 */
  const produceAllRef = useRef<() => Promise<void>>(async () => {});
  produceAllRef.current = produceAll;

  useEffect(() => {
    const onCompleted = () => {
      if (localStorage.getItem("studio.autoProduce") === "0") return;
      void produceAllRef.current();
    };
    window.addEventListener("wf:batch-completed", onCompleted);
    return () => window.removeEventListener("wf:batch-completed", onCompleted);
  }, []);

  const openVideo = (dir: string) => {
    void api.open(`${dir}/成片/最终视频.mp4`).catch(() => api.open(`${dir}/成片`).catch(() => undefined));
  };

  return (
    <section className="produce card">
      <div className="produce-head">
        <span className="produce-title">批量出片</span>
        <span className="pill run produce-batch">批量 · {runs.length} 条</span>
        <span className="produce-sub">
          逐条串行出，一次只烧一条；单条要手动兜底就选中它回单条出片页
        </span>
        <span className="spacer" />
        <button className="btn primary" onClick={() => void produceAll()} disabled={busy || pending.length === 0}>
          {busy ? "出片中…" : `全部出片${pending.length > 0 ? ` · ${pending.length} 条` : ""}`}
        </button>
      </div>

      <div className="batch-produce-list">
        {runs.map((run, index) => {
          const ready = producible(run);
          const phase = phases[run.id];
          const error = errors[run.id];
          return (
            <div className={`batch-produce-row ${currentId === run.id ? "on" : ""}`} key={run.id}>
              <span className="batch-produce-no">{index + 1}</span>
              <button className="batch-produce-main" onClick={() => onSelect(run.id)} title="选中这条，画布和运行台跟着切过去">
                <span className="batch-produce-name">{run.name || "未命名"}</span>
                <span className="batch-produce-topic">{run.topic || "（无需求摘要）"}</span>
              </button>
              <span
                className={`pill ${
                  run.produced ? "ok" : phase === "error" ? "bad" : phase === "running" ? "" : ready ? "" : "bad"
                }`}
              >
                {run.produced
                  ? "已出片"
                  : phase === "running"
                    ? "出片中"
                    : phase === "error"
                      ? "失败"
                      : ready
                        ? "待出片"
                        : "无输出"}
              </span>
              <span className="spacer" />
              {run.produced ? (
                <>
                  <button className="btn sm" onClick={() => openVideo(run.produced!.dir)}>查看成片</button>
                  <button
                    className="btn sm ghost"
                    onClick={() => {
                      if (window.confirm(`重新出片会先备份「${run.name}」并重新配音（会产生费用）。继续？`)) {
                        void produceOne(run, true);
                      }
                    }}
                    disabled={busy}
                  >
                    重新出片
                  </button>
                </>
              ) : (
                <button className="btn sm primary" onClick={() => void produceOne(run)} disabled={!ready || busy}>
                  出片
                </button>
              )}
            </div>
          );
        })}
      </div>

      {errors[currentId] && <div className="err-text">{errors[currentId]}</div>}
      <LogBox text={logs[currentId] ?? ""} placeholder="出片日志会出现在这里；先点「全部出片」或单条的「出片」" />
    </section>
  );
}
