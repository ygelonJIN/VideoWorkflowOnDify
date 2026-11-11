import type { RunInputs } from "./types.js";

interface Props {
  inputs: RunInputs;
  running: boolean;
  onChange: (patch: Partial<RunInputs>) => void;
  onRun: () => void;
  onClose: () => void;
}

export function InputPanel({ inputs, running, onChange, onRun, onClose }: Props) {
  return (
    <div className="drawer">
      <div className="drawer-head">
        <strong>运行输入</strong>
        <span className="spacer" />
        <button className="btn" onClick={onClose}>关闭</button>
      </div>
      <label className="field">
        <span>主题、原始文本或随口一句话（必填）</span>
        <textarea
          rows={9}
          value={inputs.campaign_brief}
          onChange={(event) => onChange({ campaign_brief: event.target.value })}
          placeholder="粘聊天记录、文章、清单或一句话都行"
        />
      </label>
      <label className="field">
        <span>生产要求</span>
        <input value={inputs.production_requirements} onChange={(event) => onChange({ production_requirements: event.target.value })} />
      </label>
      <div className="field-row">
        <label className="field">
          <span>请求编号</span>
          <input value={inputs.request_id} onChange={(event) => onChange({ request_id: event.target.value })} />
        </label>
        <label className="field">
          <span>TTS 供应商</span>
          <select value={inputs.tts_provider} onChange={(event) => onChange({ tts_provider: event.target.value })}>
            <option value="mimo">mimo</option>
            <option value="macos">macos</option>
            <option value="openai-compatible">openai-compatible</option>
          </select>
        </label>
        <label className="field">
          <span>TTS 声音</span>
          <select value={inputs.tts_voice} onChange={(event) => onChange({ tts_voice: event.target.value })}>
            {["mimo_default", "冰糖", "茉莉", "苏打", "白桦", "Mia", "Chloe", "Milo", "Dean"].map((voice) => (
              <option key={voice} value={voice}>{voice}</option>
            ))}
          </select>
        </label>
      </div>
      <button className="btn primary wide" onClick={onRun} disabled={running}>用这些输入运行</button>
      <div className="hint-text">留空表示沿用 fixtures/input.json 的示例。stub 模式下不调用模型。</div>
    </div>
  );
}
