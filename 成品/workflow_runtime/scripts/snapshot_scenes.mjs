#!/usr/bin/env node
// 给每一屏生成一张"稳定时刻"的快照，供页间 GT shader 转场当 from/to 纹理。
// 用法：node snapshot_scenes.mjs index.html [--out 媒体/快照] [--size 1080x1920]
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';

const require = createRequire(import.meta.url);
const argv = process.argv.slice(2);
const opt = (k, d) => { const i = argv.indexOf('--' + k); return i < 0 ? d : (argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : true); };
const htmlPath = path.resolve(argv[0] || 'index.html');
if (!fs.existsSync(htmlPath)) { console.error('缺少 HTML：' + htmlPath); process.exit(2); }
const outDir = path.resolve(path.dirname(htmlPath), opt('out', '媒体/快照'));
fs.mkdirSync(outDir, {recursive: true});

const cliPath = process.env.HYPERFRAMES_CLI || '';
const roots = [];
if (cliPath) roots.push(path.resolve(path.dirname(cliPath), '../..'));
roots.push(path.resolve(path.dirname(new URL(import.meta.url).pathname), '../node_modules'));
let puppeteer = null;
for (const root of roots) { try { puppeteer = require(path.join(root, 'puppeteer-core')); break; } catch {} }
if (!puppeteer) { console.error('缺少 puppeteer-core；请通过 HyperFrames CLI 的 node_modules 运行'); process.exit(2); }

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

const plan = await page.evaluate(() => {
  const out = [];
  document.querySelectorAll('#stage .scene').forEach(sc => {
    const cue = Number(sc.getAttribute('data-cue-start') || sc.getAttribute('data-start') || 0);
    const visStart = Number(sc.getAttribute('data-start') || 0);
    const dur = Number(sc.getAttribute('data-duration') || 0);
    const cueEnd = visStart + dur;
    // 取"切点刚过"的那一帧：转场结束时的画面必须和切点后的实时页面对得上，
    // 取晚了（比如 cue+1.2）会把还没入场的文字也算进去，切点会跳一下。
    let t = cue + 0.04;
    t = Math.min(t, cueEnd - 0.45);
    out.push({id: sc.getAttribute('data-scene'), t: Number(t.toFixed(3))});
  });
  return out;
});

for (const item of plan) {
  await page.evaluate(async (item) => {
    const scenes = [...document.querySelectorAll('#stage .scene')];
    scenes.forEach(sc => { sc.style.visibility = sc.getAttribute('data-scene') === item.id ? 'visible' : 'hidden'; });
    const tl = Object.values(window.__timelines)[0];
    if (typeof window.__seekTo === 'function') { await window.__seekTo(item.t); }
    else { tl.seek(item.t, false); if (typeof window.__hfRenderState === 'function') window.__hfRenderState(item.t); }
    scenes.forEach(sc => { sc.style.visibility = sc.getAttribute('data-scene') === item.id ? 'visible' : 'hidden'; });
  }, item);
  await new Promise(r => setTimeout(r, 120));
  const file = path.join(outDir, item.id + '.png');
  await page.screenshot({path: file, clip: {x: 0, y: 0, width: 1080, height: 1920}});
  console.log('快照 ' + item.id + ' @' + item.t + 's → ' + path.relative(process.cwd(), file));
}

await browser.close();
console.log('SNAPSHOT OK：' + plan.length + ' 屏');
