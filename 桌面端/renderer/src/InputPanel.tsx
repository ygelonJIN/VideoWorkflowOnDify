import { Select } from "./Select.js";
import type { RunInputs, StartVariable } from "./types.js";

interface Props {
  inputs: RunInputs;
  variables: StartVariable[];
  running: boolean;
  hasKey: boolean;
  onChange: (patch: Record<string, string>) => void;
  onRun: () => void;
  onClose: () => void;
}

function InputField({
  variable,
  value,
  onChange,
}: {
  variable: StartVariable;
  value: string;
  onChange: (value: string) => void;
}) {
  const label = `${variable.label || variable.variable}${variable.required ? "（必填）" : ""}`;
  if (variable.type === "paragraph") {
    return (
      <label className="field">
        <span>{label}</span>
        <textarea
          rows={variable.variable === "campaign_brief" ? 8 : 3}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={variable.variable === "campaign_brief" ? "粘聊天记录、文章、清单或一句话都行" : ""}
        />
      </label>
    );
  }
  if (variable.type === "select") {
    const values = variable.options.includes(value) || value === "" ? variable.options : [value, ...variable.options];
    return (
      <label className="field">
        <span>{label}</span>
        <Select
          value={value}
          options={values.map((option) => ({ value: option, label: option }))}
          onChange={onChange}
        />
      </label>
    );
  }
  return (
    <label className="field">
      <span>{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        {...(variable.maxLength ? { maxLength: variable.maxLength } : {})}
      />
    </label>
  );
}

export function InputPanel({ inputs, variables, running, hasKey, onChange, onRun, onClose }: Props) {
  const longFields = variables.filter((variable) => variable.type === "paragraph");
  const shortFields = variables.filter((variable) => variable.type !== "paragraph");
  return (
    <div className="drawer card">
      <div className="drawer-head">
        <strong>运行输入</strong>
        <span className="spacer" />
        <button className="btn sm" onClick={onClose}>关闭</button>
      </div>
      {variables.length === 0 && <div className="hint-text">这个工作流的 start 节点没有声明输入。</div>}
      {longFields.map((variable) => (
        <InputField
          key={variable.variable}
          variable={variable}
          value={inputs[variable.variable] ?? ""}
          onChange={(value) => onChange({ [variable.variable]: value })}
        />
      ))}
      {shortFields.length > 0 && (
        <div className="field-grid">
          {shortFields.map((variable) => (
            <InputField
              key={variable.variable}
              variable={variable}
              value={inputs[variable.variable] ?? ""}
              onChange={(value) => onChange({ [variable.variable]: value })}
            />
          ))}
        </div>
      )}
      {!hasKey && (
        <div className="warn-box">还没有 API Key，运行会直接失败；先在左栏「设置」里填 Key。</div>
      )}
      {hasKey && (
        <div className="hint-text">每次运行都会跑完整条链路（16 个 LLM 节点 + 逐屏生成），耗时和费用请留意。</div>
      )}
      <button className="btn primary wide" onClick={onRun} disabled={running || !hasKey}>用这些输入运行</button>
      <div className="hint-text">留空表示沿用 fixtures/input.json 的示例；运行一律调用真实模型。</div>
    </div>
  );
}
