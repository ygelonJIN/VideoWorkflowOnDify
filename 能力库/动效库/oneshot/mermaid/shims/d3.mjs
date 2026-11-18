// 影子 d3：只实现 mermaid 形状代码用到的选择集方法，把结果记在一棵虚拟树上，
// 最后序列化成 SVG 字符串。不碰真 DOM，也不量文字。
export class VEl {
  constructor(tag, attrs = {}) {
    this.tag = tag;
    this.attrs = { ...attrs };
    this.children = [];
    this.parent = null;
    this.text = '';
    this.styleMap = {};
    this.__data__ = undefined;
    this.bbox = null;
  }
  getBBox() {
    return this.bbox || { x: 0, y: 0, width: 0, height: 0 };
  }
  getBoundingClientRect() {
    const b = this.getBBox();
    return {
      x: b.x, y: b.y, left: b.x, top: b.y, width: b.width, height: b.height,
      right: b.x + b.width, bottom: b.y + b.height, toJSON() { return {}; },
    };
  }
  setAttribute(k, v) { if (v === null || v === undefined) delete this.attrs[k]; else this.attrs[k] = v; }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  removeChild(c) { const i = this.children.indexOf(c); if (i >= 0) this.children.splice(i, 1); }
  appendChild(c) { c.parent = this; this.children.push(c); return c; }
  insertBefore(c, ref) {
    c.parent = this;
    const i = this.children.indexOf(ref);
    this.children.splice(i < 0 ? 0 : i, 0, c);
    return c;
  }
  remove() { if (this.parent) this.parent.removeChild(this); }
  append(...els) {
    for (const e of els) { if (e && e.tag) { e.parent = this; this.children.push(e); } }
    return this;
  }
}

const matches = (el, sel) => {
  if (!sel || sel === ':first-child') return false;
  if (sel.startsWith('.')) return String(el.attrs.class || '').split(/\s+/).includes(sel.slice(1));
  if (sel.startsWith('#')) return el.attrs.id === sel.slice(1);
  return el.tag === sel;
};

const walk = (el, out = []) => {
  for (const c of el.children) { out.push(c); walk(c, out); }
  return out;
};

class Sel {
  constructor(nodes) {
    this._nodes = nodes;
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      if (!('parentNode' in n)) Object.defineProperty(n, 'parentNode', { get: () => n.parent, configurable: true });
      if (!('ownerDocument' in n)) {
        Object.defineProperty(n, 'ownerDocument', {
          get: () => ({
            createElementNS: (_ns, tag) => new VEl(tag),
            createElement: (tag) => new VEl(tag),
          }),
          configurable: true,
        });
      }
      if (!('nodeName' in n)) Object.defineProperty(n, 'nodeName', {
        get: () => String(n.tag || '').toUpperCase(), configurable: true,
      });
    }
  }
  get length() { return this._nodes.length; }
  nodes() { return this._nodes; }
  node() { return this._nodes[0] || null; }
  empty() { return this._nodes.length === 0; }
  each(fn) {
    this._nodes.forEach((n, i) => fn.call(n, n.__data__, i, this._nodes));
    return this;
  }
  attr(name, value) {
    if (arguments.length === 1 && typeof name === 'string') {
      const n = this._nodes[0];
      if (!n) return null;
      if (name in n.attrs) return n.attrs[name];
      return name === 'class' ? '' : null;
    }
    if (typeof name === 'object' && name !== null) {
      for (const [k, v] of Object.entries(name)) this.attr(k, v);
      return this;
    }
    this._nodes.forEach((n, i) => {
      let v = typeof value === 'function' ? value.call(n, n.__data__, i, this._nodes) : value;
      if (v === null || v === undefined) delete n.attrs[name];
      else n.attrs[name] = v;
    });
    return this;
  }
  style(name, value) {
    if (typeof name === 'object' && name !== null) {
      for (const [k, v] of Object.entries(name)) this.style(k, v);
      return this;
    }
    this._nodes.forEach((n, i) => {
      const v = typeof value === 'function' ? value.call(n, n.__data__, i, this._nodes) : value;
      if (v === null || v === undefined) delete n.styleMap[name]; else n.styleMap[name] = v;
    });
    return this;
  }
  classed(name, on) {
    this._nodes.forEach((n) => {
      const cur = new Set(String(n.attrs.class || '').split(/\s+/).filter(Boolean));
      if (on) cur.add(name); else cur.delete(name);
      n.attrs.class = [...cur].join(' ');
    });
    return this;
  }
  text(value) {
    this._nodes.forEach((n) => { n.children.length = 0; n.text = String(value); });
    return this;
  }
  html(value) { this._nodes.forEach((n) => { n.innerHTML = String(value); }); return this; }
  append(tag) {
    const created = [];
    this._nodes.forEach((n) => {
      const c = new VEl(typeof tag === 'function' ? tag() : tag);
      c.parent = n; n.children.push(c); created.push(c);
    });
    return new Sel(created);
  }
  insert(tag, before) {
    const created = [];
    this._nodes.forEach((n) => {
      let el = typeof tag === 'function' ? tag() : new VEl(tag);
      if (!el || !el.tag) el = new VEl(String(el || 'g'));
      el.parent = n;
      if (before === ':first-child') n.children.unshift(el);
      else if (typeof before === 'number') n.children.splice(before, 0, el);
      else n.children.push(el);
      created.push(el);
    });
    return new Sel(created);
  }
  select(sel) {
    const found = [];
    this._nodes.forEach((n) => {
      const hit = walk(n).find((c) => matches(c, sel));
      if (hit) found.push(hit);
    });
    return new Sel(found);
  }
  selectAll(sel) {
    const found = [];
    this._nodes.forEach((n) => { for (const c of walk(n)) if (matches(c, sel)) found.push(c); });
    return new Sel(found);
  }
  selectChildren(sel) {
    const found = [];
    this._nodes.forEach((n) => { for (const c of n.children) if (matches(c, sel)) found.push(c); });
    return new Sel(found);
  }
  data(arr) {
    const nodes = arr.map((d, i) => {
      const n = this._nodes[i] || null;
      return n;
    }).filter(Boolean);
    this._data = arr;
    return this;
  }
  join(tag) {
    // 极简 join：数据里每条补一个子元素，datum 挂在 __data__ 上，属性回调能用。
    const created = [];
    const host = this._nodes[0];
    if (!host) return new Sel([]);
    const data = this._data || [];
    const existing = host.children.slice();
    data.forEach((d, i) => {
      const el = existing[i] || new VEl(typeof tag === 'function' ? tag() : tag);
      if (!existing[i]) { el.parent = host; host.children.push(el); }
      el.__data__ = d;
      created.push(el);
    });
    if (typeof tag === 'function') created.forEach((el, i) => tag(el.__data__, i));
    return new Sel(created);
  }
  call(fn, ...args) { fn(this, ...args); return this; }
  lower() {
    this._nodes.forEach((n) => { if (n.parent) { n.parent.removeChild(n); n.parent.children.unshift(n); } });
    return this;
  }
  order() { return this; }
  remove() { this._nodes.forEach((n) => n.remove()); return this; }
  purge() { return this.remove(); }
  filter(fn) { return new Sel(this._nodes.filter((n, i) => fn.call(n, n.__data__, i))); }
  merge(other) { return new Sel([...this._nodes, ...other._nodes]); }
}

export const select = (target) => {
  if (target instanceof VEl) return new Sel([target]);
  if (target && target._nodes) return target;
  return new Sel([]);
};
export const selectAll = select;
export const create = (tag) => new Sel([new VEl(tag)]);
export const namespace = (ns) => `http://www.w3.org/2000/svg:${ns}`;
export const line = () => ({ x: (v) => () => v, y: (v) => () => v, curve: () => ({}) });
export const curveBasis = 'curveBasis';
export const curveLinear = 'curveLinear';
export const curveBumpX = 'curveBumpX';
export const curveMonotoneX = 'curveMonotoneX';
export const curveStep = 'curveStep';

export const serialize = (el) => {
  if (!el) return '';
  const attrs = Object.entries(el.attrs)
    .filter(([, v]) => v !== null && v !== undefined && v !== false && v !== '')
    .map(([k, v]) => `${k}="${String(v).replace(/"/g, '&quot;')}"`)
    .join(' ');
  const styleStr = Object.entries(el.styleMap).map(([k, v]) => `${k}:${v}`).join(';');
  const style = styleStr ? ` style="${styleStr}"` : '';
  const open = `<${el.tag}${attrs ? ' ' + attrs : ''}${style}>`;
  if (el.tag === 'text' && el.text) return `${open}${el.text}</${el.tag}>`;
  return `${open}${el.innerHTML || ''}${el.text || ''}${el.children.map(serialize).join('')}</${el.tag}>`;
};
