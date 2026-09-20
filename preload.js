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

  // 主进程 show() 之后发来的一次性事件：窗口已显示。
  // 开屏动画用它当"确实已显示"的硬锚点（配合 rAF 停摆-恢复检测决定起跑时刻）。
  onWindowShown(callback) {
    const handler = () => callback();
    ipcRenderer.on('window-shown', handler);
    return () => ipcRenderer.removeListener('window-shown', handler);
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

  // 快速部署占位：功能未实现，仅弹原生提示框
  confirmQuickDeploy() {
    return ipcRenderer.invoke('quick-deploy-soon');
  },

  // 开屏动画开关（应用级配置，userData 下的 config.json）
  getSplashAnimation() {
    return ipcRenderer.invoke('get-splash-animation');
  },

  setSplashAnimation(enabled) {
    return ipcRenderer.invoke('set-splash-animation', enabled);
  },

  // 启动期同步读取：开屏脚本在页面解析阶段就要决定是否渲染，异步 invoke 来不及
  getSplashAnimationSync() {
    try {
      return ipcRenderer.sendSync('get-splash-animation-sync') !== false;
    } catch (e) {
      return true;   // 读不到就按"播放"处理，保持原行为
    }
  },

  // 主题持久化：供下次启动设置窗口底色，避免浅色主题下闪黑
  setTheme(theme) {
    return ipcRenderer.invoke('set-theme', theme);
  },

  // 语言：启动期同步读取（<head> 脚本要在首帧前定好 <html lang> 并装好词典），运行时切换走 invoke
  getLanguageSync() {
    try {
      var l = ipcRenderer.sendSync('get-language-sync');
      return typeof l === 'string' ? l : null;
    } catch (e) {
      return null;
    }
  },

  setLanguage(lang) {
    return ipcRenderer.invoke('set-language', lang);
  },

  // 启动期同步读取主题（config.json 是权威源）：<head> 脚本要在首帧前定好 data-theme。
  // 读不到时返回 null，由调用方回退到 localStorage 缓存。
  getThemeSync() {
    try {
      var t = ipcRenderer.sendSync('get-theme-sync');
      return (t === 'light' || t === 'dark') ? t : null;
    } catch (e) {
      return null;
    }
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
