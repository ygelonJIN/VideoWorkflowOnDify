import { Select } from "./Select.js";
import type { RunInputs, StartVariable } from "./types.js";

interface Props {
  inputs: RunInputs;
  variables: StartVariable[];
  running: boolean;
  hasKey: boolean;
  reviewGate: boolean;
  canReview: boolean;
  onReviewGateChange: (value: boolean) => void;
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

export function InputPanel({ inputs, variables, running, hasKey, reviewGate, canReview, onReviewGateChange, onChange, onRun, onClose }: Props) {
  const longFields = variables.filter((variable) => variable.type === "paragraph");
  const shortFields = variables.filter((variable) => variable.type !== "paragraph");
  const missing = variables.filter((variable) => variable.required && !(inputs[variable.variable] ?? "").trim());
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
        <div className="hint-text">每次运行都会跑完整链路；开着「口播后暂停」会先停在 A07，审完口播再跑分镜和画面。</div>
      )}
      {missing.length > 0 && (
        <div className="warn-box">还有必填项没填：{missing.map((variable) => variable.label || variable.variable).join("、")}</div>
      )}
      {canReview && (
        <label className="check" style={{ marginTop: 12 }}>
          <input type="checkbox" checked={reviewGate} onChange={(event) => onReviewGateChange(event.target.checked)} />
          口播生成后暂停审阅（推荐）
        </label>
      )}
      {canReview && (
        <div className="hint-text">
          {reviewGate
            ? "跑到 A07 停住：先看口播，再决定重跑文案或继续跑分镜/画面。省掉审阅前的 3 次分镜/动效/合规调用。"
            : "关掉就一路跑到成片；文案不对只能整条重跑。"}
        </div>
      )}
      <button className="btn primary wide" onClick={onRun} disabled={running || !hasKey || missing.length > 0}>用这些输入运行</button>
    </div>
  );
}
