// preload-terminal.js — C1 U02 独立终端窗口的最小能力面。
// 该 preload 只由主进程创建的 terminal.html 使用；Dashboard 不加载它。
const { contextBridge, ipcRenderer } = require('electron');

const invoke = (op, args) => ipcRenderer.invoke('api:terminal:' + op, args || {});

contextBridge.exposeInMainWorld('terminalAPI', {
  onContext(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('terminal-context', handler);
    return () => ipcRenderer.removeListener('terminal-context', handler);
  },
  onData(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('terminal-data', handler);
    return () => ipcRenderer.removeListener('terminal-data', handler);
  },
  attach(sessionId) { return invoke('attach', { sessionId }); },
  input(sessionId, data) { return invoke('input', { sessionId, data }); },
  resize(sessionId, cols, rows) { return invoke('resize', { sessionId, cols, rows }); },
  close(sessionId) { return invoke('close', { sessionId }); },
});
