#!/usr/bin/env node
// 页面时间线体检：把 HTML 里的 GSAP 时间线逐时刻 seek 一遍，检查
// 1) 每屏在自己窗口内是否真的可见；2) 图片层是否在屏内消失后又回来（闪一下）；
// 3) 动作有没有落在所属场景窗口之外；4) 场景窗口有没有重叠或空洞。
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

  for (const scene of scenes) {
    if (!Number.isFinite(scene.start) || !Number.isFinite(scene.dur) || scene.dur <= 0) continue;
    const step = 0.2;
    let hiddenFor = 0;
    let maxHidden = 0;
    let emptyFor = 0;
    let maxEmpty = 0;
    let mediaMax = 0;
    let mediaMinAfterPeak = 1;
    let recovered = false;
    let peakAt = -1;
    const media = scene.el.querySelector('[data-anim="media"],[data-anim="bg"]');
    const samples = Math.max(1, Math.ceil(scene.dur / step));
    for (let i = 0; i < samples; i += 1) {
      const t = scene.start + Math.min(scene.dur - 0.02, i * step);
      await seek(t);
      const style = getComputedStyle(scene.el);
      const sceneVisible = style.visibility !== 'hidden' && Number(style.opacity) > 0.08;
      if (!sceneVisible) { hiddenFor += step; maxHidden = Math.max(maxHidden, hiddenFor); } else { hiddenFor = 0; }
      const boxes = sceneVisible ? visibleBoxes(scene.el) : 0;
      if (boxes === 0) { emptyFor += step; maxEmpty = Math.max(maxEmpty, emptyFor); } else { emptyFor = 0; }
      if (media) {
        const opacity = Number(getComputedStyle(media).opacity);
        if (opacity > mediaMax) { mediaMax = opacity; peakAt = t; mediaMinAfterPeak = 1; recovered = false; }
        if (mediaMax > 0.7 && t > peakAt + 0.2) {
          mediaMinAfterPeak = Math.min(mediaMinAfterPeak, opacity);
          if (mediaMinAfterPeak < 0.18 && opacity > 0.65 && t - peakAt < 1.4) recovered = true;
        }
      }
    }
    if (maxHidden > 0.34) errors.push(`${scene.id}: 屏内有 ${maxHidden.toFixed(1)}s 整屏不可见（空页）`);
    if (maxEmpty > 0.6) warnings.push(`${scene.id}: 屏内有 ${maxEmpty.toFixed(1)}s 没有可见的 data-anim 元素`);
    if (recovered) {
      flashes.push({scene: scene.id, peakAt: Number(peakAt.toFixed(2))});
      errors.push(`${scene.id}: 图片/背景在 ${peakAt.toFixed(2)}s 后消失又回来（闪一下）`);
    }
    sceneReports.push({
      scene: scene.id,
      start: Number(scene.start.toFixed(2)),
      dur: Number(scene.dur.toFixed(2)),
      maxHidden: Number(maxHidden.toFixed(2)),
      maxEmpty: Number(maxEmpty.toFixed(2)),
      mediaMax: Number(mediaMax.toFixed(2)),
    });
  }

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
