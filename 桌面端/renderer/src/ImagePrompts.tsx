import { useEffect, useState } from "react";
import type { ImagePlan } from "../../src/engine/imagePlan.js";
import { CopyButton } from "./CopyButton.js";
import { Select } from "./Select.js";
import { bridge } from "./bridge.js";
import type { FileEntry, Project } from "./types.js";

const api = bridge();

interface PromptFile {
  name: string;
  scene: string;
  text: string;
  url?: string;
}

/** 图像提示词：优先读项目里的 媒体/出图/*.txt（人工出图用的那份），没有才退回运行结果。 */
export function ImagePrompts({ plan }: { plan: ImagePlan | null }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectPath, setProjectPath] = useState("");
  const [prompts, setPrompts] = useState<PromptFile[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.projects()
      .then((list) => {
        setProjects(list);
        if (list[0]) setProjectPath(list[0].path);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  useEffect(() => {
    if (!projectPath) return;
    let alive = true;
    setLoading(true);
    setError(null);
    (async () => {
      const outDir = `${projectPath}/媒体/出图`;
      let entries: FileEntry[] = [];
      try {
        entries = await api.files(outDir);
      } catch {
        entries = [];
      }
      const texts = entries.filter((entry) => entry.type === "file" && /\.txt$/i.test(entry.name) && !/^readme/i.test(entry.name));
      let thumbs: FileEntry[] = [];
      try {
        thumbs = await api.files(`${projectPath}/媒体/图片/_resolved`);
      } catch {
        thumbs = [];
      }
      const thumbMap: Record<string, string> = {};
      for (const thumb of thumbs) {
        if (thumb.type !== "file" || !/\.(png|jpe?g|webp)$/i.test(thumb.name)) continue;
        thumbMap[thumb.name.replace(/\.[^.]+$/, "")] = thumb.path;
      }

      const loaded: PromptFile[] = [];
      for (const file of texts) {
        const data = await api.readText(file.path);
        const scene = file.name.replace(/\.txt$/i, "");
        if (scene === "全部提示词") continue;
        const thumbPath = thumbMap[scene];
        const url = thumbPath ? await api.fileUrl(thumbPath) : undefined;
        loaded.push({ name: file.name, scene, text: data.text.trim(), ...(url ? { url } : {}) });
      }
      if (!alive) return;
      loaded.sort((left, right) => left.scene.localeCompare(right.scene));
      setPrompts(loaded);
      setLoading(false);
    })().catch((cause: Error) => {
      if (alive) {
        setError(cause.message);
        setLoading(false);
      }
    });
    return () => {
      alive = false;
    };
  }, [projectPath]);

  return (
    <div className="image-prompts">
      <div className="inbox-head">
        <span className="inbox-title">图像提示词</span>
        <Select
          value={projectPath}
          width={240}
          options={projects.map((project) => ({ value: project.path, label: project.name }))}
          onChange={setProjectPath}
          placeholder="选择项目"
        />
        <span className="hint-text">来自 媒体/出图/</span>
        <span className="spacer" />
        {loading && <span className="hint-text">读取中…</span>}
      </div>
      {error && <div className="err-text">{error}</div>}

      {prompts.length > 0 ? (
        <div className="ip-grid">
          {prompts.map((prompt) => (
            <section className="ip-card" key={prompt.name}>
              <div className="ip-head">
                <span>{prompt.scene}</span>
                <CopyButton text={prompt.text} label="复制" />
              </div>
              {prompt.url && <img className="ip-thumb" src={prompt.url} alt="" />}
              <pre className="ip-text">{prompt.text}</pre>
            </section>
          ))}
        </div>
      ) : plan ? (
        <div className="ip-grid">
          {plan.prefix && (
            <section className="ip-card">
              <div className="ip-head"><span>prompt_prefix</span></div>
              <pre className="ip-text">{plan.prefix}</pre>
            </section>
          )}
          {plan.images.map((image, index) => (
            <section className="ip-card" key={image.id ?? `${index}`}>
              <div className="ip-head">
                <span>{image.id ?? image.scene_id ?? `#${index + 1}`}{image.role ? ` · ${image.role}` : ""}</span>
                {(image.prompt_zh || image.prompt) && (
                  <CopyButton text={String(image.prompt_zh || image.prompt)} label="复制" />
                )}
              </div>
              {image.prompt && <pre className="ip-text">{image.prompt}</pre>}
              {image.prompt_zh && <pre className="ip-text zh">{image.prompt_zh}</pre>}
            </section>
          ))}
        </div>
      ) : (
        <div className="hint-text" style={{ padding: "var(--sp-4)" }}>
          这个项目还没有 媒体/出图/*.txt；跑完整条链路（到 H01PV 或全程）后会改用运行结果里的图像计划。
        </div>
      )}
    </div>
  );
}
