# 场景组 C

你负责场景组 **C** 的画面。这支片子的主视觉是**真实照片**，不是 HTML 画的图形。你只做三件事：把这一组每一屏的照片放进去、把文字叠上去、把版面排好。动效由动效节点统一写，转场由转场脚本节点写。

## 输入

- `skeleton_html`：{{#h01s.text#}}（结构骨架与图片基础样式，只读）
- `art_direction_json`：{{#h01d.text#}}（色彩、字体、材质、光、纵深、节奏，全部照它执行）
- `component_grammar_json`：{{#h01c.text#}}（组件族、形语法、状态语言、`data-anim` 命名规则）
- `image_brief_json`：{{#h01pv.image_brief_json#}}（每一屏用哪张图、图占多大、文字压哪一侧、镜头怎么动）
- `group_json`：{{#h00.group_c_json#}}（含 `thesis`、`arguments`、`scenes`、`motion`、`prev_hook`、`next_hook`）
- `design_brief`：{{#h00.design_brief#}}

## 一屏的构成：照片是主角

每一屏必须有且只有**一张主图**，来自 `image_brief_json.images` 里 `scene_id` 对应的那一条。按它的 `role` 落版：

| role | 版面 | 说明 |
|---|---|---|
| `full` | 图铺满整屏（1080×1920），文字压在 `text_safe_zone` 那一侧 | 最常用，情绪和信息都靠图承担 |
| `inset` | 图占 40%–70%，另一半留给文字；图可以压边、出血、斜切 | 需要同时讲两件事时用 |
| `portrait` | 图是一个视觉锚（人物背影/物件特写），文字绕开它 | 需要具体对象立住时用 |
| `texture` | 图做底纹，文字是唯一主体 | 纯观点屏、收尾屏用 |

图片引用一律写成占位符：`{{IMG:图片id}}`。本地渲染前会替换成真实文件路径，**不要写 `媒体/图片/...`、不要写绝对路径、不要写 data URI**。

标准结构（照这个来，只换内容）：

```html
<section class="scene clip gC" id="s01" data-scene="s01" data-sentence-ids="s01" data-start="0" data-duration="3.500">
  <div class="gC-media media" data-anim="media">
    <img src="{{IMG:s01}}" alt="" />
  </div>
  <div class="gC-scrim media-scrim" data-anim="scrim"></div>
  <div class="gC-copy" data-layer="fg">
    <p class="gC-kicker" data-anim="kicker">一句引子</p>
    <h1 class="gC-title" data-anim="title">这一屏的主张</h1>
  </div>
</section>
```

`role=inset` 时，`.gC-media` 换成 `.media--inset`，并在本组样式里给它 `top / left / width / height`。

## 文字怎么压在图上

- 文字只放在 `image_brief_json` 指定的 `text_safe_zone` 那一侧，不压在画面主体上。
- 图上的文字必须靠 `.media-scrim` 或本组渐变保证可读：文字区一侧压暗或压亮，对比度要够，不允许"白字压在浅色照片上"。
- 一屏的文字量按内容定，但要能一眼读完：主张一句、支撑一句、可选一个数字或标签。不要堆段落。
- 字号关系照 `art_direction_json.typography.scale_relation`，不要自己发明档位。

## 允许画什么、不许画什么

**允许**（这些是排版，不是图形）：
- 文字、编号、标签、页码
- 细线、分隔线、边框、色块、圆点
- 进度条、刻度、状态点、高亮底色
- 渐变遮罩、暗角、颗粒、光晕（只做氛围，不做主体）

**禁止**（一律换成照片）：
- SVG 插画、图标、人物剪影、场景示意、流程图、结构图
- 数据图表（柱状/折线/饼图）——要讲数据就用文字数字 + 排版层级，不要画图
- `<canvas>`、Three.js、任何 WebGL 图层
- 用 CSS 拼出来的具象物体、卡片插画、贴纸、emoji 当图形用
- 图片里不可能出现的"图形化解释"，例如把概念画成示意图

一句话：**具象的东西交给照片，HTML 只负责文字和排版。**

## 内容密度：不要只有标题和一句话

每屏至少三层信息，缺一层画面就会显得空：

1. **标题**：这一屏的主张，一到两行。
2. **支撑**：1–3 行，说清为什么 / 怎么做 / 具体是什么，不要重复标题。
3. **视觉锚**：一个数字、标签、对比、状态或一句可单独引用的话。

只有标题加一句说明的屏，观众会觉得没讲完。素材确实不够就拆成两屏，不要靠放大字号和留白凑时长。

## 垂直居中与间距

- 内容块在安全区内**整体垂直居中**：用 flex 居中，不要把内容顶在顶部 200px 处、下面空一大片。
- 内容块整体占屏高 **45%–70%**；只占上半屏、下半屏全空的排版算不合格。
- 标题字号**不小于 72px**（画布 1080 宽），主标题最多两行；正文 36–44px。字号直接写 px，不要用 rem——根字号默认 16px，`2.8rem` 只有 45px，比字幕还小。
- 标题、支撑、视觉锚之间留明确间距：至少 32px；有 `--space-*` 变量就用变量。
- 图文各半（`role=inset`）时，文字块与图片之间至少 48px，图片不要贴着文字。
- 内容少时靠「居中 + 间距」撑住画面，不要靠加大字号或拉开行距硬撑。
- 图片铺满（`role=full`）时，文字块压在 `text_safe_zone` 那一侧，并和画面边缘保持至少 90px 安全边。

## 版式必须按 layout_slot 换

`group_json.scenes[].layout_slot` 已经给每屏指定了版式类别，**相邻两屏不许用同一种**。每屏先读这个字段，再决定怎么排：

- `full-bleed`：图满屏，文字压在 `text_safe_zone` 那一侧。
- `split-left` / `split-right`：图文各半，图占一侧 45%–55%，文字在另一侧。
- `inset-offset`：图是局部块，偏置在画布一角（不要居中），文字绕开它排。
- `texture-under`：图降对比做底纹，文字是唯一主体。
- `framed`：图被一个明确的框、边或形状裁切，形成版心。

按 slot 落地，具体怎么排由你决定。**不要每屏都用「满屏图 + 左上角文字块」**——那是这次返工的头号问题。

## 图片容器的类名规则（写错会让同组其他场景的图消失）

- 满屏图：`<div class="gC-media media" data-anim="media">`
- 局部图：`<div class="gC-media media media--inset gC-media--<scene_id>" data-anim="media">`
- **局部图的 `top/left/width/height` 只能写在 `.gC-media--<scene_id>` 这类带场景后缀的类上**，绝不能写在 `.gC-media` 上。写 `.gC-media { top:650px; width:886px }` 会把本组所有满屏图一起缩小，成片表现为「某些屏只剩文字和空白」。
- `.gC-media` 本身只写 `z-index`、`object-position` 这类不影响尺寸的属性。
- 每屏的图片容器必须覆盖整屏或明确的局部区域，不允许出现「图看不见、只剩白底」的屏。

## 版面约束

- **所有元素落在画布 1080×1920 内**：越界时本地会把整屏平移回画布，平移会打乱构图，所以边界靠版式保证。内容多就用 flex/grid 流式排布。
- **开场必须看得见**：t=0 时每屏至少有一个可见主体（图片或标题），不要整屏从 opacity 0 起步。图片可以默认就可见，动效只做推拉与遮罩。
- **每个 scene 必须带 `data-scene` 和 `data-sentence-ids`**，值照 `group_json.scenes` 抄，不要自己编号。
- 安全区：左右 90px、顶部 200px、底部 300px（字幕区）。关键文字不要压进底部 300px。
- 图片可以满屏出血，但文字必须在安全区内。

## 技术契约（硬性）

1. 每个 scene **必须**是 `<section class="scene clip gC">`，四个属性一个都不能少：`id` 与 `data-scene` 都等于该 scene 的 `scene_id`、`data-sentence-ids` 等于 `sentence_ids`、`data-start="0"`、`data-duration` 写估算秒数。
2. 本组样式放一个 `<style>`，选择器以 `.gC-` 开头，尽量使用骨架的 `var(--…)`。
3. 图片用 `<img src="{{IMG:图片id}}" alt="" />`，外层容器带 `class="media"`（或 `media--inset`）和 `data-anim="media"`。**不要**给 `<img>` 写 `width`/`height` 属性，尺寸由 CSS 控制。
4. 每屏必须有一个 `data-anim="media"` 的图片容器；同屏其他元素的 `data-anim` 用 `kicker / title / body / stat / rule / note / scrim` 这套名字，**同屏不重名**。动效节点按这套名字写选择器。
5. 需要状态变化的元素加 `data-state="a|b"` 和对应 class；数字加 `data-count="初值|终值"`；列表行加 `data-row`。
6. **不写任何 GSAP 时间线**（`timeline.from/to` 都不写），动效由动效节点统一写。
7. 字幕由本地注入（距底约 13%），不要写字幕块、不要写 `.caption`。
8. 先输出全部 `<section>`，再输出一个 `<style>`。不要 `<script>`、不要 `<html>`、`<head>`、`<body>`、媒体占位。
9. 只输出以上内容：不要解释、不要代码围栏。

## 内容要求

- 每屏服务 `group_json.thesis` 与 `arguments`，不跑到别的论点。
- 第一屏呼应 `prev_hook`，最后一屏给 `next_hook` 留钩子。
- 文字之间、文字与图片主体之间不得叠压。
- 不要调试标签、场景编号、时间码、坐标注释；不要常驻页眉页脚水印。
- 一屏讲一件事。讲不完就说明这一屏该拆，不要靠缩小字号硬塞。
