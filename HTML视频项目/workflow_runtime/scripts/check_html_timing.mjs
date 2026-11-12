#!/usr/bin/env node
// 页面时间线体检：把 HTML 里的 GSAP 时间线逐帧（1/30）seek 一遍，检查
// 1) 每屏在自己窗口内是否真的可见；2) 每个内容层是否都有且只有一次入场
//    （不许第一帧即最终态，不许 1→0→1 闪回）；3) 背景层是否第 1 帧就在；
// 4) 动作有没有越界被夹到屏尾；5) 场景窗口有没有重叠或空洞。
// 用法：node check_html_timing.mjs index.html
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

const require = createRequire(import.meta.url);
const htmlPath = path.resolve(process.argv[2] || 'index.html');
if (!fs.existsSync(htmlPath)) {
  console.error('缺少 HTML：' + htmlPath);
  process.exit(2);
}

const cliPath = process.env.HYPERFRAMES_CLI || '';
const moduleRoots = [];
if (cliPath) moduleRoots.push(path.resolve(path.dirname(cliPath), '../..'));
moduleRoots.push(path.resolve(path.dirname(new URL(import.meta.url).pathname), '../node_modules'));
let puppeteer = null;
for (const root of moduleRoots) {
  try { puppeteer = require(path.join(root, 'puppeteer-core')); break; } catch {}
}
if (!puppeteer) {
  console.error('缺少 puppeteer-core；请通过 HyperFrames CLI 的 node_modules 运行本检查');
  process.exit(2);
}

const browser = await puppeteer.launch({
  executablePath: process.env.HYPERFRAMES_BROWSER_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  headless: true,
  args: ['--no-sandbox', '--disable-dev-shm-usage', '--allow-file-access-from-files'],
});
const page = await browser.newPage();
await page.setViewport({width: 1080, height: 1920, deviceScaleFactor: 1});
await page.goto(pathToFileURL(htmlPath).href, {waitUntil: 'load'});
await page.evaluate(() => document.fonts.ready);
await page.waitForFunction(() => window.__timelines && Object.keys(window.__timelines).length > 0, {timeout: 60000});

const report = await page.evaluate(async () => {
  const errors = [];
  const warnings = [];
  const sceneReports = [];
  const flashes = [];
  const timeline = Object.values(window.__timelines || {})[0];
  if (!timeline) { return {errors: ['没有 window.__timelines'], warnings, sceneReports, flashes}; }

  const root = document.querySelector('#stage') || document.body;
  const total = Number(root.getAttribute('data-duration')) || 0;
  const sceneEls = [...document.querySelectorAll('#stage .scene')];
  if (!sceneEls.length) { return {errors: ['没有 #stage .scene'], warnings, sceneReports, flashes}; }

  const seek = async (t) => {
    if (typeof window.__seekTo === 'function') { await window.__seekTo(t); }
    else { timeline.seek(t, false); if (typeof window.__hfRenderState === 'function') window.__hfRenderState(t); }
    if (typeof window.__updateScenes === 'function') window.__updateScenes(t);
  };

  const scenes = sceneEls.map(el => ({
    el,
    id: el.getAttribute('data-scene') || el.id || '?',
    start: Number(el.getAttribute('data-start') || 0),
    dur: Number(el.getAttribute('data-duration') || 0),
  })).sort((a, b) => a.start - b.start);

  let previousEnd = 0;
  scenes.forEach((scene, index) => {
    if (!Number.isFinite(scene.start) || !Number.isFinite(scene.dur) || scene.dur <= 0) {
      errors.push(`${scene.id}: data-start/data-duration 无效`);
      return;
    }
    if (index === 0 && scene.start > 0.06) warnings.push(`${scene.id}: 第一屏从 ${scene.start.toFixed(2)}s 才开始，片头是空的`);
    if (scene.start < previousEnd - 0.06) warnings.push(`${scene.id}: 与上一屏重叠 ${(previousEnd - scene.start).toFixed(2)}s`);
    if (scene.start > previousEnd + 0.06) warnings.push(`${scene.id}: 与上一屏之间空了 ${(scene.start - previousEnd).toFixed(2)}s`);
    previousEnd = Math.max(previousEnd, scene.start + scene.dur);
  });
  if (total && Math.abs(previousEnd - total) > 0.2) warnings.push(`场景总时长 ${previousEnd.toFixed(2)}s 与根 data-duration ${total.toFixed(2)}s 不一致`);

  const visibleBoxes = (scene) => {
    let count = 0;
    scene.querySelectorAll('[data-anim]').forEach(el => {
      const style = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (style.visibility !== 'hidden' && Number(style.opacity) > 0.12 && r.width > 4 && r.height > 4) count += 1;
    });
    return count;
  };

  // 2026-11-12：改逐帧（1/30）扫描。原来 0.2s 抽样，抓不到"图片先以最终态
  // 出现 7 帧、再被自己的入场从 0 重演"这种 1 帧级的闪回。
  const step = 1 / 30;
  const BACKGROUND_ANIMS = ['bg', 'scrim'];

  for (const scene of scenes) {
    if (!Number.isFinite(scene.start) || !Number.isFinite(scene.dur) || scene.dur <= 0) continue;
    const allAnim = [...scene.el.querySelectorAll('[data-anim]')];
    const contentEls = allAnim.filter(el => !BACKGROUND_ANIMS.includes(el.getAttribute('data-anim') || ''));
    const bgEls = allAnim.filter(el => BACKGROUND_ANIMS.includes(el.getAttribute('data-anim') || ''));
    const samples = Math.max(2, Math.ceil(scene.dur / step));
    const history = new Map(contentEls.map(el => [el, []]));
    const bgHistory = [];
    let hiddenFor = 0;
    let maxHidden = 0;
    let emptyFor = 0;
    let maxEmpty = 0;

    for (let i = 0; i < samples; i += 1) {
      const t = scene.start + Math.min(scene.dur - 0.02, i * step);
      await seek(t);
      const style = getComputedStyle(scene.el);
      const sceneVisible = style.visibility !== 'hidden' && Number(style.opacity) > 0.08;
      if (!sceneVisible) { hiddenFor += step; maxHidden = Math.max(maxHidden, hiddenFor); } else { hiddenFor = 0; }
      // 空页判定用 0.1s 粒度：getBoundingClientRect 每帧调用会强制回流
      if (i % 3 === 0) {
        const boxes = sceneVisible ? visibleBoxes(scene.el) : 0;
        if (boxes === 0) { emptyFor += step * 3; maxEmpty = Math.max(maxEmpty, emptyFor); } else { emptyFor = 0; }
      }
      contentEls.forEach(el => { history.get(el).push(Number(getComputedStyle(el).opacity)); });
      bgHistory.push(bgEls.length ? Math.max(...bgEls.map(el => Number(getComputedStyle(el).opacity))) : 1);
    }

    // 背景层：只允许第 1 帧就在（"背景直接存在"）
    if (bgEls.length && bgHistory.length && bgHistory[0] < 0.85) {
      errors.push(`${scene.id}: 背景层没在屏起点出现（首帧透明度 ${bgHistory[0].toFixed(2)}）`);
    }

    // 内容层：必须有且只有一次入场；不许第一帧即最终态；不许 1→0→1
    contentEls.forEach(el => {
      const ops = history.get(el);
      const name = el.getAttribute('data-anim') || '?';
      const label = `${scene.id} [data-anim="${name}"]`;
      const peak = Math.max(...ops);
      if (peak < 0.85) {
        errors.push(`${label}: 整屏都没出现过（最高透明度 ${peak.toFixed(2)}），被入场代码漏掉了`);
        return;
      }
      if (ops[0] >= 0.85) {
        errors.push(`${label}: 屏第一帧就是最终态，没有入场（直接存在）`);
        return;
      }
      let sawHidden = false;
      let entered = false;
      for (let i = 0; i < ops.length; i += 1) {
        if (ops[i] <= 0.15) { sawHidden = true; }
        if (sawHidden && ops[i] >= 0.85) { entered = true; break; }
      }
      if (!entered) {
        errors.push(`${label}: 没有完成一次入场（从未从不可见走到可见）`);
      }
      let reached = false;
      let dropped = false;
      for (let i = 0; i < ops.length; i += 1) {
        if (ops[i] >= 0.85) {
          if (reached && dropped) {
            errors.push(`${label}: 出现 1→0→1 闪回（先满、后归零、再回满）`);
            break;
          }
          reached = true;
        } else if (ops[i] <= 0.15 && reached) {
          dropped = true;
        }
      }
    });

    // 2026-11-11 起首帧就是纯背景：前 1.4 秒的“不可见”是入场窗口，不算空页
    if (maxHidden > 1.4) errors.push(`${scene.id}: 屏内有 ${maxHidden.toFixed(1)}s 整屏不可见（空页）`);
    if (maxEmpty > 0.6) warnings.push(`${scene.id}: 屏内有 ${maxEmpty.toFixed(1)}s 没有可见的 data-anim 元素`);
    sceneReports.push({
      scene: scene.id,
      start: Number(scene.start.toFixed(2)),
      dur: Number(scene.dur.toFixed(2)),
      maxHidden: Number(maxHidden.toFixed(2)),
      maxEmpty: Number(maxEmpty.toFixed(2)),
      content: contentEls.length,
    });
  }

  // 运行时记下的动效违规
  (Array.isArray(window.__motionViolations) ? window.__motionViolations : []).forEach(item => {
    if (!item) return;
    if (item.kind === 'position-clamped') {
      errors.push(`${item.scene}: 动作位置 ${item.requested}s 越界，被夹到 ${item.clamped}s（屏尾最后一帧）`);
    }
    if (item.kind === 'transition-on-incoming') {
      errors.push(`${item.scene}: 转场脚本在 ${item.at}s 给进入屏写透明度/缩放/遮罩——转场只许动离场屏`);
    }
  });

  const placement = [];
  (timeline.getChildren ? timeline.getChildren(true, true, false) : []).forEach(child => {
    const targets = child.targets ? child.targets() : [];
    const element = targets.find(item => item && item.nodeType === 1);
    const sceneEl = element && element.closest ? element.closest('.scene') : null;
    if (!sceneEl) return;
    const start = Number(sceneEl.getAttribute('data-start') || 0);
    const dur = Number(sceneEl.getAttribute('data-duration') || 0);
    const begin = Number(child.startTime());
    const end = begin + Number(child.duration());
    if (begin < start - 0.5) warnings.push(`动作早于 ${sceneEl.getAttribute('data-scene')} 的窗口 ${Math.abs(begin - start).toFixed(2)}s`);
    if (end > start + dur + 0.6) warnings.push(`动作超出 ${sceneEl.getAttribute('data-scene')} 的窗口 ${(end - start - dur).toFixed(2)}s`);
    placement.push({scene: sceneEl.getAttribute('data-scene'), begin: Number(begin.toFixed(2)), dur: Number(child.duration().toFixed(2))});
  });

  return {errors, warnings, sceneReports, flashes, tweenCount: placement.length, total};
});

await browser.close();

const pretty = JSON.stringify(report, null, 2);
if (report.errors.length) {
  console.log('TIMING CHECK: FAIL —— ' + report.errors.length + ' 条时间线问题');
  report.errors.forEach(item => console.log('  error: ' + item));
  report.warnings.forEach(item => console.log('  warn: ' + item));
  if (process.argv.includes('--json')) console.log(pretty);
  process.exit(1);
}
if (report.warnings.length) {
  console.log('TIMING CHECK: WARN —— ' + report.warnings.length + ' 条提示');
  report.warnings.forEach(item => console.log('  warn: ' + item));
} else {
  console.log('TIMING CHECK: PASS');
}
if (process.argv.includes('--json')) console.log(pretty);
