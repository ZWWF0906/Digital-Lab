const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage } = require('electron');
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

// ── 读取硬件加速配置（app.whenReady 之前） ──
function getHwAccelConfigPath() {
  if (app.isPackaged) {
    return path.join(app.getPath('userData'), 'config.json');
  }
  return path.join(__dirname, 'config.json');
}

function readHwAccelConfig() {
  try {
    var configPath = getHwAccelConfigPath();
    if (fs.existsSync(configPath)) {
      var raw = fs.readFileSync(configPath, 'utf-8');
      var cfg = JSON.parse(raw);
      return cfg.hardware_acceleration !== false;
    }
  } catch(e) {}
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

function getAppIcon() {
  return path.join(__dirname, 'build', 'icons', 'icon.png');
}

function createWindow() {
  const windowIcon = nativeImage.createFromPath(getAppIcon());
  mainWindow = new BrowserWindow({
    width: 1100,
    height: 750,
    minWidth: 900,
    minHeight: 600,
    backgroundColor: '#0f1419',
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
        mainWindow.webContents.send('ai-done', { text: data.text, requestId: data.requestId });
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
  // 创建托盘图标（六边形脉冲logo）
  const icon = nativeImage.createFromPath(getAppIcon());
  tray = new Tray(icon.resize({ width: 16, height: 16 }));
  tray.setToolTip('DigitalLab');

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '显示主窗口',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      },
    },
    { type: 'separator' },
    {
      label: '退出',
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

// ============================================================
//  应用启动
// ============================================================

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
