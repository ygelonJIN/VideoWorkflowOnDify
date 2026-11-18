// 影子 roughjs：mermaid 形状里 rc.path(d, options) / rc.polygon(points) 等，只把几何原样
// 落成 SVG 元素（不做抖动）。手绘质感在场景里由 motion-kit 的 kit.rough 叠，不在提取期假装。
import { VEl } from './d3.mjs';

const ptsToD = (points) => points.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' ') + ' Z';

const styleOf = (opts = {}) => {
  const a = {};
  if (opts.stroke) a.stroke = opts.stroke;
  if (opts.fill && opts.fill !== 'none') { a.fill = opts.fill; a['fill-opacity'] = '0.18'; }
  else a.fill = 'none';
  if (opts.stroke === 'none') a.stroke = 'none';
  if (opts.strokeWidth) a['stroke-width'] = opts.strokeWidth;
  return a;
};

class RoughGen {
  constructor(host) { this.host = host; }
  _push(el) {
    const g = new VEl('g');
    g.children.push(el);
    el.parent = g;
    if (this.host) this.host.children.push(g);
    return g;
  }
  path(d, opts) {
    const el = new VEl('path', { ...styleOf(opts), d });
    return this._push(el);
  }
  polygon(points, opts) {
    const el = new VEl('path', { ...styleOf(opts), d: ptsToD(points) });
    return this._push(el);
  }
  linearPath(points, opts) {
    const el = new VEl('path', { ...styleOf(opts), d: points.map((p, i) => `${i ? 'L' : 'M'}${p[0]} ${p[1]}`).join(' ') });
    return this._push(el);
  }
  rectangle(x, y, w, h, opts) {
    const el = new VEl('rect', { ...styleOf(opts), x, y, width: w, height: h });
    return this._push(el);
  }
  circle(x, y, d, opts) {
    const el = new VEl('circle', { ...styleOf(opts), cx: x, cy: y, r: d / 2 });
    return this._push(el);
  }
  ellipse(x, y, w, h, opts) {
    const el = new VEl('ellipse', { ...styleOf(opts), cx: x, cy: y, rx: w / 2, ry: h / 2 });
    return this._push(el);
  }
  line(x1, y1, x2, y2, opts) {
    const el = new VEl('line', { ...styleOf(opts), x1, y1, x2, y2 });
    return this._push(el);
  }
  arc(x, y, w, h, start, stop, closed, opts) {
    const el = new VEl('path', { ...styleOf(opts), d: `M${x} ${y}m${-w / 2} 0a${w / 2} ${h / 2} 0 1 1 ${w} 0a${w / 2} ${h / 2} 0 1 1 ${-w} 0` });
    return this._push(el);
  }
}

const rough = {
  generator: () => new RoughGen(null),
  svg: (host) => new RoughGen(host && host.node ? host.node() : host),
  newSeed: () => 1,
};
export default rough;
export const { generator, svg } = rough;
