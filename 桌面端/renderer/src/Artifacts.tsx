import { useEffect, useState } from "react";
import { bridge } from "./bridge.js";
import type { FileEntry, Project, RunResult } from "./types.js";

const api = bridge();
const TEXT_EXT = [".txt", ".md", ".srt", ".json", ".css", ".js", ".mjs", ".py", ".yml", ".yaml"];
const MEDIA_EXT: Record<string, "html" | "video" | "image"> = {
  ".html": "html",
  ".mp4": "video",
  ".webm": "video",
  ".mp3": "video",
  ".png": "image",
  ".jpg": "image",
  ".jpeg": "image",
  ".webp": "image",
};

function ext(name: string): string {
  const index = name.lastIndexOf(".");
  return index >= 0 ? name.slice(index).toLowerCase() : "";
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
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [preview, setPreview] = useState<{ path: string; text: string; truncated: boolean } | null>(null);
  const [media, setMedia] = useState<{ url: string; kind: "html" | "video" | "image"; path: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects()
      .then((list) => {
        setProjects(list);
        if (list.length > 0) void openProject(list[0] as Project);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  async function openProject(project: Project) {
    setCurrent(project);
    setPreview(null);
    setMedia(null);
    setError(null);
    try {
      setFiles(await api.files(project.path));
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

  async function openEntry(entry: FileEntry) {
    if (entry.type === "dir") {
      try {
        setFiles(await api.files(entry.path));
      } catch (cause) {
        setError((cause as Error).message);
      }
      return;
    }
    const kind = MEDIA_EXT[ext(entry.name)];
    try {
      if (kind) {
        const url = await api.fileUrl(entry.path);
        setMedia({ url, kind, path: entry.path });
        setPreview(null);
        setError(null);
        return;
      }
      if (TEXT_EXT.includes(ext(entry.name))) {
        const data = await api.readText(entry.path);
        setPreview(data);
        setMedia(null);
        setError(null);
        return;
      }
      await api.open(entry.path);
    } catch (cause) {
      setError((cause as Error).message);
    }
  }

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
        <div className="col-title">{current?.name ?? "文件"}</div>
        {files.map((entry) => (
          <button key={entry.path} className="file-row" onClick={() => void openEntry(entry)}>
            <span className={entry.type === "dir" ? "dir" : "file"}>{entry.name}</span>
            <span className="dim">{sizeOf(entry.size)}</span>
          </button>
        ))}
        {files.length === 0 && <div className="hint-text" style={{ padding: 12 }}>没有文件</div>}
      </div>
      <div className="col">
        <div className="col-title">
          {media ? media.path.split("/").slice(-2).join("/") : "预览"}
          <span className="col-action">
            {media && <button className="btn" onClick={() => void api.open(media.path)}>用系统应用打开</button>}
            {preview && <button className="btn" onClick={() => setPreview(null)}>关闭</button>}
          </span>
        </div>
        {error && <div className="err-text">{error}</div>}
        {media ? (
          media.kind === "html" ? (
            <iframe className="media-frame" src={media.url} sandbox="allow-scripts allow-same-origin allow-forms" title="HTML 预览" />
          ) : media.kind === "video" ? (
            <video className="media-video" src={media.url} controls />
          ) : (
            <img className="media-image" src={media.url} alt="" />
          )
        ) : preview ? (
          <pre className="preview-text">{preview.text}{preview.truncated ? "\n…（已截断）" : ""}</pre>
        ) : result ? (
          <pre className="preview-text">{JSON.stringify(result.outputs, null, 2)}</pre>
        ) : (
          <div className="hint-text" style={{ padding: 12 }}>
            点左侧文件预览：文本就地看，HTML / 视频 / 图片内嵌显示，也可以交给系统应用。
          </div>
        )}
      </div>
    </div>
  );
}
