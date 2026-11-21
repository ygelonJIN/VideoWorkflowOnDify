# runtime — 视频运行时（不是成片）

这里是**可复用的运行时**：构建、排版、字幕与时间线同步、检查器、渲染器都在这一层。
它跟任何一部片子无关；**删掉它，整条链路停工**（桌面端会弹 `spawn python3 ENOENT`）。

> 2026-11-21 从 `成品/workflow_runtime/` 移到仓库根。搬的理由：它跟成片无关，
> 放在 `成品/` 里会被当成"可以一起删的产物"。

## 它由什么组成

| 路径 | 是什么 |
|---|---|
| `scripts/` | 22 个：构建、排版（`layout_composer`）、字幕与时间线同步（`sync_video`）、检查器、生图、音频 |
| `tools/` | 8 个：唯一入口（`build_black_frame_project.py`、`run_dify_output.sh`、`prepare_images.py` …） |
| `assets/` | 33 个：GSAP、`motion-kit`、`bg-kit`、组件 CSS、转场 shader |
| `template.html` | 新项目的骨架 |
| `render.sh` | 渲染入口（先找仓库里钉死的 CLI，再退 `~/.npm/_npx`、`PATH`） |
| `vendor/` | 钉死版本的 HyperFrames 渲染器；`node_modules` 不在 git 里（见下面恢复第 3 步） |
| `docs/` | `项目说明.md`、`视频说明.md` 的**模板**，构建时复制进每个项目 |

## 谁依赖它

- 桌面端 `electron/core.mjs`：构建脚本路径和子进程 `cwd` 都是 `path.join(workspaceDir, "runtime")`；
- 项目里的 `render.sh`：从项目目录向上找 `vendor/`、`runtime/vendor/` 里的 HyperFrames CLI；
- 构建脚本按 `../runtime` 的相对路径取模板、脚本、资产，并复制进新项目。

## 只读约定

- 不写运行结果、不放私人配置、不放 `不推送/`；
- 改这里的 `scripts/`、`assets/` 只影响**新**项目——旧项目用的是自己 `脚本/` 的快照，
  要生效得重新构建，或把改动的文件手动盖进项目；
- `docs/` 里那两份 md 会被复制进项目，**改模板，不改项目里的副本**。

## 万一删了怎么恢复

0. 前提：这个目录要在 git 里。`.gitignore` 里原来那条泛用的 `runtime/` 已于 2026-11-21 删掉
   （它会让整目录在 git 里静默消失），搬迁之后请提交一次；
1. 已提交过就 `git checkout -- runtime`（70 个受跟踪文件回来）；
2. 未提交的改动不在 git 里：从最近的项目快照盖回来
   （`成品/<项目>/脚本/*.py`、`成品/<项目>/素材/vendor/components.css`）；
3. `cd runtime/vendor && npm ci` —— `node_modules` 不在 git 里，必须重装；
4. 验一遍：`node runtime/tools/check_dsl_parse.mjs`、`bash runtime/render.sh --help`。

删掉之后的报错长这样：桌面端点「准备项目」弹 `spawn python3 ENOENT`。
**不是找不到 python3**——是 `spawn` 的 `cwd`（就是这个目录）不存在时，Node 也报同一个错。
