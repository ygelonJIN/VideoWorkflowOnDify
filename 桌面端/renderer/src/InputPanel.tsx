import { Select } from "./Select.js";
import type { RunInputs, StartVariable } from "./types.js";

interface Props {
  inputs: RunInputs;
  variables: StartVariable[];
  running: boolean;
  stub: boolean;
  until: string;
  onChange: (patch: Record<string, string>) => void;
  onStubChange: (value: boolean) => void;
  onUntilChange: (value: string) => void;
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

export function InputPanel({ inputs, variables, running, stub, until, onChange, onStubChange, onUntilChange, onRun, onClose }: Props) {
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
      <div className="field-row">
        <label className="field">
          <span>运行方式</span>
          <Select
            value={stub ? "stub" : "live"}
            options={[
              { value: "stub", label: "stub（不调用模型）" },
              { value: "live", label: "真实调用" },
            ]}
            onChange={(value) => onStubChange(value === "stub")}
          />
        </label>
        <label className="field">
          <span>跑到哪</span>
          <Select
            value={until}
            options={[
              { value: "a03", label: "停在 a03" },
              { value: "", label: "跑全程" },
            ]}
            onChange={onUntilChange}
          />
        </label>
      </div>
      <button className="btn primary wide" onClick={onRun} disabled={running}>用这些输入运行</button>
      <div className="hint-text">
        留空表示沿用 fixtures/input.json 的示例。stub 只有 a01 的固定输出：想跑全程请选「真实调用」，
        否则把「跑到哪」停在 a03。
      </div>
    </div>
  );
}
