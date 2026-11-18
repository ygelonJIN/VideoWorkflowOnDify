// 任何会去碰浏览器 DOM/第三方引擎的依赖，在提取期一律空转。
const noop = () => {};
export const sanitize = (s) => s;
export const addHook = noop;
export const removeHook = noop;
export const default_ = {};
export default { sanitize, addHook, removeHook };
