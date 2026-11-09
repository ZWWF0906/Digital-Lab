// preload.js — P0 安全边界（DL-SEC-02 / S3）
// 只暴露固定业务函数：渲染进程无法指定 Python 命令名、无法传任意 host/port/凭据、
// 无法调用通用 sendCommand。每个函数由 Electron 主进程做参数校验与来源校验。
const { contextBridge, ipcRenderer } = require('electron');

const invoke = (op, args) => ipcRenderer.invoke('api:' + op, args || {});

const TEST_HOOKS_ARG = Array.isArray(process.argv) && process.argv.indexOf('--dl-test-hooks') >= 0;
if (TEST_HOOKS_ARG) {
  contextBridge.exposeInMainWorld('__c1Test', {
    injectState(state) { return invoke('test:inject_state', { state }); },
  });
}

contextBridge.exposeInMainWorld('digitalLab', {
  // ── 事件订阅（只读）──
  onStateUpdate(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('state-update', handler);
    return () => ipcRenderer.removeListener('state-update', handler);
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
  onPythonStatus(callback) {
    const handler = (_event, status) => callback(status);
    ipcRenderer.on('python-status', handler);
    return () => ipcRenderer.removeListener('python-status', handler);
  },
  onWindowShown(callback) {
    const handler = () => callback();
    ipcRenderer.on('window-shown', handler);
    return () => ipcRenderer.removeListener('window-shown', handler);
  },
  onNasTestResult(callback) {
    const handler = (_event, data) => callback(data);
    ipcRenderer.on('nas-test-result', handler);
    return () => ipcRenderer.removeListener('nas-test-result', handler);
  },

  // ── 硬件与配置（配置只返回字段白名单与凭据状态）──
  getHardware() { return invoke('hardware:get'); },
  getConfig() { return invoke('config:get'); },
  saveSettings(patch, dirty) { return invoke('config:save_settings', { patch, dirty }); },
  saveDevice(device, dirty) { return invoke('config:save_device', { device, dirty }); },
  deleteDevice(name) { return invoke('config:delete_device', { name }); },
  clearCredential(kind, name) { return invoke('config:clear_credential', { kind, name }); },
  reloadConfig() { return invoke('config:reload'); },

  // ── AI 记忆与对话历史 ──
  chooseMemoryDir() { return invoke('memory:choose_dir'); },
  chooseCaBundle() { return invoke('ai:choose_ca_bundle'); },
  memoryStatus() { return invoke('memory:status'); },
  memoryList(limit) { return invoke('memory:list', { limit }); },
  memoryDelete(index, expectedSha256) { return invoke('memory:delete', { index, expectedSha256 }); },
  memoryClear() { return invoke('memory:clear'); },
  memoryDedupe() { return invoke('memory:dedupe'); },
  historyList(limit) { return invoke('history:list', { limit }); },
  historyAppend(role, content) { return invoke('history:append', { role, content }); },
  historyClear() { return invoke('history:clear'); },

  // ── AI 对话（只读事件 + 受控请求）──
  aiChat(messages, provider, lang) { return invoke('ai:chat', { messages, provider, lang }); },

  // ── NAS 信任与连通性 ──
  // 信任指纹不能由 renderer 提交；probe/test 只返回主进程生成的 challengeId。
  testNasConnection(deviceId) { return invoke('nas:test', { deviceId }); },
  sshProbe(deviceId) { return invoke('nas:probe', { deviceId }); },
  sshConfirmTrust(challengeId) { return invoke('nas:confirm_trust', { challengeId }); },

  // ── 独立终端窗口：Dashboard 只能请求打开，不能持有输入/attach 能力 ──
  terminalOpen(deviceId, cols, rows) { return invoke('terminal:open', { deviceId, cols, rows }); },

  // ── 应用信息与界面偏好（固定通道，参数由主进程校验）──
  getAppVersion() { return ipcRenderer.invoke('get-app-version'); },
  quit() { ipcRenderer.invoke('quit-app'); },
  getHardwareAccel() { return ipcRenderer.invoke('get-hardware-accel'); },
  setHardwareAccel(enabled) { return ipcRenderer.invoke('set-hardware-accel', enabled); },
  getSplashAnimation() { return ipcRenderer.invoke('get-splash-animation'); },
  setSplashAnimation(enabled) { return ipcRenderer.invoke('set-splash-animation', enabled); },
  setTheme(theme) { return ipcRenderer.invoke('set-theme', theme); },
  setLanguage(lang) { return ipcRenderer.invoke('set-language', lang); },
  setOnboardingDone(done) { return ipcRenderer.invoke('set-onboarding-done', done); },
  confirmQuickDeploy() { return ipcRenderer.invoke('quick-deploy-soon'); },

  // 外部链接：只接受固定目的地键（issues / mailto），不接受任意 URL
  openExternal(target) { return invoke('app:open_external', { target }); },

  // ── 启动期同步读取（渲染进程 <head> 脚本使用）──
  getSplashAnimationSync() {
    try { return ipcRenderer.sendSync('get-splash-animation-sync') !== false; } catch (e) { return true; }
  },
  getLanguageSync() {
    try {
      const lang = ipcRenderer.sendSync('get-language-sync');
      return typeof lang === 'string' ? lang : null;
    } catch (e) { return null; }
  },
  getOnboardingDoneSync() {
    try { return ipcRenderer.sendSync('get-onboarding-done-sync') === true; } catch (e) { return false; }
  },
  getThemeSync() {
    try {
      const theme = ipcRenderer.sendSync('get-theme-sync');
      return (theme === 'light' || theme === 'dark') ? theme : null;
    } catch (e) { return null; }
  },
});
