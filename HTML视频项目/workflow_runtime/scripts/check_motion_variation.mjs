#!/usr/bin/env node
// 动效差异体检：从真实 GSAP 时间线里读每屏用了哪些动作，报告
// 1) 相邻两屏是不是同一套文字/图片动作；2) 全片有几种文字入场；
// 3) 照片运动是不是都一个推近；4) 有没有整屏只有 1 个动作。
// 只报告，不阻塞渲染；--strict 时相邻重复会退出 1。
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
await page.waitForFunction(() => window.__timelines && Object.keys(window.__timelines).length > 0, {timeout: 60000});

const report = await page.evaluate(() => {
  const timeline = Object.values(window.__timelines || {})[0];
  if (!timeline) return {error: '没有 window.__timelines', scenes: []};
  const scenes = [...document.querySelectorAll('#stage .scene')].map(el => ({
    id: el.getAttribute('data-scene') || el.id || '?',
    start: Number(el.getAttribute('data-start') || 0),
    text: new Set(),
    media: new Set(),
    actions: 0,
  }));
  const byScene = new Map(scenes.map(s => [s.id, s]));
  const familyOf = key => {
    if (['x', 'y', 'xPercent', 'yPercent', 'left', 'top'].includes(key)) return 'translate';
    if (['scale', 'scaleX', 'scaleY'].includes(key)) return 'scale';
    if (['rotation', 'rotate'].includes(key)) return 'rotate';
    if (['opacity', 'autoAlpha'].includes(key)) return 'opacity';
    if (['clipPath', 'webkitClipPath'].includes(key)) return 'clip';
    if (['color', 'backgroundColor', 'borderColor'].includes(key)) return 'color';
    if (['width', 'height', 'flexBasis', 'gridTemplateColumns'].includes(key)) return 'size';
    if (['letterSpacing', 'fontSize', 'lineHeight'].includes(key)) return 'text';
    if (['filter', 'blur'].includes(key)) return 'filter';
    if (['strokeDashoffset', 'strokeDasharray'].includes(key)) return 'draw';
    return null;
  };
  const ownerOf = el => (el.closest ? el.closest('[data-anim]') : null) || el;
  const componentOf = el => {
    const owner = ownerOf(el);
    const anim = owner.getAttribute && owner.getAttribute('data-anim');
    if (anim) return anim;
    const cls = String(owner.className || '').split(/\s+/).filter(Boolean);
    return cls[0] || owner.tagName.toLowerCase();
  };
  const isText = el => {
    const owner = ownerOf(el);
    const anim = owner.getAttribute && owner.getAttribute('data-anim');
    if (['title', 'body', 'note', 'kicker', 'state', 'chips', 'bracket', 'axis', 'tag'].includes(anim)) return true;
    return /title|body|note|kicker|subtitle|headline/i.test(String(owner.className || ''));
  };
  const isMedia = el => {
    const owner = ownerOf(el);
    const anim = owner.getAttribute && owner.getAttribute('data-anim');
    return ['media', 'bg', 'scrim', 'mask', 'panel-top', 'panel-bottom'].includes(anim);
  };
  const children = timeline.getChildren ? timeline.getChildren(true, true, false) : [];
  children.forEach(child => {
    const targets = child.targets ? child.targets() : [];
    const el = targets.find(item => item && item.nodeType === 1);
    if (!el || !el.closest) return;
    const sceneEl = el.closest('.scene');
    if (!sceneEl) return;
    const scene = byScene.get(sceneEl.getAttribute('data-scene') || sceneEl.id);
    if (!scene) return;
    const vars = child.vars || {};
    const families = new Set();
    Object.keys(vars).forEach(key => { const family = familyOf(key); if (family) families.add(family); });
    if (!families.size) return;
    const key = componentOf(el) + ':' + [...families].sort().join('+');
    if (isText(el)) scene.text.add(key);
    else if (isMedia(el)) scene.media.add(key);
    scene.actions += 1;
  });
  return {
    scenes: scenes.map(s => ({
      id: s.id,
      start: Number(s.start.toFixed(2)),
      text: [...s.text].sort(),
      media: [...s.media].sort(),
      actions: s.actions,
    })),
  };
});

await browser.close();
if (report.error) {
  console.log('MOTION VARIATION: FAIL —— ' + report.error);
  process.exit(1);
}

const scenes = report.scenes;
const warnings = [];
const textSets = [];
const mediaSets = [];
scenes.forEach(scene => {
  const textSig = scene.text.join('|');
  const mediaSig = scene.media.join('|');
  textSets.push(textSig);
  mediaSets.push(mediaSig);
  if (scene.actions < 2) warnings.push(`${scene.id}: 只有 ${scene.actions} 个动作，整屏容易像静态图`);
});
for (let i = 1; i < scenes.length; i += 1) {
  if (textSets[i] && textSets[i] === textSets[i - 1]) warnings.push(`${scenes[i - 1].id} → ${scenes[i].id}: 文字动效是同一套（${textSets[i]}）`);
  if (mediaSets[i] && mediaSets[i] === mediaSets[i - 1]) warnings.push(`${scenes[i - 1].id} → ${scenes[i].id}: 图片/背景运动是同一套（${mediaSets[i]}）`);
}
const distinctText = new Set(textSets.filter(Boolean)).size;
const distinctMedia = new Set(mediaSets.filter(Boolean)).size;
if (scenes.length >= 4 && distinctText < 4) warnings.push(`全片只有 ${distinctText} 种文字动作组合；少于 4 种时观众会觉得每页一样`);
if (scenes.length >= 4 && distinctMedia < 3) warnings.push(`全片只有 ${distinctMedia} 种图片/背景运动；照片页容易都在推近`);

console.log('MOTION VARIATION: ' + (warnings.length ? 'WARN' : 'PASS'));
scenes.forEach(scene => console.log(`  ${scene.id}  actions=${scene.actions}  text=[${scene.text.join(', ')}]  media=[${scene.media.join(', ')}]`));
warnings.forEach(item => console.log('  warn: ' + item));
if (warnings.length && process.argv.includes('--strict')) process.exit(1);
