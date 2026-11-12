import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { findImagePlan, parseImagePlanValue } from "../src/engine/imagePlan.js";

const RAW = JSON.stringify({
  prompt_prefix: "cinematic, warm light",
  images: [
    { id: "s01", scene_id: "s01", role: "full", prompt: "a quiet kitchen", prompt_zh: "安静的厨房" },
    { id: "s02", scene_id: "s02", role: "html", prompt: "", prompt_zh: "" },
  ],
});

describe("图像提示词", () => {
  it("解析 image_plan_json", () => {
    const plan = parseImagePlanValue(RAW);
    assert.ok(plan);
    assert.equal(plan.prefix, "cinematic, warm light");
    assert.equal(plan.images.length, 2);
    assert.equal(plan.images[0]?.prompt, "a quiet kitchen");
  });

  it("从 outputsByNode 里自动找到计划，不用选节点", () => {
    const plan = findImagePlan({
      a01: { text: "..." },
      h01pv: { image_plan_json: RAW },
    });
    assert.ok(plan);
    assert.equal(plan.images.length, 2);
  });

  it("没有计划或 JSON 坏了返回 null", () => {
    assert.equal(parseImagePlanValue("not json"), null);
    assert.equal(parseImagePlanValue(JSON.stringify({ images: [] })), null);
    assert.equal(findImagePlan({ a01: { text: "x" } }), null);
    assert.equal(findImagePlan(null), null);
  });
});
