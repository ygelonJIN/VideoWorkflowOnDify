import test from "node:test";
import assert from "node:assert/strict";
import {
  autoProjectName,
  cleanRequirements,
  cleanTopicName,
  hasProducibleOutput,
  precomputedFrom,
  primaryVariable,
  startableCount,
  uniqueProjectName,
} from "../src/batch/model.js";

test("主输入变量优先 campaign_brief", () => {
  assert.equal(
    primaryVariable([
      { variable: "notes", type: "paragraph", required: true },
      { variable: "campaign_brief", type: "paragraph", required: true },
    ]),
    "campaign_brief",
  );
  assert.equal(primaryVariable([]), null);
  assert.equal(primaryVariable([{ variable: "topic", type: "text-input", required: true }]), "topic");
  // 全是下拉/开关时没有可批量替换的主需求，不能拿 select 当文本框
  assert.equal(primaryVariable([{ variable: "tts_provider", type: "select", required: false }]), null);
});

test("主题清理取第一行、去空白和路径字符", () => {
  assert.equal(cleanTopicName("  允许自己\n第二行"), "允许自己");
  assert.equal(cleanTopicName("a/b:c*d"), "abcd");
  assert.equal(cleanTopicName("   "), "");
});

test("项目名带时间戳，没有主题用序号兜底", () => {
  const when = new Date(2026, 10, 25, 10, 56);
  assert.equal(autoProjectName("允许自己", 0, when), "允许自己20261125-1056");
  assert.equal(autoProjectName("", 3, when), "批量0420261125-1056");
});

test("重名加后缀，不会跳到无限循环", () => {
  assert.equal(uniqueProjectName("a", []), "a");
  assert.equal(uniqueProjectName("a", ["a"]), "a-2");
  assert.equal(uniqueProjectName("a", ["a", "a-2"]), "a-3");
});

test("并发闸门不超过上限", () => {
  assert.equal(startableCount(4, 0, 4), 4);
  assert.equal(startableCount(4, 2, 4), 2);
  assert.equal(startableCount(4, 4, 4), 0);
  assert.equal(startableCount(0, 0, 4), 0);
});

test("审阅续跑只收成功的 LLM/代码节点", () => {
  const precomputed = precomputedFrom({
    nodes: [
      { nodeId: "a01", type: "llm", status: "success", outputs: { text: "x" } },
      { nodeId: "a02", type: "code", status: "error", outputs: { bad: true } },
      { nodeId: "a03", type: "template-transform", status: "success", outputs: { t: "y" } },
    ],
  });
  assert.deepEqual(Object.keys(precomputed), ["a01"]);
});

test("可出片必须同时有 HTML 和口播", () => {
  assert.equal(hasProducibleOutput({ html_document: "<p/>", voiceover_script: "a" }), true);
  assert.equal(hasProducibleOutput({ html_document: "<p/>" }), false);
  assert.equal(hasProducibleOutput(undefined), false);
});

test("入口清洗去空条目但保留顺序", () => {
  assert.deepEqual(cleanRequirements([" b ", "", "a", "  "]), ["b", "a"]);
  assert.deepEqual(cleanRequirements([]), []);
});
