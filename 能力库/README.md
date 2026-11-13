# 能力库索引

`能力库/` 只保存以后还会反复使用的长期资料，不保存项目状态、操作入口、运行产物或临时输出。

## 当前有效资料

| 文件或目录 | 职责 |
|---|---|
| `项目文档/用户输入事实与合规规则.md` | 任意主题通用的输入事实、CTA 和禁用表达 |
| `项目文档/内容选题与去重规则.md` | 选题模式、单条视频边界、去重规则 |
| `项目文档/视频需求与质量标准.md` | 视频需求、尺寸、结构、布局、字幕、动效和质检 |
| `工作流提示词/` | Dify YAML 中提示词的可读镜像。黑帧版（04）按环节拆开：`视觉定调提示词.md`（H01D，隐喻/色彩/字体/材质/光/纵深/节奏/摄影设定与 `:root` 令牌）、`图像计划提示词.md`（H01P，全片摄影设定 `prompt_prefix`；逐屏决定 `role`：full / inset / portrait / texture / html，有图的写可拍摄英文 prompt，无图的写 html_brief）、`组件语法提示词.md`（H01C，形语法/组件族/状态语言/`data-anim` 命名）、`转场设计提示词.md`（H01T，逐切点转场规格）、`背景系统提示词.md`（H01G，背景层 css + js）、`HTML骨架提示词.md`（H01S，只落结构契约与槽位）、`场景单屏提示词.md`（H02S，迭代节点逐屏调用：按 role 和 `composition` 排一屏的照片/HTML 背景与标记；旧的四组版 `场景组A-D提示词.md` 只对应 `Dify工作流/归档/04_黑帧口播_分组生成_分组版备份.yml`）、`屏内动效提示词.md`（H02SM，迭代内逐屏调用，只写这一屏的 GSAP；旧的整片版 `动效脚本提示词.md` 已作废）、`转场脚本提示词.md`（H02T，只写页间交接 GSAP）、`动效计划提示词.md`（A10，元素级动效计划）。数字人版（01，未迁移）：`HTML骨架提示词_有数字人.md`、`场景组A-D提示词_有数字人.md` |
| `动效库/` | 模型可选的动效能力编号（`能力卡.md`）与展开代码（`presets.json`）。H02SM 只能按编号实现动作；运行时是 `成品/workflow_runtime/assets/vendor/motion-kit.js`，渲染前由 `sync_video.py` 自动注入 |
| `画面工艺/` | 画面与声音的工艺参考（讲解图形、动效图形、风格化、模拟、角色、三维、声音、卡点）；不进提示词、不约束模型方向，供人工查阅和调优 |
| `工作流代码节点/` | Dify YAML 中 Code 节点的可读镜像。黑帧版（04）：`split_scene_groups_black_frame.py`（H00，均衡分组 + 动效切片，不再按序号分配版式/动效槽位）、`normalize_image_plan.py`（H01PV，图像计划归一化 + role 校验 + 漏屏补 HTML 背景 + 精简版 `image_brief_json`）、`normalize_transition_plan.py`（H01V，转场规格归一化）、`split_background_spec.py`（H01W，拆背景 css/js）、`expand_motion_plan.py`（H02SX，把判断 JSON 按编号展开成本屏脚本）、`merge_screen_motion.py`（H02SK，把本屏 HTML 与脚本合并）、`merge_scene_groups_black_frame.py`（H03，按分镜去重/校正 sentence_ids、注入 `data-voiceover` 后合并 + 动效/转场双槽位 + 报告）。数字人版（01）仍用 `split_scene_groups.py` / `merge_scene_groups.py`；HTML 校验和 A16 批准包按完整版/黑帧版分别镜像 |

旧文件（不在 04 链路中，只作历史参考）：`黑帧口播视频编排提示词.md`（单节点版）、`HTML批量草稿提示词.md`。

## 输入提炼层（所有 Workflow 共用）

`A01 → A02 → A03` 现在会产出 `brief.distill`，把任意形态的输入（聊天记录、会议纪要、文章、语音转写、清单、碎片想法）先压成"一个主张 + 支撑它的论点 + 证据"（条数不设配额）：

| 字段 | 含义 |
|---|---|
| `source_form` | 输入形态，用于判断是不是素材 |
| `thesis` / `thesis_source` / `thesis_type` | 一句话主张、来源、类型 |
| `arguments[]` | 条数由素材决定；每条含 `claim` / `evidence` / `support` / `strength` |
| `counterpoints` | 需要正面回应的相反说法 |
| `dropped` | 被丢弃的类别（寒暄、重复、跑题等） |
| `open_questions` | 素材没讲清、成稿不得编造的点 |

下游 `A04（论点排序）→ A06（按论点写口播）→ A07（拦流水账/照搬/漏论点）→ A08（按论点分镜）` 全部以 `distill` 为脊柱。改这条链时，`结构化活动输入提示词.md`、`内容策略提示词.md`、`口播文案提示词.md`、`口播自动扩写修订提示词.md`、`分镜导演提示词.md` 和对应 Code 节点镜像必须一起改。

## 不属于本目录的内容

| 内容 | 正确位置 |
|---|---|
| AI 维护和同步规则 | 根目录 `AGENTS.md` |
| 项目总览和操作命令 | `经验文档/使用说明.md` |
| Dify 导入、输出和故障说明 | `Dify工作流/使用说明.md` |
| 当前项目说明和成片 | `成品/333/` |
| 通用运行模板和工具 | `成品/workflow_runtime/` |
| 生图脚本与环境变量 | `成品/workflow_runtime/scripts/generate_images.py`、`经验文档/使用说明.md`「真实图像」节 |
| Dify 原始 TXT、JSON、HTML 和响应 | `成品/Dify输出/` |

## 修改 Workflow 时

按根目录 `AGENTS.md` 的同步表更新 YAML、提示词镜像、Code 节点镜像和相关说明，禁止只改其中一层。

## 已合并、待人工删除

以下旧资料已合并到通用规则，执行删除命令前会暂时保留：

- `AGENTS.md`
- `项目说明.md`
- `视频生产需求总结.md`
- `项目文档/视频质量诊断与提升标准.md`
