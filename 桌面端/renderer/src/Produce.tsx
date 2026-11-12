import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { parseImagePlanValue } from "../../src/engine/imagePlan.js";
import { CopyButton } from "./CopyButton.js";
import { bridge } from "./bridge.js";
import type { BuildEvent, BuildStarted, FileEntry, InboxFile, RunInputs, RunResult } from "./types.js";

const api = bridge();
const STORE_KEY = "studio.produce";

interface Props {
  result: RunResult | null;
  inputs: RunInputs;
  onRun: () => void;
  onArtifacts: () => void;
  onNotice: (text: string) => void;
}

interface PromptCard {
  scene: string;
  text: string;
  thumb?: string;
}

interface StoredProject {
  runId: string;
  dir: string;
  name: string;
}

function timestampName(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}-${pad(now.getHours())}${pad(now.getMinutes())}`;
}

function stem(name: string): string {
  return name.replace(/\.[^.]+$/, "");
}

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error ?? new Error("读取图片失败"));
    reader.readAsDataURL(file);
  });
}

/** 本次运行真正要出图的 id（role=html 的屏不生成照片）。 */
function imageIds(outputs: Record<string, unknown>): string[] {
  const plan = parseImagePlanValue(outputs["image_plan_json"]);
  if (!plan) return [];
  const ids: string[] = [];
  for (const image of plan.images) {
    if (String(image.role ?? "").toLowerCase() === "html") continue;
    const id = String(image.id ?? image.scene_id ?? "");
    if (id) ids.push(id);
  }
  return ids;
}

/** 出图 txt 里带中文/英文两段和保存说明；复制时只取提示词段落，别把「出图后保存为…」也塞给模型。 */
function splitPrompt(text: string): { zh: string; en: string } {
  const zhMark = text.indexOf("—— 中文提示词");
  const enMark = text.indexOf("—— 英文提示词");
  if (zhMark < 0) return { zh: text.trim(), en: "" };
  const zhStart = text.indexOf("\n", zhMark);
  const zh = text
    .slice(zhStart < 0 ? zhMark : zhStart + 1, enMark < 0 ? text.length : text.lastIndexOf("\n", enMark))
    .trim();
  let en = "";
  if (enMark >= 0) {
    const enStart = text.indexOf("\n", enMark);
    en = text.slice(enStart < 0 ? enMark : enStart + 1).split(/\n出图后保存为/)[0]?.trim() ?? "";
  }
  return { zh, en };
}

/** 和 build_black_frame_project.py 一致：文件名等于 id 的优先，其余按图片自己的修改时间顺序补齐。 */
function coverage(ids: string[], files: InboxFile[]): { present: Set<string>; missing: string[]; extra: InboxFile[] } {
  const known = new Set(ids);
  const byId = new Map<string, InboxFile>();
  for (const file of files) {
    const key = stem(file.name);
    if (known.has(key)) byId.set(key, file);
  }
  const rest = files.filter((file) => !known.has(stem(file.name))).sort((left, right) => left.mtime - right.mtime);
  const present = new Set(byId.keys());
  const missing: string[] = [];
  let cursor = 0;
  for (const id of ids) {
    if (byId.has(id)) continue;
    if (cursor < rest.length) {
      present.add(id);
      cursor += 1;
    } else {
      missing.push(id);
    }
  }
  return { present, missing, extra: rest.slice(cursor) };
}

function Step({
  index,
  title,
  summary,
  done,
  open,
  onToggle,
  children,
}: {
  index: number;
  title: string;
  summary: string;
  done: boolean;
  open: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <li className={`step ${done ? "done" : ""} ${open ? "open" : ""}`}>
      <button type="button" className="step-head" onClick={onToggle}>
        <span className="step-no">{done ? "✓" : index}</span>
        <span className="step-title">{title}</span>
        <span className="step-sum">{summary}</span>
        <span className="step-chev">{open ? "收起" : "展开"}</span>
      </button>
      {open && <div className="step-body">{children}</div>}
    </li>
  );
}

/** 出片：运行结果 → 准备项目 → 出图提示词 → 放图 → 渲染成片。 */
export function Produce({ result, inputs, onRun, onArtifacts, onNotice }: Props) {
  const [projectName, setProjectName] = useState(timestampName);
  const [projectDir, setProjectDir] = useState("");
  const [prompts, setPrompts] = useState<PromptCard[]>([]);
  const [images, setImages] = useState<InboxFile[]>([]);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [imageDir, setImageDir] = useState("");
  const [phase, setPhase] = useState<"prepare" | "render" | null>(null);
  const [started, setStarted] = useState<BuildStarted | null>(null);
  const [logs, setLogs] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  const [allowMissing, setAllowMissing] = useState(() => localStorage.getItem("studio.allowMissing") === "1");
  const [rendered, setRendered] = useState(false);
  const [mimo, setMimo] = useState<{ hasKey: boolean; hint: string } | null>(null);
  const [openStep, setOpenStep] = useState(1);
  const picker = useRef<HTMLInputElement>(null);
  const logRef = useRef<HTMLPreElement>(null);
  const dirRef = useRef("");
  dirRef.current = projectDir;
  const phaseRef = useRef<"prepare" | "render" | null>(null);
  phaseRef.current = phase;
  const nameRef = useRef(projectName);
  nameRef.current = projectName;
  const allowRef = useRef(allowMissing);
  allowRef.current = allowMissing;
  const resultRef = useRef(result);
  resultRef.current = result;

  const outputs = result?.outputs ?? {};
  const runDone = Boolean(result && typeof outputs.html_document === "string" && typeof outputs.voiceover_script === "string");
  const prepared = Boolean(projectDir);
  const ids = useMemo(() => imageIds(outputs), [result]);
  const noImages = ids.length === 0;
  const promptsDone = prompts.length > 0 || noImages;
  const cov = useMemo(() => coverage(ids, images), [ids, images]);
  const imagesDone = noImages || (cov.missing.length === 0 && images.length > 0);
  // 准备完但一张图都还没放时，当前步仍是「复制提示词」（3），别直接跳到「放图」
  const firstIncomplete = !runDone
    ? 1
    : !prepared
      ? 2
      : !promptsDone
        ? 3
        : !noImages && images.length === 0
          ? 3
          : !imagesDone
            ? 4
            : 5;

  useEffect(() => {
    localStorage.setItem("studio.allowMissing", allowMissing ? "1" : "0");
  }, [allowMissing]);

  useEffect(() => {
    api.mimoStatus().then(setMimo).catch(() => setMimo({ hasKey: false, hint: "读取 MIMO_API_KEY 失败" }));
  }, []);

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [logs]);

  const refreshImages = useCallback(async (dir: string) => {
    const data = await api.projectImages({ projectPath: dir });
    setImages(data.files);
    setImageDir(data.dir);
    const pairs = await Promise.all(data.files.map(async (file) => [file.path, await api.fileUrl(file.path)] as const));
    setUrls(Object.fromEntries(pairs));
  }, []);

  const hasFinalVideo = useCallback(async (dir: string) => {
    try {
      const entries = await api.files(`${dir}/成片`);
      return entries.some((entry) => entry.type === "file" && entry.name === "最终视频.mp4");
    } catch {
      return false;
    }
  }, []);

  const loadPrompts = useCallback(async (dir: string) => {
    let entries: FileEntry[] = [];
    try {
      entries = await api.files(`${dir}/媒体/出图`);
    } catch {
      entries = [];
    }
    const texts = entries.filter(
      (entry) => entry.type === "file" && /\.txt$/i.test(entry.name) && !/^readme/i.test(entry.name) && !/^全部/.test(entry.name),
    );
    let photos: FileEntry[] = [];
    try {
      photos = await api.files(`${dir}/媒体/图片`);
    } catch {
      photos = [];
    }
    let thumbs: FileEntry[] = [];
    try {
      thumbs = await api.files(`${dir}/媒体/图片/_resolved`);
    } catch {
      thumbs = [];
    }
    const thumbMap = new Map<string, string>();
    for (const photo of photos) {
      if (photo.type === "file" && /\.(png|jpe?g|webp)$/i.test(photo.name)) thumbMap.set(stem(photo.name), photo.path);
    }
    // _resolved 里的安全文件名副本优先（渲染后用这份）
    for (const thumb of thumbs) {
      if (thumb.type === "file" && /\.(png|jpe?g|webp)$/i.test(thumb.name)) thumbMap.set(stem(thumb.name), thumb.path);
    }
    const cards: PromptCard[] = [];
    for (const file of texts) {
      const data = await api.readText(file.path);
      const scene = stem(file.name);
      const thumbPath = thumbMap.get(scene);
      const thumb = thumbPath ? await api.fileUrl(thumbPath) : undefined;
      cards.push({ scene, text: data.text.trim(), ...(thumb ? { thumb } : {}) });
    }
    cards.sort((left, right) => left.scene.localeCompare(right.scene));
    setPrompts(cards);
  }, []);

  /* 换了工作流运行就拿新的 runId：项目名重新取时间戳，旧的准备结果不复用。 */
  const handledRun = useRef<string | null>(null);
  useEffect(() => {
    const runId = result?.runId ?? null;
    if (!runId || handledRun.current === runId) return;
    handledRun.current = runId;
    setError(null);
    setStatus("");
    setLogs("");
    setRendered(false);
    setStarted(null);
    let stored: StoredProject | null = null;
    try {
      stored = JSON.parse(localStorage.getItem(STORE_KEY) || "null") as StoredProject | null;
    } catch {
      stored = null;
    }
    if (stored && stored.runId === runId && stored.dir) {
      const dir = stored.dir;
      setProjectDir(dir);
      setProjectName(stored.name || timestampName());
      void Promise.all([loadPrompts(dir), refreshImages(dir)])
        .then(async () => {
          if (await hasFinalVideo(dir)) setRendered(true);
        })
        .catch(() => {
          setProjectDir("");
          setPrompts([]);
          setImages([]);
        });
      return;
    }
    setProjectDir("");
    setPrompts([]);
    setImages([]);
    setUrls({});
    setImageDir("");
    setProjectName(timestampName());
  }, [result?.runId, loadPrompts, refreshImages, hasFinalVideo]);

  useEffect(() => {
    if (!result?.runId || !projectDir) return;
    const stored: StoredProject = { runId: result.runId, dir: projectDir, name: projectName };
    localStorage.setItem(STORE_KEY, JSON.stringify(stored));
  }, [projectDir, projectName, result?.runId]);

  const firstRef = useRef(0);
  useEffect(() => {
    if (firstIncomplete !== firstRef.current) {
      firstRef.current = firstIncomplete;
      setOpenStep(firstIncomplete);
    }
  }, [firstIncomplete]);

  useEffect(() => {
    const off = api.onBuild((event: BuildEvent) => {
      if (event.kind === "data") {
        setLogs((previous) => (previous + (event.text ?? "")).slice(-80000));
        return;
      }
      setPhase(null);
      if (event.code === 0) {
        if (event.action === "prepare") {
          setStatus("准备完成");
          onNotice("项目已准备好：复制提示词去出图，图放回后渲染成片");
          const dir = event.projectDir;
          if (dir) {
            // 先把提示词和图片读完再切 "已完成"，避免闪一下空提示词
            void Promise.all([loadPrompts(dir), refreshImages(dir)])
              .catch(() => undefined)
              .then(() => setProjectDir(dir));
          }
        } else {
          if (event.projectDir) setProjectDir(event.projectDir);
          setRendered(true);
          setStatus("渲染完成");
          onNotice("渲染完成，去「产物」看成片");
        }
        return;
      }
      setStatus(`${event.action === "prepare" ? "准备" : "渲染"}失败（退出码 ${event.code}）`);
      setError(event.error ?? `退出码 ${event.code}`);
    });
    return off;
  }, [loadPrompts, refreshImages, onNotice]);

  async function start(action: "prepare" | "render", replace = false) {
    const current = resultRef.current;
    if (!current || phaseRef.current) return;
    if (action === "render" && !dirRef.current) return;
    setPhase(action);
    setLogs("");
    setError(null);
    setStatus(action === "prepare" ? "准备中…" : "渲染中…");
    try {
      const info = await api.build({
        action,
        projectName: nameRef.current.trim() || timestampName(),
        outputs: current.outputs,
        allowMissing: action === "render" ? allowRef.current : false,
        replace,
        tts: {
          provider: inputs.tts_provider,
          baseUrl: inputs.tts_base_url,
          model: inputs.tts_model,
          voice: inputs.tts_voice,
        },
      });
      setStarted(info);
    } catch (cause) {
      setPhase(null);
      setStatus("");
      setError((cause as Error).message);
    }
  }

  async function accept(list: FileList | File[]) {
    if (!projectDir) return;
    const files = Array.from(list).filter(
      (file) => file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name),
    );
    if (files.length === 0) {
      setError("只接受图片文件（png / jpg / webp / gif）");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      for (const file of files) {
        await api.projectImageSave({
          projectPath: projectDir,
          name: file.name,
          base64: await readBase64(file),
          mtime: file.lastModified,
        });
      }
      await refreshImages(projectDir);
      await loadPrompts(projectDir).catch(() => undefined);
      onNotice(`已放入 ${files.length} 张图`);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function openVideo() {
    if (!projectDir) return;
    const file = await api.open(`${projectDir}/成片/最终视频.mp4`).catch(() => ({ ok: false, error: "" }));
    if (!file.ok) await api.open(`${projectDir}/成片`).catch(() => undefined);
  }

  const stepSummary = [
    runDone ? `已完成 · ${result?.nodes.length ?? 0} 节点` : result ? "这次没有 html/口播，先重跑" : "还没运行",
    prepared ? `项目 ${projectName}` : "建项目、写出图提示词",
    promptsDone ? `${prompts.length} 张提示词` : "准备后才有",
    noImages ? "这次没有图片计划" : `${ids.length - cov.missing.length} / ${ids.length} 张已就位`,
    rendered ? "已完成" : "配音 + 字幕 + mp4",
  ];
  const promptBodies = prompts.map((prompt) => splitPrompt(prompt.text));

  return (
    <section className="produce card">
      <div className="produce-head">
        <span className="produce-title">出片</span>
        <span className="produce-sub">跑完工作流后按 1 → 5 走，按钮都在对应步骤里</span>
        <span className="spacer" />
        <button className="btn sm ghost" onClick={onArtifacts}>看产物</button>
      </div>

      <ol className="steps">
        <Step
          index={1}
          title="运行结果"
          summary={stepSummary[0] ?? ""}
          done={runDone}
          open={openStep === 1}
          onToggle={() => setOpenStep(openStep === 1 ? 0 : 1)}
        >
          {!result ? (
            <div className="step-row">
              <span className="hint-text">还没有运行结果。运行会真实调用模型（先在左栏「设置」里配 Key）。</span>
              <span className="spacer" />
              <button className="btn primary" onClick={onRun}>去运行</button>
            </div>
          ) : (
            <>
              <div className="step-row">
                <span className={`pill ${result.status === "success" ? "ok" : result.status === "error" ? "bad" : ""}`}>{result.status}</span>
                <span className="hint-text">{result.nodes.length} 个节点 · {(result.ms / 1000).toFixed(1)}s</span>
                <span className="spacer" />
                <button className="btn sm" onClick={onRun}>重新运行</button>
              </div>
              {!runDone && (
                <div className="warn-box">这次运行没有同时拿到 html_document 和 voiceover_script，出片需要这两样；先重新运行。</div>
              )}
              {result.error && <div className="err-text">{result.error}</div>}
            </>
          )}
        </Step>

        <Step
          index={2}
          title="准备项目"
          summary={stepSummary[1] ?? ""}
          done={prepared}
          open={openStep === 2}
          onToggle={() => setOpenStep(openStep === 2 ? 0 : 2)}
        >
          <div className="step-row">
            <label className="field inline">
              <span>项目名</span>
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} disabled={phase !== null} />
            </label>
            <button className="btn sm ghost" onClick={() => setProjectName(timestampName())} disabled={phase !== null}>用时间戳</button>
            <span className="spacer" />
            <button className="btn primary" onClick={() => void start("prepare")} disabled={!runDone || phase !== null}>
              {phase === "prepare" ? "准备中…" : "准备项目"}
            </button>
          </div>
          <div className="hint-text">
            只在本地建 <code>HTML视频项目/{projectName || "项目名"}/</code>，写入图片计划、<code>媒体/出图/*.txt</code> 和出图清单；不出图、不配音、不渲染。
          </div>
          {prepared && (
            <div className="step-row">
              <span className="hint-text">已有项目：{projectDir}</span>
              <button className="btn sm ghost" onClick={() => void api.open(projectDir)}>打开项目</button>
            </div>
          )}
          {started && started.projectDir === projectDir && started.expectedIds.length > 0 && (
            <div className="hint-text">期望图片 {started.expectedIds.length} 张：{started.expectedIds.join("、")}</div>
          )}
          {phase === "prepare" && <pre className="make-log" ref={logRef}>{logs || "准备中…"}</pre>}
          {status && !rendered && <div className="hint-text">{status}</div>}
          {error && phase === null && <div className="err-text">{error}</div>}
        </Step>

        <Step
          index={3}
          title="出图提示词"
          summary={stepSummary[2] ?? ""}
          done={promptsDone}
          open={openStep === 3}
          onToggle={() => setOpenStep(openStep === 3 ? 0 : 3)}
        >
          {!prepared ? (
            <div className="hint-text">先完成第 2 步「准备项目」，提示词才会写到项目里。</div>
          ) : prompts.length === 0 ? (
            <div className="hint-text">项目里还没有 <code>媒体/出图/*.txt</code>；重新准备一次项目看看日志。</div>
          ) : (
            <>
              <div className="step-row">
                <span className="hint-text">共 {prompts.length} 张 · 复制中文段落去出图，文件名用卡片上的 id</span>
                <span className="spacer" />
                <CopyButton text={promptBodies.map((body) => body.zh).join("\n\n")} label="复制全部中文" />
                <button className="btn sm ghost" onClick={() => void api.open(`${projectDir}/媒体/出图`)}>打开文件夹</button>
              </div>
              <div className="ip-grid">
                {prompts.map((prompt, index) => {
                  const body = promptBodies[index] ?? { zh: prompt.text, en: "" };
                  return (
                    <section className="ip-card" key={prompt.scene}>
                      <div className="ip-head">
                        <span>{prompt.scene}</span>
                        <CopyButton text={body.zh} label="复制中文" />
                        {body.en && <CopyButton text={body.en} label="复制英文" />}
                      </div>
                      {prompt.thumb && <img className="ip-thumb" src={prompt.thumb} alt="" />}
                      <pre className="ip-text">{prompt.text}</pre>
                    </section>
                  );
                })}
              </div>
            </>
          )}
        </Step>

        <Step
          index={4}
          title="放图"
          summary={stepSummary[3] ?? ""}
          done={imagesDone}
          open={openStep === 4}
          onToggle={() => setOpenStep(openStep === 4 ? 0 : 4)}
        >
          {!prepared ? (
            <div className="hint-text">先完成第 2 步「准备项目」。</div>
          ) : (
            <>
              <div className="step-row">
                <span className={`pill ${imagesDone ? "ok" : ""}`}>
                  {noImages ? "本次无需出图" : `已放 ${ids.length - cov.missing.length} / ${ids.length} 张`}
                </span>
                <span className="hint-text">文件叫 s02.png 就按 id 对；其余按图片自己的修改时间顺序对号，和拖入先后无关</span>
                <span className="spacer" />
                {busy && <span className="hint-text">写入中…</span>}
                <button className="btn sm ghost" onClick={() => void refreshImages(projectDir)} disabled={busy}>刷新</button>
                <button className="btn sm ghost" onClick={() => void api.open(imageDir || `${projectDir}/媒体/图片`)}>打开文件夹</button>
              </div>
              {ids.length > 0 && (
                <div className="img-chips">
                  {ids.map((id) => (
                    <span className={`img-chip ${cov.present.has(id) ? "ok" : ""}`} key={id}>
                      {id}{cov.present.has(id) ? " ✓" : " 缺"}
                    </span>
                  ))}
                </div>
              )}
              <div
                className={`dropzone ${drag ? "drag" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setDrag(true);
                }}
                onDragLeave={() => setDrag(false)}
                onDrop={(event) => {
                  event.preventDefault();
                  setDrag(false);
                  void accept(event.dataTransfer.files);
                }}
                onClick={() => picker.current?.click()}
              >
                <div className="dropzone-title">把图片拖到这里</div>
                <div className="dropzone-sub">存到 {imageDir || `${projectDir}/媒体/图片`}；不改工作流、不改 YAML</div>
                <button
                  className="btn"
                  onClick={(event) => {
                    event.stopPropagation();
                    picker.current?.click();
                  }}
                  disabled={busy}
                >
                  或点这里选择图片
                </button>
              </div>
              <input
                ref={picker}
                type="file"
                accept="image/*"
                multiple
                style={{ display: "none" }}
                onChange={(event) => {
                  if (event.target.files) void accept(event.target.files);
                  event.target.value = "";
                }}
              />
              <div className="inbox-grid">
                {images.map((file) => (
                  <button className="inbox-card" key={file.path} title={file.path} onClick={() => void api.open(file.path)}>
                    {urls[file.path] ? <img src={urls[file.path]} alt="" /> : <div className="inbox-ph" />}
                    <span>{file.name}</span>
                  </button>
                ))}
              </div>
              {cov.extra.length > 0 && <div className="hint-text">多出 {cov.extra.length} 张不会被本次渲染用到。</div>}
            </>
          )}
        </Step>

        <Step
          index={5}
          title="渲染成片"
          summary={stepSummary[4] ?? ""}
          done={rendered}
          open={openStep === 5}
          onToggle={() => setOpenStep(openStep === 5 ? 0 : 5)}
        >
          {!prepared ? (
            <div className="hint-text">先完成第 2 步「准备项目」。</div>
          ) : (
            <>
              <div className="step-row">
                <span className="hint-text">配音：{mimo ? mimo.hint : "检查中…"}</span>
                <label className="check">
                  <input type="checkbox" checked={allowMissing} onChange={(event) => setAllowMissing(event.target.checked)} />
                  缺图也继续（只用于排查版面）
                </label>
                <span className="spacer" />
                {rendered ? (
                  <>
                    <button className="btn primary" onClick={() => void openVideo()}>打开成片</button>
                    <button
                      className="btn"
                      onClick={() => {
                        if (window.confirm("重新渲染会先备份旧项目，并重新配音（会产生费用）。继续？")) void start("render", true);
                      }}
                      disabled={phase !== null}
                    >
                      重新渲染
                    </button>
                  </>
                ) : (
                  <button
                    className="btn primary"
                    onClick={() => void start("render")}
                    disabled={!runDone || phase !== null || (!imagesDone && !allowMissing)}
                  >
                    {phase === "render" ? "渲染中…" : "渲染成片"}
                  </button>
                )}
              </div>
              {!imagesDone && !allowMissing && ids.length > 0 && (
                <div className="warn-box">还缺 {cov.missing.length} 张：{cov.missing.join("、")}。补齐再渲染，或勾「缺图也继续」。</div>
              )}
              {status && <div className="hint-text">{status}</div>}
              {error && <div className="err-text">{error}</div>}
              {(logs || phase === "render") && (
                <pre className="make-log" ref={logRef}>{logs || "渲染中…"}</pre>
              )}
            </>
          )}
        </Step>
      </ol>
    </section>
  );
}
