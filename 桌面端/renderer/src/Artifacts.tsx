import { useEffect, useState } from "react";
import { bridge } from "./bridge.js";
import type { FileEntry, Project, RunResult } from "./types.js";

const api = bridge();
const TEXT_EXT = [".txt", ".md", ".srt", ".json", ".css", ".js", ".mjs", ".py", ".yml", ".yaml"];
type MediaKind = "html" | "video" | "audio" | "image";
const MEDIA_EXT: Record<string, MediaKind> = {
  ".html": "html",
  ".htm": "html",
  ".mp4": "video",
  ".webm": "video",
  ".mov": "video",
  ".mp3": "audio",
  ".wav": "audio",
  ".m4a": "audio",
  ".png": "image",
  ".jpg": "image",
  ".jpeg": "image",
  ".webp": "image",
  ".gif": "image",
};

function ext(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
}

function baseName(filePath: string): string {
  return filePath.split("/").slice(-1)[0] ?? filePath;
}

function sizeOf(bytes?: number): string {
  if (!bytes) return "";
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
  if (bytes > 1024) return `${(bytes / 1024).toFixed(0)}KB`;
  return `${bytes}B`;
}

export function Artifacts({ result }: { result: RunResult | null }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [current, setCurrent] = useState<Project | null>(null);
  const [trail, setTrail] = useState<Array<{ name: string; path: string }>>([]);
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [preview, setPreview] = useState<{ path: string; text: string; truncated: boolean } | null>(null);
  const [media, setMedia] = useState<{ url: string; kind: MediaKind; path: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [copiedResult, setCopiedResult] = useState(false);

  useEffect(() => {
    api.projects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0) void openProject(list[0] as Project);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  function resetView() {
    setPreview(null);
    setMedia(null);
    setError(null);
  }

  async function listOf(dirPath: string) {
    setLoading(true);
    try {
      setFiles(await api.files(dirPath));
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function openProject(project: Project) {
    setCurrent(project);
    setTrail([]);
    resetView();
    await listOf(project.path);
  }

  async function openDir(entry: FileEntry) {
    setTrail((previous) => [...previous, { name: entry.name, path: entry.path }]);
    resetView();
    await listOf(entry.path);
  }

  async function goUp() {
    if (!current) return;
    const next = trail.slice(0, -1);
    setTrail(next);
    resetView();
    await listOf(next.length > 0 ? (next[next.length - 1] as { path: string }).path : current.path);
  }

  async function openEntry(entry: FileEntry) {
    if (entry.type === "dir") {
      await openDir(entry);
      return;
    }
    const kind = MEDIA_EXT[ext(entry.name)];
    setError(null);
    try {
      if (kind) {
        const url = await api.fileUrl(entry.path);
        setMedia({ url, kind, path: entry.path });
        setPreview(null);
        return;
      }
      if (TEXT_EXT.includes(ext(entry.name))) {
        const data = await api.readText(entry.path);
        setPreview(data);
        setMedia(null);
        return;
      }
      await api.open(entry.path);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function openInSystem(filePath: string) {
    const outcome = await api.open(filePath);
    if (!outcome.ok) setError(outcome.error ?? "系统应用打不开这个文件");
  }

  const title = media ? baseName(media.path) : preview ? baseName(preview.path) : "预览";

  return (
    <div className="browser card">
      <div className="col">
        <div className="col-title">项目</div>
        {projects.map((project) => (
          <button
            key={project.path}
            className={`file-row ${current?.path === project.path ? "on" : ""}`}
            onClick={() => void openProject(project)}
          >
            {project.name}
          </button>
        ))}
      </div>

      <div className="col">
        <div className="col-title">
          {trail.length > 0 && (
            <button className="btn sm ghost" onClick={() => void goUp()} title="返回上一级">← 返回</button>
          )}
          <span className="path-name">{trail.length > 0 ? (trail[trail.length - 1] as { name: string }).name : (current?.name ?? "文件")}</span>
          <span className="col-action">
            <button className="btn sm ghost" onClick={() => void listOf(trail.length > 0 ? (trail[trail.length - 1] as { path: string }).path : current?.path ?? "")} disabled={!current || loading}>
              {loading ? "读取中…" : "刷新"}
            </button>
          </span>
        </div>
        {files.map((entry) => (
          <button key={entry.path} className="file-row" onClick={() => void openEntry(entry)}>
            <span className={entry.type === "dir" ? "dir" : "file"}>{entry.name}</span>
            <span className="dim">{entry.type === "dir" ? "目录" : sizeOf(entry.size)}</span>
          </button>
        ))}
        {files.length === 0 && !loading && <div className="hint-text" style={{ padding: 12 }}>没有文件</div>}
      </div>

      <div className="col preview">
        <div className="col-title">
          <span className="path-name">{title}</span>
          <span className="col-action">
            {!media && !preview && result && (
              <button
                className="btn sm ghost"
                onClick={() => {
                  void api.copyText(JSON.stringify(result.outputs, null, 2)).then(() => {
                    setCopiedResult(true);
                    window.setTimeout(() => setCopiedResult(false), 1200);
                  });
                }}
              >
                {copiedResult ? "已复制" : "复制 JSON"}
              </button>
            )}
            {(media || preview) && (
              <button className="btn sm ghost" onClick={() => resetView()}>返回列表</button>
            )}
            {media && <button className="btn sm" onClick={() => void openInSystem(media.path)}>用系统应用打开</button>}
            {preview && <button className="btn sm" onClick={() => void openInSystem(preview.path)}>用系统应用打开</button>}
          </span>
        </div>
        {error && <div className="err-text">{error}</div>}
        <div className="preview-body">
          {media ? (
            media.kind === "html" ? (
              <iframe key={media.path} className="media-frame" src={media.url} sandbox="allow-scripts allow-same-origin allow-forms" title="HTML 预览" />
            ) : media.kind === "video" ? (
              <video
                key={media.path}
                className="media-video"
                src={media.url}
                controls
                playsInline
                preload="metadata"
                onError={() => setError("这个视频浏览器解不了（编码或封装不支持），用「用系统应用打开」播放。")}
              />
            ) : media.kind === "audio" ? (
              <audio
                key={media.path}
                className="media-audio"
                src={media.url}
                controls
                preload="metadata"
                onError={() => setError("这个音频浏览器解不了，用「用系统应用打开」播放。")}
              />
            ) : (
              <img
                key={media.path}
                className="media-image"
                src={media.url}
                alt=""
                onError={() => setError("这张图片浏览器打不开，用「用系统应用打开」查看。")}
              />
            )
          ) : preview ? (
            <pre className="preview-text">{preview.text}{preview.truncated ? "\n…（已截断）" : ""}</pre>
          ) : result ? (
            <pre className="preview-text">{JSON.stringify(result.outputs, null, 2)}</pre>
          ) : (
            <div className="hint-text" style={{ padding: 12 }}>
              点左侧文件预览：文本就地看，HTML / 视频 / 音频 / 图片内嵌显示，也可以交给系统应用。
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
