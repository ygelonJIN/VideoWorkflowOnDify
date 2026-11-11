import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { VariablePool } from "../src/engine/vars.js";
import { difySelectors, interpolateDify, renderTemplateJinja } from "../src/engine/template.js";

describe("变量与模板", () => {
  it("按 {{#node.field#}} 取值，缺失为空串", () => {
    const pool = new VariablePool({ HEYGEN_API_BASE: "https://x" }, { query: "q" });
    pool.setNodeOutputs("a00", { campaign_brief: "原始素材", n: 3, flag: true });
    const text = interpolateDify(
      "{{#a00.campaign_brief#}} / {{#a00.n#}} / {{#a00.flag#}} / {{#a00.missing#}} / {{#env.HEYGEN_API_BASE#}}",
      pool,
    );
    assert.equal(text, "原始素材 / 3 / true /  / https://x");
  });

  it("能列出提示词里引用到的选择器", () => {
    assert.deepEqual(difySelectors("a {{#a01.text#}} b {{#env.X#}}"), [["a01", "text"], ["env", "X"]]);
  });

  it("template-transform 支持 {{ var }} 与 default", () => {
    const text = renderTemplateJinja('错误：{{ copy_errors_json }}；缺失：{{ missing | default("无") }}', {
      copy_errors_json: '["x"]',
    });
    assert.equal(text, '错误：["x"]；缺失：无');
  });
});
