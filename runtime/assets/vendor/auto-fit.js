/* auto-fit.js — 按栏宽自动定字号
 * 场景里给标题写 data-fit="0.96"（0–1，占父级宽度的比例），本文件在字体就绪后
 * 把 font-size 调到刚好填满那一行。字号不再由模型猜。
 * 只处理带 data-fit 的元素；没标记的一律不动。
 */
(function () {
  "use strict";

  var BASE = 100;

  function measure(el) {
    var parent = el.parentElement;
    var pw = parent ? parent.getBoundingClientRect().width : 900;
    if (!pw) return 0;
    el.style.fontSize = BASE + "px";
    var w = el.getBoundingClientRect().width;
    if (!w) return 0;
    var ratio = parseFloat(el.getAttribute("data-fit")) || 1;
    return Math.max(8, Math.round(BASE * (pw * ratio) / w));
  }

  function apply() {
    var els = document.querySelectorAll("[data-fit]");
    for (var i = 0; i < els.length; i++) {
      var size = measure(els[i]);
      if (size) els[i].style.fontSize = size + "px";
    }
  }

  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(apply);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
  window.addEventListener("load", apply);
})();
