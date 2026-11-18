// 提取器：把 mermaid 的 113 个形状模块真跑一遍（影子 d3 + 影子 rough），
// 每个形状得到一段可直接内联的 <svg>。不手抄几何，几何就是 mermaid 自己算的。
import { readdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { VEl, select } from './shims/d3.mjs';
import { measureText, getConfig } from './shims/env.mjs';

const SRC = process.argv[2];
const OUT = process.argv[3] || './shapes.json';

// ---- bbox 估算：把虚拟树算成盒，形状靠它定位标签 ----
const num = /-?\d+(?:\.\d+)?/g;

function elemBox(el) {
  const a = el.attrs || {};
  const f = (k, d = 0) => (a[k] === undefined ? d : parseFloat(a[k]));
  switch (el.tag) {
    case 'rect':
      return { x: f('x'), y: f('y'), w: f('width'), h: f('height') };
    case 'circle':
      return { x: f('cx') - f('r'), y: f('cy') - f('r'), w: 2 * f('r'), h: 2 * f('r') };
    case 'ellipse':
      return { x: f('cx') - f('rx'), y: f('cy') - f('ry'), w: 2 * f('rx'), h: 2 * f('ry') };
    case 'line':
      return {
        x: Math.min(f('x1'), f('x2')), y: Math.min(f('y1'), f('y2')),
        w: Math.abs(f('x2') - f('x1')), h: Math.abs(f('y2') - f('y1')),
      };
    case 'text': {
      const m = measureText(el.text || '', f('font-size', 16));
      return { x: -m.width / 2, y: -m.height / 2, w: m.width, h: m.height };
    }
    case 'polygon':
    case 'polyline': {
      const ns = (String(a.points || '').match(num) || []).map(Number);
      if (ns.length < 2) return null;
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (let i = 0; i + 1 < ns.length; i += 2) {
        x0 = Math.min(x0, ns[i]); y0 = Math.min(y0, ns[i + 1]);
        x1 = Math.max(x1, ns[i]); y1 = Math.max(y1, ns[i + 1]);
      }
      return isFinite(x0) ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
    }
    case 'path': {
      const d = String(a.d || '');
      const ns = (d.match(num) || []).map(Number);
      if (ns.length < 2) return null;
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (let i = 0; i + 1 < ns.length; i += 2) {
        const x = ns[i], y = ns[i + 1];
        if (!isFinite(x) || !isFinite(y)) continue;
        x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
      }
      return isFinite(x0) ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : null;
    }
    default:
      return null;
  }
}

function treeBox(el) {
  if (el.bbox) return { x: el.bbox.x, y: el.bbox.y, w: el.bbox.width, h: el.bbox.height };
  const boxes = [];
  const own = elemBox(el);
  if (own) boxes.push(own);
  for (const c of el.children) {
    const b = treeBox(c);
    if (b) boxes.push(b);
  }
  if (!boxes.length) return null;
  const x0 = Math.min(...boxes.map((b) => b.x));
  const y0 = Math.min(...boxes.map((b) => b.y));
  const x1 = Math.max(...boxes.map((b) => b.x + b.w));
  const y1 = Math.max(...boxes.map((b) => b.y + b.h));
  // translate 也要算进去（形状常把标签挪位）
  const t = /translate\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)?/.exec(String(el.attrs?.transform || ''));
  if (t) {
    const tx = parseFloat(t[1]), ty = t[2] === undefined ? 0 : parseFloat(t[2]);
    return { x: x0 - tx, y: y0 - ty, w: x1 - x0, h: y1 - y0 };
  }
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

const SKIP_TAGS = new Set(['text', 'tspan']);
function treeBoxNoText(el) {
  const boxes = [];
  const own = SKIP_TAGS.has(el.tag) ? null : elemBox(el);
  if (own) boxes.push(own);
  for (const c of el.children) {
    const b = treeBoxNoText(c);
    if (b) boxes.push(b);
  }
  if (!boxes.length) return null;
  const t = /translate\(\s*(-?[\d.]+)[\s,]+(-?[\d.]+)?/.exec(String(el.attrs?.transform || ''));
  const tx = t ? parseFloat(t[1]) : 0;
  const ty = t && t[2] !== undefined ? parseFloat(t[2]) : 0;
  const x0 = Math.min(...boxes.map((b) => b.x)) - tx;
  const y0 = Math.min(...boxes.map((b) => b.y)) - ty;
  const x1 = Math.max(...boxes.map((b) => b.x + b.w)) - tx;
  const y1 = Math.max(...boxes.map((b) => b.y + b.h)) - ty;
  return { x: x0, y: y0, w: x1 - x0, h: y1 - y0 };
}

function bboxOf(el) {
  const b = treeBox(el);
  return b || { x: 0, y: 0, w: 0, h: 0 };
}

// 让形状代码里 polygon.getBBox() 拿到真值
const patchGetBBox = (node) => {
  if (!node.getBBox) return node;
  node.getBBox = () => {
    const b = bboxOf(node);
    return { x: b.x, y: b.y, width: b.w, height: b.h, top: b.y, left: b.x, bottom: b.y + b.h, right: b.x + b.w };
  };
  return node;
};

const serialize = (el) => {
  const attrs = Object.entries(el.attrs || {})
    .filter(([, v]) => v !== null && v !== undefined && v !== false && v !== '')
    .map(([k, v]) => `${k}="${String(v).replace(/"/g, '&quot;')}"`)
    .join(' ');
  const styleStr = Object.entries(el.styleMap || {}).map(([k, v]) => `${k}:${v}`).join(';');
  const style = styleStr ? ` style="${styleStr}"` : '';
  const tag = el.tag === 'foreignobject' ? 'foreignObject' : el.tag;
  const open = `<${tag}${attrs ? ' ' + attrs : ''}${style}>`;
  if (tag === 'text') return `${open}${el.text || ''}</${tag}>`;
  return `${open}${el.innerHTML || ''}${el.text || ''}${(el.children || []).map(serialize).join('')}</${tag}>`;
};

const NODE_LABEL = process.env.LABEL || '形状';

const mkRoot = () => {
  const root = new VEl('g', {});
  root.getBBox = () => {
    const b = bboxOf(root);
    return { x: b.x, y: b.y, width: b.w, height: b.h, top: b.y, left: b.x, bottom: b.y + b.h, right: b.x + b.w };
  };
  return root;
};

// 少数形状靠外部布局数据才成形：给一份最小可用数据，让它画出本体而不是退化成点/零宽
const NODE_EXTRA = {
  blockArrow: { directions: ['right'], width: 180, height: 90 },
  kanbanItem: { width: 200, height: 90 },
};

const mkNode = () => ({
  id: 'n1',
  domId: 'n1',
  label: NODE_LABEL,
  labelType: 'string',
  padding: 15,
  look: 'classic',
  cssCompiledStyles: [],
  cssStyles: [],
  labelStyle: '',
  centerLabel: false,
  useHtmlLabels: false,
  intersect: undefined,
});

const pick = (mod, file) => {
  const base = file.replace(/\.ts$/, '');
  const want = base;
  const fns = Object.entries(mod).filter(([, v]) => typeof v === 'function');
  const exact = fns.find(([k]) => k === want);
  if (exact) return exact[1];
  // 没有同名导出：取"长得像渲染器"的那个（不是 create*/get*/is*/parse*/update*）
  const render = fns.filter(([k, v]) => !/^(create|insert|get|is|parse|update|has|register|make)/.test(k) && v.length >= 2);
  if (render.length) return render[0][1];
  return null;
};

const files = readdirSync(SRC).filter((f) => f.endsWith('.ts') && !f.endsWith('.spec.ts')).sort();
const out = [];
const failed = [];

for (const file of files) {
  const base = file.replace(/\.ts$/, '');
  if (['util', 'insertPolygonShape', 'roundedRectPath', 'handDrawnShapeStyles', 'drawRect',
    'labelImageUtils', 'c4LabelHelper', 'bpmnIconPack', 'bpmnIcons', 'bpmnShapeCore',
    'insertPolygonShape'].includes(base)) continue;
  try {
    const mod = await import(pathToFileURL(path.join(SRC, file)).href);
    let render = pick(mod, file);
    if (base === 'bpmnEvent') {
      render = (sel, n, ctx) => mod.renderBpmnEvent(sel, n, 'start', ctx);
    }
    if (base === 'erBox') {
      render = (sel, n) => mod.erBox(sel, Object.assign(n, { attributes: [] }));
    }
    if (base === 'state') {
      // state() 只传了 rx/ry，没给 labelPadding；补齐再走同一个 drawRect
      render = (sel, n, ctx) => mod.state(sel, Object.assign(n, { look: n.look || 'classic' }), ctx);
      const drawRectMod = await import(pathToFileURL(path.join(SRC, 'drawRect.ts')).href);
      render = (sel, n, ctx) => drawRectMod.drawRect(sel, n, { rx: 5, ry: 5, classes: 'flowchart-node', labelPaddingX: 30, labelPaddingY: 15 });
    }
    if (!render) { failed.push([base, '没有可调的渲染函数']); continue; }
    const root = mkRoot();
    const sel = select(root);
    const node = Object.assign(mkNode(), NODE_EXTRA[base] || {});
    await render(sel, node, { config: getConfig(), alt: false });
    const kids = root.children.filter((c) => c.tag !== 'style');
    if (!kids.length) { failed.push([base, '没画出元素']); continue; }
    kids.forEach(patchGetBBox);
    const b = treeBoxNoText(root) || bboxOf(root);
    if (!isFinite(b.w) || b.w <= 0 || !isFinite(b.h) || b.h <= 0) {
      failed.push([base, 'bbox 无效 ' + JSON.stringify(b) + ' :: ' + kids.map(serialize).join('').slice(0, 160)]);
      continue;
    }
    const pad = 16;
    const vb = { x: b.x - pad, y: b.y - pad, w: b.w + pad * 2, h: b.h + pad * 2 };
    const svg = `<svg viewBox="${vb.x.toFixed(1)} ${vb.y.toFixed(1)} ${vb.w.toFixed(1)} ${vb.h.toFixed(1)}" ` +
      `xmlns="http://www.w3.org/2000/svg" data-shape="${base}">${kids.map(serialize).join('')}</svg>`;
    out.push({ name: base, w: Math.round(vb.w), h: Math.round(vb.h), vb,
      nodeW: Math.round(node.width || b.w), nodeH: Math.round(node.height || b.h), svg });
    process.stdout.write('.');
  } catch (e) {
    failed.push([base, String(e.message).slice(0, 120)]);
    process.stdout.write('x');
  }
}

writeFileSync(OUT, JSON.stringify({ count: out.length, failed, shapes: out }, null, 1));
console.log(`\n成功 ${out.length} / 失败 ${failed.length}`);
if (failed.length) for (const [n, why] of failed) console.log('  ✗', n, '—', why);
