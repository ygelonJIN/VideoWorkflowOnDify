// 影子 khroma：只做通道读取与明暗微调，不改几何。
const hex = (c) => {
  const s = String(c || '#000').replace('#', '');
  const full = s.length === 3 ? s.split('').map((x) => x + x).join('') : s;
  const n = parseInt(full.slice(0, 6) || '000000', 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};
const toHex = (rgb) => '#' + rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('');
export const channel = (color, ch) => {
  const [r, g, b] = hex(color);
  return ch === 'r' ? r : ch === 'g' ? g : ch === 'b' ? b : 255;
};
export const lighten = (color, amount = 10) => { const [r, g, b] = hex(color); return toHex([r + amount, g + amount, b + amount]); };
export const darken = (color, amount = 10) => { const [r, g, b] = hex(color); return toHex([r - amount, g - amount, b - amount]); };
export const mix = (a, b) => { const A = hex(a), B = hex(b); return toHex([(A[0] + B[0]) / 2, (A[1] + B[1]) / 2, (A[2] + B[2]) / 2]); };
export const invert = (c) => { const [r, g, b] = hex(c); return toHex([255 - r, 255 - g, 255 - b]); };
export const isDark = (c) => { const [r, g, b] = hex(c); return (r * 299 + g * 587 + b * 114) / 1000 < 128; };
export const adjust = (c, amount = 0) => (amount >= 0 ? lighten(c, amount) : darken(c, -amount));
export const toHexColor = toHex;
export default { channel, lighten, darken, mix, invert, isDark, adjust };
