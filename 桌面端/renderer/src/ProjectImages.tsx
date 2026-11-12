import { useEffect, useRef, useState } from "react";
import { Select } from "./Select.js";
import { bridge } from "./bridge.js";
import type { InboxFile, Project } from "./types.js";

const api = bridge();

function readBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? "").split(",")[1] ?? "");
    reader.onerror = () => reject(reader.error ?? new Error("读取图片失败"));
    reader.readAsDataURL(file);
  });
}

/** 控制台里的「图片」：对应项目的 媒体/图片/，拖图直接落进去。 */
export function ProjectImages() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectPath, setProjectPath] = useState("");
  const [files, setFiles] = useState<InboxFile[]>([]);
  const [urls, setUrls] = useState<Record<string, string>>({});
  const [dir, setDir] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drag, setDrag] = useState(false);
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.projects()
      .then((list) => {
        setProjects(list);
        if (list[0]) setProjectPath(list[0].path);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  async function refresh(path = projectPath) {
    if (!path) return;
    const data = await api.projectImages({ projectPath: path });
    setFiles(data.files);
    setDir(data.dir);
    const entries = await Promise.all(data.files.map(async (file) => [file.path, await api.fileUrl(file.path)] as const));
    setUrls(Object.fromEntries(entries));
  }

  useEffect(() => {
    if (!projectPath) return;
    refresh().catch((cause: Error) => setError(cause.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectPath]);

  async function accept(list: FileList | File[]) {
    if (!projectPath) {
      setError("先在上面选一个项目");
      return;
    }
    const images = Array.from(list).filter((file) => file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif|bmp)$/i.test(file.name));
    if (images.length === 0) {
      setError("只接受图片文件（png / jpg / webp / gif）");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      for (const file of images) {
        await api.projectImageSave({ projectPath, name: file.name, base64: await readBase64(file) });
      }
      await refresh();
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className={`inbox ${drag ? "drag" : ""}`}
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
    >
      <div className="inbox-head">
        <span className="inbox-title">项目图片</span>
        <Select
          value={projectPath}
          width={240}
          options={projects.map((project) => ({ value: project.path, label: project.name }))}
          onChange={setProjectPath}
          placeholder="选择项目"
        />
        <span className="hint-text">把图片拖到这里，或</span>
        <button className="btn sm" onClick={() => picker.current?.click()} disabled={busy || !projectPath}>选择图片</button>
        <span className="spacer" />
        {busy && <span className="hint-text">写入中…</span>}
        <button className="btn sm ghost" onClick={() => void refresh()} disabled={!projectPath}>刷新</button>
        <button className="btn sm ghost" onClick={() => void api.open(dir)} disabled={!dir}>打开文件夹</button>
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
      </div>
      {error && <div className="err-text">{error}</div>}
      <div
        className={`dropzone ${drag ? "drag" : ""}`}
        onClick={() => picker.current?.click()}
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
      >
        <div className="dropzone-title">把图片拖到这里</div>
        <div className="dropzone-sub">会存到 {dir || "所选项目的 媒体/图片/"}，不会新建工作流节点</div>
        <button
          className="btn"
          onClick={(event) => {
            event.stopPropagation();
            picker.current?.click();
          }}
          disabled={busy || !projectPath}
        >
          或点这里选择图片
        </button>
      </div>
      <div className="inbox-grid">
        {files.map((file) => (
          <button className="inbox-card" key={file.path} title={file.path} onClick={() => void api.open(file.path)}>
            {urls[file.path] ? <img src={urls[file.path]} alt="" /> : <div className="inbox-ph" />}
            <span>{file.name}</span>
          </button>
        ))}
        {files.length === 0 && (
          <div className="hint-text" style={{ padding: "var(--sp-4)" }}>
            还没有图片。拖进来的文件会存到 {dir || "所选项目的 媒体/图片/"}，不会新建工作流节点。
          </div>
        )}
      </div>
    </div>
  );
}
