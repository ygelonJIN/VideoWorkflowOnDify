# 视频工作流桌面端

本地执行 Dify DSL、看画布、跑运行台、管产物。**YAML 仍是唯一真源**：这里的引擎直接读
`../Dify工作流/*.yml`，不导入数据库、不改格式。

## 能干什么

| 区域 | 现在的能力 |
|---|---|
| 引擎 | 读 `../Dify工作流/*.yml`，按变量池执行 start / llm / code / if-else / template-transform / end，输出 trace；容器节点 iteration（含 `is_parallel`）/ loop / assigner / *-start 都支持 |
| 画布 | 按 DSL 坐标画节点与连线；加节点（Code / LLM / if-else / 模板 / HTTP / End，自动连边）、删节点（连带删边）、连线模式、点连线删除；拖动松手才落盘 |
| 编辑 | 检视器直接改提示词/代码，**只写回原 YAML**（注释、缩进、块标量、文件末尾换行逐字保留）；多消息节点按条编辑；**镜像同步已退役**（2026-11-16），不再往 `能力库/` 写副本 |
| 运行 | 运行台在画布右栏、详情下方（可收起），实时显示节点状态与输出值（超 4000 字符截断并注明）；可手动停止（节点间立即停，模型请求/子进程会中断，已完成结果保留）；**从选中节点重跑**（右侧详情「从此节点重跑」）：把该节点之前已成功的 LLM/代码节点输出直接喂回，不重新请求，容器节点可当起点、容器内部节点不行 |
| 输入 | 按 start 节点声明的变量动态生成输入抽屉，字段类型/选项/必填/最大长度都读 YAML；留空沿用 fixture |
| 产物 | 列出 `成品/` 下的项目与文件；文本/JSON/字幕就地预览，HTML 走内嵌 iframe，图/视频/音频内嵌播放（`wfs-file://` 带 Range），任何文件可交系统应用打开 |
| 设置 | 顶栏「设置」改 API Base / 模型 / 协议 / Key，写 `桌面端/.env`（600、gitignored）；Key 只写不读，界面只显示末四位 |
| 模型 | YAML 里的 `model.name` 只是给 Dify 导入的声明；本地执行统一用「设置」里的模型。卡片只显示节点 id，详情里写明运行时模型 |
| 布局 | 画布占满左栏全高，右栏是详情 + 运行台；最小窗口宽 860，窄窗口顶栏折成两行、顶栏信息让位 |
| 编辑手感 | 撤销/重做（每步前留快照，最多 50 步）；滚轮缩放上限 300%、下限按全图适配 ×0.4；打开先给 60%；详情可整栏收起（连运行台一起让出），运行台也能单独收起；所有自绘下拉点别处/按 Esc 收起 |
| 外部改动 | 顶栏「重载」按钮直接重读磁盘上的 YAML（不看 sha1）；切窗口时也会比对 sha1 自动重载并提示 |

下一步：打包 .app；外部改动升级成常驻监听；完整 04 用真模型跑通（现在可在应用内「设置」填 Key）。

## 目录

```text
桌面端/
├── electron/            # 主进程、preload、本地引擎桥（IPC 与 HTTP 壳共用 core.mjs）
├── renderer/            # React 界面（画布 / 详情 / 运行台 / 出片 / 产物），构建产物在 dist/
├── src/engine/          # DSL、变量池、模板、LLM、Code、调度器、trace
├── src/cli.ts           # 命令行入口
├── test/                # node:test 用例
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
npm test        # tsc + node --test
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

## 怎么自测

```bash
npm test          # DSL / 模板 / Code / 端到端 stub / iteration / loop / 写回 / 结构编辑 / 手动停止
npm run typecheck
npm run smoke     # 隐藏窗口加载 04，检查 bridge 与节点/边数量
WFS_PROBE=1 npm run app   # 探针：选中、缩放、收起、产物切换、输入抽屉、图片落盘
```

验收只看这三条是否全过；具体某次复测的数字不进文档（节点数与边数以 YAML 为准）。

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
