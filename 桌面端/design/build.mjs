// 由同一份原型生成 4 个独立版本 + 1 个可切换对比页。
// 用法：node build.mjs
import { writeFileSync } from "node:fs";

const THEMES = [
  { id: "graphite", file: "01-graphite.html", name: "石墨 Graphite", note: "深色中性 · 蓝强调 · 紧凑" },
  { id: "paper", file: "02-paper.html", name: "纸白 Paper", note: "暖白纸面 · 墨蓝 · 编辑型" },
  { id: "deepspace", file: "03-deepspace.html", name: "深空 Deep Space", note: "近黑 · 紫青 · 低密度" },
  { id: "film", file: "04-film.html", name: "胶片 Film", note: "暖褐 · 赭石 · 衬线标题" },
];

const icons = {
  canvas: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="8" height="6" rx="1.5"/><rect x="13" y="14" width="8" height="6" rx="1.5"/><path d="M11 7h3a2 2 0 0 1 2 2v5"/></svg>',
  prompts: '<svg viewBox="0 0 24 24"><path d="M5 4h9l5 5v11H5z"/><path d="M14 4v5h5"/><path d="M8 14h8M8 17h5"/></svg>',
  artifacts: '<svg viewBox="0 0 24 24"><path d="M4 7h6l2 2h8v10H4z"/><path d="M4 7V5h5l2 2"/></svg>',
  terminal: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M7 10l3 2-3 2M12 15h5"/></svg>',
  settings: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/></svg>',
};

function node({ x, y, kind, title, meta, status = "", sel = false, dim = false, ins = true, outs = true }) {
  const cls = ["node", sel ? "sel" : "", dim ? "dim" : ""].join(" ").trim();
  return `<div class="${cls}" style="left:${x}px;top:${y}px">
    ${ins ? '<i class="h in"></i>' : ""}
    <div class="node-head"><i class="dot ${status}"></i><span class="node-title">${title}</span></div>
    <div class="node-kind">${kind}</div>
    <div class="node-meta">${meta}</div>
    ${outs ? '<i class="h out"></i>' : ""}
  </div>`;
}

function body() {
  return `
<div class="app">
  <header class="topbar">
    <div class="brand"><span class="mark">V</span>视频工作流 · Studio</div>
    <span class="crumb">04 黑帧口播 / <b>run 20261111-1150</b></span>
    <span class="spacer"></span>
    <span class="pill"><i class="dot ok"></i>opencode · gpt-6-luna</span>
    <span class="pill">Dify DSL 0.7.0</span>
    <button class="btn ghost">停止</button>
    <button class="btn primary">▶ 运行</button>
  </header>

  <div class="main">
    <nav class="rail">
      <span class="tool on">${icons.canvas}</span>
      <span class="tool">${icons.prompts}</span>
      <span class="tool">${icons.artifacts}</span>
      <span class="sep"></span>
      <span class="tool">${icons.terminal}</span>
      <span class="spacer"></span>
      <span class="tool">${icons.settings}</span>
    </nav>

    <section class="canvas-wrap">
      <div class="canvas-hint"><span>画布</span><span>·</span><span>49 节点</span><span>·</span><span>51 连线</span></div>
      <svg class="edges" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
            <path d="M0 0L10 5L0 10z" fill="var(--edge)"/>
          </marker>
        </defs>
        <path d="M214 152H258" stroke="var(--edge)" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
        <path d="M444 152H488" stroke="var(--edge)" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
        <path d="M674 152H718" stroke="var(--edge)" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
        <path d="M904 152H948" stroke="var(--edge)" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
        <path d="M1041 186V240H1031V262" stroke="var(--edge)" stroke-width="1.5" fill="none" marker-end="url(#arrow)"/>
        <path d="M948 152H801V262" stroke="var(--edge)" stroke-width="1.5" stroke-dasharray="4 4" fill="none" marker-end="url(#arrow)"/>
        <text x="1012" y="216" class="hit" fill="var(--fg-faint)" font-size="10">valid</text>
        <text x="806" y="176" class="hit" fill="var(--fg-faint)" font-size="10">false</text>
      </svg>

      ${node({ x: 28, y: 118, kind: "start", title: "A00 输入活动需求", meta: "6 个输入变量", status: "ok", ins: false })}
      ${node({ x: 258, y: 118, kind: "llm", title: "A01 整理自然语言需求", meta: "gpt-6-luna · 12.4s", status: "ok" })}
      ${node({ x: 488, y: 118, kind: "code", title: "A02 解析整理结果", meta: "python3 · 0.02s", status: "run" })}
      ${node({ x: 718, y: 118, kind: "code", title: "A03 标准化 Brief", meta: "python3", status: "" })}
      ${node({ x: 948, y: 118, kind: "if-else", title: "A03_Brief 门禁", meta: "validation_ok is true", status: "", sel: true, outs: false })}
      ${node({ x: 938, y: 262, kind: "llm", title: "A04 选择内容角度", meta: "等待上游", status: "", dim: true })}
      ${node({ x: 708, y: 262, kind: "code", title: "A90 未完成诊断", meta: "false 分支", status: "", dim: true })}

      <div class="canvas-tools"><span>−</span><span>+</span><span>⌗</span></div>
    </section>

    <aside class="inspector">
      <div class="insp-head">
        <div>
          <h2>A03_Brief 门禁</h2>
          <div class="insp-sub">if-else · a03_gate</div>
        </div>
        <span class="spacer"></span>
        <button class="btn ghost">⋯</button>
      </div>

      <div class="sec">
        <div class="sec-title">条件</div>
        <div class="field">
          <label>分支 valid</label>
          <div class="input sel">validation_ok <span class="tag">is true</span></div>
        </div>
        <div class="field">
          <label>否则</label>
          <div class="input">false → A90_未完成诊断</div>
        </div>
      </div>

      <div class="sec">
        <div class="sec-title">提示词 · a03</div>
        <div class="code">把 <em>{{#a02.campaign_json#}}</em> 与创作偏好合并为内部 brief；
必须保留 <em>{{#a02.history_json#}}</em> 中的已确认事实…</div>
      </div>

      <div class="sec">
        <div class="sec-title">输出变量</div>
        <table class="vars">
          <tr><td>brief_json</td><td>string</td></tr>
          <tr><td>target_duration_seconds</td><td>number</td></tr>
          <tr><td>validation_ok</td><td>boolean</td></tr>
        </table>
      </div>

      <div class="sec">
        <div class="sec-title">单节点</div>
        <div class="row">
          <button class="btn">试运行</button>
          <button class="btn ghost">从该节点重跑</button>
        </div>
      </div>
    </aside>
  </div>

  <footer class="bottom">
    <div class="tabs">
      <span class="tab on">运行台</span><span class="tab">终端</span><span class="tab">产物</span><span class="tab">提示词</span>
      <span class="right">run 20261111-1150 · 00:13</span>
    </div>
    <div class="log">
      <div><span class="t">11:50:12</span> <span class="run">run</span> 启动 04_黑帧口播 · 输入 6 项</div>
      <div><span class="t">11:50:12</span> <span class="ok">ok</span> A00 输入活动需求 · 0.1s</div>
      <div><span class="t">11:50:13</span> <span class="ok">ok</span> A01 整理自然语言需求 · 2.1k→1.8k tok · 12.4s</div>
      <div><span class="t">11:50:25</span> <span class="ok">ok</span> A02 解析整理结果 · 2.8k 字符 · 0.02s</div>
      <div><span class="t">11:50:25</span> <span class="run">run</span> A03 标准化 Brief …</div>
      <div><span class="t">11:50:25</span> <span class="dim">hint</span> 门禁未通过时会走 A90，运行不中断</div>
    </div>
  </footer>
</div>`;
}

function page(theme, title, withSwitcher) {
  const buttons = THEMES.map(
    (t) => `<button data-theme-set="${t.id}" aria-pressed="${t.id === theme}">${t.name}</button>`
  ).join("");
  return `<!doctype html>
<html lang="zh-CN" data-theme="${theme}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title} · 桌面端原型</title>
<link rel="stylesheet" href="tokens.css">
<link rel="stylesheet" href="app.css">
</head>
<body>
${body()}
${withSwitcher ? `<div class="themer">${buttons}</div>` : ""}
${withSwitcher ? `<script>
document.querySelectorAll('[data-theme-set]').forEach((b) => {
  b.addEventListener('click', () => {
    const id = b.getAttribute('data-theme-set');
    document.documentElement.setAttribute('data-theme', id);
    document.querySelectorAll('[data-theme-set]').forEach((x) =>
      x.setAttribute('aria-pressed', String(x === b)));
  });
});
</script>` : ""}
</body>
</html>`;
}

for (const t of THEMES) {
  writeFileSync(new URL(`./${t.file}`, import.meta.url), page(t.id, t.name, false));
  console.log("wrote", t.file);
}
writeFileSync(new URL("./compare.html", import.meta.url), page("paper", "四版对比", true));
console.log("wrote compare.html");
