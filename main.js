const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog } = require('electron');
// 多语言：语言清单、词典与 t() 机制，与渲染进程共用 locales/ 下的同一份文件
const Locales = require('./locales/index.js');
const i18n = require('./i18n.js');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const readline = require('readline');
const crypto = require('crypto');

// ── 单实例锁：防止多开 ──
// 注意：app.requestSingleInstanceLock() 必须在 app.whenReady() 之前调用
// 如果未获取到锁，直接退出，不执行任何后续代码
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  app.quit();
}

// ── 应用级配置（userData 下的 config.json）：硬件加速、开屏动画、主题等启动期偏好 ──
// 说明：曾经在开发模式下指向仓库根 config.json，导致运行时把 hardware_acceleration 与
// auth_token 写进被 git 跟踪的模板文件。现在统一用 userData，与打包模式行为一致。
function getHwAccelConfigPath() {
  return path.join(app.getPath('userData'), 'config.json');
}

// 读取应用级配置对象（读不到就返回空对象）
function readAppConfig() {
  try {
    var configPath = getHwAccelConfigPath();
    if (fs.existsSync(configPath)) {
      var cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      if (cfg && typeof cfg === 'object') return cfg;
    }
  } catch (e) {}
  return {};
}

function readHwAccelConfig() {
  try {
    var configPath = getHwAccelConfigPath();
    if (fs.existsSync(configPath)) {
      var cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
      return cfg.hardware_acceleration !== false;
    }
  } catch (e) {}
  return false; // 默认关闭，虚拟机兼容
}

var hwAccelEnabled = readHwAccelConfig();
if (!hwAccelEnabled) {
  app.disableHardwareAcceleration();
  app.commandLine.appendSwitch('disable-gpu');
  app.commandLine.appendSwitch('in-process-gpu');
}

// ── 全局异常捕获，输出到日志文件 ──
var logFile = path.join(app.getPath('userData'), 'digital-lab.log');
function writeLog(msg) {
  try {
    fs.appendFileSync(logFile, '[' + new Date().toISOString() + '] ' + msg + '\n');
  } catch(e) {}
}

process.on('uncaughtException', function(err) {
  writeLog('UNCAUGHT: ' + err.message + '\n' + err.stack);
  console.error('UNCAUGHT:', err);
});

let mainWindow = null;
let tray = null;
let isQuitting = false;
let pythonProcess = null;
let pythonRetryCount = 0;
const MAX_RETRIES = 3;
let latestState = { monitor: { cpu: 0, memory: 0, disk: 0, processes: [] }, hardware: null };

// Python stderr 缓冲：进程崩溃时写入日志辅助诊断
let pythonStderrBuffer = [];
const STDERR_BUFFER_MAX = 30;

// 待处理的 stdin 请求 Map: requestId → { resolve, reject, timer }
const pendingRequests = new Map();

function getWindowIcon() {
  return path.join(__dirname, 'build', 'icons', 'icon.ico');
}

function getTrayIcon() {
  return path.join(__dirname, 'build', 'icons', 'icon_tray.png');
}

function createWindow() {
  const windowIcon = nativeImage.createFromPath(getWindowIcon());
  // 窗口底色跟随已保存的主题：否则浅色主题下窗口先以深色底出现约 100~300ms，
  // 再被浅色开屏覆盖，看起来就是"闪黑"。主题存在应用级 config.json 的 theme 键里。
  var startupTheme = readAppConfig().theme === 'light' ? 'light' : 'dark';
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: startupTheme === 'light' ? '#f2f5f8' : '#0f1419',
    show: false,
    icon: windowIcon,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  writeLog('Window created, loading dashboard.html');
  mainWindow.loadFile('dashboard.html');

  // 超时兜底：5 秒后仍未 ready-to-show 则强制显示（VM 兼容）
  var showTimeout = setTimeout(function() {
    writeLog('Window show timeout fired');
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      mainWindow.show();
    }
  }, 5000);

  mainWindow.once('ready-to-show', function() {
    writeLog('Window ready-to-show');
    clearTimeout(showTimeout);
    mainWindow.show();
    // ── 正式接口：告诉渲染进程"窗口已显示" ──
    // 开屏动画据此决定起跑时刻：show() 之后合成器还要几百毫秒才恢复出帧，
    // 渲染进程收到这个事件才把它当作"确实已显示"的硬锚点（配合 rAF 停摆-恢复检测起跑）。
    // 与下面的临时探针并行发送：页面优先用 IPC，探针只作兼容与排障。
    try {
      mainWindow.webContents.send('window-shown');
    } catch (e) {}
  });

  // 页面加载完成
  mainWindow.webContents.on('did-finish-load', function() {
    writeLog('Page did-finish-load');
  });

  // 页面加载失败处理
  mainWindow.webContents.on('did-fail-load', function(_event, errorCode, errorDescription) {
    writeLog('Page load FAILED: ' + errorCode + ' ' + errorDescription);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.show();
    }
  });

  // 渲染进程崩溃处理
  mainWindow.webContents.on('render-process-gone', function(_event, details) {
    writeLog('Renderer GONE: ' + details.reason + ' exitCode=' + details.exitCode);
  });

  // 窗口显示确认
  mainWindow.on('show', function() {
    writeLog('Window show event fired');
  });

  // 关闭窗口 → 隐藏到托盘，而非退出
  mainWindow.on('close', function(e) {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
      writeLog('Window hidden to tray');
    }
  });

  mainWindow.on('closed', function() { mainWindow = null; writeLog('Window closed'); });
}

function startPython() {
  var isPackaged = app.isPackaged;
  var pythonPath, args, cwd;

  if (isPackaged) {
    // 打包模式：使用内置的 backend.exe
    pythonPath = path.join(process.resourcesPath, 'backend.exe');
    args = ['--json-mode'];
    cwd = process.resourcesPath;
  } else {
    // 开发模式：优先使用本地 backend.exe，否则使用系统 Python
    var backendExePath = path.join(__dirname, 'backend.exe');
    if (fs.existsSync(backendExePath)) {
      pythonPath = backendExePath;
      args = ['--json-mode'];
    } else {
      pythonPath = 'python';
      args = [path.join(__dirname, 'main.py'), '--json-mode'];
    }
    cwd = __dirname;
  }

  pythonProcess = spawn(pythonPath, args, {
    cwd: cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
  });

  const rl = readline.createInterface({ input: pythonProcess.stdout });

  rl.on('line', (line) => {
    try {
      const data = JSON.parse(line);

      // 命令响应（__cmd_response__ 标记）→ 匹配 pending 请求，不广播
      if (data.__cmd_response__) {
        if (data.requestId && pendingRequests.has(data.requestId)) {
          const pending = pendingRequests.get(data.requestId);
          clearTimeout(pending.timer);
          pendingRequests.delete(data.requestId);
          pending.resolve(data);
        }
        return;
      }

      // AI 流式响应 → 转发到渲染进程
      if (data.type === 'ai_token' && mainWindow && !mainWindow.isDestroyed()) {
        const tokenData = typeof data.data === 'object' ? data.data : { token: data.data, kind: 'content' };
        mainWindow.webContents.send('ai-token', { token: tokenData.token, kind: tokenData.kind || 'content', requestId: data.requestId });
        return;
      }
      if (data.type === 'ai_done' && mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('ai-done', { text: data.text, memory: data.memory, requestId: data.requestId });
        return;
      }
      // 兼容旧 AI 响应
      if (data.type === 'ai_response' && mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('ai-message', data.text);
        return;
      }

      // 终端输出（session_id + data 字段）→ 转发到 terminal-data 通道
      if (data.session_id !== undefined && data.data !== undefined) {
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('terminal-data', data);
        }
        return;
      }

      // 状态更新 → 缓存并推送
      latestState = data;
      // 首次收到有效数据 → 重置重试计数
      if (pythonRetryCount > 0 && data.hardware) {
        pythonRetryCount = 0;
      }
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('state-update', data);
      }
    } catch (e) {
      // ignore unparseable lines
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    const text = data.toString().trim();
    if (text) {
      console.error(`[Python] ${text}`);
      pythonStderrBuffer.push('[' + new Date().toISOString() + '] ' + text);
      if (pythonStderrBuffer.length > STDERR_BUFFER_MAX) {
        pythonStderrBuffer.shift();
      }
    }
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] exited with code ${code}`);
    // 写入崩溃诊断日志
    const stderrTail = pythonStderrBuffer.length > 0
      ? '\n--- stderr tail ---\n' + pythonStderrBuffer.join('\n')
      : '';
    writeLog('Python process exited code=' + code + stderrTail);
    pythonStderrBuffer = [];
    pythonProcess = null;
    // 清理所有未完成的请求
    for (const [id, pending] of pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new Error('Python process closed'));
    }
    pendingRequests.clear();
    // 重新拉起（遵守重试次数限制）
    pythonRetryCount++;
    if (pythonRetryCount <= MAX_RETRIES && mainWindow && !mainWindow.isDestroyed()) {
      console.log(`[Python] retry ${pythonRetryCount}/${MAX_RETRIES}...`);
      setTimeout(startPython, 2000);
    } else if (pythonRetryCount > MAX_RETRIES) {
      console.error(`[Python] max retries (${MAX_RETRIES}) exceeded`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('python-status', {
          available: false,
          error: `Process exited with code ${code} after ${MAX_RETRIES} retries`,
          retriesExhausted: true,
        });
      }
    }
  });

  pythonProcess.on('error', (err) => {
    console.error(`[Python] spawn error: ${err.message}`);
    pythonProcess = null;
    pythonRetryCount++;
    if (pythonRetryCount <= MAX_RETRIES && mainWindow && !mainWindow.isDestroyed()) {
      console.log(`[Python] retry ${pythonRetryCount}/${MAX_RETRIES}...`);
      setTimeout(startPython, 2000);
    } else {
      // 超过重试次数，通知渲染进程
      console.error(`[Python] max retries (${MAX_RETRIES}) exceeded`);
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('python-status', {
          available: false,
          error: err.message,
          retriesExhausted: true,
        });
      }
    }
  });
}

/**
 * 向 Python 子进程发送命令，返回 Promise。
 * 自动生成 requestId，Python 响应时原样带回。
 */
function sendToPython(cmd) {
  return new Promise((resolve, reject) => {
    if (!pythonProcess || !pythonProcess.stdin.writable) {
      reject(new Error('Python process not available'));
      return;
    }

    const requestId = crypto.randomUUID();
    cmd.requestId = requestId;

    // 10 秒超时
    const timer = setTimeout(() => {
      pendingRequests.delete(requestId);
      reject(new Error(`Request timeout: ${cmd.cmd || 'unknown'}`));
    }, 10000);

    pendingRequests.set(requestId, { resolve, reject, timer });

    try {
      pythonProcess.stdin.write(JSON.stringify(cmd) + '\n');
    } catch (e) {
      clearTimeout(timer);
      pendingRequests.delete(requestId);
      reject(e);
    }
  });
}

function createTray() {
  // 建托盘之前先按配置把语言定好（托盘菜单文案走 i18n）
  applyConfiguredLanguage();
  // 创建托盘图标（六边形 QRS 波形）：单独的 32x32 小尺寸优化版，笔画更粗以便 16px 显示时清晰
  const icon = nativeImage.createFromPath(getTrayIcon());
  tray = new Tray(icon);
  tray.setToolTip('DigitalLab');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: i18n.t('tray.showMain'),
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    { type: 'separator' },
    {
      label: i18n.t('tray.quit'),
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

// ============================================================
//  IPC handlers
// ============================================================

ipcMain.handle('get-hardware', () => {
  return latestState.hardware;
});

ipcMain.handle('get-processes', () => {
  return latestState.monitor?.processes || [];
});

ipcMain.handle('get-history', async (_event, hours) => {
  try {
    const response = await sendToPython({ cmd: 'get_history', hours: hours || 24 });
    // Python 响应: { cpu_avg, cpu_max, memory_avg, memory_max, disk_avg, disk_max, count }
    if (response.error) {
      return { cpu_avg: 0, cpu_max: 0, memory_avg: 0, memory_max: 0, disk_avg: 0, disk_max: 0, count: 0, error: response.error };
    }
    return {
      cpu_avg: response.cpu_avg || 0,
      cpu_max: response.cpu_max || 0,
      memory_avg: response.memory_avg || 0,
      memory_max: response.memory_max || 0,
      disk_avg: response.disk_avg || 0,
      disk_max: response.disk_max || 0,
      count: response.count || 0,
    };
  } catch (e) {
    return { cpu_avg: 0, cpu_max: 0, memory_avg: 0, memory_max: 0, disk_avg: 0, disk_max: 0, count: 0, error: e.message };
  }
});

ipcMain.handle('send-message', async (_event, text) => {
  try {
    const response = await sendToPython({ cmd: 'ai_message', text });
    return response;
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('send-command', async (_event, cmd) => {
  try {
    return await sendToPython(cmd);
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('get-config', async () => {
  try {
    return await sendToPython({ cmd: 'get_config' });
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('save-config', async (_event, config) => {
  try {
    return await sendToPython({ cmd: 'save_config', config });
  } catch (e) {
    return { error: e.message };
  }
});

ipcMain.handle('quit-app', () => {
  isQuitting = true;
  app.quit();
});

// ── 硬件加速配置（直接读写 config.json，不经过 Python） ──
ipcMain.handle('get-hardware-accel', function() {
  try {
    var p = getHwAccelConfigPath();
    if (fs.existsSync(p)) {
      var cfg = JSON.parse(fs.readFileSync(p, 'utf-8'));
      return { enabled: cfg.hardware_acceleration !== false };
    }
  } catch(e) {}
  return { enabled: true };
});

ipcMain.handle('set-hardware-accel', function(_event, enabled) {
  try {
    var p = getHwAccelConfigPath();
    var cfg = {};
    if (fs.existsSync(p)) {
      cfg = JSON.parse(fs.readFileSync(p, 'utf-8'));
    }
    cfg.hardware_acceleration = !!enabled;
    fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf-8');
    return { ok: true, needRestart: true };
  } catch(e) {
    return { ok: false, error: e.message };
  }
});

// ── 开屏动画开关（应用级配置，与硬件加速同一份 config.json，键名 splash_animation） ──
ipcMain.handle('get-splash-animation', function() {
  try {
    var cfg = readAppConfig();
    return { enabled: cfg.splash_animation !== false };
  } catch (e) {}
  return { enabled: true };
});

ipcMain.handle('set-splash-animation', function(_event, enabled) {
  try {
    var p = getHwAccelConfigPath();
    var cfg = readAppConfig();
    cfg.splash_animation = !!enabled;
    fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf-8');
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// 启动期同步读取：开屏覆盖层的脚本在页面解析阶段就要决定是否渲染，异步 invoke 来不及，
// 所以单开一条 sendSync 通道（每次启动只调用一次，开销可忽略）。
ipcMain.on('get-splash-animation-sync', function(event) {
  var enabled = true;
  try {
    var cfg = readAppConfig();
    enabled = cfg.splash_animation !== false;
  } catch (e) {}
  event.returnValue = enabled;
});

// 启动期同步读取主题：<head> 里的初始化脚本要在首帧前定好 data-theme，异步来不及。
// config.json 是主题的唯一权威源；localStorage 只作渲染进程侧的快速缓存。
ipcMain.on('get-theme-sync', function(event) {
  var theme = 'dark';
  try {
    var cfg = readAppConfig();
    theme = (cfg.theme === 'light') ? 'light' : 'dark';
  } catch (e) {}
  event.returnValue = theme;
});

// ── 主题持久化（应用级配置，键名 theme）：供下次启动设置窗口底色，避免浅色主题下闪黑 ──
ipcMain.handle('set-theme', function(_event, theme) {
  try {
    var p = getHwAccelConfigPath();
    var cfg = readAppConfig();
    cfg.theme = (theme === 'light') ? 'light' : 'dark';
    fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf-8');
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ── 语言（应用级配置，键名 language）：与主题同一套写法 ──
// 默认值来自 locales/index.js 的默认语言函数（系统语言以 zh 开头用 zh-CN，否则 en-US）。
function resolveConfiguredLanguage() {
  var lang = null;
  try {
    var cfg = readAppConfig();
    if (typeof cfg.language === 'string' && Locales.hasLanguage(cfg.language)) { lang = cfg.language; }
  } catch (e) {}
  if (!lang) { lang = Locales.getDefaultLanguage(); }
  return lang;
}

// 把配置里的语言应用到主进程自己的 i18n 实例（托盘菜单与原生对话框都用它取文案）
function applyConfiguredLanguage() {
  var lang = resolveConfiguredLanguage();
  i18n.setLanguage(lang);
  return lang;
}

// 启动期同步读取语言：<head> 脚本要在首帧前定好 <html lang> 并装好词典
ipcMain.on('get-language-sync', function(event) {
  event.returnValue = resolveConfiguredLanguage();
});

// 语言切换：校验必须在本语言清单里，非法值直接拒绝（返回 ok:false），不写文件
ipcMain.handle('set-language', function(_event, lang) {
  try {
    if (!Locales.hasLanguage(lang)) { return { ok: false, error: 'unsupported language: ' + lang }; }
    var p = getHwAccelConfigPath();
    var cfg = readAppConfig();
    cfg.language = lang;
    fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf-8');
    i18n.setLanguage(lang);   // 主进程同步切换，后续对话框/托盘立刻用新语言
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ── 快速部署占位：功能尚未实现，仅弹原生提示对话框 ──
ipcMain.handle('quick-deploy-soon', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  const opts = {
    type: 'info',
    title: 'DigitalLab',
    message: i18n.t('dlg.deploySoon.message'),
    buttons: [i18n.t('dlg.deploySoon.button')],
    defaultId: 0,
    cancelId: 0,
    noLink: true,
  };
  try {
    const r = win ? await dialog.showMessageBox(win, opts) : await dialog.showMessageBox(opts);
    return { ok: true, response: r.response };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ── AI 记忆删除确认：Windows 原生警告对话框（不可逆操作，最大化注意力） ──
ipcMain.handle('confirm-memory-delete', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender) || mainWindow;
  const opts = {
    type: 'warning',
    title: 'DigitalLab',
    message: i18n.t('dlg.memoryDelete.message'),
    buttons: [i18n.t('dlg.memoryDelete.delete'), i18n.t('dlg.memoryDelete.cancel')],
    defaultId: 1,   // 默认选中“取消”，防止误按回车直接删除
    cancelId: 1,    // 关闭对话框等同取消
    noLink: true,
  };
  try {
    const r = win ? await dialog.showMessageBox(win, opts) : await dialog.showMessageBox(opts);
    return { confirmed: r.response === 0 };
  } catch (e) {
    return { confirmed: false, error: e.message };
  }
});

// ============================================================
//  应用启动
// ============================================================

// ── 应用名：系统对话框/提示显示为 DigitalLab，而不是包名 digital-lab ──
// 注意：userData 路径会随应用名变化，这里先冻结原路径，避免升级后配置与日志目录迁移
const ORIGINAL_USER_DATA = app.getPath('userData');
app.setName('DigitalLab');
try { app.setPath('userData', ORIGINAL_USER_DATA); } catch (e) {}

// ── 任务栏身份（AppUserModelID）：与 electron-builder 写入快捷方式的 build.appId 保持一致 ──
// 否则运行进程与安装快捷方式的 AUMID 不一致，固定到任务栏会出现重复按钮/固定项不合并。
// MSIX/商店包的 AUMID 由系统按包标识分配，硬设会破坏商店包身份，故仅在非商店包设置。
if (!process.windowsStore) {
  app.setAppUserModelId('com.digitallab.desktop');
}

// 第二个实例启动时，聚焦已有窗口
app.on('second-instance', function() {
  if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
});

app.whenReady().then(() => {
  if (!gotTheLock) return;
  createWindow();
  createTray();
  startPython();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else if (mainWindow) mainWindow.show();
  });
});

app.on('window-all-closed', () => {
  // 不退出，因为有关闭到托盘
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
  // 只在真正退出时调用 app.quit()
});

app.on('before-quit', () => {
  isQuitting = true;
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});
