import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { buildRequestBody } from "../src/engine/llm.js";
import { providerFromEnv } from "../src/engine/config.js";

const ENV = { WF_API_KEY: "test-key", WF_BASE_URL: "https://example.com/v1", WF_MODEL: "gpt-6-luna" };

describe("模型请求体", () => {
  it("responses：只有 system 时也提供 input，不发空数组", () => {
    const provider = providerFromEnv({ ...ENV, WF_PROTOCOL: "responses" });
    const { body } = buildRequestBody(provider, [{ role: "system", content: "你是助手" }]);
    assert.deepEqual(body["input"], [{ role: "user", content: "你是助手" }]);
    assert.equal(body["instructions"], undefined);
  });

  it("responses：有 user 时 system 走 instructions", () => {
    const provider = providerFromEnv({ ...ENV, WF_PROTOCOL: "responses" });
    const { body } = buildRequestBody(provider, [
      { role: "system", content: "系统" },
      { role: "user", content: "正文" },
    ]);
    assert.deepEqual(body["input"], [{ role: "user", content: "正文" }]);
    assert.equal(body["instructions"], "系统");
  });

  it("anthropic：只有 system 时 messages 不为空且不重复塞 system", () => {
    const provider = providerFromEnv({ ...ENV, WF_PROTOCOL: "anthropic" });
    const { body } = buildRequestBody(provider, [{ role: "system", content: "系统" }]);
    assert.deepEqual(body["messages"], [{ role: "user", content: "系统" }]);
    assert.equal(body["system"], undefined);
  });

  it("chat：只有 system 时补一条 user", () => {
    const provider = providerFromEnv({ ...ENV, WF_PROTOCOL: "chat" });
    const { body } = buildRequestBody(provider, [{ role: "system", content: "系统" }]);
    assert.deepEqual(body["messages"], [{ role: "user", content: "系统" }]);
  });
});
