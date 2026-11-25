import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * 桌面端「多开」的底层前提：同一个工作流能被并发跑多份，
 * 事件各自带 clientId（界面靠它分流），结果互不污染。
 */
const CONCURRENT_YAML = `
version: "0.7.0"
kind: app
app:
  name: 并发测试
  mode: workflow
workflow:
  graph:
    nodes:
      - id: s
        type: custom
        data:
          type: start
          title: S
          variables:
            - variable: tag
              type: text-input
              required: true
      - id: c
        type: custom
        data:
          type: code
          title: C
          variables:
            - variable: tag
              value_selector: [s, tag]
          outputs:
            - variable: result
              value_type: string
          code: |
            def main(tag: str) -> dict:
                import time
                time.sleep(0.6)
                return {"result": "TAG-" + tag}
      - id: e
        type: custom
        data:
          type: end
          title: E
          outputs:
            - variable: result
              value_selector: [c, result]
    edges:
      - {id: e1, source: s, target: c}
      - {id: e2, source: c, target: e}
`;

test("四条运行并行，事件按 clientId 分流且结果互不影响", async () => {
  const dir = await mkdtemp(join(tmpdir(), "wfs-concurrent-"));
  const workflowPath = join(dir, "concurrent.yml");
  await writeFile(workflowPath, CONCURRENT_YAML, "utf8");

  // core.mjs 是主进程模块（无类型声明），用动态 import 拿到运行入口
  const core = (await import(new URL("../../electron/core.mjs", import.meta.url).href)) as {
    runWorkflow: (options: Record<string, unknown>) => Promise<{ status: string; outputs: Record<string, unknown> }>;
  };

  const tags = ["1", "2", "3", "4"];
  const events = new Map<string, Array<{ clientId?: string; type?: string; at?: string }>>();

  const results = await Promise.all(
    tags.map(async (tag) => {
      const clientId = `client-${tag}`;
      const list: Array<{ clientId?: string; type?: string; at?: string }> = [];
      events.set(clientId, list);
      const result = await core.runWorkflow({
        path: workflowPath,
        clientId,
        inputs: { tag },
        onEvent: (event: { clientId?: string; type?: string; at?: string }) => list.push(event),
      });
      return { tag, result };
    }),
  );

  for (const { tag, result } of results) {
    assert.equal(result.status, "success", `第 ${tag} 条应该成功`);
    assert.equal(result.outputs.result, `TAG-${tag}`, `第 ${tag} 条结果不能串到别人`);
  }

  for (const [clientId, list] of events) {
    assert.ok(list.length > 0, `${clientId} 应该有事件`);
    assert.ok(
      list.every((event) => event.clientId === clientId),
      `${clientId} 的事件不能混入别人的 clientId`,
    );
  }

  // 并发的证据：四条运行的起点落在同一小段时间里，而单条本身要跑 0.6 秒以上
  const starts = [...events.values()]
    .map((list) => list.find((event) => event.type === "run_start")?.at)
    .filter((at): at is string => typeof at === "string")
    .map((at) => new Date(at).getTime());
  assert.equal(starts.length, 4, "每条运行都要有 run_start");
  const spread = Math.max(...starts) - Math.min(...starts);
  assert.ok(spread < 500, `四条应该几乎同时开跑，实际起点跨了 ${spread}ms`);
});
