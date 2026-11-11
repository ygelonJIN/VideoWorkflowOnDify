# 视频工作流桌面端

本地执行 Dify DSL、看画布、跑运行台、开终端、管产物。**YAML 仍是唯一真源**：这里的引擎直接读
`../Dify工作流/*.yml`，不导入数据库、不改格式。

## 现在到哪了

- ✅ **M0 引擎**：读 04 的 YAML，按变量池执行 start / llm / code / if-else / template-transform /
  end，跑通 `a00 → a01 → a02 → a03`，输出 trace；31 项测试通过。
- ✅ **M1 只读画布**：Electron 主进程 + preload + React 渲染层；顶栏选工作流、画布按 DSL 坐标画
  节点和连线、右侧检视器看提示词/代码/输出值、底部运行台实时显示节点状态；运行时会调本地引擎。
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
- ✅ **输入抽屉**：按 start 节点声明的变量动态生成（目前 04 是 10 项：主题、创作偏好、背景/规范、历史、
  请求编号、生产要求、TTS 供应商/模型/Base/声音），字段类型、选项、必填、最大长度都读 YAML；留空沿用 fixture。
- ✅ **界面**：顶栏铺到最左，左侧 84px 留给红绿灯；左栏与顶栏、画布、控制台保持同样的 12px 间距（画布 / 产物 / 撤销重做 / 运行状态都在左栏）；产物占主区三栏，不再挤在底栏。
- ✅ **可收起**：右侧节点详情（顶栏「收起详情」）、下方运行台/终端（标签条「收起」），收起都不改缩放。
- ✅ **缩放手感**：滚轮系数 0.006（同样滑动距离是上一版的两倍）；下限不写死，按「全图适配比例 × 0.4」自动算，上限 300%；打开工作流先给 60% 可读比例，「适应」看全图；四个按钮都可用。
- ✅ **手动停止**：运行中顶栏变「停止」，节点间立即停，进行中的模型请求 / Code 子进程会中断；
  停下来时保留已完成节点的结果，运行台显示「已停止」。
- ✅ **节点输出值**：检视器「输出值」逐项显示本次运行该节点的真实输出（字符串原样、对象格式化，
  超 4000 字符截断并注明总长度），不用再翻 trace。
- ✅ **镜像映射单一真源**：提示词/代码镜像的 node→文件映射直接读
  `HTML视频项目/workflow_runtime/tools/sync_prompts_to_yaml.py` 的 `MAPPING` / `CODE_MAPPING`；
  映射读不到或目标文件不存在时会明确提示，不再静默跳过同步。
- ✅ **结构编辑逐字还原**：加/删节点、连线/断线后文件末尾换行保留，一加一删逐字回到原文件。
- ✅ **多消息提示词**：LLM 节点有 system+user 等多条 message 时，检视器按条列出，每条单独「编辑这条」，
  写回只动那一条的 `text`；单条节点保持原来的整段编辑。多行引号标量/块标量也能安全替换。
- ✅ **外部改动同步**：窗口重新获得焦点时比对文件 sha1；YAML 被脚本改过就自动重载并提示，
  不再出现「画布还是旧图、接着编辑把别人的改动覆盖掉」。
- ✅ **节点输入值**：检视器除了输出值，也显示这个节点本次实际读到的输入（`*_selector` 与
  `{{#node.field#}}` 全部解析成值；单条超 6000 字符、单节点超 24000 字符截断并注明）。
- ✅ **画布搜索/定位**：画布右上角搜索框（⌘F 聚焦），按标题或 id 过滤，回车/点选后把节点移
  到视口中心并选中；切工作流自动清空。
- ⏳ 下一步：打包 .app；外部改动从「切回窗口同步」升级成常驻监听；完整 04 用真模型跑通。

## 目录

```text
桌面端/
├── src/engine/          # DSL、变量池、模板、LLM、Code、调度器、trace
├── src/cli.ts           # 命令行入口
├── test/                # node:test 用例（31 项）
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
npm test        # tsc + node --test，31 项
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

## 验收记录（2026-11-11 复测）

| 检查 | 结果 |
|---|---|
| `npm test` | **31 项全过**：DSL（数量以 YAML 为准）、模板、Code、端到端 stub、未实现节点、iteration（串行/并行/04 真实 H02I 三点链）、loop、字段写回、加减节点逐字还原、连线/断线、移动节点、镜像映射、手动停止、多消息提示词按索引写回、节点输入采集 |
| `npm run typecheck` | 无错误（含渲染层 TSX） |
| `npm run smoke` | 隐藏窗口加载 04（复测时 51 节点 / 53 条边，数量随 YAML），bridge 正常 |
| `WFS_PROBE=1` | 选中、缩放、收起、产物切换正常；stub 跑 a00→a03 后 A00 显示 10 条输出值、A01 显示 6 条输入值；输入抽屉 12 个字段（10 变量 + 2 控制）；切到 01 选中 D01 显示 2 条 message；搜索 D01 命中并定位；外部改文件后 focus 自动重载并提示 |
| `/api/run` + `/api/cancel` | 起一个 10 秒 Code 节点，1.3 秒后取消：`status=stopped`，该节点 `stopped(已停止)`，子进程被杀 |
| `/api/update-node`（临时副本） | 改 h02sm 提示词：节点/边数量不变、文件头注释原样、只动目标行 |
| 镜像同步（h02sm / h02sk） | 返回 `mirror: 保留资料/工作流提示词/屏内动效提示词.md` 与 `…/merge_screen_motion.py`，内容与 YAML 逐字一致 |
| 结构编辑（临时副本） | 加节点 +1、删节点后文件与原始逐字相等（含末尾换行） |
| `/api/file-url` + Range | 视频请求 206 Partial Content |
| 终端 `/api/exec` | `echo hello` 流式返回 stdout/stderr 与 `term-done`，退出码正确 |
| 产物 `/api/projects`、`/api/files`、`/files` | 项目/文件列表与 JSON / HTML / 视频内容正常返回 |

2026-11-11 16:30 复测时 `npm test` 曾 7 项红：测试写死 49 节点/51 边，而 04 当时已是 50/52，且 H02I 切片停在
`h02i_start → h02s → h02j`。现在数量从 YAML 推导、切片直接从 YAML 抓 `parentId=h02i` 的整条链，
04 再加减节点不会假红。

体积提示：这个盘（exFAT）上 `npm install` 偶尔不会生成 `node_modules/.bin`，所以 `package.json`
里的脚本直接调 `node node_modules/typescript/bin/tsc`，不依赖 `.bin`；Vitest 的 esbuild 服务在该
沙箱里起不来，测试改用 `node:test` + tsc 产物跑。

## 已知边界

- 结构编辑会直接写回 YAML：动手前先 `git commit` 更稳（应用内也有 50 步撤销）。
- 没有多选、复制/粘贴、框选；加完节点要自己挪位置。
- 新节点的字段是通用默认值（if-else 会按来源节点生成一条“非空”条件）。
- 内嵌 HTML 预览在 Electron 里如果被跨源策略挡住，用面板上的「用系统应用打开」。
- Jinja 只支持 `{{ var }}` 与 `{{ var | default("x") }}`；复杂模板待补。
- 外部改动只在窗口重新获得焦点时同步，后台不轮询；如果另一个进程在应用运行期间连续写同一文件，
  仍然可能出现「最后写入者赢」，动手前先 commit 更稳。
- 画布有搜索没有小地图；「适应」全图约 8%，只适合看轮廓，细看仍要缩放或搜索定位。
