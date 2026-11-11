import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { loadMirrorMaps } from "../src/engine/mirrors.js";
import { WORKSPACE } from "./paths.js";

const TOOL = resolve(WORKSPACE, "HTML视频项目/workflow_runtime/tools/sync_prompts_to_yaml.py");
const PROMPT_DIR = resolve(WORKSPACE, "保留资料/工作流提示词");
const CODE_DIR = resolve(WORKSPACE, "保留资料/工作流代码节点");

describe("镜像映射", () => {
  it("从 sync_prompts_to_yaml.py 读到的映射覆盖 04 的逐屏节点", async () => {
    const maps = await loadMirrorMaps(TOOL);
    assert.equal(maps.warning, undefined, "映射表应能正常解析");
    assert.equal(maps.prompts["h02s"], "场景单屏提示词.md");
    assert.equal(maps.prompts["h02sm"], "屏内动效提示词.md");
    assert.equal(maps.codes["h02sk"], "merge_screen_motion.py");
    assert.equal(maps.codes["h00"], "split_scene_groups_black_frame.py");
  });

  it("映射里每个镜像文件都真的存在", async () => {
    const maps = await loadMirrorMaps(TOOL);
    for (const [nodeId, name] of Object.entries(maps.prompts)) {
      assert.ok(existsSync(resolve(PROMPT_DIR, name)), `提示词镜像缺失：${nodeId} → ${name}`);
    }
    for (const [nodeId, name] of Object.entries(maps.codes)) {
      assert.ok(existsSync(resolve(CODE_DIR, name)), `代码镜像缺失：${nodeId} → ${name}`);
    }
  });

  it("映射表读不到时给 warning，而不是静默不同步", async () => {
    const maps = await loadMirrorMaps(resolve(WORKSPACE, "不存在的映射表.py"));
    assert.ok(maps.warning);
    assert.deepEqual(maps.prompts, {});
    assert.deepEqual(maps.codes, {});
  });
});
