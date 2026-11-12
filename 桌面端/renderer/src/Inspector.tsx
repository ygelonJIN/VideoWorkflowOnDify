import { useState } from "react";
import { parseImagePlanValue } from "../../src/engine/imagePlan.js";
import { CopyButton } from "./CopyButton.js";
import type { RunResult, WorkflowInfo, WorkflowNode } from "./types.js";

type EditableField = "title" | "prompt" | "code";

const OUTPUT_LIMIT = 4000;

/** 节点输出值：字符串原样、对象格式化；超长截断并注明总长度。 */
function formatOutput(value: unknown): string {
  const text = typeof value === "string" ? value : (JSON.stringify(value, null, 2) ?? String(value));
  return text.length > OUTPUT_LIMIT ? `${text.slice(0, OUTPUT_LIMIT)}\n…（已截断，共 ${text.length} 字符）` : text;
}

function rawText(value: unknown): string {
  return typeof value === "string" ? value : (JSON.stringify(value, null, 2) ?? String(value));
}

interface Props {
  graph: WorkflowInfo;
  node: WorkflowNode | null;
  result: RunResult | null;
  status: string;
  onUpdate: (field: EditableField, value: string, messageIndex?: number) => Promise<void>;
  onDelete: () => void;
}

function Section({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="sec">
      <div className="sec-title">
        {title}
        {action && <span className="sec-action">{action}</span>}
      </div>
      {children}
    </div>
  );
}

export function Inspector({ graph, node, result, status, onUpdate, onDelete }: Props) {
  const [editor, setEditor] = useState<{ field: EditableField; value: string; index?: number } | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [editError, setEditError] = useState<string | null>(null);

  async function save() {
    if (!editor) return;
    setSaving(true);
    setEditError(null);
    setMessage(null);
    try {
      await onUpdate(editor.field, editor.value, editor.index);
      setEditor(null);
      setMessage("已写回 YAML");
    } catch (error) {
      setEditError((error as Error).message);
    } finally {
      setSaving(false);
    }
  }

  if (!node) {
    return (
      <aside className="inspector">
        <div className="insp-head">
          <div>
            <h2>{graph.appName || "工作流"}</h2>
            <div className="insp-sub">{graph.name}</div>
          </div>
        </div>
        <Section title="概况">
          <table className="vars">
            <tbody>
              <tr><td>DSL</td><td>{graph.version}</td></tr>
              <tr><td>节点</td><td>{graph.nodes.length}</td></tr>
              <tr><td>连线</td><td>{graph.edges.length}</td></tr>
            </tbody>
          </table>
        </Section>
        {graph.warnings.length > 0 && (
          <Section title="YAML 警告">
            {graph.warnings.map((warning) => <div key={warning} className="warn-text">{warning}</div>)}
          </Section>
        )}
        <Section title="提示">
          <div className="hint-text">点画布上的节点查看参数；提示词和代码可以直接改并写回 YAML。</div>
        </Section>
      </aside>
    );
  }

  const runNode = result?.nodes.find((item) => item.nodeId === node.id);
  const imagePlan = parseImagePlanValue(runNode?.outputs?.["image_plan_json"]);

  return (
    <aside className="inspector">
      <div className="insp-head">
        <div>
          <h2>{node.title}</h2>
          <div className="insp-sub">{node.type} · {node.id}</div>
        </div>
        <span className={`pill ${status === "success" ? "ok" : status === "error" ? "bad" : ""}`}>
          {status || "未运行"}
        </span>
        <button className="btn sm danger" onClick={onDelete} title="删除节点">删除</button>
      </div>

      {message && <div className="ok-text">{message}</div>}
      {editError && <div className="err-text">{editError}</div>}

      {editor ? (
        <div className="editor">
          <div className="sec-title">
            {editor.field === "prompt"
              ? `编辑提示词${editor.index !== undefined && editor.index > 0 ? `（第 ${editor.index + 1} 条）` : ""}`
              : editor.field === "code" ? "编辑代码" : "编辑标题"}
            <span className="sec-action">
              <button className="btn" onClick={() => setEditor(null)} disabled={saving}>取消</button>
              <button className="btn primary" onClick={() => void save()} disabled={saving}>
                {saving ? "保存中…" : "保存"}
              </button>
            </span>
          </div>
          <textarea
            className="editor-text"
            value={editor.value}
            onChange={(event) => setEditor({ ...editor, value: event.target.value })}
            rows={editor.field === "title" ? 2 : 14}
          />
          <div className="hint-text">保存会写回原 YAML（注释保留）；04 的提示词/代码同时同步 保留资料/ 镜像。</div>
        </div>
      ) : (
        <>
          {node.model && (
            <Section title="模型">
              <div className="input">{node.model}</div>
            </Section>
          )}

          <Section title="输入">
            {node.inputs.length === 0 ? (
              <div className="hint-text">无声明输入</div>
            ) : (
              <table className="vars">
                <tbody>
                  {node.inputs.map((input) => (
                    <tr key={input.variable}>
                      <td>{input.variable}</td>
                      <td>{input.selector?.join(".") ?? input.valueType ?? ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Section>

          <Section title="输出">
            {node.outputs.length === 0 ? (
              <div className="hint-text">无声明输出</div>
            ) : (
              <div className="chips">
                {node.outputs.map((name) => <span className="tag" key={name}>{name}</span>)}
              </div>
            )}
          </Section>

          {node.promptSections && node.promptSections.length > 0 && node.promptSections.length === 1 && (
            <Section
              title="提示词"
              action={
                <>
                  <CopyButton text={node.promptSections[0]?.text ?? ""} />
                  <button className="btn sm" onClick={() => setEditor({ field: "prompt", value: node.promptSections?.[0]?.text ?? "", index: 0 })}>编辑</button>
                </>
              }
            >
              <div className="code">{(node.promptSections[0]?.text ?? "").slice(0, 2000)}</div>
            </Section>
          )}

          {node.promptSections && node.promptSections.length > 1 && (
            <Section title={`提示词（${node.promptSections.length} 条消息）`}>
              {node.promptSections.map((section, index) => (
                <div className="prompt-msg" key={section.id}>
                  <div className="prompt-msg-head">
                    <span className="prompt-role">{section.role} #{index + 1}</span>
                    <span className="sec-action">
                      <CopyButton text={section.text} />
                      <button className="btn sm" onClick={() => setEditor({ field: "prompt", value: section.text, index })}>编辑这条</button>
                    </span>
                  </div>
                  <div className="code">{section.text.slice(0, 1200)}</div>
                </div>
              ))}
            </Section>
          )}

          {node.code !== undefined && (
            <Section
              title="代码"
              action={<button className="btn sm" onClick={() => setEditor({ field: "code", value: node.code ?? "" })}>编辑</button>}
            >
              <div className="code">{node.code.slice(0, 2000)}</div>
            </Section>
          )}

          {node.conditions !== undefined && (
            <Section title="条件">
              <div className="code">{JSON.stringify(node.conditions, null, 2).slice(0, 2000)}</div>
            </Section>
          )}

          {runNode && (
            <Section title="本次运行">
              <table className="vars">
                <tbody>
                  <tr><td>状态</td><td>{runNode.status}</td></tr>
                  <tr><td>耗时</td><td>{runNode.ms}ms</td></tr>
                  {runNode.usage?.total_tokens !== undefined && <tr><td>Tokens</td><td>{runNode.usage.total_tokens}</td></tr>}
                  {runNode.error && <tr><td>错误</td><td className="bad-text">{runNode.error}</td></tr>}
                </tbody>
              </table>
            </Section>
          )}

          {runNode?.inputs && Object.keys(runNode.inputs).length > 0 && (
            <Section title="输入值">
              {Object.entries(runNode.inputs).map(([name, value]) => (
                <div className="out-item" key={name}>
                  <div className="out-name"><span>{name}</span><CopyButton text={value} /></div>
                  <pre className="out-value">{value}</pre>
                </div>
              ))}
            </Section>
          )}

          {imagePlan && imagePlan.images.length > 0 && (
            <Section title={`图像提示词（${imagePlan.images.length} 张）`}>
              {imagePlan.prefix && (
                <div className="out-item">
                  <div className="out-name"><span>prompt_prefix</span><CopyButton text={imagePlan.prefix} /></div>
                  <pre className="out-value">{imagePlan.prefix}</pre>
                </div>
              )}
              {imagePlan.images.map((image, index) => (
                <div className="out-item" key={image.id ?? `${index}`}>
                  <div className="out-name">
                    <span>{image.id ?? image.scene_id ?? `#${index + 1}`}{image.role ? ` · ${image.role}` : ""}</span>
                    {image.prompt && <CopyButton text={image.prompt} label="复制英文" />}
                    {image.prompt_zh && <CopyButton text={image.prompt_zh} label="复制中文" />}
                  </div>
                  {image.prompt && <pre className="out-value">{image.prompt}</pre>}
                  {image.prompt_zh && <pre className="out-value out-zh">{image.prompt_zh}</pre>}
                </div>
              ))}
            </Section>
          )}

          {runNode?.outputs && Object.keys(runNode.outputs).length > 0 && (
            <Section title="输出值">
              {Object.entries(runNode.outputs).map(([name, value]) => (
                <div className="out-item" key={name}>
                  <div className="out-name"><span>{name}</span><CopyButton text={rawText(value)} /></div>
                  <pre className="out-value">{formatOutput(value)}</pre>
                </div>
              ))}
            </Section>
          )}

          <Section title="标题" action={<button className="btn sm" onClick={() => setEditor({ field: "title", value: node.title })}>改名</button>}>
            <div className="input">{node.title}</div>
          </Section>
        </>
      )}
    </aside>
  );
}
