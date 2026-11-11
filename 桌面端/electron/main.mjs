import { app, BrowserWindow, ipcMain, protocol, shell } from "electron";
import { readFile, stat } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as core from "./core.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const desktopDir = path.resolve(here, "..");
console.log(`[wfs] Electron ${process.versions.electron} · app ${desktopDir}`);

ipcMain.handle("wf:workflows", () => core.listWorkflows());
ipcMain.handle("wf:env", () => core.envInfo());
ipcMain.handle("wf:inputs", () => core.inputDefaults());
ipcMain.handle("wf:load", (_event, filePath) => core.loadGraph(filePath));
ipcMain.handle("wf:run", (event, options) =>
  core.runWorkflow({
    ...options,
    onEvent: (payload) => {
      if (!event.sender.isDestroyed()) event.sender.send("wf:event", payload);
    },
  }),
);
ipcMain.handle("wf:projects", () => core.listProjects());
ipcMain.handle("wf:update-node", async (_event, payload) => {
  const result = await core.updateNode(payload);
  return { ...result, graph: await core.loadGraph(payload.path) };
});
ipcMain.handle("wf:file-url", async (_event, filePath) => {
  const safe = core.safePath(filePath);
  return `wfs-file://${encodeURI(safe)}`;
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
      const run = (code) => win.webContents.executeJavaScript(code);
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
        const artifacts = await run(`({ browser: !!document.querySelector(".browser"), canvas: !!document.querySelector(".canvas-wrap"), inspector: !!document.querySelector(".inspector") })`);
        await run(clickText("画布"));
        await sleep(200);
        const back = await run(`({ zoom: document.querySelector(".canvas-hud .zoom").textContent, canvas: !!document.querySelector(".canvas-wrap") })`);

        console.log("PROBE", JSON.stringify({ before, afterSelect, afterWheel, clickedZoomIn, afterZoomIn, clickedFit, afterFit, clicked100, after100, afterMin, widthBefore, collapsed, bottomBefore, consoleCollapsed, consoleBack, artifacts, back }, null, 2));
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
      const filePath = decodeURIComponent(url.pathname);
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
