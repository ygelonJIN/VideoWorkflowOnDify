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
  const win = new BrowserWindow({
    show: !smoke,
    width: 1480,
    height: 940,
    minWidth: 1080,
    minHeight: 680,
    backgroundColor: "#f4f1ea",
    titleBarStyle: "hiddenInset",
    trafficLightPosition: { x: 14, y: 16 },
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
