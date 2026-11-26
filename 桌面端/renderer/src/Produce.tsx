import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent } from "react";
import { projectStamp, uniqueProjectName } from "../../src/batch/model.js";
import { parseImagePlanValue } from "../../src/engine/imagePlan.js";
import { CopyButton } from "./CopyButton.js";
import { readSize, startDrag } from "./drag.js";
import { bridge } from "./bridge.js";
import type { BuildEvent, BuildStarted, FileEntry, InboxFile, RunInputs, RunResult } from "./types.js";

const api = bridge();
const STORE_KEY = "studio.produce";

interface Props {
  result: RunResult | null;
  /** 当前这条运行的 id：渲染完成时按它回写「已出片」。 */
  runId: string;
  inputs: RunInputs;
  /** 批量时这条自动生成的项目名；单条为空，沿用时间戳。 */
  defaultName?: string;
  /** 批量上下文：只在界面标一下这是第几条，出片流程本身不变。 */
  batch?: { index: number; total: number; topic: string } | null;
  onRun: () => void;
  onArtifacts: () => void;
  onNotice: (text: string) => void;
  onProduced: (runId: string, dir: string) => void;
}

interface PromptCard {
  scene: string;
  text: string;
}

interface StoredProject {
  runId: string;
  dir: string;
  name: string;
}

/** 每条运行各自记自己的项目：切到另一条时不会串到上一批的目录。 */
function storeKeyFor(runId: string | undefined): string {
  return runId ? `${STORE_KEY}:${runId}` : STORE_KEY;
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
  actions,
  children,
}: {
  index: number;
  title: string;
  summary: string;
  done: boolean;
  open: boolean;
  onToggle: () => void;
  /** 折叠状态下也能点的动作（出图提示词的「复制 / 打开文件夹」）。 */
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <li className={`step ${done ? "done" : ""} ${open ? "open" : ""}`}>
      {/* 用 div 而不是 button：标题行里要嵌真按钮，button 不能套 button */}
      <div
        className="step-head"
        role="button"
        tabIndex={0}
        onClick={onToggle}
        onKeyDown={(event) => {
          if (event.key !== "Enter" && event.key !== " ") return;
          event.preventDefault();
          onToggle();
        }}
      >
        <span className="step-no">{done ? "✓" : index}</span>
        <span className="step-title">{title}</span>
        <span className="step-sum">{summary}</span>
        {actions && (
          <span className="step-actions" onClick={(event) => event.stopPropagation()}>
            {actions}
          </span>
        )}
        <span className="step-chev">{open ? "收起" : "展开"}</span>
      </div>
      {open && <div className="step-body">{children}</div>}
    </li>
  );
}

/**
 * 日志框：框里不出滚动条，只露末尾几行。
 * 以前是 260px 的内滚区，滚轮落在上面就只滚日志，永远滚不到下一个步骤框；
 * 现在超出的从顶部裁掉，要看全按「展开全部」，由出片页自己滚。
 */
export function LogBox({ text, placeholder }: { text: string; placeholder: string }) {
  const [height, setHeight] = useState(() => readSize("studio.logH", 220, 80));
  const [expanded, setExpanded] = useState(false);
  const clip = useRef<HTMLDivElement>(null);
  const body = text || placeholder;
  /* 日志会一行行追加，行数只在内容变化时算一次 */
  const lines = useMemo(() => (body.match(/\n/g)?.length ?? 0) + 1, [body]);

  useEffect(() => {
    localStorage.setItem("studio.logH", String(Math.round(height)));
  }, [height]);

  /* 跟着末尾走：框里没有滚动条，但 scrollTop 还能设 */
  useEffect(() => {
    const element = clip.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [body, height, expanded]);

  const resize = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (expanded) return;
    startDrag(event, { axis: "y", from: height, min: 80, max: 560, onMove: setHeight });
  };

  return (
    <div className={`logbox ${expanded ? "expanded" : ""}`} style={{ "--log-h": `${Math.round(height)}px` } as CSSProperties}>
      <div className="logbox-clip" ref={clip}>
        <pre className="make-log">{body}</pre>
      </div>
      <div className="logbox-bar" onPointerDown={resize}>
        <span>{lines} 行{expanded ? "" : " · 只显示末尾"}</span>
        <span className="spacer" />
        <button
          className="btn sm ghost"
          onPointerDown={(event) => event.stopPropagation()}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? "收起到末尾" : "展开全部"}
        </button>
      </div>
    </div>
  );
}

/** 出片：运行结果 → 准备项目 → 出图提示词 → 放图 → 渲染成片。 */
export function Produce({ result, runId, inputs, defaultName = "", batch = null, onRun, onArtifacts, onNotice, onProduced }: Props) {
  const [projectName, setProjectName] = useState(() => defaultName || projectStamp());
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
  const [autoProduce, setAutoProduce] = useState(() => localStorage.getItem("studio.autoProduce") !== "0");
  const [rendered, setRendered] = useState(false);
  const [mimo, setMimo] = useState<{ hasKey: boolean; hint: string } | null>(null);
  const [imageKey, setImageKey] = useState(false);
  const [openStep, setOpenStep] = useState(1);
  const picker = useRef<HTMLInputElement>(null);
  const dirRef = useRef("");
  dirRef.current = projectDir;
  const phaseRef = useRef<"prepare" | "render" | null>(null);
  phaseRef.current = phase;
  /** 本次构建的 jobId：批量里同时有多条项目在构建，只收自己这条的事件。 */
  const jobRef = useRef("");
  const nameRef = useRef(projectName);
  nameRef.current = projectName;
  const allowRef = useRef(allowMissing);
  allowRef.current = allowMissing;
  const autoProduceRef = useRef(autoProduce);
  autoProduceRef.current = autoProduce;
  const imageKeyRef = useRef(imageKey);
  imageKeyRef.current = imageKey;
  const resultRef = useRef(result);
  resultRef.current = result;
  /* 跑完自动出片：事件先记 runId，等 result 真的换过来再启动。 */
  const pendingAutoRef = useRef("");
  const autoDoneRef = useRef(new Set<string>());
  /* 构建按 jobId 收事件：完成时回写的必须是「起这个构建的那条」，不是当前正在看的那条 */
  const runIdRef = useRef(runId);
  runIdRef.current = runId;
  const buildRunRef = useRef(runId);
  const onProducedRef = useRef(onProduced);
  onProducedRef.current = onProduced;

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

  /** 全自动开关：设置面板与出片页共用 localStorage，改哪边都同步。 */
  useEffect(() => {
    const reload = () => setAutoProduce(localStorage.getItem("studio.autoProduce") !== "0");
    window.addEventListener("wf:auto-produce-changed", reload);
    return () => window.removeEventListener("wf:auto-produce-changed", reload);
  }, []);

  /** App 在单条运行跑完时发出来；这里只记 runId，等 result 换过来再动手。 */
  useEffect(() => {
    const onCompleted = (event: Event) => {
      const detail = (event as CustomEvent<{ runId?: string }>).detail;
      if (detail?.runId) pendingAutoRef.current = detail.runId;
    };
    window.addEventListener("wf:run-completed", onCompleted);
    return () => window.removeEventListener("wf:run-completed", onCompleted);
  }, []);

  /** 跑完就自动出片：开关开着、配了生图 Key、这条还没自动跑过。 */
  useEffect(() => {
    const id = pendingAutoRef.current;
    if (!id || !result || result.runId !== id) return;
    pendingAutoRef.current = "";
    if (!autoProduceRef.current || !imageKeyRef.current) return;
    if (autoDoneRef.current.has(id)) return;
    autoDoneRef.current.add(id);
    onNotice("跑完了，自动出片中…");
    void start("render");
  }, [result?.runId]);

  useEffect(() => {
    api.mimoStatus().then(setMimo).catch(() => setMimo({ hasKey: false, hint: "读取 MIMO_API_KEY 失败" }));
  }, []);

  // 设置面板保存后同步一次：配完生图 Key 不用重开出片页，按钮直接换成「生图并出片」。
  useEffect(() => {
    const reload = () => {
      api.settings().then((info) => setImageKey(Boolean(info.hasImageKey))).catch(() => setImageKey(false));
    };
    reload();
    window.addEventListener("wf:settings-saved", reload);
    return () => window.removeEventListener("wf:settings-saved", reload);
  }, []);

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
    // 只留「有多少张、复制哪几段」：逐张全文不再渲染到界面里，要看去文件夹
    const cards: PromptCard[] = [];
    for (const file of texts) {
      const data = await api.readText(file.path);
      cards.push({ scene: stem(file.name), text: data.text.trim() });
    }
    cards.sort((left, right) => left.scene.localeCompare(right.scene));
    setPrompts(cards);
  }, []);

  /* 换了工作流运行就拿新的 runId：每条运行只认自己存的项目，互不串。 */
  const handledRun = useRef<string | null>(null);
  useEffect(() => {
    const runId = result?.runId ?? null;
    if (!runId) {
      if (handledRun.current !== null) {
        handledRun.current = null;
        jobRef.current = "";
        setPhase(null);
        setProjectDir("");
        setPrompts([]);
        setImages([]);
        setUrls({});
        setImageDir("");
        setRendered(false);
        setStarted(null);
        setProjectName(defaultName || projectStamp());
      }
      return;
    }
    if (handledRun.current === runId) return;
    handledRun.current = runId;
    // 换了条目：上一段的构建事件不再属于这个界面，直接停掉监听对应关系
    jobRef.current = "";
    setPhase(null);
    setError(null);
    setStatus("");
    setLogs("");
    setRendered(false);
    setStarted(null);
    let stored: StoredProject | null = null;
    try {
      stored = JSON.parse(localStorage.getItem(storeKeyFor(runId)) || "null") as StoredProject | null;
    } catch {
      stored = null;
    }
    if (stored && stored.runId === runId && stored.dir) {
      const dir = stored.dir;
      setProjectDir(dir);
      setProjectName(stored.name || defaultName || projectStamp());
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
    setProjectName(defaultName || projectStamp());
  }, [result?.runId, defaultName, loadPrompts, refreshImages, hasFinalVideo]);

  useEffect(() => {
    if (!result?.runId || !projectDir) return;
    const stored: StoredProject = { runId: result.runId, dir: projectDir, name: projectName };
    try {
      localStorage.setItem(storeKeyFor(result.runId), JSON.stringify(stored));
    } catch {
      /* 存不下不影响本次出片 */
    }
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
      // 只收当前这条启动的构建：切到别的条目后，旧构建的日志和完成不再改写这个界面
      if (!jobRef.current || (event.jobId && event.jobId !== jobRef.current)) return;
      if (event.kind === "data") {
        setLogs((previous) => (previous + (event.text ?? "")).slice(-80000));
        return;
      }
      jobRef.current = "";
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
          onNotice("已出片 · 运行台和出片页都有「查看成片」");
          if (event.projectDir) onProducedRef.current(buildRunRef.current, event.projectDir);
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
    setPhase(action);
    setLogs("");
    setError(null);
    setStatus(action === "prepare" ? "准备中…" : "渲染中…");
    const jobId = `produce-${crypto.randomUUID()}`;
    jobRef.current = jobId;
    buildRunRef.current = runIdRef.current;
    try {
      /* 默认名就是时间戳；这一分钟里已经有同名目录就加（1）（2），不覆盖别人的成品 */
      const requested = nameRef.current.trim() || projectStamp();
      let projectName = requested;
      // 没准备过项目时，出片也从零建一个（自动避开同名目录），不必先点「准备项目」。
      if (!dirRef.current) {
        const projects = await api.projects().catch(() => []);
        projectName = uniqueProjectName(requested, projects.map((project) => project.name));
        if (projectName !== requested) {
          setProjectName(projectName);
          onNotice(`已有同名项目，改用 ${projectName}`);
        }
      }
      const info = await api.build({
        jobId,
        action,
        projectName,
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
      jobRef.current = "";
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
    promptsDone ? `${prompts.length} 张 · 媒体/出图` : "准备后才有",
    noImages ? "这次没有图片计划" : `${ids.length - cov.missing.length} / ${ids.length} 张已就位`,
    rendered ? "已完成" : "配音 + 字幕 + mp4",
  ];
  const promptBodies = prompts.map((prompt) => splitPrompt(prompt.text));
  const allZhPrompts = promptBodies.map((body) => body.zh).join("\n\n");

  /** 复制完 / 打开完都接着放图：两步本来就是一口气的事，不用再找一次。 */
  const goPlaceImages = (message: string) => {
    setOpenStep(4);
    onNotice(message);
  };

  return (
    <section className="produce card">
      <div className="produce-head">
        <span className="produce-title">出片</span>
        {batch && (
          <span className="pill run produce-batch">
            批量 · 第 {batch.index + 1}/{batch.total} 条
          </span>
        )}
        <span className="produce-sub">
          {batch
            ? batch.topic.split(/\r?\n/).map((line) => line.trim()).find(Boolean) || "当前这条"
            : "跑完工作流后按 1 → 5 走，按钮都在对应步骤里"}
        </span>
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
              <span className="hint-text">还没有运行结果。运行会真实调用模型（先在顶栏「设置」里配 Key）。</span>
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
            <button className="btn sm ghost" onClick={() => setProjectName(projectStamp())} disabled={phase !== null}>用时间戳</button>
            <span className="spacer" />
            <button className="btn primary" onClick={() => void start("prepare")} disabled={!runDone || phase !== null}>
              {phase === "prepare" ? "准备中…" : "准备项目"}
            </button>
          </div>
          <div className="hint-text">
            只在本地建 <code>成品/{projectName || "项目名"}/</code>，写入图片计划、<code>媒体/出图/*.txt</code> 和出图清单；不出图、不配音、不渲染。
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
          {phase === "prepare" && <LogBox text={logs} placeholder="准备中…" />}
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
          actions={
            prompts.length > 0 ? (
              <>
                <CopyButton
                  text={allZhPrompts}
                  label="复制所有提示词"
                  onCopied={() => goPlaceImages(`已复制 ${prompts.length} 张提示词，接着把图放进「放图」`)}
                />
                <button
                  className="btn sm ghost"
                  onClick={() => {
                    void api.open(`${projectDir}/媒体/出图`);
                    goPlaceImages("已在 Finder 打开 媒体/出图，放完图回到「放图」");
                  }}
                >
                  打开文件夹
                </button>
              </>
            ) : undefined
          }
        >
          {!prepared ? (
            <div className="hint-text">先完成第 2 步「准备项目」，提示词才会写到项目里。</div>
          ) : prompts.length === 0 ? (
            <div className="hint-text">项目里还没有 <code>媒体/出图/*.txt</code>；重新准备一次项目看看日志。</div>
          ) : (
            <div className="step-row">
              <span className="hint-text">
                共 {prompts.length} 张（{prompts.map((prompt) => prompt.scene).join("、")}），已写入 <code>媒体/出图</code>。
                界面不再逐张摊开提示词：要逐个核对就点上面「打开文件夹」。
              </span>
            </div>
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
            <div className="hint-text">先完成第 2 步「准备项目」，或直接跳到第 5 步出片（会自动建项目）。</div>
          ) : (
            <>
              {imageKey && (
                <div className="hint-text">已配生图 Key：出片时会按图像计划自动出图，这一步只用于手动替换或补图。</div>
              )}
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
          title={imageKey ? "生图并出片" : "渲染成片"}
          summary={stepSummary[4] ?? ""}
          done={rendered}
          open={openStep === 5}
          onToggle={() => setOpenStep(openStep === 5 ? 0 : 5)}
        >
          {!runDone ? (
            <div className="hint-text">先完成第 1 步「运行结果」。</div>
          ) : (
            <>
              <div className="step-row">
                <span className="hint-text">配音：{mimo ? mimo.hint : "检查中…"}</span>
                <span className="hint-text">
                  {imageKey ? "生图：已配 Key，缺的图自动出" : "生图：未配 Key，图要手动放（设置里可配）"}
                </span>
                <label className="check">
                  <input type="checkbox" checked={allowMissing} onChange={(event) => setAllowMissing(event.target.checked)} />
                  缺图也继续（只用于排查版面）
                </label>
                <span className="spacer" />
                {rendered ? (
                  <>
                    <button className="btn primary" onClick={() => void openVideo()}>查看成片</button>
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
                    disabled={!runDone || phase !== null || (!imagesDone && !allowMissing && !imageKey)}
                  >
                    {phase === "render" ? (imageKey ? "生图并出片中…" : "渲染中…") : (imageKey ? "生图并出片" : "渲染成片")}
                  </button>
                )}
              </div>
              {!imagesDone && !allowMissing && !imageKey && ids.length > 0 && (
                <div className="warn-box">还缺 {cov.missing.length} 张：{cov.missing.join("、")}。补齐再渲染，或勾「缺图也继续」。</div>
              )}
              <div className="step-row">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={autoProduce}
                    onChange={(event) => {
                      const value = event.target.checked;
                      setAutoProduce(value);
                      try {
                        localStorage.setItem("studio.autoProduce", value ? "1" : "0");
                      } catch {
                        /* 忽略 */
                      }
                      window.dispatchEvent(new Event("wf:auto-produce-changed"));
                    }}
                  />
                  跑完自动出片
                </label>
                <span className="hint-text">
                  {!imageKey
                    ? "配了生图 Key 才生效：运行成功后自动建项目、出图、配音、出 mp4"
                    : autoProduce
                      ? "运行成功后不用再点，直接建项目、出图、出片"
                      : "运行成功后停在这里，需要你点上面的按钮"}
                </span>
              </div>
              {imageKey && !prepared && (
                <div className="hint-text">会从零建项目：写入图片计划 → 按计划出图 → 配音 → 字幕 → MP4，中间不用再点。</div>
              )}
              {status && <div className="hint-text">{status}</div>}
              {error && <div className="err-text">{error}</div>}
              {(logs || phase === "render") && <LogBox text={logs} placeholder="出片中…" />}
            </>
          )}
        </Step>
      </ol>
    </section>
  );
}
