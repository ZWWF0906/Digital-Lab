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
function readHwAccelConfig() {
  try {
    var configPath = path.join(__dirname, 'config.json');
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

// 待处理的 stdin 请求 Map: requestId → { resolve, reject, timer }
const pendingRequests = new Map();

function createWindow() {
  const windowIcon = nativeImage.createFromDataURL('data:image/png;base64,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');
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
  const pythonPath = 'python';
  // 开发模式（electron . / npm start）：process.defaultApp 有值
  // 打包模式（electron-builder）：process.defaultApp 为 undefined
  const isPackaged = !process.defaultApp;
  const cwd = isPackaged ? path.join(__dirname, '..') : __dirname;
  const args = [path.join(cwd, 'main.py'), '--json-mode'];

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
    console.error(`[Python] ${data.toString().trim()}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] exited with code ${code}`);
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
  const icon = nativeImage.createFromDataURL(
    'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAA2ElEQVR4nGNkYGBg4JfT/c9ABvj46DIjI0LzHzKMYGFgQXAYyXEEAxOqAZhY/kQnTjmwLn6YF9AcIH+8DcO2h5ZVqAL/UQxgZJA/3oqkuBrNQCxy//+jewGmoAbDuRAxdO+CghEuhjBA/ngL9hBDV/sfJRCRmAQBE1w9E1YvWDXAaRgbzQkEvHCsgeGhdSOKGFYvoEQjMwdE89E6nA5/aN2EKvD3B7IBXChy8keRQx2kGUvA/v2GZAALN4a8/JFqhoc2iPjHAH++IhvAg1shTgO+QIKSkuwMAGdUPoxu6x/kAAAAAElFTkSuQmCC'
  );
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
function getHwAccelConfigPath() {
  return path.join(__dirname, 'config.json');
}

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
