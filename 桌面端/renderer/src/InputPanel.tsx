import { useEffect, useMemo, useState } from "react";
import { Select } from "./Select.js";
import { cleanRequirements, primaryVariable } from "../../src/batch/model.js";
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
  onRunBatch: (topics: string[], cap: number) => void;
  runCap: number;
  onRunCapChange: (value: number) => void;
  onClose: () => void;
}

type Mode = "single" | "batch";

const MODE_KEY = "studio.runMode";
const ITEMS_KEY = "studio.batchItems";

function readMode(): Mode {
  return localStorage.getItem(MODE_KEY) === "batch" ? "batch" : "single";
}

function readItems(): string[] {
  try {
    const saved = JSON.parse(localStorage.getItem(ITEMS_KEY) ?? "null");
    if (Array.isArray(saved) && saved.length > 0) return saved.map((item) => String(item ?? ""));
  } catch {
    /* 存坏了就当没有 */
  }
  return ["", "", "", ""];
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

/**
 * 运行输入抽屉。批量不是另一个页面：只是把主需求字段换成逐条列表，其余输入仍然全批共用。
 * 批量列表只负责「填什么」，跑起来之后由画布上方的切换条逐条查看。
 */
export function InputPanel({
  inputs,
  variables,
  running,
  hasKey,
  reviewGate,
  canReview,
  onReviewGateChange,
  onChange,
  onRun,
  onRunBatch,
  runCap,
  onRunCapChange,
  onClose,
}: Props) {
  const [mode, setMode] = useState<Mode>(readMode);
  const [items, setItems] = useState<string[]>(readItems);

  const primary = useMemo(() => primaryVariable(variables), [variables]);
  const primaryField = variables.find((variable) => variable.variable === primary) ?? null;
  const primaryLabel = primaryField?.label || primary || "主需求";
  // 没有可替换的主需求字段就不存在批量模式：切工作流后自动退回单条
  const activeMode: Mode = mode === "batch" && primary ? "batch" : "single";

  const longFields = variables.filter((variable) => variable.type === "paragraph" && variable.variable !== primary);
  const shortFields = variables.filter((variable) => variable.type !== "paragraph");
  const batchShortFields = shortFields.filter((variable) => variable.variable !== primary);
  const shared = variables.filter((variable) => variable.variable !== primary);

  const singleMissing = variables.filter((variable) => variable.required && !(inputs[variable.variable] ?? "").trim());
  const sharedMissing = shared.filter((variable) => variable.required && !(inputs[variable.variable] ?? "").trim());
  const filled = cleanRequirements(items);
  const canBatch = Boolean(primary) && filled.length > 0 && sharedMissing.length === 0 && hasKey && !running;

  useEffect(() => {
    localStorage.setItem(MODE_KEY, activeMode);
  }, [activeMode]);

  useEffect(() => {
    localStorage.setItem(ITEMS_KEY, JSON.stringify(items));
  }, [items]);

  function addItem() {
    setItems((previous) => [...previous, ""]);
  }

  function removeItem(index: number) {
    setItems((previous) => (previous.length <= 1 ? previous : previous.filter((_, position) => position !== index)));
  }

  function updateItem(index: number, value: string) {
    setItems((previous) => previous.map((item, position) => (position === index ? value : item)));
  }

  return (
    <div className="drawer run-drawer">
      <div className="drawer-head">
        <strong>运行输入</strong>
        <span className="spacer" />
        <button className="btn sm" onClick={onClose}>关闭</button>
      </div>

      <div className="seg run-mode" role="tablist" aria-label="运行模式">
        <button
          role="tab"
          aria-selected={activeMode === "single"}
          className={activeMode === "single" ? "on" : ""}
          onClick={() => setMode("single")}
        >
          单条
        </button>
        <button
          role="tab"
          aria-selected={activeMode === "batch"}
          className={activeMode === "batch" ? "on" : ""}
          onClick={() => setMode("batch")}
          disabled={!primary}
          title={primary ? "同一个工作流一次跑多条：只换主需求，其余输入共用" : "这个工作流没有可批量替换的主需求字段"}
        >
          批量
        </button>
      </div>

      {variables.length === 0 && <div className="hint-text">这个工作流的 start 节点没有声明输入。</div>}

      {activeMode === "single" ? (
        <>
          {variables
            .filter((variable) => variable.type === "paragraph")
            .map((variable) => (
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
        </>
      ) : (
        <>
          <section className="batch-editor">
            <div className="batch-editor-head">
              <span className="batch-editor-label">原始需求 · {primaryLabel}</span>
              <span className="batch-editor-count">{filled.length} 条</span>
              <span className="spacer" />
              <span className="batch-cap">
                同时跑
                <Select
                  value={String(runCap)}
                  width={68}
                  options={[1, 2, 3, 4].map((value) => ({ value: String(value), label: String(value) }))}
                  onChange={(value) => onRunCapChange(Math.min(4, Math.max(1, Number(value) || 1)))}
                />
                条
              </span>
            </div>
            <div className="batch-rows">
              {items.map((value, index) => (
                <div className="batch-item" key={index}>
                  <span className="batch-item-no">{index + 1}</span>
                  <textarea
                    rows={3}
                    value={value}
                    placeholder={
                      index === 0
                        ? "第 1 条：粘一段原始需求"
                        : `第 ${index + 1} 条：这条只替换「${primaryLabel}」`
                    }
                    onChange={(event) => updateItem(index, event.target.value)}
                  />
                  <div className="batch-item-actions">
                    {items.length > 1 && (
                      <button className="btn sm ghost" onClick={() => removeItem(index)}>移除</button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <div className="batch-editor-foot">
              <button className="btn sm ghost" onClick={addItem}>添加一条</button>
              <span className="hint-text">每条只替换「{primaryLabel}」，下面这些输入所有条目共用。</span>
            </div>
          </section>

          {longFields.map((variable) => (
            <InputField
              key={variable.variable}
              variable={variable}
              value={inputs[variable.variable] ?? ""}
              onChange={(value) => onChange({ [variable.variable]: value })}
            />
          ))}
          {batchShortFields.length > 0 && (
            <div className="field-grid">
              {batchShortFields.map((variable) => (
                <InputField
                  key={variable.variable}
                  variable={variable}
                  value={inputs[variable.variable] ?? ""}
                  onChange={(value) => onChange({ [variable.variable]: value })}
                />
              ))}
            </div>
          )}
        </>
      )}

      {!hasKey && (
        <div className="warn-box">还没有 API Key，运行会直接失败；先在顶栏「设置」里填 Key。</div>
      )}
      {hasKey && activeMode === "single" && (
        <div className="hint-text">每次运行都会跑完整链路；开着「口播后暂停」会先停在 A07，审完口播再跑分镜和画面。</div>
      )}
      {activeMode === "batch" && (
        <div className="hint-text">
          {reviewGate && canReview
            ? "每条都会先停在 A07：在上方切换条里点「待审阅」那条逐条审，续跑只补它自己的后半段。"
            : "每条都会独立跑完整链路；跑完在画布上方的切换条里逐条看出片。"}
        </div>
      )}
      {activeMode === "single" && singleMissing.length > 0 && (
        <div className="warn-box">还有必填项没填：{singleMissing.map((variable) => variable.label || variable.variable).join("、")}</div>
      )}
      {activeMode === "batch" && sharedMissing.length > 0 && (
        <div className="warn-box">共用输入还有必填项没填：{sharedMissing.map((variable) => variable.label || variable.variable).join("、")}</div>
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

      {activeMode === "single" ? (
        <button
          className="btn primary wide"
          onClick={onRun}
          disabled={running || !hasKey || singleMissing.length > 0}
        >
          用这些输入运行
        </button>
      ) : (
        <button
          className="btn primary wide"
          onClick={() => onRunBatch(filled, runCap)}
          disabled={!canBatch}
        >
          {filled.length > 0 ? `开始批量运行 · ${filled.length} 条` : "先写一条原始需求"}
        </button>
      )}
    </div>
  );
}
