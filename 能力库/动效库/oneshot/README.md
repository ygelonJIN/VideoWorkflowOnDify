# oneshot/（一次性搬运脚本，不进日常流程）

这些脚本都服务**已经做完的那一批**外部素材，留着是为了"要复现某一批"时能跑，不是日常入口。
日常进件只有两条：`render_candidates.sh` + `add_card.py --batch`，或 `admit.py scan/build/render`；
转正只有 `add_card.py` 一个入口。

| 脚本 | 干什么 | 什么时候才用 |
|---|---|---|
| `revideo_port.py` | revideo 精选 16 条的搬运与渲染 | 要重跑那一批候选 |
| `revideo_promote.py` | 同一批的转正（直写 `presets.json`，**不符合现行闸门**） | 只在复现历史时用，别拿它加新卡 |
| `revideo_sweep.py` | revideo 全量 231 条清点与渲染 | 要重新清点上游 |
| `build_gltrans.py` | 把 gl-transitions 的 `.glsl` 编译成可渲包 | 复活双图 shader 转场时（那套已整族删除，见 `来源台账.md` §四） |
| `intake.py` | gl-transitions 专用进件：`keep` 直接写表并搬片进 `全卡审阅/` | 只用于 gl 包；**新卡别走它**，闸门在 `add_card.py` |

几条约束照旧：候选只落 `样片/待筛/<批次>/`；`全卡审阅/` 只收通过件；跑完把批次目录删掉，结论写进
`来源台账.md`。
