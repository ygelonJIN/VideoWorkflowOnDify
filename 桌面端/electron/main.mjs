import { app, BrowserWindow, clipboard, dialog, ipcMain, protocol, shell } from "electron";
import { readFile, readdir, rmdir, stat, unlink, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { createServer } from "node:http";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as core from "./core.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const desktopDir = path.resolve(here, "..");
console.log(`[wfs] Electron ${process.versions.electron} · app ${desktopDir}`);

ipcMain.handle("wf:workflows", () => core.listWorkflows());
ipcMain.handle("wf:pick-workflow", async () => {
  const result = await dialog.showOpenDialog({
    title: "选择 Dify 工作流 YAML",
    defaultPath: path.join(core.workspaceDir, "Dify工作流"),
    properties: ["openFile"],
    filters: [{ name: "Dify 工作流", extensions: ["yml", "yaml"] }],
  });
  return result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0];
});
ipcMain.handle("wf:env", () => core.envInfo());
ipcMain.handle("wf:settings", () => core.getSettings());
ipcMain.handle("wf:save-settings", (_event, payload) => core.saveSettings(payload));
ipcMain.handle("wf:inputs", () => core.inputDefaults());
ipcMain.handle("wf:load", (_event, filePath) => core.loadGraph(filePath));
ipcMain.handle("wf:rev", (_event, filePath) => core.fileRevision(filePath));
ipcMain.handle("wf:run", (event, options) =>
  core.runWorkflow({
    ...options,
    onEvent: (payload) => {
      if (!event.sender.isDestroyed()) event.sender.send("wf:event", payload);
    },
  }),
);
ipcMain.handle("wf:cancel", (_event, clientId) => core.cancelRun(clientId));
ipcMain.handle("wf:projects", () => core.listProjects());
ipcMain.handle("wf:update-node", async (_event, payload) => {
  const result = await core.updateNode(payload);
  return { ...result, graph: await core.loadGraph(payload.path) };
});
ipcMain.handle("wf:file-url", async (_event, filePath) => {
  const safe = core.safePath(filePath);
  // 固定 host + 整体编码：空 host 的标准 scheme 会把第一段目录当成 host（/Volumes 被吃掉）
  return `wfs-file://local/${encodeURIComponent(safe)}`;
});
ipcMain.handle("wf:history", (_event, payload) => core.historyStatus(payload));
ipcMain.handle("wf:undo", (_event, payload) => core.undo(payload));
ipcMain.handle("wf:redo", (_event, payload) => core.redo(payload));
ipcMain.handle("wf:move-node", (_event, payload) => core.moveNode(payload));
ipcMain.handle("wf:add-node", (_event, payload) => core.addNode(payload));
ipcMain.handle("wf:remove-node", (_event, payload) => core.removeNode(payload));
ipcMain.handle("wf:connect", (_event, payload) => core.connectNodes(payload));
ipcMain.handle("wf:remove-edge", (_event, payload) => core.removeEdge(payload));
ipcMain.handle("wf:files", (_event, dirPath) => core.listFiles(dirPath));
ipcMain.handle("wf:read", (_event, filePath) => core.readText(filePath));
ipcMain.handle("wf:open", async (_event, filePath) => {
  const safe = core.safePath(filePath);
  const error = await shell.openPath(safe);
  return { ok: !error, error };
});
ipcMain.handle("wf:presets", () => core.termPresets());
ipcMain.handle("wf:copy", (_event, text) => { clipboard.writeText(String(text ?? "")); return { ok: true }; });
ipcMain.handle("wf:mimo", () => core.mimoKeyStatus());
ipcMain.handle("wf:build", (event, payload) =>
  core.startBuild({
    ...payload,
    onData: (data) => {
      if (!event.sender.isDestroyed()) event.sender.send("wf:build", data);
    },
    onExit: (data) => {
      if (!event.sender.isDestroyed()) event.sender.send("wf:build-done", data);
    },
  }),
);
ipcMain.handle("wf:project-images", (_event, payload) => core.listProjectImages(payload));
ipcMain.handle("wf:project-image-save", (_event, payload) => core.saveProjectImage(payload));
ipcMain.handle("wf:exec", (event, { cmd, cwd }) => {
  const run = core.startCommand({
    cmd,
    cwd,
    onData: (payload) => {
      if (!event.sender.isDestroyed()) event.sender.send("wf:term", payload);
    },
    onExit: (payload) => {
      if (!event.sender.isDestroyed()) event.sender.send("wf:term-done", payload);
    },
  });
  return { id: run.id };
});

function createWindow() {
  const smoke = process.argv.includes("--smoke");
  const probe = process.env.WFS_PROBE === "1";
  const win = new BrowserWindow({
    show: !(smoke || probe),
    width: 1480,
    height: 940,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: "#eef1f5",
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 20, y: 20 },
    webPreferences: {
      preload: path.join(here, "preload.mjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });
  win.loadFile(path.join(desktopDir, "renderer", "index.html"));
  win.webContents.on("did-fail-load", (_event, code, description, url) => {
    console.error(`[wfs] 页面加载失败 ${code} ${description} ${url}`);
  });
  win.webContents.on("render-process-gone", (_event, details) => {
    console.error(`[wfs] 渲染进程退出：${details.reason}`);
  });
  if (probe) {
    win.webContents.on("did-finish-load", async () => {
      const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
      let step = 0;
      const run = async (code) => {
        step += 1;
        try {
          return await win.webContents.executeJavaScript(code);
        } catch (error) {
          console.error(`PROBE STEP ${step} FAILED: ${String(code).replace(/\s+/g, ' ').slice(0, 400)}`);
          throw error;
        }
      };
      try {
        for (let attempt = 0; attempt < 40; attempt += 1) {
          if ((await run("document.querySelectorAll('.node').length")) > 0) break;
          await sleep(200);
        }
        const rect = (selector) => `(() => { const e = document.querySelector(${JSON.stringify(selector)}); if (!e) return null; const r = e.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; })()`;
        const clickText = (text) => `(() => { const b = [...document.querySelectorAll("button")].find((item) => item.textContent.trim() === ${JSON.stringify(text)}); if (!b) return false; b.click(); return true; })()`;
        const clickAt = async (text) => {
          const point = await run(`(() => { const b = [...document.querySelectorAll("button")].find((item) => item.textContent.trim() === ${JSON.stringify(text)}); if (!b) return null; const r = b.getBoundingClientRect(); return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }; })()`);
          if (!point) return false;
          win.webContents.sendInputEvent({ type: "mouseDown", x: point.x, y: point.y, button: "left", clickCount: 1 });
          win.webContents.sendInputEvent({ type: "mouseUp", x: point.x, y: point.y, button: "left", clickCount: 1 });
          await sleep(220);
          return true;
        };

        const pickButton = await run(`[...document.querySelectorAll("button")].some((button) => button.textContent.trim() === "打开文件…")`);
        const panesEarly = await run(`({ panes: [...document.querySelectorAll(".pane")].map((item) => item.className), imageEls: document.querySelectorAll(".image-prompts").length, hasHintText: document.body.innerText.includes("跑完整条链路") })`);
        const before = await run(`({ zoom: document.querySelector(".canvas-hud .zoom").textContent, nodes: document.querySelectorAll(".node").length, edges: document.querySelectorAll(".canvas-edges path").length, rail: ${rect(".rail")}, railRadius: getComputedStyle(document.querySelector(".rail")).borderTopLeftRadius + " / " + getComputedStyle(document.querySelector(".rail")).borderTopRightRadius, lights: ${rect(".lights")}, topbar: ${rect(".topbar")}, bottom: ${rect("#root .bottom")}, canvas: ${rect(".canvas-wrap")}, inspector: ${rect(".inspector")}, icons: (document.body.innerText.match(/[▶◀✕✖＋−⤢▤▣✎⌘⚙●]/g) || []).length, termBg: getComputedStyle(document.querySelector(".term-output")).backgroundColor, termFg: getComputedStyle(document.querySelector(".term-output")).color, termPrompt: getComputedStyle(document.querySelector(".term-input .prompt")).color })`);

        const center = await run(`(() => { const n = document.querySelector(".node"); const r = n.getBoundingClientRect(); return { x: Math.round(r.x + r.width / 2), y: Math.round(r.y + r.height / 2) }; })()`);
        win.webContents.sendInputEvent({ type: "mouseDown", x: center.x, y: center.y, button: "left", clickCount: 1 });
        win.webContents.sendInputEvent({ type: "mouseUp", x: center.x, y: center.y, button: "left", clickCount: 1 });
        await sleep(400);
        const afterSelect = await run(`({ zoom: document.querySelector(".canvas-hud .zoom").textContent, selected: document.querySelectorAll(".node.sel").length, title: (document.querySelector(".insp-head h2") || {}).textContent || "", danger: (() => { const b = document.querySelector(".btn.danger"); return b ? { text: b.textContent.trim(), color: getComputedStyle(b).color, border: getComputedStyle(b).borderColor } : null; })() })`);

        await run(`(() => {
          const canvas = document.querySelector(".canvas-wrap");
          const r = canvas.getBoundingClientRect();
          canvas.dispatchEvent(new WheelEvent("wheel", { deltaY: -100, clientX: r.x + r.width / 2, clientY: r.y + r.height / 2, bubbles: true, cancelable: true }));
          return true;
        })()`);
        await sleep(200);
        const afterWheel = await run(`document.querySelector(".canvas-hud .zoom").textContent`);

        const clickedZoomIn = await clickAt("放大");
        const afterZoomIn = await run(`document.querySelector(".canvas-hud .zoom").textContent`);
        const clickedFit = await clickAt("适应");
        const afterFit = await run(`document.querySelector(".canvas-hud .zoom").textContent`);
        const clicked100 = await clickAt("100%");
        const after100 = await run(`document.querySelector(".canvas-hud .zoom").textContent`);
        for (let i = 0; i < 14; i += 1) await clickAt("缩小");
        const afterMin = await run(`document.querySelector(".canvas-hud .zoom").textContent`);

        const widthBefore = (await run(rect(".canvas-wrap"))).w;
        await run(clickText("收起详情"));
        await sleep(150);
        const collapsed = await run(`({ inspector: !!document.querySelector(".inspector"), canvasWidth: ${rect(".canvas-wrap")}.w, label: [...document.querySelectorAll("button")].map((b) => b.textContent.trim()).includes("展开详情") })`);

        const bottomBefore = (await run(rect("#root .bottom"))).h;
        await run(clickText("收起"));
        await sleep(150);
        const consoleCollapsed = await run(`({ bottom: ${rect("#root .bottom")}.h, log: !!document.querySelector(".log") && getComputedStyle(document.querySelector(".log").parentElement).display !== "none" })`);
        await run(clickText("展开"));
        await sleep(150);
        const consoleBack = (await run(rect("#root .bottom"))).h;

        await run(clickText("产物"));
        await sleep(250);
        const artifacts = await run(`({ browser: !!document.querySelector(".browser"), canvas: !!document.querySelector(".canvas-wrap"), inspector: !!document.querySelector(".inspector"), rows: document.querySelectorAll(".file-row").length, titles: [...document.querySelectorAll(".col-title")].map((item) => item.textContent.trim()), firstRows: [...document.querySelectorAll(".file-row")].slice(0, 5).map((item) => item.textContent.trim()) })`);

        // 媒体协议自检：wfs-file:// 能否真的加载 PNG / MP4
        const pngPath = path.join(desktopDir, "..", "成品", "20261109-1355", "媒体", "图片", "jimeng-2026-11-09-3725-素面陶瓷盘放在同一蓝灰桌面的左下方，两根粗细相同的灰线从盘边松散分向不同方向，都....png");
        const mp4Path = path.join(desktopDir, "..", "成品", "20261109-1355", "成片", "最终视频.mp4");
        const mediaProbe = await run(`(async () => {
          const pngUrl = await window.wfs.fileUrl(${JSON.stringify(pngPath)});
          const mp4Url = await window.wfs.fileUrl(${JSON.stringify(mp4Path)});
          const img = new Image();
          const imgResult = await new Promise((resolve) => {
            img.onload = () => resolve({ ok: true, w: img.naturalWidth, h: img.naturalHeight });
            img.onerror = () => resolve({ ok: false });
            img.src = pngUrl;
            setTimeout(() => resolve({ ok: false, timeout: true }), 4000);
          });
          const video = document.createElement("video");
          video.src = mp4Url;
          video.preload = "metadata";
          const videoResult = await new Promise((resolve) => {
            video.onloadedmetadata = () => resolve({ ok: true, duration: video.duration, w: video.videoWidth, h: video.videoHeight });
            video.onerror = () => resolve({ ok: false, code: video.error && video.error.code, message: video.error && video.error.message });
            setTimeout(() => resolve({ ok: false, timeout: true, readyState: video.readyState, networkState: video.networkState }), 5000);
          });
          let fetchInfo = null;
          try {
            const res = await fetch(pngUrl);
            const text = await res.text();
            fetchInfo = { status: res.status, type: res.headers.get("content-type"), body: text.slice(0, 300) };
          } catch (error) {
            fetchInfo = { error: String(error && error.message || error) };
          }
          return { pngUrl, mp4Url, img: imgResult, video: videoResult, fetchInfo };
        })()`);
        // 产物：进项目 → 子目录 → 视频/图片，检查内嵌预览与返回
        const artProject = await run(`(() => { const rows = [...document.querySelectorAll(".browser .col:nth-child(1) .file-row")]; const row = rows.find((item) => item.textContent.includes("20261109-1355")); if (!row) return { ok: false, sample: rows.slice(0, 40).map((item) => item.textContent.trim()), browser: Boolean(document.querySelector(".browser")), canvas: Boolean(document.querySelector(".canvas-wrap")), text: document.body.innerText.slice(0, 120) }; row.click(); return { ok: true }; })()`);
        await sleep(600);
        const artDir = await run(`(() => { const row = [...document.querySelectorAll(".browser .col:nth-child(2) .file-row")].find((item) => item.textContent.includes("成片")); if (!row) return false; row.click(); return true; })()`);
        await sleep(600);
        const artFile = await run(`(() => { const row = [...document.querySelectorAll(".browser .col:nth-child(2) .file-row")].find((item) => item.textContent.includes("最终视频.mp4")); if (!row) return false; row.click(); return true; })()`);
        await sleep(1500);
        const artVideo = await run(`(() => {
          const video = document.querySelector(".media-video");
          if (!video) return null;
          const rect = video.getBoundingClientRect();
          return { ready: video.readyState, w: video.videoWidth, h: video.videoHeight, err: video.error ? video.error.code : 0, rect: [Math.round(rect.width), Math.round(rect.height)] };
        })()`);
        const artBackList = await run(clickText("返回列表"));
        await sleep(300);
        const artBackState = await run(`({ video: Boolean(document.querySelector(".media-video")), rows: document.querySelectorAll(".file-row").length })`);
        await run(clickText("← 返回"));
        await sleep(600);
        const artMediaDir = await run(`(() => { const row = [...document.querySelectorAll(".browser .col:nth-child(2) .file-row")].find((item) => item.textContent.includes("媒体")); if (!row) return false; row.click(); return true; })()`);
        await sleep(600);
        const artImageDir = await run(`(() => { const row = [...document.querySelectorAll(".browser .col:nth-child(2) .file-row")].find((item) => item.textContent.includes("图片")); if (!row) return false; row.click(); return true; })()`);
        await sleep(1000);
        const artPng = await run(`(() => { const rows = [...document.querySelectorAll(".browser .col:nth-child(2) .file-row")]; const row = rows.find((item) => item.textContent.includes(".png")); if (!row) return { ok: false, sample: rows.slice(0, 10).map((item) => item.textContent.trim()) }; row.click(); return { ok: true }; })()`);
        await sleep(1200);
        const artImage = await run(`(() => {
          const image = document.querySelector(".media-image");
          if (!image) return null;
          const rect = image.getBoundingClientRect();
          return { w: image.naturalWidth, h: image.naturalHeight, rect: [Math.round(rect.width), Math.round(rect.height)] };
        })()`);

        await run(clickText("画布"));
        await sleep(200);
        const back = await run(`({ zoom: document.querySelector(".canvas-hud .zoom").textContent, canvas: !!document.querySelector(".canvas-wrap") })`);

        // 跑一次 stub（默认停在 a03），验证运行台、节点输出值和「停止」按钮的显隐
        const reopened = await run(clickText("展开详情"));
        // 「运行」现在先开输入抽屉，确认后才跑
        const clickedRun = await run(clickText("运行"));
        await sleep(300);
        const runDialog = await run(`({
          open: Boolean(document.querySelector(".drawer")),
          fields: document.querySelectorAll(".drawer .field").length,
          labels: [...document.querySelectorAll(".drawer .field > span")].map((span) => span.textContent.trim()),
          runDisabled: [...document.querySelectorAll(".drawer button")].find((button) => button.textContent.includes("用这些输入运行"))?.disabled ?? null
        })`);
        // 探针不走外网：起一个本地 responses 端点，用 a01 的固定输出冒充模型
        const a01Fixture = await readFile(path.join(desktopDir, "fixtures", "stub", "a01.txt"), "utf8");
        const mockServer = createServer((request, response) => {
          request.on("data", () => {});
          request.on("end", () => {
            // 稍微延迟，让探针能抓到「运行中」的样式和镜头
            setTimeout(() => {
              response.writeHead(200, { "content-type": "application/json" });
              response.end(JSON.stringify({ output_text: a01Fixture, usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 } }));
            }, 400);
          });
        });
        await new Promise((resolve) => mockServer.listen(0, "127.0.0.1", resolve));
        const mockAddress = mockServer.address();
        const mockPort = typeof mockAddress === "object" && mockAddress ? mockAddress.port : 0;
        const envBefore = { base: process.env.WF_BASE_URL, model: process.env.WF_MODEL, protocol: process.env.WF_PROTOCOL };
        process.env.WF_BASE_URL = `http://127.0.0.1:${mockPort}/v1`;
        process.env.WF_MODEL = "probe-model";
        process.env.WF_PROTOCOL = "responses";
        const viewBeforeRun = await run(`document.querySelector(".stage")?.style.transform || ""`);
        const clickedStart = await run(clickText("用这些输入运行"));
        let settle = "";
        let sawRunning = false;
        let runningSelected = "";
        let viewDuringRun = "";
        for (let attempt = 0; attempt < 80; attempt += 1) {
          await sleep(250);
          const live = await run(`({
            running: Boolean(document.querySelector(".node.st-running")),
            selected: document.querySelector(".insp-head h2")?.textContent || "",
            transform: document.querySelector(".stage")?.style.transform || ""
          })`);
          if (live.running) {
            sawRunning = true;
            runningSelected = live.selected;
            viewDuringRun = live.transform;
          }
          settle = await run(`document.querySelector(".tabs .right")?.textContent?.trim() || ""`);
          if (settle && !settle.includes("运行中")) break;
        }
        const runningStyle = { sawRunning, runningSelected, cameraMoved: viewDuringRun !== "" && viewDuringRun !== viewBeforeRun };
        const nodeCenter = await run(`(() => { const node = document.querySelector(".node"); if (!node) return null; const rect = node.getBoundingClientRect(); return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2) }; })()`);
        if (nodeCenter) {
          win.webContents.sendInputEvent({ type: "mouseDown", x: nodeCenter.x, y: nodeCenter.y, button: "left", clickCount: 1 });
          win.webContents.sendInputEvent({ type: "mouseUp", x: nodeCenter.x, y: nodeCenter.y, button: "left", clickCount: 1 });
          await sleep(300);
        }
        const copied = await run(`(() => {
          const button = document.querySelector(".out-item .btn");
          if (!button) return false;
          button.click();
          return true;
        })()`);
        await sleep(300);
        const clipboardText = clipboard.readText();
        const runError = await run(`document.querySelector(".log .err")?.textContent?.trim() || ""`);
        const probeMockPort = mockPort;
        await new Promise((resolve) => mockServer.close(resolve));
        for (const [key, value] of [["WF_BASE_URL", envBefore.base], ["WF_MODEL", envBefore.model], ["WF_PROTOCOL", envBefore.protocol]]) {
          if (value === undefined) delete process.env[key];
          else process.env[key] = value;
        }
        const afterRun = await run(`({
          settle: document.querySelector(".tabs .right")?.textContent?.trim() || "",
          selected: document.querySelector(".insp-head h2")?.textContent || "",
          outputs: document.querySelectorAll(".out-item").length,
          outChars: (document.querySelector(".out-value")?.textContent || "").length,
          stopWhileIdle: [...document.querySelectorAll("button")].some((button) => button.textContent.trim() === "停止"),
          runVisible: [...document.querySelectorAll("button")].some((button) => button.textContent.trim() === "运行")
        })`);

        // 控制台：新消息在最上面
        const firstLogLine = await run(`document.querySelector(".log > div")?.textContent?.trim() || ""`);
        const tabsText = await run(`[...document.querySelectorAll(".tabs .tab")].map((item) => item.textContent.trim())`);

        // 图片页签：选中 20261111-1813，拖入一张 1x1 PNG → 落到 媒体/图片/
        const mediaProject = path.join(desktopDir, "..", "成品", "20261111-1813");
        await run(clickText("图片"));
        await sleep(300);
        const pickProject = async (paneIndex) => {
          const opened = await run(`(() => {
            const pane = document.querySelectorAll(".pane")[${paneIndex}];
            const button = pane?.querySelector(".sel-btn");
            if (!button) return false;
            button.click();
            return true;
          })()`);
          await sleep(250);
          const chosen = await run(`(() => {
            const option = [...document.querySelectorAll(".sel-menu li")].find((item) => item.textContent.includes("20261111-1813"));
            if (!option) return false;
            option.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
            return true;
          })()`);
          await sleep(700);
          const label = await run(`document.querySelectorAll(".pane")[${paneIndex}]?.querySelector(".sel-label")?.textContent?.trim() || ""`);
          return { opened, chosen, label };
        };
        const pickImages = await pickProject(3);
        const inboxDrop = await run(`(() => {
          const base64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==";
          const bytes = Uint8Array.from(atob(base64), (char) => char.charCodeAt(0));
          const file = new File([bytes], "probe-1x1.png", { type: "image/png" });
          const transfer = new DataTransfer();
          transfer.items.add(file);
          const zone = document.querySelector(".inbox");
          if (!zone) return false;
          zone.dispatchEvent(new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: transfer }));
          return true;
        })()`);
        await sleep(1200);
        const inboxState = await run(`(() => {
          const pane = document.querySelectorAll(".pane")[3];
          const cards = pane ? pane.querySelectorAll(".inbox-card") : [];
          const image = pane ? pane.querySelector(".inbox-card img") : null;
          return { cards: cards.length, names: [...cards].map((item) => item.querySelector("span")?.textContent?.trim() || ""), img: image ? image.naturalWidth : 0 };
        })()`);
        const imageDir = path.join(mediaProject, "媒体", "图片");
        const imageFiles = await readdir(imageDir).catch(() => []);
        const savedProbeImage = imageFiles.some((name) => name.includes("probe-1x1"));
        for (const name of imageFiles) {
          if (name.includes("probe-1x1")) await unlink(path.join(imageDir, name)).catch(() => {});
        }

        // 图像提示词：读 20261111-1813 的 媒体/出图/*.txt
        const imagesTabClick = await run(`(() => {
          const tab = [...document.querySelectorAll(".tabs .tab")].find((item) => item.textContent.includes("图像提示词"));
          if (!tab) return false;
          tab.click();
          return true;
        })()`);
        await sleep(300);
        const pickPrompts = await pickProject(4);
        await sleep(600);
        const imagesTabHint = await run(`(() => {
          const pane = document.querySelectorAll(".pane")[4];
          const cards = pane ? pane.querySelectorAll(".ip-card") : [];
          const text = pane ? pane.querySelector(".ip-text") : null;
          return {
            cards: cards.length,
            first: (text?.textContent || "").slice(0, 40),
            copies: pane ? pane.querySelectorAll(".ip-card button").length : 0,
            hint: pane ? (pane.textContent || "").trim().slice(0, 60) : ""
          };
        })()`);
        // 制作页签：项目名默认时间戳、TTS 从终端读取、没跑完时准备按钮禁用
        await run(`(() => { const tab = [...document.querySelectorAll(".tabs .tab")].find((item) => item.textContent.includes("制作")); if (tab) tab.click(); return true; })()`);
        await sleep(900);
        const makePanel = await run(`(() => {
          const pane = document.querySelectorAll(".pane")[1];
          const input = pane ? pane.querySelector(".field.inline input") : null;
          const buttons = pane ? Array.from(pane.querySelectorAll("button")) : [];
          const prepare = buttons.find((button) => button.textContent.includes("准备项目"));
          const text = pane ? pane.textContent || "" : "";
          return {
            open: Boolean(pane && !pane.classList.contains("hidden")),
            projectName: input ? input.value : "",
            prepareDisabled: prepare ? prepare.disabled : null,
            ttsFromTerminal: text.indexOf("从终端读取") >= 0,
            ttsMissing: text.indexOf("没找到") >= 0,
            options: pane ? pane.querySelectorAll(".make-options input[type=checkbox]").length : 0
          };
        })()`);
        await run(`(() => { const tab = [...document.querySelectorAll(".tabs .tab")].find((item) => item.textContent.trim() === "运行台"); if (tab) tab.click(); return true; })()`);

        // 节点输入值：选中 A01，检视器应出现「输入值」并列出它读的 a00 字段
        const clickedA01 = await run(`(() => {
          const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("A01_整理自然语言需求"));
          if (!node) return false;
          node.dispatchEvent(new MouseEvent("click", { bubbles: true }));
          return true;
        })()`);
        await sleep(300);
        const inputValues = await run(`(() => {
          const section = [...document.querySelectorAll(".sec")].find((item) => (item.querySelector(".sec-title")?.textContent || "").startsWith("输入值"));
          return { found: Boolean(section), items: section ? section.querySelectorAll(".out-item").length : 0 };
        })()`);

        // 下拉：点旁边（画布）要能收起来
        await run(`document.querySelector(".topbar .sel-btn").click()`);
        await sleep(200);
        const menuOpen = await run(`document.querySelectorAll(".sel-menu li").length`);
        await run(`document.querySelector(".canvas-wrap").dispatchEvent(new PointerEvent("pointerdown", { bubbles: true }))`);
        await sleep(200);
        const menuClosed = await run(`document.querySelectorAll(".sel-menu li").length === 0`);

        // 设置面板：能打开、有四个字段、关闭后不残留
        const clickedSettings = await run(clickText("设置"));
        await sleep(300);
        const settingsPanel = await run(`({
          open: Boolean(document.querySelector(".drawer.settings")),
          inputs: document.querySelectorAll(".drawer.settings input").length,
          selects: document.querySelectorAll(".drawer.settings .sel-btn").length,
          keyPlaceholder: document.querySelector(".drawer.settings input[type=password]")?.placeholder || ""
        })`);
        await run(clickText("关闭"));
        await sleep(150);
        const settingsClosed = await run(`!document.querySelector(".drawer.settings")`);
        const railLayout = await run(`(() => {
          const tool = document.querySelector(".rail .tool");
          const rail = document.querySelector(".rail");
          const actions = document.querySelector(".rail-actions");
          const railRect = rail.getBoundingClientRect();
          const actionsRect = actions.getBoundingClientRect();
          return {
            toolJustify: getComputedStyle(tool).justifyContent,
            actionsToBottom: Math.round(railRect.bottom - actionsRect.bottom),
            hasSettings: [...document.querySelectorAll(".rail button")].some((button) => button.textContent.trim() === "设置"),
            meta: document.querySelector(".tabs .meta")?.textContent?.trim() || ""
          };
        })()`);

        // 输入抽屉按 start 变量动态生成：04 应出现 10 个变量 + 2 个运行控制
        await run(clickText("输入"));
        await sleep(250);
        const inputDrawer = await run(`({
          fields: document.querySelectorAll(".drawer .field").length,
          labels: [...document.querySelectorAll(".drawer .field > span")].map((span) => span.textContent.trim()),
          hasCreative: [...document.querySelectorAll(".drawer .field > span")].some((span) => span.textContent.includes("创作偏好")),
          hasTtsBase: [...document.querySelectorAll(".drawer .field > span")].some((span) => span.textContent.includes("TTS Base"))
        })`);

        await run(clickText("关闭"));

        // 拖动：连线要跟着节点走；原地放回不写盘
        const workflowPath = path.join(desktopDir, "..", "Dify工作流", "04_黑帧口播_分组生成.yml");
        const hashFile = async (filePath) => createHash("sha1").update(await readFile(filePath)).digest("hex");
        const hashBefore = await hashFile(workflowPath);
        const dragStart = await run(`(() => {
          const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("A00_输入活动需求"));
          if (!node) return null;
          const rect = node.getBoundingClientRect();
          return { x: Math.round(rect.x + rect.width / 2), y: Math.round(rect.y + rect.height / 2), left: Math.round(rect.left), top: Math.round(rect.top) };
        })()`);
        let dragTest = { skipped: true };
        if (dragStart) {
          const beforeEdges = await run(`[...document.querySelectorAll(".canvas-edges path")].map((item) => item.getAttribute("d"))`);
          win.webContents.sendInputEvent({ type: "mouseDown", x: dragStart.x, y: dragStart.y, button: "left", clickCount: 1 });
          await sleep(100);
          win.webContents.sendInputEvent({ type: "mouseMove", x: dragStart.x + 60, y: dragStart.y + 30, button: "left" });
          win.webContents.sendInputEvent({ type: "mouseMove", x: dragStart.x + 120, y: dragStart.y + 60, button: "left" });
          await sleep(250);
          const mid = await run(`(() => {
            const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("A00_输入活动需求"));
            const rect = node.getBoundingClientRect();
            return {
              dx: Math.round(rect.left) - ${dragStart.left},
              dy: Math.round(rect.top) - ${dragStart.top},
              dragging: node.className.includes("dragging"),
              edges: [...document.querySelectorAll(".canvas-edges path")].map((item) => item.getAttribute("d"))
            };
          })()`);
          // 先用 DOM pointermove 把节点挪回原点，再 pointerup：moved=false，不应写 YAML
          await run(`(() => {
            const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("A00_输入活动需求"));
            node.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: ${dragStart.x}, clientY: ${dragStart.y}, pointerId: 1 }));
            return true;
          })()`);
          await sleep(200);
          await run(`(() => {
            const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("A00_输入活动需求"));
            node.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: ${dragStart.x}, clientY: ${dragStart.y}, pointerId: 1 }));
            return true;
          })()`);
          await sleep(500);
          const after = await run(`(() => {
            const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("A00_输入活动需求"));
            const rect = node.getBoundingClientRect();
            return { dx: Math.round(rect.left) - ${dragStart.left}, dy: Math.round(rect.top) - ${dragStart.top}, dragging: node.className.includes("dragging") };
          })()`);
          const hashAfter = await hashFile(workflowPath);
          dragTest = {
            mid,
            after,
            edgesChanged: JSON.stringify(beforeEdges) !== JSON.stringify(mid.edges),
            fileUnchanged: hashBefore === hashAfter,
          };
        }

        // 切到 01 看多消息提示词：d01 应拆成 system / user 两块，各自可编辑
        const openedWorkflowMenu = await run(`(() => { const button = document.querySelector(".topbar .sel-btn"); if (!button) return false; button.click(); return true; })()`);
        await sleep(250);
        const workflowMenu = await run(`[...document.querySelectorAll(".sel-menu li")].map((item) => item.textContent.trim())`);
        const switched = await run(`(() => {
          const option = [...document.querySelectorAll(".sel-menu li")].find((item) => item.textContent.includes("01_"));
          if (!option) return false;
          option.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
          return true;
        })()`);
        await sleep(1200);
        const clickedD01 = await run(`(() => {
          const node = [...document.querySelectorAll(".node")].find((item) => item.textContent.includes("D01_批量HTML草稿"));
          if (!node) return false;
          node.dispatchEvent(new MouseEvent("click", { bubbles: true }));
          return true;
        })()`);
        await sleep(350);
        const multiMessage = await run(`({
          selected: document.querySelector(".insp-head h2")?.textContent || "",
          messages: document.querySelectorAll(".prompt-msg").length,
          roles: [...document.querySelectorAll(".prompt-role")].map((item) => item.textContent.trim()),
          editButtons: [...document.querySelectorAll(".prompt-msg button")].map((button) => button.textContent.trim())
        })`);

        // 画布搜索：输入 D01 应出现结果，点第一条应选中并清空输入
        const searchTyped = await run(`(() => {
          const input = document.querySelector(".canvas-search input");
          if (!input) return false;
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value").set;
          setter.call(input, "D01");
          input.dispatchEvent(new Event("input", { bubbles: true }));
          return true;
        })()`);
        await sleep(300);
        const searchResults = await run(`({
          items: document.querySelectorAll(".search-results li").length,
          first: document.querySelector(".search-results li")?.textContent?.trim() || ""
        })`);
        const searchPicked = await run(`(() => {
          const item = document.querySelector(".search-results li");
          if (!item) return false;
          item.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
          return true;
        })()`);
        await sleep(350);
        const afterSearch = await run(`({
          selected: document.querySelector(".insp-head h2")?.textContent || "",
          query: document.querySelector(".canvas-search input")?.value || "",
          results: document.querySelectorAll(".search-results li").length
        })`);

        // 外部改动同步：往当前打开的工作流末尾写一行注释，再触发 window focus，应自动重载并提示
        let externalSync = { skipped: true };
        if (switched) {
          const target = path.join(desktopDir, "..", "Dify工作流", "01_有数字人完整视频工作流.yml");
          const original = await readFile(target);
          try {
            await writeFile(target, `${original.toString("utf8")}\n# probe-external-change\n`, "utf8");
            await run(`window.dispatchEvent(new Event("focus"))`);
            await sleep(900);
            externalSync = await run(`({ toast: document.querySelector(".toast")?.textContent?.trim() || "", nodes: document.querySelectorAll(".node").length })`);
          } finally {
            await writeFile(target, original);
          }
        }

        console.log("PROBE", JSON.stringify({ before, afterSelect, afterWheel, clickedZoomIn, afterZoomIn, clickedFit, afterFit, clicked100, after100, afterMin, widthBefore, collapsed, bottomBefore, consoleCollapsed, consoleBack, artifacts, mediaProbe, pickButton, dragTest, menuOpen, menuClosed, probeMockPort, panesEarly, runningStyle, firstLogLine, tabsText, inboxDrop, inboxState, imagesTabHint, makePanel, imagesTabClick, copied, clipboardLength: clipboardText.length, runError, clickedSettings, settingsPanel, settingsClosed, railLayout, artProject, artDir, artFile, artVideo, artBackList, artBackState, artMediaDir, artImageDir, artPng, artImage, back, reopened, clickedRun, runDialog, clickedStart, afterRun, inputDrawer, openedWorkflowMenu, workflowMenu, switched, clickedD01, multiMessage, clickedA01, inputValues, searchTyped, searchResults, searchPicked, afterSearch, externalSync }, null, 2));
        app.exit(0);
      } catch (error) {
        console.error("PROBE FAILED", error);
        app.exit(1);
      }
    });
  }
  if (smoke) {
    win.webContents.on("console-message", (_event, level, message) => console.log(`[renderer:${level}] ${message}`));
    win.webContents.on("did-finish-load", async () => {
      try {
        const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
        let summary = null;
        for (let attempt = 0; attempt < 40; attempt += 1) {
          summary = await win.webContents.executeJavaScript(
            "({ title: document.title, bridge: typeof window.wfs, nodes: document.querySelectorAll('.node').length, edges: document.querySelectorAll('.canvas-edges path').length, text: document.body.innerText.slice(0, 120) })",
          );
          if (summary && summary.nodes > 0) break;
          await sleep(200);
        }
        console.log("SMOKE", JSON.stringify(summary));
        app.exit(summary && summary.nodes > 0 ? 0 : 2);
      } catch (error) {
        console.error("SMOKE FAILED", error);
        app.exit(1);
      }
    });
  }
}

protocol.registerSchemesAsPrivileged([
  { scheme: "wfs-file", privileges: { standard: true, secure: true, supportFetchAPI: true, stream: true } },
]);

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".webp": "image/webp", ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".srt": "text/plain; charset=utf-8",
};

app.whenReady().then(() => {
  protocol.handle("wfs-file", async (request) => {
    try {
      const url = new URL(request.url);
      const filePath = decodeURIComponent(url.pathname.replace(/^\/+/, ""));
      const safe = core.safePath(filePath);
      const info = await stat(safe);
      const buffer = await readFile(safe);
      const type = MIME[safe.slice(safe.lastIndexOf("."))] ?? "application/octet-stream";
      const range = request.headers.get("range");
      if (range) {
        const match = /bytes=(\d*)-(\d*)/.exec(range);
        const start = match && match[1] ? Number(match[1]) : 0;
        const end = match && match[2] ? Number(match[2]) : info.size - 1;
        const chunk = buffer.subarray(start, end + 1);
        return new Response(chunk, {
          status: 206,
          headers: {
            "content-type": type,
            "content-range": `bytes ${start}-${end}/${info.size}`,
            "accept-ranges": "bytes",
          },
        });
      }
      return new Response(buffer, { headers: { "content-type": type, "accept-ranges": "bytes" } });
    } catch (error) {
      return new Response(String(error?.message ?? error), { status: 404 });
    }
  });
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
