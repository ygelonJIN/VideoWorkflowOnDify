# 场景组 A

你只负责场景组 **A** 的画面、样式和动效，不负责别的组。风格不必和其它组一致，但论点必须同一条。

## 输入

- `skeleton_html`：{{#h01s.text#}}（全局骨架，只读）
- `group_json`：{{#h00.group_a_json#}}（含 `thesis`、`arguments`、`scenes`、`prev_hook`、`next_hook`）
- `design_brief`：{{#h00.design_brief#}}

## 结构（必须）

- 每个 scene 是一整页，布局方式随你：flex、grid、绝对定位、整屏插画、全出血构图都可以，怎么好看怎么来。
- 唯一的结果要求：这一屏的内容在 1080×1920 里是稳的——不叠字、不出界、该看的都看得见。本地渲染会自动做一次垂直校正。
- 这一组每一屏都要服务 `group_json.thesis` 和 `group_json.arguments`，不要跑到别的论点上去。

## 衔接（必须）

- 第一屏承接 `prev_hook`：呼应它的结论，但不要重复它的标题；
- 最后一屏给 `next_hook` 留钩子：一句话把话题推到下一组，不要提前讲完。

## 输出（严格，不要解释）

```
<style>/* 本组样式，选择器统一以 .gA- 开头 */</style>
<section class="scene clip gA" id="s03" data-scene="s03" data-sentence-ids="s05" data-start="0" data-duration="4">
  <div class="gA-stack">
    <h1 class="gA-title" data-anim="headline">一句论点</h1>
    <p class="gA-note" data-anim="note">支撑它的事实</p>
  </div>
</section>
<script>
window.__sceneBuilders.push(function(timeline, at){
  timeline.from('.gA [data-scene="s03"] [data-anim="headline"]', {opacity:0, y:26, duration:0.6, ease:'power3.out'}, at(0.2));
  timeline.to('.gA [data-scene="s03"] [data-anim="note"]', {opacity:1, duration:0.5, ease:'power2.out'}, at(0.9));
});
</script>
```

## 动效契约（只这几条是硬的）

- `data-start` 可以先写 0、`data-duration` 先写估算值：本地渲染会按真实口播重排，不要为对齐绝对时间做计算。
- `id` 和 `data-scene` 用 `group_json.scenes[].scene_id`，`data-sentence-ids` 用该 scene 的 `sentence_ids`，三者必须对得上；不要自己重新编号，否则四组会撞车。
- 脚本必须立即执行 `window.__sceneBuilders.push(...)`；不要包 `DOMContentLoaded`、`window.onload` 或 `setTimeout`，否则动作永远不执行。
- 时间位置用 `at(秒)` 取场景内相对时间，不要写绝对秒数。
- 动作只作用在本组自己的 scene 上，不要跨组选择。
- 给要动的元素加 `data-anim="语义名"` 最稳（合并时会按它检查选择器是否命中）；用你自己发明的 class 选择器也能跑，只是命中失败时没人替你兜底。

## 动效要求（要拉满，但不数个数）

- 画面里出现的**每一个组件**都要有自己的动作：进入一次，之后至少还有一次属于它的状态变化。只有整屏淡入、组件全程不动，等于没做动效。
- 优先做「能看见变化」的动作：量级的增减、次序的重排、位置的迁移、层级的升降、阈值的跨越、归属的转移、焦点的收束。观众要看到一件事从 A 变成 B，而不是看见它飞进来。
- 上面是变化的种类，不是组件清单：不要照抄成「数字递增＋进度条」这类模板，按这一屏的信息自己发明形态。
- 动作能不能对应口播里的词或那次状态变化，是判断它该不该存在的唯一标准；说不出来就不做。
- 动作要铺满这一屏：从进场到退场都要有节拍，不要全挤在开头两秒。
- 这一屏要当独立作品打磨：组件形态、层级、间距、字重、留白和动效节奏都为它重新决定，不要复用一个通用布局再往里塞字。

## 要求

- 只用骨架里的 CSS 变量；新样式加 `.gA-` 前缀。
- 不要输出 `<html>`、`<head>`、`<body>`、字幕块、媒体占位。
- 禁止可见的调试标签、场景编号、时间码、坐标注释（如 “SCENE 04 · …”、“16.78s — …”）。
- 文字与文字、文字与组件不得互相叠压。
- 不要固定页眉、页脚、品牌角标、章节编号或水印层；画面只服务当前这一屏。
