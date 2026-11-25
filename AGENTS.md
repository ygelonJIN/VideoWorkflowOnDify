# 视频工作流

## 读取规则
- 要改任何一层（提示词 / Code 节点 / 卡 / 检查器 / 渲染脚本）之前 → 先读 `经验文档/设计原则.md`。
- 分不清"编号 / 能力卡 / 样片 / 源码"在哪 → 先读根目录 `动效能力总览.md`。
- 动 Workflow、提示词、Code 节点 → `经验文档/使用说明.md` 和 `能力库/README.md`。
- 动视频质量、字幕、布局、渲染规则 → `能力库/项目文档/视频需求与质量标准.md`。
- 选题、去重、对外内容合规 → `能力库/项目文档/用户输入事实与合规规则.md`。
- 导入 Dify、节点报错、变量对不上 → `Dify工作流/使用说明.md`。
- 跑完不对：黑屏、静帧、音画不同步、字幕错位、整屏空白、输出残缺 → `经验文档/事故排查.md`。
- 外部包渲出来的候选片全黑/静止/零时长 → 同上「进件候选片渲染」一节。
- 出图、图片没生成、即梦出了图要往项目里丢 → `经验文档/生图与图片链路.md`。
- 加 / 删 / 改一张卡、改选择层、动效"没生效" → `经验文档/能力层架构.md`，再看 `经验文档/动效与能力卡.md`。
- 要把外部包搬进能力库（多来源、批量进件、待筛转正）→ `经验文档/能力层架构.md` 的「进件流水线」一节。
- 查某个编号的来历、能不能提、删过没有 → `能力库/动效库/来源台账.md`。
- 处理具体项目 → `成品/项目状态.md`，再看 `成品/<项目>/项目说明.md`。
- 有一条沾边就读；判断不了就把 `经验文档/` 全读。

## 是什么
- Dify 视频工作流仓库：可导入的 Dify Workflow + HTML 视频运行时。**提示词与 Code 节点只在 YAML 里，不留镜像副本。**
- 仓库根就是工作区根，会话在这一层开；本文件会被 AI 对话自动读取。
- `04_黑帧口播` 是默认生产线；`01_有数字人` = 04 + 右上角数字人小窗（同一条两段式链路，多一个 `H01Z` 注入小窗、出口换 HeyGen）。两份共用能力层，改卡两层一起变。

统一处理入口：

```bash
bash /Volumes/TUF ESD-T1A Media/视频工作流/runtime/tools/run_dify_output.sh 项目名
```

## 口径（唯一真值，其他文档只写指路）

这几条以代码为准，文档里不再各写一套。改之前先 `git grep` 一下，别再抄进第二处。

| 事实 | 真值 | 真值在哪 |
|---|---|---|
| 页间转场几张 | **15 张（`PT01–PT15`）**，`kind` 全在 `__ptList` 里 | `presets.json` + `sync_video.py` 的 `window.__ptList` |
| 照片 `role` 取值 | **`band` / `inset` / `portrait` / `thumb` / `texture` / `html`**；`large` 等同 `band`；`full`、`cover`、`background`、`photo` 一律降级成 `band` 并告警 | `S2N` 的 `ROLE_SIZES` |
| `full` / `black-frame` / `html-only` | 是**渲染模式名**，不是 `role`；`full` 指数字人线，不是"照片铺满" | `视频需求与质量标准.md` §3 |
| 时长 | **没有目标时长**，文案写多长成片就多长，以真实口播为唯一主时钟 | `视频需求与质量标准.md` §5 |
| 去重 | 只有 `script_hash` 一个指纹在跑 | `S1N` 的 Code 节点 |
| 界面元素 | 只能取编号组件（`U*`）；模型只给编号+槽位文字，不写 HTML | `S2` 规格 + `R2` 槽位渲染 + `component_slots.py` |
| 组件动效配对 | 组件卡 `provides`、动效 `needs`；`motion_by_component` 由 `gen_catalog` 算，`S2N`/`R1` 再验 | `contracts.py` + `gen_catalog.py` |
| 状态卡落点 | 卡 `needs` 里的锚点（如 S36 的 `num`）必须由目标组件 `provides`；`R1` 把 `sel` 绑到锚点元素，缺锚点就丢卡。S04 勾选 2026-11-23 起 `needs=check`、`needs-work`（没有组件提供 check，先停用） | `gen_catalog` 的 `card_needs` + `S2N`/`R1` |
| 状态卡能改什么 | `writes=content`（会 `textContent`/`innerHTML`）的卡**只能落文字节点或组件声明的锚点**；没声明锚点的 `overlay` 卡也不许落组件根。落错就丢弃并重跑 `S2` | `gen_catalog` 的 `state_meta` + `S2N`/`R1` |
| 假交互 | `trigger=true` 的卡（点击/勾选/拖动/切换/状态灯）必须在同屏配一条 `then`（同一目标），没有 then 整条丢弃：只在说「发生了一件事」而没有结果，不算动效 | `state_meta.trigger` + `S2N`/`R1` |
| 装饰与离场槽 | 每屏 `deco` 0–1（`motion.decoration`，落本屏已有元素）、`out` 0–1（`motion.exit`，固定在切点前 0.5 秒，不许动标题）；`out` 不占内容槽位 | `S2` 规格 + `R1` 的 rank/out 分支 |
| 标注语义 | `deco` 是手绘标注不是装饰：叉/划掉=否掉一个具体做法，括号/框=补一句旁注或归组，圈/荧光/下划线=强调一个关键词，进度条/数值条=有真实数字（`state_meta.requires_number`）。**标注不许落标题**，全片 ≤ ⌈屏数÷3⌉ 且相邻两屏不都写 | `catalog.motion_cards` 的 `use`/`avoid` + `S2N`/`R1` |
| 选卡看语义 | `catalog.motion` 只给编号；**每张可选卡都带卡级描述**——动效卡在 `motion_cards`（name/use/avoid），背景/组件/转场在各自条目（note/use/avoid）。`use` 只写「什么时候选」、`avoid` 只写「什么时候别选」，实现说明不进卡。加卡、加族漏发会被门禁点名 | `gen_catalog` 的 `card_desc` + `check_catalog_sync` 的覆盖断言 |
| 全片用量 | 同一编号 ≤2 次；组件 ≥4 种、同一组件 ≤2 次；最近三支用过的编号写进 `catalog.recent_usage` 喂给模型 | `gen_catalog` + `motion_ledger.py` + `S2` 提示词 + `S2N` 点名 |
| 首屏背景 | 第一屏只能从 `catalog.first_screen_background` 选；最近 3 支同编号 + 上一支同 family 已排除 | `gen_catalog` 现算 + `S2` 提示词 |
| 组件槽位 | 组数由 `texts` 给到的**完整组**决定；不补空串、不满组整组丢 | `S2N` 的 `fit_component_texts` |
| 组件落哪一层 | 组件默认进 840 文字栏；卡上写 `span: "full"` 的进 1080 通栏层 `.scene-ui`，版面给它留一条横带（`data-ui-full`） | `gen_catalog` 的 `COMPONENT_TPL.span` + `R2` + `layout_composer` 的 `ui_band` |
| 组件根唯一 | 模板有多个顶层节点的片段由 `R2` 包一层 `.ui-comp-row` 再挂 `data-anim`；`R1` 的"显示这一层"打在根上 | `R2` 的 `top_level_count` + `R1` 的 `layer_sel` + `components.css` 的 `.ui-comp-row` |
| 背景可绑定 | 目录里有哪张就能绑哪张（`catalog.background`），不再写死 B23–B39；目录外的编号丢弃并点名，不塞默认卡 | `R1` 的 `CANVAS_BG` + `S2N` |
| 照片入场 | **只能选 `catalog.motion.entrance_media`**（`gen_catalog` 从 `entrance_block` 派生的那格：只动根节点、不依赖子结构和元素自带属性）；列表为空就留空，`R2` 给默认淡入 | `gen_catalog.media_entrance_ok` + `S2N` + `R1` |
| 照片槽的压暗 | 是 `.media` 的子元素 `.media-scrim`，**不是槽上的 `::after`**——空槽不许露板，装饰要跟内容同透明度 | `R2` 的 `media_html` + `layout_composer.build_scene_css` |
| 状态卡 | `state_*` 卡不许给**根元素**设隐藏起始态（动子元素要声明 `child`）；一屏一个 role / 一个组件 `anim` 名只留一条 | `add_card.validate` + `S2N` 去重 |
| 标题换行 | **`R2` 按标点切 2 段写死 `<br>`**，`solve_scale` 再按「最长那一行」反算字号（840/8=105→100 档） | `R2` 的 code + `layout_composer.solve_scale` |
| 屏内动作时刻 | 顺序由 `role` 槽位定（title → 辅助 → body → media → deco（跟在它自己的目标后面）→ 组件 → state；`out` 不占槽位、固定切点前 0.5s）；时刻由 `__slot` 按真实屏长铺开：有余量时按**等间隔**排、末位收在切点前 **2.0s**（`window.__slotTail`）；挤不下时才退回按收尾时刻等距。`beat` 只在槽内微调。每屏收完到切点的静止统一 2.0s | `R1` 展开成 `at(slot(...))` + `sync_video` 的 `window.__slot` |
| 页间转场几刀 | **N 屏必出 N-1 条 `__pt`**：`R3` 按切点表逐刀生成，kind 从能力目录派生；模型只给偏好，漏的按本片转场族补齐并点名重跑 `S2` | `R3` 的 `build_transition_script` + `pt_catalog` |
| 照片落版 | 全部 840 通栏横带，高度 `band` 600/420/300、`portrait` 520、`inset` 360、`thumb` 300、`texture` 620；**只有 `full` 满屏**，而 `full` 在 `S2N` 就归一成 `band`，所以生成端写不出满屏照片 | `R2` 的 `FIXED_H` / `slot` |
| 场景脚本外壳 | `<script>` + `push(function(timeline, at){` + `});` **只由 `R2` 生成一次**；剥壳、丢卡、补入场都在 body 层，永远碰不到外壳 | `R2` 的 code |
| 卡片字号 | `.ui-card h3` = 本屏主字号 × 0.5、`p` = × 0.3（`--ui-card-title` / `--ui-card-body`）；`--ui-scale` 只给其它组件用 | `layout_composer` + `components.css` |
| 组件栅格宽度 | 栅格列等分且永不越栏（`minmax(0,1fr)`）；`ui-cell` 按最长文字反算 `--ui-scale`（下限 1.55）；`ui-card` 标题按列宽反算 `--ui-card-title`（下限 34px）；U54 标签/值分两行 | `layout_composer.ui_grid_scale_cap` / `ui_card_title_cap` + `components.css` |

## 目录与职责（唯一一份目录表）

| 路径 | 职责 |
|---|---|
| `动效能力总览.md` | 先看这页：编号 / 能力卡 / 样片 / 源码各在哪 |
| `Dify工作流/*.yml` | 实际导入 Dify 的唯一运行版本；`归档/` 只作历史备份 |
| `能力库/动效库/presets.json` | **唯一源**：编号、名字、`role`、参数、代码、来源 |
| `能力库/动效库/能力卡.md`、`组件卡.md` | **生成物**，由 `gen_catalog.py` 从 presets 生成，不要手改 |
| `能力库/动效库/来源台账.md` | 来源、结论、删过的编号、当前缺口、许可、`src` 标注规范 |
| `能力库/动效库/样片/全卡审阅/` | 每张卡一个 3 秒确认片（按族分目录）；进件候选只在 `样片/待筛/<批次>/` |
| `能力库/动效库/oneshot/` | 一次性搬运脚本（revideo / gl-transitions / mermaid / 旧 intake）。复现某一批才用，日常进件不走这里 |
| `能力库/项目文档/` | 任意主题通用的输入事实、内容规则、视频质量标准；不保存固定产品故事 |
| `经验文档/` | 怎么做、怎么排查、踩过的坑。一个领域一篇，新经验先并入已有文件 |
| `成品/<项目>/` | 正式项目：成品与项目内运行脚本，不作为新项目模板直接修改 |
| `成品/试验/<项目>/` | 没上线的试验、`-check` / `-rebuild` 副本、结构/图片链路的测试项目 |
| `成品/失败项目/`、`成品/项目备份/` | 渲染失败与 `--replace` 的自动备份，各自带 README 写保留策略 |
| `runtime/` | 可复用模板、脚本、GSAP 运行时、工具，钉死的 HyperFrames CLI（`vendor/`，`node_modules` 不进仓库）。只读，不往里写运行结果，也不放任何私人配置 |
| `成品/Dify输出/` | Dify 原始 TXT / JSON / HTML 和 HeyGen 响应 |
| `成品/HTML预览/` | 只有 `html_document` 的输出（浏览器预览，不渲染 MP4） |
| `成品/项目状态.md` | 在跑、待重跑、已归档的项目清单（只列正式项目） |
| `能力库/动效库/usage_ledger.json` | 生成物：每支成片用过哪些编号、首页背景；`motion_ledger.py` 扫 `成品/*/index.html` 重算。只作报告，`gen_catalog` 每次生成时现算 `recent_usage` / `recent_openers` |
| `桌面端/` | 本地跑 Dify DSL 的 Electron 应用（独立 npm 工程，`node_modules` 不进仓库）；YAML 仍是唯一真源 |

## 铁律

### 加一张卡：一条命令

**只改 `presets.json` 是不行的，但也不需要再手改七八个文件。** 派生全部由脚本做：

```bash
python3 能力库/动效库/add_card.py 新卡.json        # 校验 + 写入 + 生成 + 同步 + 查样片
python3 能力库/动效库/remove_card.py T27            # 删卡，对称走同一条链
python3 能力库/动效库/check_catalog_sync.py         # 四层一致性门禁，必须过
```

`add_card.py` 会拒绝这些情况：`role` 不合法、`code` 里的 `{{x}}` 在 `params` 里没有默认值、
背景卡缺 `bg_family`/`keywords`/`note`、组件卡用了 `components.css` 里没有的类、PT 卡的 `kind` 不在 `__ptList`、
**没有样片的卡**（规则：没样片不入表；`--render` 只是先把候选片渲到 `样片/待筛/` 再停，不转正）、
**状态卡会改写目标文字却没声明 `needs=text` 或锚点**、以及**声明了 `trigger` 却没有可落元素、声明了 `exit` 却不是 `decoration`/代码里没有 `opacity:0`**。
能力契约也在这里拦：组件卡缺 `provides`、`component_motion` 卡缺 `needs` 锚点 / `target`、
或者算下来没有任何组件能接（没有宿主），同样拒收。

各层谁生成谁，见 `经验文档/能力层架构.md`。

**一批卡（整批外部来源）走「出候选片 → 人审 → 转正」三步，别一张张等**：

```bash
bash 能力库/动效库/render_candidates.sh <批次> 本批.json   # 只落 样片/待筛/<批次>/
#   ↑ 人看片、点名通过后，写 样片/待筛/<批次>/通过.tsv（编号 + 名字）
python3 能力库/动效库/add_card.py 本批.json --batch <批次>  # 写表 + 把审过的片搬进全卡审阅
```

候选片**不许**直接落 `全卡审阅/`。`add_card.py` 拿不到 `通过.tsv` 点名就拒收，且表不动
（`render_candidates.sh` 只写待筛，`add_card.py` 才是唯一能往 `全卡审阅/` 放片的入口）。
已在表里的卡重渲仍写 `全卡审阅/`：`bash 能力库/动效库/render_cards.sh B49 B51`。

### 加卡顺序：先待审，审过才转正

**任何新卡（外部搬来的、自己新写的）都不许直接落进 `样片/全卡审阅/`。**
候选先渲到 `样片/待筛/<日期>-<批次>/`，人工看完点名通过，才 `add_card.py` 转正、片才进 `全卡审阅/`；
没通过的删卡删片，审完 `待筛/` 清空。`全卡审阅/` 只收通过件。

### 出片优先：结构由生成端保证，检查只做诊断

**内容不允许把渲染拦死**。硬失败只留给环境问题（缺 Chrome / Node / HyperFrames）。做法不是"渲完再修 HTML"，而是**让生成端从一开始就写不出坏 HTML**：

1. `S2` 一次输出**全片规格 JSON**（每屏 `bg` / `media` / `copy` / `components`（编号+槽位文字）/ `state`（可带 `then`）/ `deco` / `out` / `transition`，**没有 `css`、没有 HTML**），由 `S2N` 归一成 `motions`；
2. `R2` 用固定模板 + 组件槽位把规格渲染成唯一合法的 `<section>`（标签、属性、槽位、作用域 CSS 都由代码保证）；
3. 模型给的组件片段先过标签平衡检查，不平衡就丢弃并记 warning；`copy` 是纯文本，直接转义。

每一步只做自己的事、**不用默认值顶替**：口播不合格退回 `S1R` 重写，规格对不上退回 `S2`，缺屏不合成、不换卡、不猜转场。

本地检查器（契约/排版/时间线/构图）只写 `诊断/检查结果.txt`，**不阻塞渲染**；`STRICT_RENDER=1` 才是排查用的旧行为。

**禁止**新增"不达标就 `exit 1`"的内容检查，也禁止再加"渲染前改 HTML"的补救层——结构正确是生成端的责任。

**治本口径**（什么叫治本、六类必须拒绝的替代品、诊断的合法出口）见 `经验文档/设计原则.md` §三。一句话判断：**改完之后，同样的输入再跑一遍，还会不会出同样的错。** 会就是没改完。

### 修改必须同步

| 修改内容 | 必须同步检查 |
|---|---|
| `presets.json` 的字段、`role`、参数 | 跑 `add_card.py` / `remove_card.py` / `gen_catalog.py`，再跑 `check_catalog_sync.py` |
| 能力目录、选择层、`H00` 的 catalog | `gen_catalog.py` 生成，不要手改 YAML 里的 CATALOG 块 |
| 输出变量、字段或 JSON 结构 | `Dify工作流/使用说明.md`、`经验文档/使用说明.md`、`runtime/tools/` |
| 04 的链路节点（骨架 / 单屏规格 / 落版 / 检查） | `Dify工作流/01_有数字人完整视频工作流.yml` 的对应差异块，清单在 `经验文档/能力层架构.md` §七 |
| 媒体、字幕、布局或渲染规则 | `runtime/`、`能力库/项目文档/视频需求与质量标准.md` |
| 图像计划、生图 prompt 规则、图片契约 | `runtime/scripts/generate_images.py`、`runtime/tools/build_black_frame_project.py`、`能力库/项目文档/视频需求与质量标准.md` |
| 新增或重命名节点 | `能力库/README.md` 和相关说明 |
| 本地命令或目录职责 | 根目录 `AGENTS.md`、`经验文档/使用说明.md` |
| `admit.py` / `adapters/` 的进件流程 | `经验文档/能力层架构.md` §三之二、`能力库/动效库/样片/README.md` |

提示词与 Code 节点直接改 `Dify工作流/*.yml`，不在别处留副本。禁止只改说明文档而不改实际 Workflow。

### 视频制作（v2，2026-11-13 生效）

- 整片至少一张真实照片；无照片的屏靠排版撑住（`role=html` + `data-visual="html"`）。图像计划逐屏决定 `role`，六个取值见本文件「口径」表。
- **每屏一个主运动**，其余是次级；相邻两屏的主运动不能是同一张卡。切点前要有收束（离场或自带回位），**不强制用 X 卡**。
- **数字人小窗（full 线）固定在右上角**：270×480、距顶 120、距右 44，几何写在 `H01Z` 的 `--pip-*` 里，版面按它自动避让；提示词不许另写一套位置。黑帧线零占位。
- **字由 HTML 承载**：canvas 里不放文字。
- **动效由时间线驱动**，任意一帧可 seek 复现；禁 `requestAnimationFrame`、`performance.now`、`Math.random`、`yoyo`/`repeat` 无限循环（按 `t` 的周期函数不算循环）。
- 静态图不能当动效镜头，每屏必须有语义相关的元素级动画；产品 UI 用编号模板组件，示例数据标"场景演示"，不得冒充真实产品截图。
- 构图逐屏不同（`family` / `text_zone` / `align` / `scale`），相邻两屏不得同族；渲染前跑 `check_composition_variation.mjs`，要拦截加 `STRICT_COMPOSITION=1`。
- **模型写数据不写实现**：只给编号 + 目标 `data-anim` 名 + 时序；坐标、目标框、路径一律由场景 HTML 给。卡不测量布局，唯一例外是指针类卡（临时显示隐藏场景量一次再还原）。
- **技术契约以 `check_html_contract.py` 为准**：canvas 固定 1080×1920 且不得按 `getBoundingClientRect` 改尺寸、canvas 由时间线驱动（`bgkit.bind` 的哑 tween 读 `timeline.time()`，`hf-seek` 兜底；绘制不挂 `onUpdate` 回调）、canvas 与照片不许同屏、字幕由本地注入。**机器拦得住的细则这里不复述**，去改检查器而不是抄一份文档。

**交付前**：检查时长、音画同步、响度、字幕对齐和运动量；若提供 `npm run quality:video`，必须执行并通过。

### 修改后的最低验证

1. 用**导入时同一份解析器**解析全部 YAML：`node runtime/tools/check_dsl_parse.mjs`。
   `yaml.safe_load` 过了不代表能导入（2026-11-20 踩过，见 `经验文档/事故排查.md`「导入 Dify 报 YAML 解析失败」）。
2. 改过的提示词和 Code 节点确实写进了对应 YAML（`yaml.safe_load` 能解析、节点里找得到）。
3. Python 文件执行语法编译，Shell 文件执行 `bash -n`。
4. 动了能力层就跑 `python3 能力库/动效库/check_catalog_sync.py`。
5. 搜索旧项目名、旧节点名、旧命令路径和旧 Worker/Webhook 表述。
6. 检查 `333` 成片、字幕、媒体身份和 `Dify输出/333*` 未被误删；改了构建流程至少运行 `--help` 或无副作用的 smoke test。

### 清理

- 保留 `333`、`runtime/` 和 `Dify输出/333*`。
- 正式字幕只放在项目自己的 `字幕/` 目录。
- 不把运行结果写入 `runtime/`。
- 删除历史资料、备份或外部分发包前，先确认已合并有效内容并明确告知不可恢复。

## 经验索引

### 经验文档/设计原则.md
- 什么时候读：改任何一层之前；想加校验、想加默认值、想把"不通过就停"写进流程的时候
- 包含：治本口径（不校验/不拦截/不兜底、三步归层、六类替代品、环境是唯一例外、诊断只记录和点名）、不兜底清单、结构在生成端消灭、卡必须 seek 安全、新逻辑该放哪一层、自检 5 问
- 不用读：只是调一个参数值

### 经验文档/能力层架构.md
- 什么时候读：加 / 删 / 改卡、改选择层、想动 `presets.json` 的字段、怀疑"卡加了不生效"、要重造某一层之前
- 包含：定义层 / 选择层 / 展开层 / 样片层四层各自由谁生成、`role` 的全部取值、照片入场派生族 `entrance_media`、状态卡不许重置根元素、**状态卡锚点 `card_needs`（S36 落 `num`）**、**状态卡落点与因果 `state_meta`（`writes`/`requires`/`trigger`，触发卡必须配 `then`）**、**每屏六个位置与 `deco`/`out` 槽**、**跨片用量台账 `recent_usage`**、**卡级描述（动效卡 `motion_cards` / 背景·组件·转场条目里的 note/use/avoid）与标注配额**、**组件槽位按完整组切、不补空串**、**组件 `span: full` 落 1080 通栏层**、**背景可绑定集合从 `catalog.background` 派生**、一条命令加删卡、四层门禁查什么、`H00` 选择层 / `R1` 动效展开 / `R2` 槽位落版各自读哪个字段、01 = 04 + 小窗（含两边的同步清单）、进件流水线 `admit.py`（scan/build/render/keep/drop、适配器、编号分配、筛完即清）、审阅的三条（样片才是审阅物 / scan 判不能提就别 build / 外观片不留文件）、来源标注只认 `src` 且必须带前缀
- 不用读：只是对某张卡的参数不满意

### 经验文档/使用说明.md
- 什么时候读：跑一次完整流程、导 Dify、重渲染、改配置、加新项目之前
- 包含：当前方案、输入怎么进、目录结构、推荐入口、从文件处理、黑帧 TTS、渲染器 CLI 与 vendor、字幕、检查策略、Dify 导入、模板边界
- 不用读：只改一句提示词、只调样式

### 经验文档/事故排查.md
- 什么时候读：渲染失败、黑屏或静帧、音画不同步、字幕错位、整屏空白、Dify 输出残缺、页面只剩零点几秒
- 包含：生成端结构保证与诊断清单、**最后一屏没背景 / 卡片空一格 / 屏上冒出数字（目录给的选择下游兑现不了）**、**导入报 YAML 解析失败（PyYAML 过了不等于能导入）**、Dify 无输出、场景没识别、输出超限、失败定位与续跑、动效/黑屏/音画不同步的五种症状、空页与闪回、时间码缺失、render slot、**进件候选片渲染的五种成因（CDN 依赖 / paused 时间轴 / composition-id 不匹配 / template 片段 / scan 判「没有可 seek 的时间轴」）**、canvas 画面、页面节奏锚定、`window.__cue`、**动作时刻错位 / 转场吃掉入场 / 整屏 script 语法错**、成片复核工具、跑外部检查器的两条前提（Node ≥ 22 / Chrome `--no-sandbox`）、**数字人版（01）小窗与图片的三条症状**、文字对比度的量测口径、已知未修
- 不用读：流程本身跑得通、只是想跑一遍

### 经验文档/生图与图片链路.md
- 什么时候读：画面要真实照片、图片没生成、改生图模型或尺寸、用即梦手动出图后要丢进项目
- 包含：图像计划（`S2N`）→ 本地生图的分工、环境变量、即梦/火山方舟、无 API 时手动出图与"按修改时间对号"规则、单独跑与构建时替换、旧项目重渲染被拦
- 不用读：图已经齐了只想渲染

### 经验文档/动效与能力卡.md
- 什么时候读：改 `motion-kit.js`、`bg-kit.js`、`components.css`、`auto-fit.js` 之后；成片动效不对、卡片没生效、渲染黑屏或静止
- 包含：运行时契约（空 tween、hf-seek、blend、workers、选择器作用域、组件逐条、`kt.split`、img 子节点、z-index、Illegal invocation、容器 `color:transparent` 连带子元素）、**状态卡改内容必须落叶子 / `out` 的 `at()` 换算 / `deco` 排序**、WebGL/shader 卡契约、`kit.anno` 手绘标注（类型表 / 逐行 Range / dashoffset 揭示 / 与旧 `kit.rough` 并存）、ping-pong seek 重放、竖屏算尺寸公式、`__pt` 页间转场、样张验证、已知问题、GSAP 插件写法、不能落在文字上的卡（`text_safe`）与动效空转的两种原因
- 不用读：加卡流程本身（那在 `能力层架构.md`）

## 文档不留过时信息（2026-11-15 定）

- 目录一旦删除，文档里**不许再留它的路径**，哪怕标注"已删除"。留下名字只会让人去找一个不存在的东西。
- 编号一旦入表，**不许再留"候选编号 ↔ 正式编号"对照表**。查卡只看 `presets.json` 的 `src`。
- 一次性素材（候选、对照、全库）用完即清，清完不改文档去列"清空了哪些"。
- 判断一条信息该不该留：**读到它的人能不能据此做成一件事**。做不到就删。
- 同一件事只写一处，其他位置写成指路。目录表只在本文件，不复制到别处。

## 禁止
- 只改文档不改实际 Workflow。
- 手改 `能力卡.md` / `组件卡.md` / YAML 里的 `CATALOG` 块：它们是生成物。
- 不调用 HeyGen API、不读取或输出 API Key，除非用户明确要求。
- 不提交 `.env`、API Key、生成产物。
- 文档里不写已删除的目录路径、已失效的编号对照。
- `AGENTS.md` 和 `经验文档/` 里不写密码、Key、客户隐私。
