#!/usr/bin/env node
// 构图差异检查：逐屏量出「构图指纹」，比较相邻屏、首尾屏，并统计全片是不是同一套骨架。
//
// 只约束结果，不规定做法：画面由照片还是排版承担、文字压在哪、左边界多少、
// 主标题字号、对齐方式、元素密度——合起来就是一屏的构图指纹。
// 相邻两屏指纹落在容差内，说明换的只是文案，不是构图。
//
// 用法：
//   node 脚本/check_composition_variation.mjs index.html
//   STRICT_COMPOSITION=1 node 脚本/check_composition_variation.mjs index.html   # 有问题退出 1
//
// 默认只报告、退出 0，和排版/动效检查一致：成片优先，问题留给人看。

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

const report = await page.evaluate(() => {
  const scenes = [...document.querySelectorAll('.scene.clip')];
  const problems = [];
  const items = [];
  if (!scenes.length) {
    return {sceneCount: 0, distinctSkeletons: 0, scenes: [], problems: ['未找到 .scene.clip：这份 HTML 不是本管线的场景结构，检查没有执行']};
  }

  const seekTimeline = (seconds) => {
    if (typeof window.__seekTo === 'function') {
      window.__seekTo(seconds);
      try { window.dispatchEvent(new CustomEvent('hf-seek', { detail: { time: seconds } })); } catch {}
      return;
    }
    const tl = Object.values(window.__timelines || {}).find(item => item && (typeof item.totalTime === 'function' || typeof item.seek === 'function'));
    if (tl) {
      if (typeof tl.totalTime === 'function') { tl.totalTime(0, false); tl.totalTime(seconds, false); }
      else { tl.seek(0, false); tl.seek(seconds, false); }
    }
    if (window.__hfTimeline && typeof window.__hfTimeline.seek === 'function' && window.__hfTimeline !== tl) {
      window.__hfTimeline.seek(seconds, false);
    }
    try { window.dispatchEvent(new CustomEvent('hf-seek', { detail: { time: seconds } })); } catch {}
  };

  const visible = (el) => {
    const style = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) <= 0.05) return false;
    if (r.width <= 2 || r.height <= 2) return false;
    if (el.closest('#captions,.caption-layer,.captions,#progress')) return false;
    return true;
  };

  const carrierOf = (scene, canvasW, canvasH, sceneRect) => {
    const media = scene.querySelector('[data-anim="media"]');
    const bg = scene.querySelector('[data-anim="bg"]');
    if (String(scene.dataset.visual || '') === 'html' || bg) return 'html-bg';
    if (!media) return 'layout-only';
    const r = media.getBoundingClientRect();
    const ratio = (r.width * r.height) / (canvasW * canvasH);
    if (ratio >= 0.8) return 'photo-full';
    if (ratio >= 0.35) return 'photo-block';
    return 'photo-small';
  };

  for (const scene of scenes) {
    const start = Number(scene.dataset.start || 0);
    const duration = Number(scene.dataset.duration || 0);
    // 停在屏尾前 15%：入场已经落定，是这一屏最完整的样子。
    const settle = start + duration * 0.85;
    seekTimeline(settle);
    window.__hfRenderState?.(settle);

    const sceneRect = scene.getBoundingClientRect();
    const canvasW = sceneRect.width || innerWidth;
    const canvasH = sceneRect.height || innerHeight;

    const carrier = carrierOf(scene, canvasW, canvasH, sceneRect);

    const title = scene.querySelector('[data-anim="title"]') || scene.querySelector('h1,h2,h3');
    const titleStyle = title ? getComputedStyle(title) : null;
    const titleRect = title ? title.getBoundingClientRect() : null;
    const titleFont = titleStyle ? parseFloat(titleStyle.fontSize) : 0;
    const alignRaw = titleStyle ? titleStyle.textAlign : 'none';
    const align = alignRaw === 'start' ? 'left' : alignRaw;

    const textEls = [...scene.querySelectorAll('*')].filter(el => {
      if (!visible(el)) return false;
      const own = [...el.childNodes].some(node => node.nodeType === 3 && node.textContent.trim());
      return own && el.textContent.trim();
    });
    let textLeft = 0, textTop = 0, textRight = 0, textBottom = 0;
    if (textEls.length) {
      textLeft = Infinity; textTop = Infinity; textRight = -Infinity; textBottom = -Infinity;
      for (const el of textEls) {
        const r = el.getBoundingClientRect();
        textLeft = Math.min(textLeft, r.left); textRight = Math.max(textRight, r.right);
        textTop = Math.min(textTop, r.top); textBottom = Math.max(textBottom, r.bottom);
      }
    }

    const animated = [...scene.querySelectorAll('[data-anim]')].filter(visible);

    const rel = (value, size) => Number(((value - (size === canvasW ? sceneRect.left : sceneRect.top)) / size).toFixed(3));
    items.push({
      scene: scene.dataset.scene || scene.id,
      carrier,
      align,
      textLeftPx: Math.round(textLeft - sceneRect.left),
      textTopPx: Math.round(textTop - sceneRect.top),
      titleLeftPx: titleRect ? Math.round(titleRect.left - sceneRect.left) : null,
      titleTopPx: titleRect ? Math.round(titleRect.top - sceneRect.top) : null,
      titleFont: Math.round(titleFont),
      titleWidthRatio: titleRect ? Number((titleRect.width / canvasW).toFixed(2)) : null,
      textWidthRatio: textLeft ? Number(((textRight - textLeft) / canvasW).toFixed(2)) : null,
      textCenterYRatio: textLeft ? Number((((textTop + textBottom) / 2 - sceneRect.top) / canvasH).toFixed(2)) : null,
      density: animated.length,
    });
  }

  // 同一套骨架 = 对齐相同、文字左边界近似、标题顶边近似、标题字号近似、画面承担者相同。
  const near = (a, b, tolerance) => Math.abs(a - b) <= tolerance;
  const sameSkeleton = (a, b) => {
    if (a.align !== b.align) return false;
    if (a.carrier !== b.carrier) return false;
    if (!near(a.textLeftPx, b.textLeftPx, 40)) return false;
    if (a.titleTopPx !== null && b.titleTopPx !== null && !near(a.titleTopPx, b.titleTopPx, 90)) return false;
    if (!near(a.titleFont, b.titleFont, 14)) return false;
    return true;
  };

  for (let i = 1; i < items.length; i++) {
    if (sameSkeleton(items[i - 1], items[i])) {
      problems.push(`相邻两屏是同一套构图骨架：${items[i - 1].scene} 与 ${items[i].scene}` +
        `（承担者 ${items[i].carrier}、${items[i].align} 对齐、文字左边界 ${items[i].textLeftPx}px、标题顶边 ${items[i].titleTopPx}px、字号 ${items[i].titleFont}px）`);
    }
  }
  if (items.length >= 2) {
    const first = items[0];
    const last = items[items.length - 1];
    if (sameSkeleton(first, last)) {
      problems.push(`首尾两屏是同一套构图骨架：${first.scene} 与 ${last.scene}`);
    }
  }

  // 全片是不是被一套排版吃掉了：对齐方式 + 文字左边界先聚类，再看占比。
  const clusters = new Map();
  for (const item of items) {
    const key = `${item.align}@${Math.round(item.textLeftPx / 40) * 40}`;
    clusters.set(key, (clusters.get(key) || []).concat(item.scene));
  }
  let dominant = null;
  for (const [key, list] of clusters) {
    if (!dominant || list.length > dominant.list.length) dominant = {key, list};
  }
  if (dominant && items.length >= 3 && dominant.list.length / items.length >= 0.8) {
    problems.push(`全片排版被一套吃掉了：${dominant.list.length}/${items.length} 屏都是「${dominant.key.split('@')[0]} 对齐 + 左边界 ${dominant.key.split('@')[1]}px 档（±40px）」（${dominant.list.join('、')}）`);
  }

  return {
    sceneCount: items.length,
    distinctSkeletons: (() => {
      const groups = [];
      for (const item of items) {
        const hit = groups.find(group => sameSkeleton(group[0], item));
        if (hit) hit.push(item); else groups.push([item]);
      }
      return groups.length;
    })(),
    scenes: items,
    problems,
  };
});

console.log(JSON.stringify(report, null, 2));

if (report.problems.length) {
  console.log('');
  console.log('构图差异检查：' + report.problems.length + ' 条问题（' + report.sceneCount + ' 屏 / ' + report.distinctSkeletons + ' 种骨架）');
  for (const item of report.problems) console.log('  · ' + item);
  console.log('说明：只比对「画面承担者 + 对齐 + 文字左边界 + 标题位置与字号」，不评价好看与否。');
  if (process.env.STRICT_COMPOSITION === '1') {
    console.log('COMPOSITION CHECK: FAIL（STRICT_COMPOSITION=1，已拦截）');
    await browser.close();
    process.exit(1);
  }
  console.log('COMPOSITION CHECK: WARN（未加 STRICT_COMPOSITION=1，不拦截）');
} else {
  console.log('COMPOSITION CHECK: PASS（' + report.sceneCount + ' 屏 / ' + report.distinctSkeletons + ' 种骨架）');
}

await browser.close();
