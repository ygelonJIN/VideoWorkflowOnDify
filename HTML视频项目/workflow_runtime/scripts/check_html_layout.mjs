#!/usr/bin/env node
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
  const errors = [];
  const warnings = [];
  const sceneMetrics = [];
  const subtitleMetrics = {};
  const topMetrics = [];
  const rect = el => {
    const r = el.getBoundingClientRect();
    return {left:r.left, right:r.right, top:r.top, bottom:r.bottom, width:r.width, height:r.height};
  };
  const overlap = (a,b) => Math.max(0, Math.min(a.right,b.right)-Math.max(a.left,b.left)) *
    Math.max(0, Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top));
  const contains = (outer,inner,tolerance=2) =>
    outer.left <= inner.left+tolerance && outer.right >= inner.right-tolerance &&
    outer.top <= inner.top+tolerance && outer.bottom >= inner.bottom-tolerance;

  const captionRoot = document.querySelector('#captions,.caption-layer');
  const captionSample = document.querySelector('.caption');
  if (!captionRoot || !captionSample) {
    errors.push('缺少字幕根节点或字幕样例');
  } else {
    const rootStyle = getComputedStyle(captionRoot);
    const capStyle = getComputedStyle(captionSample);
    const rootRect = rect(captionRoot);
    const expectedBottom = innerHeight * 0.24;
    const expectedWidth = innerWidth * 0.62;
    subtitleMetrics.bottom = rootStyle.bottom;
    subtitleMetrics.width = Number(rootRect.width.toFixed(1));
    subtitleMetrics.fontSize = capStyle.fontSize;
    subtitleMetrics.lineHeight = capStyle.lineHeight;
    subtitleMetrics.fontWeight = capStyle.fontWeight;
    subtitleMetrics.background = capStyle.backgroundColor;
    if (Math.abs(parseFloat(rootStyle.bottom)-expectedBottom) > 2) errors.push(`字幕位置错误：bottom=${rootStyle.bottom}，应为24%`);
    if (Math.abs(rootRect.width-expectedWidth) > 3) errors.push(`字幕宽度错误：${rootRect.width.toFixed(1)}px，应约为${expectedWidth.toFixed(1)}px`);
    if (Math.abs(parseFloat(capStyle.fontSize)-37) > 0.1) errors.push(`字幕字号错误：${capStyle.fontSize}，应为37px`);
    if (Math.abs(parseFloat(capStyle.lineHeight)/37-1.35) > 0.02) errors.push(`字幕行高错误：${capStyle.lineHeight}，应为1.35`);
    if (parseInt(capStyle.fontWeight,10) < 700) errors.push(`字幕字重错误：${capStyle.fontWeight}，应为700`);
  }

  const scenes = [...document.querySelectorAll('.scene.clip')];
  if (!scenes.length) errors.push('未找到 scene.clip');
  for (const scene of scenes) {
    const mid = Number(scene.dataset.start||0)+Number(scene.dataset.duration||0)*0.85;
    if (window.__hfTimeline?.seek) window.__hfTimeline.seek(mid);
    window.__hfRenderState?.(mid);

    const baseVisible = el => {
      const style = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0.05 &&
        r.width > 2 && r.height > 2;
    };
    const visible = el => baseVisible(el) && !el.closest('#captions,.caption-layer,#progress,.kicker,.label-demo');
    const all = [...scene.querySelectorAll('*')].filter(visible);
    const textLeaves = all.filter(el => {
      const ownText = [...el.childNodes].some(node => node.nodeType === 3 && node.textContent.trim());
      return ownText && el.textContent.trim();
    });
    const components = all.filter(el => {
      const style = getComputedStyle(el);
      const r = rect(el);
      const painted = style.backgroundColor !== 'rgba(0, 0, 0, 0)' || style.backgroundImage !== 'none' ||
        [...style.borderTopWidth,style.borderRightWidth,style.borderBottomWidth,style.borderLeftWidth].some(v => parseFloat(v) > 0);
      const fullCanvas = r.width >= innerWidth*0.8 && r.height >= innerHeight*0.8;
      return painted && r.width*r.height > 15000 && !fullCanvas && el.textContent.trim().length > 0;
    });

    for (const text of textLeaves) {
      const tr = rect(text);
      for (const component of components) {
        if (component.contains(text) || text.contains(component)) continue;
        const area = overlap(tr, rect(component));
        if (area > 25) errors.push(`${scene.dataset.scene}: 文字“${text.textContent.trim().replace(/\s+/g,' ').slice(0,24)}”与组件 .${String(component.className).split(/\s+/)[0]} 重叠 ${Math.round(area)}px²`);
      }
    }
    for (let i=0;i<textLeaves.length;i++) for (let j=i+1;j<textLeaves.length;j++) {
      const a=textLeaves[i], b=textLeaves[j];
      if (a.contains(b) || b.contains(a)) continue;
      const area=overlap(rect(a),rect(b));
      if (area > 25) errors.push(`${scene.dataset.scene}: 两段文字重叠 ${Math.round(area)}px²：“${a.textContent.trim().slice(0,16)}” / “${b.textContent.trim().slice(0,16)}”`);
    }
    for (const component of components) {
      for (const text of component.querySelectorAll('*')) {
        if (!visible(text) || ![...text.childNodes].some(node => node.nodeType===3 && node.textContent.trim())) continue;
        if (!contains(rect(component),rect(text))) {
          errors.push(`${scene.dataset.scene}: 组件 .${String(component.className).split(/\s+/)[0]} 内文字溢出：${text.textContent.trim().slice(0,24)}`);
          break;
        }
      }
    }

    const topText = [...scene.querySelectorAll('*')].filter(el => {
      const r = el.getBoundingClientRect();
      return baseVisible(el) && el.textContent.trim() &&
        [...el.childNodes].some(node => node.nodeType === 3 && node.textContent.trim()) &&
        r.top < 420 && !el.closest('.label-demo,#captions,.caption-layer,#progress');
    }).map(el => ({el, r:rect(el), text:el.textContent.trim().replace(/\s+/g,' ').slice(0,24)}));
    if (topText.length) {
      const leftmost = topText.reduce((a,b)=>a.r.left<=b.r.left?a:b);
      const leftStyle = getComputedStyle(leftmost.el);
      const centered = leftStyle.textAlign === 'center' || /translateX\(-50%\)/.test(leftStyle.transform);
      const leftLaneUsed = topText.some(item => item.r.left < 300);
      topMetrics.push({scene:scene.dataset.scene,left:Number(leftmost.r.left.toFixed(1)),top:Number(leftmost.r.top.toFixed(1)),text:leftmost.text});
      if (leftmost.r.left >= 300 && !centered && !leftLaneUsed) {
        errors.push(`${scene.dataset.scene}: 顶部内容从 ${leftmost.r.left.toFixed(1)}px 开始，左上区域仍保留旧数字人/黑帧避让空槽`);
      }
    }
    const activeCaption = [...document.querySelectorAll('.caption')].find(el => {
      const style=getComputedStyle(el);
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) > 0.05;
    });
    const mainRects = [...textLeaves.map(rect), ...components.map(rect)];
    if (mainRects.length) {
      const bounds = {
        top:Math.min(...mainRects.map(r=>r.top)), bottom:Math.max(...mainRects.map(r=>r.bottom)),
        left:Math.min(...mainRects.map(r=>r.left)), right:Math.max(...mainRects.map(r=>r.right)),
      };
      const center=(bounds.top+bounds.bottom)/2;
      if (center < 740 || center > 1060) errors.push(`${scene.dataset.scene}: 主内容垂直中心=${center.toFixed(1)}px，应在740–1060px`);
      if (bounds.bottom > 1480) errors.push(`${scene.dataset.scene}: 主内容底部=${bounds.bottom.toFixed(1)}px，超出画面安全区`);
      if (activeCaption) {
        const captionRect=rect(activeCaption);
        const captionOverlap=Math.max(...mainRects.map(r=>overlap(r,captionRect)),0);
        if (captionOverlap > 25) errors.push(`${scene.dataset.scene}: 主内容与字幕重叠 ${Math.round(captionOverlap)}px²`);
      }
      sceneMetrics.push({scene:scene.dataset.scene, top:Number(bounds.top.toFixed(1)), bottom:Number(bounds.bottom.toFixed(1)), center:Number(center.toFixed(1))});
    } else {
      sceneMetrics.push({scene:scene.dataset.scene, top:null, bottom:null, center:null});
    }
  }
  return {errors:[...new Set(errors)], warnings:[...new Set(warnings)], sceneCount:scenes.length, subtitleMetrics, topMetrics, sceneMetrics};
});

await browser.close();
console.log(JSON.stringify(report, null, 2));
if (report.errors.length) process.exit(1);
