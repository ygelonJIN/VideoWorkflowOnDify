# 视频工作流桌面端

本地执行 Dify DSL、看画布、跑运行台、开终端、管产物。**YAML 仍是唯一真源**：这里的引擎直接读
`../Dify工作流/*.yml`，不导入数据库、不改格式。

## 现在到哪了

- ✅ **M0 引擎**：读 04 的 YAML，按变量池执行 start / llm / code / if-else / template-transform /
  end，跑通 `a00 → a01 → a02 → a03`，输出 trace；39 项测试通过。
- ✅ **M1 只读画布**：Electron 主进程 + preload + React 渲染层；顶栏选工作流、画布按 DSL 坐标画
  节点和连线、右侧检视器看提示词/代码/输出值、底部运行台实时显示节点状态；运行时会调本地引擎。
  同一份渲染代码也能跑在浏览器调试壳里。
- ✅ **M2 终端**：底部「终端」页签，自由输入，`bash -lc` 流式输出；工作目录固定为工作区根，
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
- ✅ **运行态可见**：运行中的节点放大 1.045、双层脉冲光环 + 「运行中」胶囊，其余节点和连线变暗，
  进入当前节点的连线流动；画布角上显示「运行中 · 节点名 · 已完成 N 个」，镜头跟到当前节点。
  跑完停在最后执行的节点，运行台顶部出现「下一步：去出片」。
- ✅ **一键复制**：节点每个输入/输出、每条提示词、每张图的 prompt、产物页的最终 JSON 都有「复制」。
- ✅ **运行台新消息在上**：事件倒序显示，最新的 `run_end` 在最上面，不再往下滚。
- ✅ **出片（主区，5 步一条线）**：左栏「出片」是一条竖着的流程，当前步展开、完成步打勾：
  1. 运行结果（状态/节点数/耗时）；
  2. 准备项目（项目名默认时间戳可改）——调 `--prepare` 建项目、写图片计划和 `媒体/出图/*.txt`，
     不出图、不配音、不渲染；
  3. 出图提示词——每张一张卡，单独复制中文/英文段落（不会把「出图后保存为…」也复制进去），
     也可以「复制全部中文」；缩略图取 `媒体/图片/_resolved/`；
  4. 放图——一个大拖放区对应 `媒体/图片/`，显示「已放 N / 共 M 张」和缺哪几张；文件名是 `s02.png`
     就按 id 对，其余按图片自己的修改时间顺序对（保留原文件 mtime，和拖入先后无关）；
  5. 渲染成片——调 `--skip-images`（TTS + 映射图片 + 渲染 mp4），缺图可勾「缺图也继续」，
     日志实时滚动；完成后「打开成片 / 重新渲染（--replace）/ 看产物」。
  跑完工作流自动切到出片第 2 步；项目名和项目目录记在本地，切走再回来不丢。
- ✅ **下栏只留运行台 / 终端**：图片、图像提示词不再单独占页签，都并进「出片」；
  终端去掉了旧流程的三个预设（它们会打开 TextEdit 让人粘 Dify 文本），只保留自由命令。
- ✅ **TTS Key 从终端读**：MIMO 的 Key 直接从 `~/.zshrc` 读（`zsh -lc 'source ~/.zshrc; printenv MIMO_API_KEY'`），
  只放进子进程环境，不写盘、不显示，界面上只写「从终端读取（末四位）」。

- ✅ **图像提示词**：选中 H01PV 这类产出 `image_plan_json` 的节点，检视器直接摊开
  「图像提示词（N 张）」：`prompt_prefix` + 每张图的英文 `prompt` / 中文 `prompt_zh`，都可单独复制。

- ✅ **节点输入值**：检视器除了输出值，也显示这个节点本次实际读到的输入（`*_selector` 与
  `{{#node.field#}}` 全部解析成值；单条超 6000 字符、单节点超 24000 字符截断并注明）。
- ✅ **画布搜索/定位**：画布右上角搜索框（⌘F 聚焦），按标题或 id 过滤，回车/点选后把节点移
  到视口中心并选中；切工作流自动清空。
- ✅ **工作流选择**：左上角是主题化下拉，列出 `Dify工作流/` 下的 YAML；旁边「打开文件…」走系统
  文件框，可以选工作区里任意位置的 `.yml / .yaml`。
- ✅ **运行先填输入**：点「运行」先打开输入抽屉，确认「用这些输入运行」才执行；跑到设定节点自然
  只跑全程，没有“跑到某个节点”的选项；**界面只跑真实模型**，没配 Key 会禁用运行并提示去「设置」。
- ✅ **输入不再预填示例**：开始节点只留 TTS 默认值和自动生成的 `request_id`，正文空白；必填项没填时
  「用这些输入运行」禁用并列出缺哪项，不再把 `fixtures/input.json` 里那段示例文案带进真实运行。
- ✅ **口播闸门（A07 暂停）**：输入抽屉里「口播生成后暂停审阅」默认开；跑到 A07（口播刚整理完，
  **分镜/动效/合规还没跑**）停住，弹出审阅卡：口播全文、字数、预计时长、口播自检错误与警告。
  三个操作：**重跑文案**（可填修改意见，带进 A01 的创作偏好，从 a01 重走：a01、a04、a06 共 3 次 LLM）、
  **继续生成画面**（复用这版口播，接着跑 a08 分镜 → a10 动效 → a12 合规 → H00 画面/HTML，中途不再停）、
  **放弃这次运行**（二次确认后丢结果）。关掉开关就恢复一路跑到成片。
  为什么停 A07 而不是 A17：口播是 a06 生成的，a08/a10/a12 三个下游 LLM 都建立在口播之上；停在 A17 等于
  先为一张审阅卡烧掉 3 次分镜/动效/合规调用，改一版文案要重跑 6 次。停在 A07 审阅前只要 3 次、改稿也只要 3 次。
- ✅ **审阅卡可以收起再点回来**：点卡片外面、按 Esc、点右上角 ✕ 都只是**收起**，不是放弃——
  这次口播段的结果留在内存和 `localStorage`（`studio.pendingReview`），顶栏出现「文案待审阅 · 点开」，
  点它回到同一张卡；重启应用或重开同一条工作流也会恢复成收起状态。只有卡片里的「放弃这次运行」才真丢结果。
  有待审阅的卡时重新运行会先弹确认，不会再悄悄覆盖。
  实现：引擎支持 `precomputed`（已跑完的 llm/code 节点直接复用输出，if-else 等仍然重算分支），
  桌面端先 `until=a07` 跑口播段，继续时带 precomputed 一口气跑到底。
- ✅ **上次运行可恢复**：跑完把 End 输出（html/口播/图像计划）存到本地，重启应用或重开工作流时
  提示「已恢复上次运行结果」，直接去「出片」接着做，不用为了出片重跑一遍模型。
- ✅ **只有 system 的提示词也能跑**：04 的 LLM 节点几乎都是单条 system，Responses / Anthropic
  以前会发空 `input`/`messages` 被 400 拒掉；现在会自动把它当成唯一一条 user 消息发出，
  chat 协议也补一条 user。gpt-6-luna 实测 200。
- ✅ **主题化下拉**：工作流、加节点类型、输入抽屉里的选择项都换成自绘下拉，弹层跟界面同一套
  颜色/圆角/阴影；未实现的节点类型以灰色列出并注明原因。
- ✅ **产物预览**：修掉 `wfs-file://` 空 host 把 `/Volumes` 当域名的问题（PNG/MP4 之前因此打不开）；
  视频、音频、图片、HTML 都能内嵌看，任何文件都能「用系统应用打开」；目录有「← 返回」和
  「刷新」，预览有「返回列表」，媒体按比例缩放不再灰屏。
- ✅ **拖拽跟手**：拖动位移按当前缩放换算（以前放大/缩小后节点移动距离和鼠标对不上），并用
  函数式状态更新避免高频移动掉帧；拖动时**连线跟着节点走**，松手先在本地落位再后台写盘，
  不会闪回或重新计算。
- ✅ **设置（Key / 模型）**：左栏底部「设置」打开面板，改 API Base URL、模型、协议、API Key；
  写 `桌面端/.env`（权限 600、git 已忽略）。Key 只写不读，界面只显示「已配置（末四位）」，
  支持清除 Key；保存后下一次运行生效。
- ✅ **左栏**：画布/产物居中；设置、撤销/重做贴底；节点数/模型/Key 状态这些小字移到运行台
  和终端标签条的右侧空白处。
- ✅ **下拉收起**：所有自绘下拉点旁边、点另一个下拉、按 Esc 都能收起来。
- ⏳ 下一步：打包 .app；外部改动从「切回窗口同步」升级成常驻监听；完整 04 用真模型跑通
  （现在可以在应用内「设置」里填 Key 了）。

## 目录

```text
桌面端/
├── src/engine/          # DSL、变量池、模板、LLM、Code、调度器、trace
├── src/cli.ts           # 命令行入口
├── test/                # node:test 用例（39 项）
├── fixtures/            # 输入样例 + 自动化测试用的固定模型输出
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
npm test        # tsc + node --test，39 项
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

## 节点支持（DSL 0.7 执行层）

| 节点类型 | 执行 | 新建 |
|---|---|---|
| start / llm / code / if-else / template-transform / http-request / end | ✅ | ✅（Code / LLM / if-else / 模板 / HTTP / End） |
| iteration / loop / assigner（含 iteration-start / loop-start） | ✅ | ❌ 画布内暂不能新建容器 |
| question-classifier / variable-aggregator / parameter-extractor / knowledge-retrieval / tool / agent / doc-extractor | ❌ 运行到会明确报「节点类型未实现」 | ❌ |

另外，Dify 的插件类节点（各种工具、知识库、Agent 策略）没有对接；画布里的灰色项就是这些。

## 模型出口

`.env` 里配 `WF_BASE_URL` / `WF_API_KEY` / `WF_MODEL` / `WF_PROTOCOL`：

| 场景 | 配置 |
|---|---|
| OpenCode Go（默认） | base `https://opencode.ai/zen/go/v1`，模型 `gpt-6-luna`，协议 `responses` |
| 任意 OpenAI 兼容 | base 换成对方的 `/v1`，协议 `chat` |
| Anthropic 兼容 | 协议 `anthropic` |

`gpt-6-luna` 只走 `/responses`，不能套 chat 客户端。界面没有 stub 开关；`--stub` 只保留给
CLI 和自动化测试（`fixtures/stub/`）。

## 验收记录（2026-11-11 复测）

| 检查 | 结果 |
|---|---|
| `npm test` | **39 项全过**：DSL（数量以 YAML 为准）、模板、Code、端到端 stub、未实现节点、iteration（串行/并行/04 真实 H02I 三点链）、loop、字段写回、加减节点逐字还原、连线/断线、移动节点、镜像映射、手动停止、多消息提示词按索引写回、节点输入采集、system-only 请求体（responses / anthropic / chat）、image_plan_json 解析 |
| `npm run typecheck` | 无错误（含渲染层 TSX） |
| `npm run smoke` | 隐藏窗口加载 04（复测时 51 节点 / 53 条边，数量随 YAML），bridge 正常 |
| `WFS_PROBE=1` | 选中、缩放、收起、产物切换正常；探针用本地 responses 假端点跑一次；A00 显示输出值、A01 显示 6 条输入值；输入抽屉 10 个字段（只剩 start 变量），没有 stub / 跑到哪；图片页签拖图落盘；图像提示词每卡 1 个复制按钮；切到 01 选中 D01 显示 2 条 message；搜索 D01 命中并定位；外部改文件后 focus 自动重载并提示 |
| `/api/run` + `/api/cancel` | 起一个 10 秒 Code 节点，1.3 秒后取消：`status=stopped`，该节点 `stopped(已停止)`，子进程被杀 |
| `/api/update-node`（临时副本） | 改 h02sm 提示词：节点/边数量不变、文件头注释原样、只动目标行 |
| 镜像同步（h02sm / h02sk） | 返回 `mirror: 保留资料/工作流提示词/屏内动效提示词.md` 与 `…/merge_screen_motion.py`，内容与 YAML 逐字一致 |
| 结构编辑（临时副本） | 加节点 +1、删节点后文件与原始逐字相等（含末尾换行） |
| `/api/file-url` + Range | 视频请求 206 Partial Content |
| 终端 `/api/exec` | `echo hello` 流式返回 stdout/stderr 与 `term-done`，退出码正确 |
| 产物 `/api/projects`、`/api/files`、`/files` | 项目/文件列表与 JSON / HTML / 视频内容正常返回 |
| 产物内嵌预览（探针） | 项目 → 成片 → 最终视频.mp4：`readyState=4`、1080×1920、显示区 311×553；图片 1440×2560 同样显示；「返回列表」「← 返回」都可用 |
| 媒体协议（探针） | `wfs-file://local/...` 取 PNG（200，image/png）与 MP4 元数据（34.4s，1080×1920） |
| 运行时交互（探针） | 「运行」先出输入抽屉（10 字段），确认后执行；工作流下拉能切到 01 |
| system-only 提示词（真实接口） | 用配置的 Key 发一条只有 system 的请求：HTTP 200，返回「正常」 |
| 控制台（探针） | 运行台第一条是 `run_end`；页签含 运行台/终端/素材/图像提示词；「图像提示词」空态提示正确 |
| 制作页签（探针） | 打开「制作」：项目名默认时间戳、TTS 提示「从终端读取」、3 个选项、没跑完时「准备项目」禁用 |
| MIMO Key（本机） | `~/.zshrc` 里存在，`mimoKeyStatus` 返回 `hasKey=true`、末四位只用于界面提示 |
| 图片页签（探针） | 选中 20261111-1813 拖入 1x1 PNG：落到 `媒体/图片/`、列表出现、缩略图 naturalWidth=1；测试文件已清理 |
| 图像提示词（探针） | 选中 20261111-1813：从 `媒体/出图/` 读出 4 张提示词卡（s02/s03/s05/s06），每卡 1 个复制按钮 |
| 运行态（探针） | 抓到 `.node.st-running`；检视器自动切到 A01；画布 transform 随节点变化；复制按钮把 965 字符写进剪贴板 |
| 真实模型（手动，一次最小请求） | 已配置的 Key 连通：HTTP 200，协议 responses，模型 gpt-6-luna |
| 拖拽（探针） | 指针移 120/60 屏幕像素，节点跟 120/61；连线路径同步变化；原地放回后位置归零、YAML sha1 不变 |
| 下拉（探针） | 打开工作流下拉有 2 项，点画布后菜单关闭 |
| 设置（接口） | 保存 4 个键后 `.env` 权限 600、Key 显示末四位；清除后 `hasKey=false`；测试完文件已删除 |

### 2026-11-12 改版复测

| 检查 | 结果 |
|---|---|
| `npm run typecheck` | 无错误（含新的 `Produce.tsx`） |
| `npm run build:renderer` | `renderer/dist/app.js` 生成成功 |
| `npm test` | 39 项全过 |
| 准备项目（真跑 `--prepare`） | 用 `20261111-1813-blackframe-input.json` 跑通：4 张照片 + 2 屏 HTML，落 `媒体/图片计划.json`、`媒体/出图/`（s02/s03/s05/s06 四份 txt），临时项目已清理 |
| `startBuild` 兼容 `action` | 修掉主进程传 `action`、core 只认 `kind` 的错位；`action=prepare` 端到端返回 `code 0`、`expectedIds=[s02,s03,s05,s06]` |
| TTS 参数 | 修掉 `--tts-voice`（脚本没这个参数，之前必挂在 argparse）→ `--voice-name`；Base 地址改用 `approved_package_json.tts_config` 里解析好的 URL，不再把「默认（按量付费）」当中文 URL 传下去 |
| 输入不预填 | `inputDefaults()` 只返回 TTS 默认值和自动生成的 `request_id`；必填项空着时「用这些输入运行」禁用并列出缺哪项 |

界面在本机沙箱里起不了 Electron，以上是引擎、脚本入口和构建层验证；窗口里的实际观感需要你本机 `npm run app` 确认。

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
- 工作流文件框只能选工作区内的文件；选到工作区外会报「路径不在工作区内」。
- 设置面板写入 `桌面端/.env`；同名环境变量优先于 `.env`，面板里不显示环境变量来源。
- 复制已经是一键；粘贴到别的应用（Dify、即梦等）仍需手动，桌面端没有对接它们的写入接口。
- 「出片」的准备已验证到 `--prepare` 完整跑通（4 张图的项目：建目录、图片计划、`媒体/出图/*.txt`）；
  渲染只验证了参数拼装，还没在完整 04 上真出片。渲染依赖 Node 22 + Chrome（render.sh 自带检测）。
- 外部出图的对号规则：文件名是 `s02.png` 就按 id；其余按图片自己的修改时间顺序对到计划里的 id。
  拖进来时会保留原文件名和原 mtime，所以拖入先后不影响对号；但生成/下载顺序仍要和计划顺序一致。
- 放图只是落到当前项目的 `媒体/图片/`，桌面端不会替你生成图片（保留外部出图）。
- `媒体/图片/_resolved/` 是渲染前按场景重命名的安全文件名副本（HTML 里引用中文名会出问题），
  原图仍在 `媒体/图片/`；桌面端不会把 `_resolved` 当成用户图片列表。
- 拖拽跟手只在 60% 附近手动验证过，没做自动化（拖动会真实写回 YAML，测试不便回滚）。
- Jinja 只支持 `{{ var }}` 与 `{{ var | default("x") }}`；复杂模板待补。
- 外部改动只在窗口重新获得焦点时同步，后台不轮询；如果另一个进程在应用运行期间连续写同一文件，
  仍然可能出现「最后写入者赢」，动手前先 commit 更稳。
- 画布有搜索没有小地图；「适应」全图约 8%，只适合看轮廓，细看仍要缩放或搜索定位。
