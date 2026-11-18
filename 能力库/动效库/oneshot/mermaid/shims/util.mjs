// 影子 shapes/util：labelHelper / updateNodeBounds 这几个是全形状共用的落脚点。
// 真版本要量 DOM、要读全局 config；这里只用估宽，把标签摆到形状中心，几何仍由形状自己算。
import { VEl } from './d3.mjs';
import { measureText, createText } from './env.mjs';

export const getNodeClasses = (node, extra = '') => {
  const classes = ((node && node.cssClasses) || '').split(/\s+/).filter(Boolean);
  if (node && node.classSelector) classes.push(node.classSelector);
  if (extra) classes.push(extra);
  return classes.join(' ');
};

export const labelHelper = async (parent, node, classes) => {
  const cls = classes || 'node default';
  const shapeSvg = parent.insert('g').attr('class', cls).attr('id', node.id);
  const labelEl = shapeSvg
    .insert('g')
    .attr('class', 'label')
    .attr('style', node.labelStyle || null);
  const label = node.label === undefined ? '' : typeof node.label === 'string' ? node.label : node.label[0];
  const text = await createText(labelEl, label, {
    useHtmlLabels: false,
    width: node.width || node.wrappingWidth || 200,
    classes: '',
    style: node.labelStyle,
  });
  const bbox = { x: -text.bbox.width / 2, y: -text.bbox.height / 2, width: text.bbox.width, height: text.bbox.height };
  labelEl.attr('transform', 'translate(' + 0 + ', ' + -bbox.height / 2 + ')');
  if (node.centerLabel) {
    labelEl.attr('transform', 'translate(' + -bbox.width / 2 + ', ' + -bbox.height / 2 + ')');
  }
  labelEl.insert('rect', ':first-child');
  return { shapeSvg, bbox, halfPadding: (node.padding || 0) / 2, label: labelEl };
};

export const insertLabel = async (parent, label, options = {}) => {
  const labelEl = parent.insert('g').attr('class', 'label').attr('style', options.labelStyle || '');
  const text = await createText(labelEl, String(label ?? ''), { classes: '' });
  const bbox = { x: -text.bbox.width / 2, y: -text.bbox.height / 2, width: text.bbox.width, height: text.bbox.height };
  labelEl.attr('transform', 'translate(' + 0 + ', ' + -bbox.height / 2 + ')');
  labelEl.insert('rect', ':first-child');
  return { node: parent, label: labelEl, bbox };
};

export const updateNodeBounds = (node, element) => {
  if (!element || !element.node) return;
  const el = element.node();
  const b = el && el.getBBox ? el.getBBox() : { width: 0, height: 0 };
  node.width = Math.max(node.width || 0, b.width);
  node.height = Math.max(node.height || 0, b.height);
};

export const createPathFromPoints = (points) =>
  points.map((p, i) => `${i ? 'L' : 'M'}${p.x},${p.y}`).join(' ') + ' Z';

export const generateCirclePoints = (cx, cy, radius, count, start, end) => {
  const pts = [];
  const step = (end - start) / (count - 1);
  for (let i = 0; i < count; i++) {
    const a = ((start + step * i) * Math.PI) / 180;
    pts.push({ x: cx + Math.cos(a) * radius, y: cy + Math.sin(a) * radius });
  }
  return pts;
};

export const generateFullSineWavePoints = (x1, y1, x2, y2, amplitude, numCycles) => {
  const pts = [];
  const n = 60;
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    pts.push({ x: x1 + (x2 - x1) * t, y: y1 + (y2 - y1) * t + Math.sin(t * Math.PI * 2 * numCycles) * amplitude });
  }
  return pts;
};

export const insertPolygonShape = (parent, w, h, points) =>
  parent
    .insert('polygon', ':first-child')
    .attr('points', points.map((p) => `${p.x},${p.y}`).join(' '))
    .attr('transform', 'translate(' + -w / 2 + ', ' + -h / 2 + ')');

export const mergePaths = (...d) => d.filter(Boolean).join(' ');
export const withMinWidth = (bbox) => bbox;
export const createTextForShape = createText;
export const measure = measureText;
export const getConfigSafe = () => ({});
export default { labelHelper, updateNodeBounds, getNodeClasses, createPathFromPoints, generateCirclePoints };
