# 视频工作流桌面端

本地执行 Dify DSL、看画布、跑运行台、开终端、管产物。**YAML 仍是唯一真源**：这里的引擎直接读
`../Dify工作流/*.yml`，不导入数据库、不改格式。

## 现在到哪了

- ✅ **M0 引擎**：读 04 的 YAML，按变量池执行 start / llm / code / if-else / template-transform /
  end，跑通 `a00 → a01 → a02 → a03`，输出 trace；9 项测试通过。
- ✅ **M1 只读画布**：Electron 主进程 + preload + React 渲染层；顶栏选工作流、画布按 DSL 坐标画
  节点和连线、右侧检视器看提示词/代码/输入输出、底部运行台实时显示节点状态；运行时会调本地引擎。
  同一份渲染代码也能跑在浏览器调试壳里。
- ✅ **M2 终端**：底部「终端」页签，预设命令 + 自由输入，`bash -lc` 流式输出；工作目录固定为工作区根，
  输出与退出码通过 SSE / IPC 实时回传。
- ✅ **M3 产物区**：列出 `HTML视频项目/` 下的项目与文件；文本/JSON/字幕就地预览，HTML 用内嵌 iframe、
  视频/图片内嵌播放，也可以交给系统默认应用。运行结束后还能直接看 `outputs`。
- ✅ **容器节点**：iteration（逐项执行并收集为数组）、loop（loop_count / break_conditions）、assigner
  （写回循环变量）、iteration-start / loop-start 入口。
- ✅ **提示词/代码编辑**：检视器里直接改，保存写回原 YAML（注释、缩进、长单行都不动），04 的提示词和
  代码节点同时同步 `保留资料/` 镜像。
- ✅ **画布结构编辑**：加节点（Code / LLM / if-else / 模板 / HTTP / End，自动从选中节点连一条边）、
  删节点（连带删边，一进一出自动接上）、连线模式（点起点再点终点）、点连线删除。
- ✅ **并行迭代**：`is_parallel: true` 时按 `parallel_nums` 分批并发，每项独立变量池，结果顺序不变。
- ✅ **拖动节点**：画布里直接拖，松手才写回 YAML（position / positionAbsolute），拖动过程不落盘。
- ✅ **撤销 / 重做**：每次编辑前留快照，左栏「撤销 / 重做」或 ⌘Z / ⇧⌘Z；最多 50 步。
- ✅ **Electron 内嵌预览**：自定义 `wfs-file://` 协议，带 Range，HTML/视频不再受 file:// 跨源限制。
- ✅ **输入抽屉**：主题正文、生产要求、请求编号、TTS 供应商/声音，跑之前可改；留空沿用 fixture。
- ✅ **界面**：顶栏铺到最左，左侧 84px 留给红绿灯；左栏与顶栏、画布、控制台保持同样的 12px 间距（画布 / 产物 / 撤销重做 / 运行状态都在左栏）；产物占主区三栏，不再挤在底栏。
- ✅ **可收起**：右侧节点详情（顶栏「收起详情」）、下方运行台/终端（标签条「收起」），收起都不改缩放。
- ✅ **缩放手感**：滚轮系数 0.006（同样滑动距离是上一版的两倍）；下限不写死，按「全图适配比例 × 0.4」自动算，上限 300%；打开工作流先给 60% 可读比例，「适应」看全图；四个按钮都可用。
- ⏳ 下一步：画布编辑（加/删节点、改提示词写回 YAML）、HTML 内嵌预览与视频播放器。

## 目录

```text
桌面端/
├── src/engine/          # DSL、变量池、模板、LLM、Code、调度器、trace
├── src/cli.ts           # 命令行入口
├── test/                # node:test 用例（9 项）
├── fixtures/            # 输入样例 + stub 模型输出
├── design/              # 设计原型；v2/tokens.css 是当前主题（雾蓝）
└── dist/                # tsc 产物，不进仓库
```

## 跑

```bash
npm install
npm run build

# 用固定模型输出跑通 a00→a03（不需要 key）
node dist/src/cli.js ../Dify工作流/04_黑帧口播_分组生成.yml \
  --input fixtures/input.json --stub --until a03 --trace /tmp/wf.trace.jsonl

# 列节点
node dist/src/cli.js ../Dify工作流/04_黑帧口播_分组生成.yml --list

# 真模型：先把 .env.example 复制成 .env 填 WF_API_KEY
node dist/src/cli.js ../Dify工作流/04_黑帧口播_分组生成.yml \
  --input fixtures/input.json --until a01
```

界面回归（隐藏窗口，检查缩放/选中/收起/产物视图）：

```bash
WFS_PROBE=1 bash scripts/run-app.sh --no-sandbox
```

测试：

```bash
npm test        # tsc + node --test，9 项
npm run typecheck
```

## 界面

两种壳共用同一份渲染代码（`renderer/`）：

```bash
# A. Electron 桌面窗口
npm run app

# B. 浏览器调试壳（Electron 起不来时用）
npm run dev            # http://127.0.0.1:4321/renderer/index.html
```

`npm run dev` 起的是本地 Node 服务，`/api/*` 与 Electron 主进程提供同一套接口，渲染层通过
`renderer/src/bridge.ts` 自动选择走 IPC 还是 HTTP。

**环境坑（两个）**：

1. DSH 终端里带着 `ELECTRON_RUN_AS_NODE=1`，直接跑 Electron 会变成 Node 模式并报
   `does not provide an export named 'BrowserWindow'`。`scripts/run-app.sh` 已经 `env -u` 掉它。
2. Electron 必须把**应用目录**作为参数传进去；不传就会跑它自带的默认应用，只打印
   `To run a local app, execute the following on the command line: … path-to-app`。`run-app.sh`
   在没参数或只给选项时会自动补 `.`。

`npm run smoke` 会隐藏窗口启动并把渲染结果打出来（标题、桥接、节点数、连线数），用来确认
Electron 壳本身没问题。

**当前机器**：Electron 包是 37.10.3，二进制从本机已有安装复制（`scripts/setup-electron.sh`）；
cdnnpmmirror 下载只有 20–25KB/s，全新下载要 80 分钟以上。沙箱里 agent 无法启动 GUI
（Electron/Chrome 都被 WindowServer 拦），界面需要你本机执行 `npm run app` 看。

## 引擎怎么执行

1. **变量池**：`[nodeId, field]`，外加 `sys.*` / `env.*`；提示词里的 `{{#node.field#}}` 运行时替换。
2. **节点**：start 校验必填输入；llm 按 `prompt_template` 拼消息、三种协议（chat / responses /
   anthropic）任选；code 把声明变量写成 JSON 参数，用 `python3` 跑原样代码、取 `__WF_RESULT__`；
   if-else 逐条算条件、按 `case_id`/`false` 选分支；template-transform 走 `{{ var }}` 子集；
   end 按 `value_selector` 收口。
3. **调度**：从 start 出发沿边推进，已执行节点不重入；`--until` 到点即停；超过 200 步兜底。
4. **trace**：`run_start / node_start / node_end / node_error / run_end`，JSONL 可回放。

未实现的节点类型（iteration / loop / assigner / 其它）**不会静默跳过**：运行到它时状态记
`unimplemented`，报「节点类型未实现」，前面的结果保留。

## 模型出口

`.env` 里配 `WF_BASE_URL` / `WF_API_KEY` / `WF_MODEL` / `WF_PROTOCOL`：

| 场景 | 配置 |
|---|---|
| OpenCode Go（默认） | base `https://opencode.ai/zen/go/v1`，模型 `gpt-6-luna`，协议 `responses` |
| 任意 OpenAI 兼容 | base 换成对方的 `/v1`，协议 `chat` |
| Anthropic 兼容 | 协议 `anthropic` |

`gpt-6-luna` 只走 `/responses`，不能套 chat 客户端；没有 key 时用 `--stub` 跑链路。

## M0 验收记录（2026-11-11）

| 检查 | 结果 |
|---|---|
| `npm test` | 9 项全过：DSL 读取 49 节点 / 51 边、模板替换、Code 节点真实执行、端到端 stub 跑通、未实现节点报错 |
| `node dist/src/cli.js … --stub --until a03` | 4 个节点全 success，产出 `brief_json` / `validation_ok: true`，trace 10 条事件 |
| 不带 key 跑 a01 | 明确报「缺少 API Key」，A00 结果保留，退出码 1 |
| `--list` | 正确列出 49 个节点 |
| `npm test` | **22 项全过**：DSL、模板、Code、端到端、未实现节点、iteration（串行/并行）、loop、04 的 H02I 切片、字段写回、加/删节点、连线/断线、移动节点、if-else 默认条件 |
| `npm run typecheck` | 无错误（含渲染层 TSX） |
| `/api/update-node`（临时副本） | 改 a01 提示词后节点仍 49、边仍 51、文件头注释原样，提示词逐字相等 |
| `/api/file-url` + Range | 返回 `/files?path=…` 与 `file://` 两种 URL；视频请求 206 Partial Content |
| 终端 `/api/exec` | `echo hello` 流式返回 stdout 与 `term-done`，退出码正确 |
| 产物 `/api/projects`、`/api/files`、`/files` | 项目/文件列表与文件内容（JSON / HTML / 视频）正常返回 |
| 带输入运行 `/api/run` | 覆盖 `campaign_brief` 后仍跑通 a00→a03，`validation_ok=true` |

体积提示：这个盘（exFAT）上 `npm install` 偶尔不会生成 `node_modules/.bin`，所以 `package.json`
里的脚本直接调 `node node_modules/typescript/bin/tsc`，不依赖 `.bin`；Vitest 的 esbuild 服务在该
沙箱里起不来，测试改用 `node:test` + tsc 产物跑。

## 已知边界

- 结构编辑会直接写回 YAML：动手前先 `git commit` 更稳（应用内也有 50 步撤销）。
- 没有多选、复制/粘贴、框选；加完节点要自己挪位置。
- 新节点的字段是通用默认值（if-else 会按来源节点生成一条“非空”条件）。
- 内嵌 HTML 预览在 Electron 里如果被跨源策略挡住，用面板上的「用系统应用打开」。
- Jinja 只支持 `{{ var }}` 与 `{{ var | default("x") }}`；复杂模板待补。
- YAML 写回（保留注释）还没做，按 M0 范围只读。
