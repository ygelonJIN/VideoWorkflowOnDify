import { useEffect, useState } from "react";
import { bridge } from "./bridge.js";
import { Select } from "./Select.js";
import type { SettingsInfo } from "./types.js";

const api = bridge();

interface Props {
  onClose: () => void;
  onSaved: (info: SettingsInfo) => void;
}

/** 模型出口设置：写 桌面端/.env，Key 只写不读（界面只显示是否已配置和末四位）。 */
export function Settings({ onClose, onSaved }: Props) {
  const [info, setInfo] = useState<SettingsInfo | null>(null);
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [protocol, setProtocol] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [clearKey, setClearKey] = useState(false);
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
      })
      .catch((cause: Error) => setError(cause.message));
  }, []);

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
        ...(clearKey ? { clearKey: true } : {}),
      });
      setInfo(next);
      setApiKey("");
      setClearKey(false);
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
        <span className="spacer" />
        <button className="btn sm" onClick={onClose}>关闭</button>
      </div>

      {error && <div className="err-text">{error}</div>}

      <label className="field">
        <span>API Base URL</span>
        <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="https://opencode.ai/zen/go/v1" />
      </label>

      <label className="field">
        <span>模型</span>
        <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="gpt-6-luna" />
      </label>

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

      <label className="field">
        <span>API Key</span>
        <input
          type="password"
          value={apiKey}
          onChange={(event) => setApiKey(event.target.value)}
          autoComplete="off"
          placeholder={info?.hasKey ? `已配置（${info.keyHint}），留空保持不变` : "未配置"}
        />
      </label>

      <div className="settings-actions">
        <button
          className={`btn sm ${clearKey ? "danger" : ""}`}
          onClick={() => setClearKey((value) => !value)}
          disabled={!info?.hasKey && !clearKey}
        >
          {clearKey ? "取消清除" : "清除 Key"}
        </button>
        <span className="spacer" />
        <button className="btn primary" onClick={() => void save()} disabled={saving}>
          {saving ? "保存中…" : "保存"}
        </button>
      </div>

      {message && <div className="ok-text">{message}</div>}
      {clearKey && <div className="err-text">保存后会删除 .env 里的 WF_API_KEY。</div>}
      <div className="hint-text">
        保存在 {info?.path ?? "桌面端/.env"}（已被 git 忽略）。环境变量里的同名值优先；保存后下一次运行生效。
      </div>
    </div>
  );
}
