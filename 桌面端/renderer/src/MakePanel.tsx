import { useEffect, useRef, useState } from "react";
import { parseImagePlanValue } from "../../src/engine/imagePlan.js";
import { bridge } from "./bridge.js";
import type { BuildEvent, BuildStarted, RunInputs, RunResult } from "./types.js";

const api = bridge();

function timestampName(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
}

interface Props {
  result: RunResult | null;
  inputs: RunInputs;
  onNotice: (text: string) => void;
}

/** 制作：准备项目（落 HTML/口播/出图提示词）→ 外部出图 → 渲染成片。 */
export function MakePanel({ result, inputs, onNotice }: Props) {
  const [projectName, setProjectName] = useState(timestampName());
  const [autoPrepare, setAutoPrepare] = useState(() => localStorage.getItem("studio.autoPrepare") === "1");
  const [autoRender, setAutoRender] = useState(() => localStorage.getItem("studio.autoRender") === "1");
  const [allowMissing, setAllowMissing] = useState(() => localStorage.getItem("studio.allowMissing") === "1");
  const [running, setRunning] = useState<"prepare" | "render" | null>(null);
  const [logs, setLogs] = useState("");
  const [status, setStatus] = useState<string>("");
  const [started, setStarted] = useState<BuildStarted | null>(null);
  const [mimo, setMimo] = useState<{ hasKey: boolean; hint: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastAutoRun = useRef<string | null>(null);
  const logRef = useRef<HTMLPreElement>(null);
  const opts = useRef({ autoRender, allowMissing, inputs });
  opts.current = { autoRender, allowMissing, inputs };

  const outputs = result?.outputs ?? {};
  const plan = parseImagePlanValue(outputs["image_plan_json"]);
  const canPrepare = typeof outputs["html_document"] === "string" && typeof outputs["voiceover_script"] === "string";

  useEffect(() => {
    localStorage.setItem("studio.autoPrepare", autoPrepare ? "1" : "0");
    localStorage.setItem("studio.autoRender", autoRender ? "1" : "0");
    localStorage.setItem("studio.allowMissing", allowMissing ? "1" : "0");
  }, [autoPrepare, autoRender, allowMissing]);

  useEffect(() => {
    api.mimoStatus().then(setMimo).catch(() => setMimo({ hasKey: false, hint: "读取 MIMO_API_KEY 失败" }));
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  async function start(action: "prepare" | "render") {
    if (!canPrepare || running) return;
    setRunning(action);
    setLogs("");
    setError(null);
    setStatus(action === "prepare" ? "准备中…" : "渲染中…");
    try {
      const info = await api.build({
        action,
        projectName: projectName.trim() || timestampName(),
        outputs,
        allowMissing: opts.current.allowMissing,
        tts: {
          provider: opts.current.inputs.tts_provider,
          baseUrl: opts.current.inputs.tts_base_url,
          model: opts.current.inputs.tts_model,
          voice: opts.current.inputs.tts_voice,
        },
      });
      setStarted(info);
    } catch (cause) {
      setRunning(null);
      setStatus("");
      setError((cause as Error).message);
    }
  }

  useEffect(() => {
    const off = api.onBuild((event: BuildEvent) => {
      if (event.kind === "data") {
        setLogs((previous) => (previous + (event.text ?? "")).slice(-60000));
        return;
      }
      setRunning(null);
      setStatus(event.code === 0 ? `${event.action === "prepare" ? "准备" : "渲染"}完成` : `${event.action === "prepare" ? "准备" : "渲染"}失败（退出码 ${event.code}）`);
      if (event.code === 0) onNotice(event.action === "prepare" ? "项目已准备好，去「图片」页签放图，再回来渲染" : "渲染完成，去「产物」看成片");
      if (event.code !== 0) setError(event.error ?? `退出码 ${event.code}`);
      if (event.action === "prepare" && event.code === 0 && opts.current.autoRender && event.projectDir) {
        const expected = event.expectedIds ?? [];
        void api.projectImages({ projectPath: event.projectDir }).then((data) => {
          if (expected.length > 0 && data.files.length >= expected.length) void start("render");
          else onNotice(`图片还差 ${Math.max(0, expected.length - data.files.length)} 张，补齐后再点「渲染成片」`);
        });
      }
    });
    return off;
  }, [onNotice]);

  useEffect(() => {
    if (!result || !autoPrepare || !canPrepare || running) return;
    if (lastAutoRun.current === result.runId) return;
    lastAutoRun.current = result.runId;
    void start("prepare");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [result, autoPrepare]);

  return (
    <div className="make">
      <div className="make-head">
        <label className="field inline">
          <span>项目名</span>
          <input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
        </label>
        <button className="btn sm ghost" onClick={() => setProjectName(timestampName())}>用时间戳</button>
        <span className="spacer" />
        <button className="btn primary" onClick={() => void start("prepare")} disabled={!canPrepare || running !== null}>
          {running === "prepare" ? "准备中…" : "准备项目"}
        </button>
        <button className="btn" onClick={() => void start("render")} disabled={!canPrepare || running !== null}>
          {running === "render" ? "渲染中…" : "渲染成片"}
        </button>
      </div>
      <div className="make-options">
        <label><input type="checkbox" checked={autoPrepare} onChange={(event) => setAutoPrepare(event.target.checked)} /> 跑完自动准备</label>
        <label><input type="checkbox" checked={autoRender} onChange={(event) => setAutoRender(event.target.checked)} /> 准备完图片齐了自动渲染</label>
        <label><input type="checkbox" checked={allowMissing} onChange={(event) => setAllowMissing(event.target.checked)} /> 缺图也继续（看版面）</label>
        <span className="hint-text">TTS：{mimo ? mimo.hint : "检查中…"}</span>
        {plan && <span className="hint-text">本次图像计划 {plan.images.length} 张</span>}
      </div>
      {!canPrepare && (
        <div className="hint-text">需要先跑完整条链路（End 输出里有 html_document 和 voiceover_script）才能准备项目。</div>
      )}
      {error && <div className="err-text">{error}</div>}
      {status && <div className="ok-text">{status}</div>}
      {started && (
        <div className="hint-text">
          项目：{started.projectDir}
          {" · "}
          <button className="btn sm ghost" onClick={() => void api.open(started.projectDir)}>打开项目</button>
          {" · "}
          期望图片 {started.expectedIds.length} 张：{started.expectedIds.join("、") || "（无）"}
        </div>
      )}
      <pre className="make-log" ref={logRef}>{logs || "点「准备项目」开始。图片在外面生成，放回媒体/图片后点「渲染成片」。"}</pre>
    </div>
  );
}
