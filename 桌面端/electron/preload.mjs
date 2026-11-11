import { contextBridge, ipcRenderer } from "electron";

function subscribe(channel, handler) {
  const listener = (_event, payload) => handler(payload);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.off(channel, listener);
}

contextBridge.exposeInMainWorld("wfs", {
  workflows: () => ipcRenderer.invoke("wf:workflows"),
  load: (filePath) => ipcRenderer.invoke("wf:load", filePath),
  rev: (filePath) => ipcRenderer.invoke("wf:rev", filePath),
  run: (options) => ipcRenderer.invoke("wf:run", options),
  cancel: (clientId) => ipcRenderer.invoke("wf:cancel", clientId),
  env: () => ipcRenderer.invoke("wf:env"),
  inputs: () => ipcRenderer.invoke("wf:inputs"),
  projects: () => ipcRenderer.invoke("wf:projects"),
  updateNode: (payload) => ipcRenderer.invoke("wf:update-node", payload),
  fileUrl: (filePath) => ipcRenderer.invoke("wf:file-url", filePath),
  addNode: (payload) => ipcRenderer.invoke("wf:add-node", payload),
  removeNode: (payload) => ipcRenderer.invoke("wf:remove-node", payload),
  connect: (payload) => ipcRenderer.invoke("wf:connect", payload),
  removeEdge: (payload) => ipcRenderer.invoke("wf:remove-edge", payload),
  moveNode: (payload) => ipcRenderer.invoke("wf:move-node", payload),
  history: (payload) => ipcRenderer.invoke("wf:history", payload),
  undo: (payload) => ipcRenderer.invoke("wf:undo", payload),
  redo: (payload) => ipcRenderer.invoke("wf:redo", payload),
  files: (dirPath) => ipcRenderer.invoke("wf:files", dirPath),
  readText: (filePath) => ipcRenderer.invoke("wf:read", filePath),
  open: (filePath) => ipcRenderer.invoke("wf:open", filePath),
  presets: () => ipcRenderer.invoke("wf:presets"),
  exec: (options) => ipcRenderer.invoke("wf:exec", options),
  onEvent: (handler) => subscribe("wf:event", handler),
  onTerm: (handler) => {
    const offData = subscribe("wf:term", (payload) => handler({ kind: "data", ...payload }));
    const offDone = subscribe("wf:term-done", (payload) => handler({ kind: "done", ...payload }));
    return () => {
      offData();
      offDone();
    };
  },
});
