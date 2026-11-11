// 浏览器调试壳：与 Electron 主进程同一套 /api，渲染代码完全一致。
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import * as core from "../electron/core.mjs";

const desktopDir = core.desktopDir;
const port = Number(process.env.WF_DEV_PORT ?? 4321);
const clients = new Set();

function broadcast(name, payload) {
  const message = `event: ${name}\ndata: ${JSON.stringify(payload)}\n\n`;
  for (const response of clients) response.write(message);
}

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8", ".map": "application/json; charset=utf-8",
  ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8",
  ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".mp4": "video/mp4", ".mp3": "audio/mpeg", ".srt": "text/plain; charset=utf-8",
};

async function jsonBody(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const text = Buffer.concat(chunks).toString("utf8");
  return text ? JSON.parse(text) : {};
}

function send(response, status, value) {
  const body = JSON.stringify(value);
  response.writeHead(status, { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" });
  response.end(body);
}

async function serveStatic(response, pathname) {
  const clean = pathname === "/" ? "/renderer/index.html" : pathname;
  const target = path.normalize(path.join(desktopDir, clean));
  if (!target.startsWith(desktopDir)) return send(response, 403, { error: "forbidden" });
  if (!existsSync(target)) return send(response, 404, { error: "not found" });
  const data = await readFile(target);
  response.writeHead(200, { "content-type": MIME[path.extname(target)] ?? "application/octet-stream" });
  response.end(data);
}

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", `http://127.0.0.1:${port}`);
  try {
    if (url.pathname === "/api/events") {
      response.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-store", connection: "keep-alive" });
      response.write(": connected\n\n");
      clients.add(response);
      request.on("close", () => clients.delete(response));
      return;
    }
    if (url.pathname === "/api/workflows") return send(response, 200, await core.listWorkflows());
    if (url.pathname === "/api/env") return send(response, 200, await core.envInfo());
    if (url.pathname === "/api/inputs") return send(response, 200, await core.inputDefaults());
    if (url.pathname === "/api/projects") return send(response, 200, await core.listProjects());
    if (url.pathname === "/api/update-node" && request.method === "POST") {
      const payload = await jsonBody(request);
      const result = await core.updateNode(payload);
      return send(response, 200, { ...result, graph: await core.loadGraph(payload.path) });
    }
    if (url.pathname === "/api/add-node" && request.method === "POST") {
      return send(response, 200, await core.addNode(await jsonBody(request)));
    }
    if (url.pathname === "/api/remove-node" && request.method === "POST") {
      return send(response, 200, await core.removeNode(await jsonBody(request)));
    }
    if (url.pathname === "/api/connect" && request.method === "POST") {
      return send(response, 200, await core.connectNodes(await jsonBody(request)));
    }
    if (url.pathname === "/api/move-node" && request.method === "POST") {
      return send(response, 200, await core.moveNode(await jsonBody(request)));
    }
    if (url.pathname === "/api/history" && request.method === "POST") {
      return send(response, 200, await core.historyStatus(await jsonBody(request)));
    }
    if (url.pathname === "/api/undo" && request.method === "POST") {
      return send(response, 200, await core.undo(await jsonBody(request)));
    }
    if (url.pathname === "/api/redo" && request.method === "POST") {
      return send(response, 200, await core.redo(await jsonBody(request)));
    }
    if (url.pathname === "/api/remove-edge" && request.method === "POST") {
      return send(response, 200, await core.removeEdge(await jsonBody(request)));
    }
    if (url.pathname === "/api/file-url" && request.method === "POST") {
      const { path: filePath } = await jsonBody(request);
      return send(response, 200, { url: `/files?path=${encodeURIComponent(filePath)}`, href: await core.fileUrl(filePath) });
    }
    if (url.pathname === "/api/presets") return send(response, 200, core.termPresets());
    if (url.pathname === "/api/load" && request.method === "POST") {
      const { path: filePath } = await jsonBody(request);
      return send(response, 200, await core.loadGraph(filePath));
    }
    if (url.pathname === "/api/files" && request.method === "POST") {
      const { path: dirPath } = await jsonBody(request);
      return send(response, 200, await core.listFiles(dirPath));
    }
    if (url.pathname === "/api/read" && request.method === "POST") {
      const { path: filePath } = await jsonBody(request);
      return send(response, 200, await core.readText(filePath));
    }
    if (url.pathname === "/api/run" && request.method === "POST") {
      const options = await jsonBody(request);
      const result = await core.runWorkflow({
        ...options,
        onEvent: (payload) => broadcast("trace", payload),
      });
      return send(response, 200, result);
    }
    if (url.pathname === "/api/exec" && request.method === "POST") {
      const { cmd, cwd } = await jsonBody(request);
      const run = core.startCommand({
        cmd,
        cwd,
        onData: (payload) => broadcast("term", payload),
        onExit: (payload) => broadcast("term-done", payload),
      });
      return send(response, 200, { id: run.id });
    }
    if (url.pathname === "/files") {
      const filePath = url.searchParams.get("path") ?? "";
      const safe = core.safePath(filePath);
      const info = await stat(safe);
      const data = await readFile(safe);
      const type = MIME[path.extname(safe)] ?? "application/octet-stream";
      const range = request.headers.range;
      if (range) {
        const match = /bytes=(\d*)-(\d*)/.exec(range);
        const start = match && match[1] ? Number(match[1]) : 0;
        const end = match && match[2] ? Number(match[2]) : info.size - 1;
        const chunk = data.subarray(start, end + 1);
        response.writeHead(206, {
          "content-type": type,
          "content-length": chunk.length,
          "content-range": `bytes ${start}-${end}/${info.size}`,
          "accept-ranges": "bytes",
        });
        response.end(chunk);
        return;
      }
      response.writeHead(200, {
        "content-type": type,
        "content-length": info.size,
        "accept-ranges": "bytes",
      });
      response.end(data);
      return;
    }
    return await serveStatic(response, url.pathname);
  } catch (error) {
    send(response, 500, { error: String(error?.message ?? error) });
  }
});

server.listen(port, "127.0.0.1", () => {
  console.log(`dev shell: http://127.0.0.1:${port}/renderer/index.html`);
});
