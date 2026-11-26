import { useEffect, useState } from "react";
import { bridge } from "./bridge.js";
import { Select } from "./Select.js";
import type { SettingsInfo } from "./types.js";

const api = bridge();

interface Props {
  onClose: () => void;
  onSaved: (info: SettingsInfo) => void;
}

/** 按 Base / 模型名算出实际会走哪个入口，直接显示给人看，省得猜。 */
function imageEndpointLabel(baseUrl: string, model: string): string {
  const base = baseUrl.trim().toLowerCase();
  const name = model.trim().toLowerCase();
  if (base.includes("compatible-mode")) return "百炼 · OpenAI 兼容入口";
  if (base.includes("aliyuncs") || base.includes("dashscope")) return "百炼 · 原生同步入口";
  if (base.includes("volces") || base.includes("ark.cn")) return "火山方舟";
  if (base) return "自定义 OpenAI 兼容入口";
  if (name.includes("qwen") || name.includes("wanx")) return "百炼 · 原生同步入口（按模型名推断）";
  if (name.includes("seedream") || name.includes("doubao")) return "火山方舟（按模型名推断）";
  return "OpenAI";
}

/** Key 字段：已配置时只显示状态和末四位，点「更换」才出输入框。 */
function KeyField({
  label,
  hint,
  configured,
  keyHint,
  value,
  clear,
  onChange,
  onToggleClear,
}: {
  label: string;
  hint?: string;
  configured: boolean;
  keyHint: string;
  value: string;
  clear: boolean;
  onChange: (value: string) => void;
  onToggleClear: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const showInput = !configured || editing;

  return (
    <div className="field">
      <span>{label}</span>
      {showInput ? (
        <>
          <input
            type="password"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            autoComplete="off"
            placeholder={configured ? "粘贴新 Key 会替换旧的" : "粘贴 Key"}
          />
          <div className="key-row">
            {configured && (
              <button
                className="btn sm ghost"
                onClick={() => {
                  setEditing(false);
                  onChange("");
                }}
              >
                取消更换
              </button>
            )}
            {configured && (
              <button className={`btn sm ${clear ? "danger" : "ghost"}`} onClick={onToggleClear} disabled={Boolean(value.trim())}>
                {clear ? "取消清除" : "清除 Key"}
              </button>
            )}
          </div>
        </>
      ) : (
        <div className="key-row">
          <span className="key-status">
            <i className="key-dot ok" />
            已配置 · {keyHint || "末四位未知"}
          </span>
          <span className="spacer" />
          <button className="btn sm ghost" onClick={() => setEditing(true)}>更换</button>
          <button className={`btn sm ${clear ? "danger" : "ghost"}`} onClick={onToggleClear}>
            {clear ? "取消清除" : "清除"}
          </button>
        </div>
      )}
      {clear && <span className="field-hint">保存后会从 .env 里删掉这一行。</span>}
      {hint && <span className="field-hint">{hint}</span>}
    </div>
  );
}

/**
 * 设置：三张卡片——文本模型 / 生图模型 / 全自动。
 * 文本与生图写 桌面端/.env；全自动是界面偏好，两处开关同步。
 */
export function Settings({ onClose, onSaved }: Props) {
  const [info, setInfo] = useState<SettingsInfo | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [protocol, setProtocol] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
  const [imageBaseUrl, setImageBaseUrl] = useState("");
  const [imageModel, setImageModel] = useState("");
  const [imageApiKey, setImageApiKey] = useState("");
  const [clearImageKey, setClearImageKey] = useState(false);
  const [autoProduce, setAutoProduce] = useState(() => localStorage.getItem("studio.autoProduce") !== "0");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api.settings()
      .then((loaded) => {
        setInfo(loaded);
        setBaseUrl(loaded.baseUrl);
        setModel(loaded.model);
        setProtocol(loaded.protocol);
        setImageBaseUrl(loaded.imageBaseUrl);
        setImageModel(loaded.imageModel);
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

  function setAuto(value: boolean) {
    setAutoProduce(value);
    try {
      localStorage.setItem("studio.autoProduce", value ? "1" : "0");
    } catch {
      /* 忽略 */
    }
    // 出片页和批量页都听这个事件，改完立刻生效。
    window.dispatchEvent(new Event("wf:auto-produce-changed"));
  }

  async function save() {
    setSaving(true);
    setError(null);
    setMessage("");
    try {
      const next = await api.saveSettings({
        baseUrl,
        model,
        protocol,
        ...(apiKey.trim() ? { apiKey } : {}),
        ...(clearKey && !apiKey.trim() ? { clearKey: true } : {}),
        imageBaseUrl,
        imageModel,
        ...(imageApiKey.trim() ? { imageApiKey } : {}),
        ...(clearImageKey && !imageApiKey.trim() ? { clearImageKey: true } : {}),
      });
      setInfo(next);
      setApiKey("");
      setClearKey(false);
      setImageApiKey("");
      setClearImageKey(false);
      setMessage("已保存，下一次运行生效");
      onSaved(next);
    } catch (cause) {
      setError((cause as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="drawer settings card">
      <div className="drawer-head">
        <strong>设置</strong>
        <span className="settings-head-sub">Key、生图、全自动</span>
        <span className="spacer" />
        <button className="btn sm" onClick={onClose}>关闭</button>
      </div>

      <div className="settings-body">
        {error && <div className="err-text">{error}</div>}

        <section className="settings-block">
          <div className="settings-block-head">
            <span className="settings-block-title">文本模型</span>
            <span className="settings-block-sub">运行工作流时调用的对话模型</span>
          </div>

          <label className="field">
            <span>Base URL</span>
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://opencode.ai/zen/go/v1" />
          </label>

          <label className="field">
            <span>模型</span>
            <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="gpt-6-luna" />
          </label>

          <KeyField
            label="API Key"
            configured={Boolean(info?.hasKey)}
            keyHint={info?.keyHint ?? ""}
            value={apiKey}
            clear={clearKey}
            onChange={setApiKey}
            onToggleClear={() => setClearKey((value) => !value)}
            hint={
              info?.inProcessEnv
                ? "当前用的是环境变量里的 WF_API_KEY（优先级高于 .env）；要改 .env 就粘贴一个新 Key。"
                : undefined
            }
          />

          <details className="settings-advanced">
            <summary>高级：接口协议</summary>
            <label className="field">
              <span>协议</span>
              <Select
                value={protocol}
                options={[
                  { value: "", label: "自动（按模型判断）" },
                  { value: "chat", label: "chat · /chat/completions" },
                  { value: "responses", label: "responses · /responses" },
                  { value: "anthropic", label: "anthropic · /messages" },
                ]}
                onChange={setProtocol}
              />
            </label>
          </details>
        </section>

        <section className="settings-block">
          <div className="settings-block-head">
            <span className="settings-block-title">生图模型</span>
            <span className="settings-block-sub">出片时自动出图，不用手动去即梦</span>
          </div>

          <div className="settings-note">
            当前引擎：<strong>{imageEndpointLabel(imageBaseUrl, imageModel)}</strong>
          </div>

          <label className="field">
            <span>Base URL</span>
            <input
              value={imageBaseUrl}
              onChange={(event) => setImageBaseUrl(event.target.value)}
              placeholder="留空自动：按模型名判断百炼 / 火山 / OpenAI"
            />
          </label>

          <label className="field">
            <span>模型</span>
            <input value={imageModel} onChange={(event) => setImageModel(event.target.value)} placeholder="qwen-image-3.0" />
          </label>

          <KeyField
            label="生图 API Key"
            configured={Boolean(info?.hasImageKey)}
            keyHint={info?.imageKeyHint ?? ""}
            value={imageApiKey}
            clear={clearImageKey}
            onChange={setImageApiKey}
            onToggleClear={() => setClearImageKey((value) => !value)}
            hint={
              !info?.hasImageKey
                ? "没配 Key 时出片走手动：准备项目 → 复制提示词 → 放图 → 渲染。"
                : "字段名 IMAGE_API_KEY / IMAGE_MODEL / IMAGE_API_BASE，也读 DASHSCOPE_API_KEY 和 ~/.zshrc。"
            }
          />
        </section>

        <section className="settings-block">
          <div className="settings-block-head">
            <span className="settings-block-title">全自动</span>
            <span className="settings-block-sub">运行完直接出片，不用再点</span>
          </div>

          <label className="check">
            <input type="checkbox" checked={autoProduce} onChange={(event) => setAuto(event.target.checked)} />
            跑完自动出片
          </label>
          <div className="settings-note">
            {autoProduce
              ? "单条运行成功直接出 mp4；批量跑完自动逐条串行出（一次只烧一条）。"
              : "运行完停在出片页，等你点按钮。批量也不会自动出。"}
          </div>
          <div className="settings-note settings-note-dim">
            开关存在本机界面，不进 .env；出片页第 5 步也有同一个开关，两处同步。
          </div>
        </section>

        {message && <div className="ok-text">{message}</div>}
      </div>

      <div className="settings-foot">
        <span className="settings-foot-note">
          保存在 {info?.path ?? "桌面端/.env"}（已 git 忽略），环境变量优先
        </span>
        <span className="spacer" />
        <button className="btn sm" onClick={onClose}>取消</button>
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? "保存中…" : "保存"}
        </button>
      </div>
    </div>
  );
}
