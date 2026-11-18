// 影子环境：把 mermaid 形状代码会碰到的运行期依赖一次给全。
// 真值的唯一来源仍是 mermaid 自己的几何计算，这里只提供"不量 DOM、不读配置"的常量。
import { VEl } from './d3.mjs';

export const FONT_SIZE = 14;

export const getConfig = () => ({
  theme: 'default',
  look: 'classic',
  handDrawnSeed: 1,
  fontFamily: 'PingFang SC, sans-serif',
  fontSize: FONT_SIZE,
  htmlLabels: false,
  flowchart: { wrappingWidth: 200, nodeSpacing: 50, rankSpacing: 50, curve: 'basis', padding: 15 },
  sequence: { actorFontSize: 16, messageFontSize: 16 },
  themeVariables: {
    borderColorArray: ['#9370DB', '#8A2BE2', '#7B68EE', '#6A5ACD'],
    mainBkg: '#ECECFF',
    nodeBorder: '#9370DB',
    lineColor: '#333333',
    primaryColor: '#ECECFF',
    primaryTextColor: '#333',
    primaryBorderColor: '#9370DB',
  },
  class: {},
  state: {},
  er: {},
});

export const getEffectiveHtmlLabels = () => false;
export const evaluate = (v) => (typeof v === 'function' ? v() : v);
export const handleUndefinedAttr = (v) => (v === undefined ? null : v);
export const decodeEntities = (s) => (s === undefined || s === null ? s : String(s));
export const sanitizeText = (text) => (text === undefined || text === null ? '' : String(text));
export const sanitizeUrl = (u) => u;
export const calculateTextDimensions = (text, cfg) => {
  const fs = (cfg && cfg.fontSize) || FONT_SIZE;
  const { width, height } = measureText(String(text || ''), fs);
  return { width, height };
};
export const calculateTextWidth = (text, cfg) => calculateTextDimensions(text, cfg).width;
export const calculateTextHeight = (text, cfg) => calculateTextDimensions(text, cfg).height;
export const configureSvgSize = (svg) => svg;
export const getDiagramTitle = () => '';
export const wrapLabel = (t) => t;

const CJK = /[\u3000-\u9fff\uff00-\uffef]/;

/** 按字符估宽：CJK 记 1em，其余 0.58em。样片只要形准，不求像素级。 */
export const measureText = (text, fontSize = FONT_SIZE) => {
  let w = 0;
  for (const ch of text) w += CJK.test(ch) ? fontSize : fontSize * 0.58;
  return { width: Math.max(w, fontSize), height: Math.round(fontSize * 1.4) };
};

/** createText：造一个 <text>，把它塞进父节点，并给出估出来的 bbox（居中于原点）。 */
export const createText = async (parent, text, opts = {}) => {
  const fs = opts?.fontSize || FONT_SIZE;
  const str = String(text ?? '');
  const lines = str.split('\n');
  const { width } = measureText(str, fs);
  const height = Math.round(fs * 1.4) * lines.length;
  const el = new VEl('text', {
    'font-size': fs,
    'font-family': 'PingFang SC, sans-serif',
    'text-anchor': 'middle',
    'dominant-baseline': 'middle',
    'xml:space': 'preserve',
    class: opts?.classes || '',
    style: opts?.style || '',
  });
  el.text = str.replace(/\n/g, ' ');
  el.bbox = { x: -width / 2, y: -height / 2, width, height };
  const div = new VEl('div', {});
  div.bbox = el.bbox;
  div.text = str;
  el.children.push(div);
  if (parent && parent.node) {
    const host = parent.node();
    el.parent = host;
    host.children.push(el);
  }
  return el;
};

globalThis.injected = { profiling: false };
if (typeof globalThis.Image === 'undefined') {
  globalThis.Image = class {
    constructor() { this.onload = null; this.width = 64; this.height = 64; }
    set src(v) { this._src = v; if (this.onload) this.onload(); }
    async decode() { return true; }
    get complete() { return true; }
    get naturalWidth() { return 64; }
    get naturalHeight() { return 64; }
    get src() { return this._src; }
  };
}
export const measure = async (fn) => fn();
export const mutate = async (fn) => fn();
export const clear = () => {};

export const fastdom = {
  measure: async (fn) => fn(),
  mutate: async (fn) => fn(),
  clear: () => {},
};

export const configureLabelImages = async () => {};
export const c4LabelHelper = async () => ({ shapeSvg: null, bbox: { width: 0, height: 0 } });
export const stampColorSlot = () => {};
export const log = { debug: () => {}, info: () => {}, warn: () => {}, error: () => {}, fatal: () => {} };
export const profiler = {
  tickSync: (_name, fn) => fn(),
  startFrame: () => {},
  endFrame: () => {},
  add: () => {},
};
export const injectUtils = (mods) => Object.assign(globalThis, mods);
export const injected = { profiling: false };
export const getConfig2 = getConfig;
export const intersect = {
  node: (node, point) => point,
  polygon: (node, points, point) => point,
  rect: (node, point) => point,
  circle: (node, point) => point,
  ellipse: (node, point) => point,
};
export const getIconSVG = (_name, _w, _h) => '';
export const isIconAvailable = () => false;
export const isIconPackRegistered = () => false;
export const registerIconPacks = () => {};
export const hasKatex = () => false;
export const parseGenericTypes = (s) => s;
export const renderKatex = async (s) => s;
export const utils = {};
export const getIcon = () => null;
export const iconsCache = new Map();

export default {
  getConfig, handleUndefinedAttr, decodeEntities, sanitizeText, calculateTextDimensions,
  calculateTextWidth, measureText, createText, fastdom, log, profiler, evaluate,
  getIconSVG, getIcon, config: getConfig(),
};

/** 公共配置形态：有些模块读 config.flowchart / config.look 的字段。 */
export const config = getConfig();
export const themeVariables = getConfig().themeVariables;
export const setConfig = () => {};
export const reset = () => {};
export const defaultConfig = getConfig();
export const saveConfigFromJSON = () => {};
export const getThemeVariables = () => getConfig().themeVariables;
