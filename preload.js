const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('digitalLab', {
  onStateUpdate(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('state-update', handler);
    return () => ipcRenderer.removeListener('state-update', handler);
  },

  getHardware() {
    return ipcRenderer.invoke('get-hardware');
  },

  getProcesses() {
    return ipcRenderer.invoke('get-processes');
  },

  getHistory(hours) {
    return ipcRenderer.invoke('get-history', hours);
  },

  sendMessage(text) {
    return ipcRenderer.invoke('send-message', text);
  },

  aiChat(messages, provider) {
    return ipcRenderer.invoke('send-command', { cmd: 'ai_chat', messages, provider });
  },

  onAiToken(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('ai-token', handler);
    return () => ipcRenderer.removeListener('ai-token', handler);
  },

  onAiDone(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('ai-done', handler);
    return () => ipcRenderer.removeListener('ai-done', handler);
  },

  onMessage(callback) {
    const handler = (_event, text) => callback(text);
    ipcRenderer.on('ai-message', handler);
    return () => ipcRenderer.removeListener('ai-message', handler);
  },

  onPythonStatus(callback) {
    const handler = (_event, status) => callback(status);
    ipcRenderer.on('python-status', handler);
    return () => ipcRenderer.removeListener('python-status', handler);
  },

  onTerminalData(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('terminal-data', handler);
    return () => ipcRenderer.removeListener('terminal-data', handler);
  },

  sendCommand(cmd) {
    return ipcRenderer.invoke('send-command', cmd);
  },

  getNasDevices() {
    return ipcRenderer.invoke('send-command', { cmd: 'get_nas_devices' });
  },

  getConfig() {
    return ipcRenderer.invoke('get-config');
  },

  saveConfig(config) {
    return ipcRenderer.invoke('save-config', config);
  },

  confirmMemoryDelete() {
    return ipcRenderer.invoke('confirm-memory-delete');
  },

  quit() {
    ipcRenderer.invoke('quit-app');
  },

  getHardwareAccel() {
    return ipcRenderer.invoke('get-hardware-accel');
  },

  setHardwareAccel(enabled) {
    return ipcRenderer.invoke('set-hardware-accel', enabled);
  },
});
