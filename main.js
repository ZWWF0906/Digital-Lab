const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog, Notification, shell, session } = require('electron');
const { pathToFileURL } = require('url');
// 多语言：语言清单、词典与 t() 机制，与渲染进程共用 locales/ 下的同一份文件
const Locales = require('./locales/index.js');
const i18n = require('./i18n.js');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const readline = require('readline');
const crypto = require('crypto');
const { isTestHooksEnabled } = require('./core/test_hook_policy.js');

// ── DL-SEC-02 / DL-SEC-02-A 验收测试钩子（生产构建强制关闭）──
// 用途：1) 原生对话框测试替身（覆盖取消/确认分支）；2) 不可信窗口 IPC 来源测试。
// 注意：测试钩子只影响“是否弹真实对话框”和“是否创建测试窗口”，不改变任何安全判定逻辑。
// 生产安全边界（DL-SEC-02-B）：打包环境 app.isPackaged === true 时，无论环境变量如何设置，
// 测试钩子一律不启用；该检查发生在注册 test:report、不可信窗口工厂、对话框替身之前。
// 测试环境可用 DIGITAL_LAB_TEST_SIMULATE_PACKAGED=1 在非打包构建中模拟“已打包”条件。
const SIMULATED_PACKAGED = app.isPackaged !== true &&
  process.env.DIGITAL_LAB_TEST_SIMULATE_PACKAGED === '1';
const TEST_HOOKS = isTestHooksEnabled(
  app.isPackaged === true || SIMULATED_PACKAGED,
  process.env.DIGITAL_LAB_TEST_HOOKS
);
const TEST_DIALOG_MODE = String(process.env.DIGITAL_LAB_TEST_DIALOG || '').toLowerCase();
const TEST_REPORT_PATH = process.env.DIGITAL_LAB_TEST_REPORT || '';
// 仅测试模式：Electron 的 appData 不跟随 APPDATA 环境变量，测试需要显式隔离主进程读取的配置目录。
const TEST_APPDATA = (TEST_HOOKS && process.env.DIGITAL_LAB_TEST_APPDATA) ? process.env.DIGITAL_LAB_TEST_APPDATA : '';

function testReport(entry) {
  if (!TEST_HOOKS || !TEST_REPORT_PATH) return;
  try {
    fs.appendFileSync(TEST_REPORT_PATH, JSON.stringify(entry) + '\n', 'utf-8');
  } catch (e) {}
}

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
      // 去 BOM：用记事本等带 BOM 的工具编辑过 config.json 时，JSON.parse 会直接失败，
      // 导致主题/语言/硬件加速等设置被静默忽略
      var cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8').replace(/^\uFEFF/, ''));
      if (cfg && typeof cfg === 'object') return cfg;
    }
  } catch (e) {}
  return {};
}

function readHwAccelConfig() {
  try {
    var configPath = getHwAccelConfigPath();
    if (fs.existsSync(configPath)) {
      var cfg = JSON.parse(fs.readFileSync(configPath, 'utf-8').replace(/^\uFEFF/, ''));
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

// ── 日志子系统（1.5.1 重写）──
// 设计目标：永不阻塞主线程、永不因 stdio 断开而递归、磁盘占用有上限。
//   1) 异步写：fs.createWriteStream 追加；写入只入内存队列，失败丢弃不抛异常；
//   2) 熔断：stdout/stderr 或日志流出错时置 stdioMuted，此后不再向 console 写任何内容
//      （console 写断开的管道会抛 EPIPE，被 uncaughtException 捕获后又 console.* —— 这正是
//       1.5.0 线上 411MB 日志与白屏卡死的根因，必须在此切断）；
//   3) 轮转：单文件上限 5MB，保留 digital-lab.log.1/.2/.3；
//   4) 启动检查：历史文件超过上限时只保留尾部 256KB，避免遗留的巨型日志继续膨胀；
//   5) 同类 I/O 异常（EPIPE/ECONNRESET 等）只记一条摘要，绝不逐条写盘。
const LOG_MAX_BYTES = 5 * 1024 * 1024;
const LOG_KEEP_FILES = 3;
const LOG_DELETE_FACTOR = 10;   // 超过上限 10 倍（50MB）直接删除，不归档
const LOG_QUEUE_MAX = 500;
const LOG_TAIL_KEEP_BYTES = 256 * 1024;
const IO_ERROR_RE = /EPIPE|ECONNRESET|ECONNREFUSED|broken pipe|EIO/i;

var logFile = path.join(app.getPath('userData'), 'digital-lab.log');
var logStream = null;
var logQueue = [];
var logBytes = 0;
var logDropped = 0;
var stdioMuted = false;
var loggedIoSummary = Object.create(null);

function muteStdio(reason) {
  if (stdioMuted) return;
  stdioMuted = true;
  writeLog('stdio muted: ' + String(reason).slice(0, 200));
}

// stdout/stderr 断开时先由流自己的 error 事件接住，不再冒泡成 uncaughtException
try {
  if (process.stdout && typeof process.stdout.on === 'function') {
    process.stdout.on('error', function (e) { muteStdio('stdout ' + ((e && e.message) || e)); });
  }
  if (process.stderr && typeof process.stderr.on === 'function') {
    process.stderr.on('error', function (e) { muteStdio('stderr ' + ((e && e.message) || e)); });
  }
} catch (e) {}

// 唯一允许走控制台的入口：熔断后直接返回，绝不因管道断开再次抛异常
function safeLogError() {
  if (stdioMuted) return;
  try {
    console.error.apply(console, arguments);
  } catch (e) {
    muteStdio('console ' + ((e && e.message) || e));
  }
}

function rotateLogs() {
  try {
    for (var i = LOG_KEEP_FILES - 1; i >= 1; i--) {
      var from = logFile + '.' + i;
      var to = logFile + '.' + (i + 1);
      if (fs.existsSync(from)) {
        try { fs.rmSync(to, { force: true }); } catch (e) {}
        fs.renameSync(from, to);
      }
    }
    if (fs.existsSync(logFile)) {
      try { fs.rmSync(logFile + '.1', { force: true }); } catch (e) {}
      fs.renameSync(logFile, logFile + '.1');
    }
  } catch (e) {}
}

function purgeGiantRotations() {
  // 连带清理历史遗留的巨型归档（例如旧策略留下的 411MB .1）
  try {
    for (var i = 1; i <= LOG_KEEP_FILES; i++) {
      var p = logFile + '.' + i;
      try {
        if (fs.existsSync(p) && fs.statSync(p).size > LOG_MAX_BYTES * LOG_DELETE_FACTOR) {
          fs.rmSync(p, { force: true });
        }
      } catch (e) {}
    }
  } catch (e) {}
}

function prepareLogFile() {
  try {
    if (!fs.existsSync(logFile)) { logBytes = 0; return; }
    var st = fs.statSync(logFile);
    logBytes = st.size;
    if (st.size <= LOG_MAX_BYTES) return;
    if (st.size > LOG_MAX_BYTES * LOG_DELETE_FACTOR) {
      // 超大（> 50MB）：直接删除，不归档。这类文件只会来自异常风暴，
      // 留档既占盘又没有诊断价值（P0 修复后不应再产生）。
      try { fs.rmSync(logFile, { force: true }); } catch (e) {}
      purgeGiantRotations();
      fs.writeFileSync(logFile, '[' + new Date().toISOString() + '] log deleted: previous file ' +
        st.size + ' bytes exceeded ' + (LOG_MAX_BYTES * LOG_DELETE_FACTOR) + ' bytes (no archive kept)\n');
      logBytes = fs.statSync(logFile).size;
      return;
    }
    // 5MB ~ 50MB：正常轮转，保留 .1/.2/.3
    rotateLogs();
    fs.writeFileSync(logFile, '[' + new Date().toISOString() + '] log rotated: previous file ' +
      st.size + ' bytes archived as .1\n');
    logBytes = fs.statSync(logFile).size;
  } catch (e) {
    logBytes = 0;
  }
}

var rotating = false;

// Windows 上无法重命名仍被打开的日志文件：必须先等旧流 close，再轮转、再开新流。
// 轮转窗口期内到达的日志先留在队列里，新流 'open' 后自动 flush，避免静默丢日志。
function rotateAndReopen() {
  if (rotating) return;
  rotating = true;
  var old = logStream;
  logStream = null;
  logBytes = 0;
  var finished = false;
  function finish() {
    if (finished) return;
    finished = true;
    rotateLogs();
    openLogStream();
    rotating = false;
  }
  if (!old) { finish(); return; }
  try {
    old.once('close', finish);
    old.end();
    setTimeout(finish, 800);   // 兜底：事件丢失也要恢复写入
  } catch (e) {
    finish();
  }
}

function flushLogQueue() {
  if (!logStream || !logQueue.length) return;
  var chunk = logQueue.join('');
  logQueue = [];
  try {
    logStream.write(chunk);
    logBytes += Buffer.byteLength(chunk);
  } catch (e) {
    muteStdio('log write ' + ((e && e.message) || e));
    return;
  }
  if (logBytes > LOG_MAX_BYTES && !rotating) {
    rotateAndReopen();
  }
}

function openLogStream() {
  try {
    logStream = fs.createWriteStream(logFile, { flags: 'a' });
    logStream.on('error', function (e) {
      muteStdio('log stream ' + ((e && e.message) || e));
      logStream = null;
      logQueue = [];
    });
    logStream.on('open', flushLogQueue);
    logStream.on('drain', flushLogQueue);
  } catch (e) {
    logStream = null;
  }
}

// 对外保持原签名：调用方（createWindow / startPython / 各处）无需改动
function writeLog(msg) {
  try {
    if (logQueue.length >= LOG_QUEUE_MAX) { logDropped++; return; }
    if (!logStream && !rotating) return;   // 流不可用且不在轮转：直接丢弃，不阻塞
    logQueue.push('[' + new Date().toISOString() + '] ' + msg + '\n');
    flushLogQueue();
  } catch (e) {}
}

function writeIoSummary(kind, message) {
  if (loggedIoSummary[kind]) return;
  loggedIoSummary[kind] = true;
  writeLog('IO error summary [' + kind + ']: ' + String(message).slice(0, 200) +
    ' (同类型后续出现不再记录，累计丢弃 ' + logDropped + ' 条)');
}

prepareLogFile();
openLogStream();

// ── 全局异常捕获：只写日志队列，不在处理器内 console.* ──
process.on('uncaughtException', function (err) {
  var message = (err && err.message) || String(err);
  if (IO_ERROR_RE.test(message)) {
    muteStdio('uncaught ' + message);
    writeIoSummary(message.replace(/\s+/g, ' ').slice(0, 60), message);
    return;
  }
  writeLog('UNCAUGHT: ' + message + '\n' + ((err && err.stack) || ''));
});

process.on('unhandledRejection', function (reason) {
  var message = (reason && reason.message) || String(reason);
  if (IO_ERROR_RE.test(message)) {
    muteStdio('rejection ' + message);
    writeIoSummary('rejection ' + message.replace(/\s+/g, ' ').slice(0, 60), message);
    return;
  }
  writeLog('UNHANDLED REJECTION: ' + message);
});

let mainWindow = null;
// U02：独立 Terminal WebContents 与会话能力。
let terminalWindow = null;
let terminalSession = null;
// W-04：打开请求从并发入口到 backend 会话创建完成前必须串行，防止孤儿会话。
let terminalOpenInFlight = false;
let testTerminalFailUsed = false;
const trustChallenges = new Map();
// DL-SEC-06-03 / W-02：只有主进程原生选择器返回、或已存在于用户配置中的路径可被保存。
const approvedMemoryDirs = new Set();
const approvedCaBundles = new Set();
// W-09：同一设备的探测/连接测试至少间隔 1 秒，避免 UI 或 renderer 被滥用成快速探测放大器。
const nasProbeLast = new Map();
const NAS_PROBE_COOLDOWN_MS = 1000;
// W-09：高成本/有状态的局部并发与容量限制。不做全量全局 IPC 配额，避免破坏正常交互。
let dialogInFlight = false;
let aiChatInFlight = false;
let aiChatRequestId = '';
let aiChatTimer = null;
const TRUST_CHALLENGE_MAX = 128;
const APPROVED_MEMORY_MAX = 64;
const APPROVED_CA_MAX = 32;
let tray = null;
let isQuitting = false;
let pythonProcess = null;
let pythonRetryCount = 0;
const MAX_RETRIES = 3;
// DL-SEC-05-04：Dashboard 只有一个当前对话，历史能力不得跨会话扩大。
// session_id 由主进程持有，renderer 不能提交或覆盖；当前产品仅使用 default 会话。
const HISTORY_SESSION_ID = 'default';
let latestState = { monitor: { cpu: 0, memory: 0, disk: 0, processes: [] }, hardware: null };
// 阈值告警通知：已处理过的最大告警序号。Python 侧的 seq 在进程内递增、重启后归零，
// 所以这里也在 startPython() 里归零，两边协同避免重启后漏弹或重复弹。
let lastSeenSeq = 0;

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
      // P0（S9）：显式声明安全默认值，不依赖 Electron 默认行为
      sandbox: true,
      webSecurity: true,
      webviewTag: false,
      spellcheck: false,
      additionalArguments: TEST_HOOKS ? ['--dl-test-hooks'] : [],
    },
  });

  // P0（S9）：窗口打开/导航加固——远程页面绝不能继承 preload
  mainWindow.webContents.setWindowOpenHandler(function () {
    writeLog('blocked window.open');
    return { action: 'deny' };
  });
  var blockNavigation = function (event, url) {
    if (!isTrustedPage(url)) {
      writeLog('blocked navigation');
      try { event.preventDefault(); } catch (e) {}
    }
  };
  mainWindow.webContents.on('will-navigate', blockNavigation);
  mainWindow.webContents.on('will-redirect', blockNavigation);

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

// ── 阈值告警：Windows 系统气泡通知 ──
// 文案走主进程自己的 i18n 实例（applyConfiguredLanguage 启动时设定，set-language handler 实时同步）；
// 点击通知把主窗口带到前台。整段包 try/catch，失败只告警不打断主流程。
// 注意：Electron 的 Notification 只 new 出来不会显示，必须显式调用 show()。
function showAlertNotification(alert) {
  try {
    if (!Notification.isSupported()) return;
    const metricKey = (alert && alert.metric_key) || '';
    const num = Number(alert && alert.value);
    const title = i18n.t('alert.title');
    const body = i18n.t('alert.body', {
      metric: i18n.t('alert.' + metricKey),
      value: isNaN(num) ? '--' : num.toFixed(1),
      threshold: (alert && alert.threshold),
    });
    const n = new Notification({ title: title, body: body });
    n.on('click', () => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.show();
        mainWindow.focus();
      }
    });
    n.show();
  } catch (e) {
    console.warn('[alert] notification failed: ' + ((e && e.message) || e));
  }
}

// 不可信窗口测试：只用于 DL-SEC-02-A 验收，证明非主窗口无法调用业务 API 与固定偏好通道。
// 该窗口使用测试专用 preload（含 nodeIntegration），模拟“不受信任但能触达 ipcRenderer”的场景。
function openUntrustedTestWindow() {
  if (!TEST_HOOKS) return;
  var testPreload = path.join(__dirname, 'tests', 'untrusted-preload.js');
  if (!fs.existsSync(testPreload)) {
    testReport({ kind: 'untrusted_window', created: false, error: 'preload_missing' });
    return;
  }
  try {
    var win = new BrowserWindow({
      width: 600,
      height: 420,
      show: false,
      webPreferences: {
        preload: testPreload,
        contextIsolation: false,
        nodeIntegration: true,
        sandbox: false,
      },
    });
    win.loadURL('data:text/html,<html><body><h1>untrusted test page</h1></body></html>');
    testReport({ kind: 'untrusted_window', created: true });
  } catch (e) {
    testReport({ kind: 'untrusted_window', created: false, error: String((e && e.message) || e) });
  }
}

// 测试专报通道：只写入测试报告文件，不触发任何特权操作；仅测试模式注册。
if (TEST_HOOKS) {
  ipcMain.handle('test:report', function (event, payload) {
    var url = '';
    try { url = event.senderFrame ? event.senderFrame.url : ''; } catch (e) {}
    testReport({ kind: 'untrusted_result', senderUrl: url, payload: payload });
    return { ok: true };
  });
}

function startPython() {
  lastSeenSeq = 0;   // 新进程的 seq 从 0 开始，游标同步归零
  var isPackaged = app.isPackaged;
  var pythonPath, args, cwd;

  if (isPackaged) {
    // 打包模式：使用内置的 backend.exe（保持发布兼容，本次不改打包配置）
    pythonPath = path.join(process.resourcesPath, 'backend.exe');
    args = ['--json-mode'];
    cwd = process.resourcesPath;
  } else {
    // 开发模式：固定使用当前仓库的 Python 源码，避免误启动仓库里过期的 backend.exe。
    // 正常开发启动与测试启动使用同一条规则（不依赖测试专用环境变量）。
    pythonPath = 'python';
    args = [path.join(__dirname, 'main.py'), '--json-mode'];
    cwd = __dirname;
  }

  // DL-SEC-05-03：PyInstaller onefile 在启动早期需要一个可写的解压临时目录。
  // 使用当前应用 userData 下的专用 tmp，不依赖宿主机的 TEMP/TMP；只对本次 child 生效。
  var backendTemp = path.join(app.getPath('userData'), 'tmp');
  fs.mkdirSync(backendTemp, { recursive: true });
  var backendEnv = {
    ...process.env,
    TEMP: backendTemp,
    TMP: backendTemp,
    PYTHONUNBUFFERED: '1',
    PYTHONIOENCODING: 'utf-8',
  };
  writeLog('Python temp dir: ' + backendTemp);
  pythonProcess = spawn(pythonPath, args, {
    cwd: cwd,
    stdio: ['pipe', 'pipe', 'pipe'],
    env: backendEnv,
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
        finishAiChat(data.requestId);
        // 这里的载荷是逐字段重建的，新增字段必须在这里带上，否则渲染进程永远收不到。
        // error：阶段 4a 的结构化错误（{code, params}）；旧后端没有该字段时为 undefined，
        // 前端回退到 text 的 [错误] 前缀判断，两条路都不会空白。
        mainWindow.webContents.send('ai-done', { text: data.text, memory: data.memory, error: data.error, requestId: data.requestId });
        return;
      }
      // 兼容旧 AI 响应
      if (data.type === 'ai_response' && mainWindow && !mainWindow.isDestroyed()) {
        finishAiChat();
        mainWindow.webContents.send('ai-message', data.text);
        return;
      }

      // 连接类命令的异步结果只允许进入独立 Terminal 窗口；Dashboard 不再接收终端能力。
      if (data.type === 'terminal_connect_result' && terminalWindow && !terminalWindow.isDestroyed()) {
        if (terminalSession && data.data && String(data.data.session_id || '') === terminalSession.sessionId) {
          terminalWindow.webContents.send('terminal-connect-result', data.data || {});
        }
        return;
      }
      if (data.type === 'nas_test_result' && mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('nas-test-result', data.data || {});
        return;
      }

      // 终端输出/关闭事件只路由到创建它的 Terminal WebContents，绝不广播到 Dashboard。
      if (data.session_id !== undefined && (data.data !== undefined || data.closed === true)) {
        if (terminalWindow && !terminalWindow.isDestroyed() && terminalSession &&
            String(data.session_id) === terminalSession.sessionId) {
          terminalWindow.webContents.send('terminal-data', data);
          if (data.closed === true) terminalSession = null;
        }
        return;
      }

      // 状态更新 → 缓存并推送
      latestState = data;
      // 阈值告警：状态帧里带最近 5 条告警（含递增 seq），只处理没见过的；
      // 这一支不 return，状态帧照常广播给渲染进程。
      if (Array.isArray(data.alerts)) {
        for (const a of data.alerts) {
          if (typeof a.seq === 'number' && a.seq > lastSeenSeq) {
            lastSeenSeq = a.seq;
            showAlertNotification(a);
          }
        }
      }
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
      // P0（S10 前置）：stderr 只保留错误类型与长度，不把整段文本落盘（避免异常细节泄露）
      const kind = (text.split(':')[0] || 'stderr').replace(/[^A-Za-z_ ]/g, '').slice(0, 40);
      writeLog('Python stderr: kind=' + kind + ' bytes=' + text.length);
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

// ============================================================
//  P0 安全边界（DL-SEC-02 / S3、S5、S9）
//  - 渲染进程只能调用固定业务 API（api:<op>），不能指定 Python 命令名
//  - 主进程负责 op → Python command 映射、参数校验与来源校验
//  - 高影响操作（改 AI 服务商/地址、改 NAS 目标、授权内网 HTTP、开终端）走原生确认
// ============================================================

const _userConfigPath = () => path.join(TEST_APPDATA || app.getPath('appData'), 'DigitalLab', 'user_config.json');

function readUserConfig() {
  try {
    var p = _userConfigPath();
    if (!fs.existsSync(p)) return {};
    var data = JSON.parse(fs.readFileSync(p, 'utf-8').replace(/^\uFEFF/, ''));
    return (data && typeof data === 'object' && !Array.isArray(data)) ? data : {};
  } catch (e) {
    return {};
  }
}

function nasProbeRateLimited(deviceId) {
  var key = String(deviceId || '');
  var now = Date.now();
  var last = nasProbeLast.get(key) || 0;
  if (now - last < NAS_PROBE_COOLDOWN_MS) return true;
  nasProbeLast.set(key, now);
  if (nasProbeLast.size > 128) {
    nasProbeLast.forEach(function (ts, k) {
      if (now - ts > 60000) nasProbeLast.delete(k);
    });
  }
  return false;
}

function isApprovedUserPath(kind, value) {
  if (value === undefined || value === null || value === '') return true;
  var text = String(value);
  var set = kind === 'memory' ? approvedMemoryDirs : approvedCaBundles;
  if (set.has(text)) return true;
  // 兼容升级前已经存在的配置路径；仍是主进程读取的现有值，不是 renderer 新造路径。
  var current = kind === 'memory'
    ? configValueAt(readUserConfig(), 'ai.memory.dir')
    : configValueAt(readUserConfig(), 'ai.ca_bundle');
  if (current === text) {
    set.add(text);
    return true;
  }
  return false;
}

function isPlainObject(v) {
  return v !== null && typeof v === 'object' && !Array.isArray(v);
}

function validInt(v, low, high) {
  return typeof v === 'number' && Number.isInteger(v) && v >= low && v <= high;
}

function requiredString(v, max) {
  return typeof v === 'string' && v.length > 0 && v.length <= max;
}

function validateMessages(messages) {
  if (!Array.isArray(messages) || messages.length < 1 || messages.length > 16) return 'messages';
  for (var i = 0; i < messages.length; i++) {
    var m = messages[i];
    if (!isPlainObject(m)) return 'messages';
    if (m.role !== 'user' && m.role !== 'assistant') return 'messages.role';
    if (typeof m.content !== 'string' || m.content.length > 4000) return 'messages.content';
  }
  return null;
}

function isTrustedPage(url) {
  try {
    if (typeof url !== 'string') return false;
    var u = new URL(url);
    if (u.protocol !== 'file:') return false;
    var expected = pathToFileURL(path.join(__dirname, 'dashboard.html')).href;
    return u.href.split('#')[0].split('?')[0] === expected;
  } catch (e) {
    return false;
  }
}

function trustedSender(event) {
  try {
    if (!mainWindow || mainWindow.isDestroyed()) return false;
    if (!event || event.sender !== mainWindow.webContents) return false;
    if (!event.senderFrame) return false;
    return isTrustedPage(event.senderFrame.url);
  } catch (e) {
    return false;
  }
}

// U02：终端窗口有独立页面和独立 preload，不继承 dashboard 的 bridge。
function isTerminalPage(url) {
  try {
    if (typeof url !== 'string') return false;
    var u = new URL(url);
    if (u.protocol !== 'file:') return false;
    var expected = pathToFileURL(path.join(__dirname, 'terminal.html')).href;
    return u.href.split('#')[0].split('?')[0] === expected;
  } catch (e) {
    return false;
  }
}

function terminalSender(event) {
  try {
    if (!terminalWindow || terminalWindow.isDestroyed()) return false;
    if (!event || event.sender !== terminalWindow.webContents) return false;
    if (!event.senderFrame || !isTerminalPage(event.senderFrame.url)) return false;
    return !!(terminalSession && terminalSession.webContentsId === event.sender.id);
  } catch (e) {
    return false;
  }
}

function closeTerminalSession(sendClose) {
  var session = terminalSession;
  terminalSession = null;
  if (session && sendClose && session.sessionId) {
    sendToPython({ cmd: 'terminal_close', session_id: session.sessionId }).catch(function () {});
  }
}

function failTerminalWindow() {
  // W-04-R1：窗口构造/加载失败的统一回收点。先断开 session 所有权并关闭
  // backend 会话，再销毁可能已创建但不可用的窗口。
  var win = terminalWindow;
  var failedSession = terminalSession ? terminalSession.sessionId : '';
  terminalWindow = null;
  try { closeTerminalSession(true); } catch (e) {}
  if (win && !win.isDestroyed()) {
    try { win.destroy(); } catch (e) {}
  }
  testReport({ kind: 'terminal_open_cleanup', session_id: failedSession });
}

function rememberApproved(set, value, limit) {
  if (!set || !value) return;
  if (set.has(value)) set.delete(value);
  set.add(value);
  while (set.size > limit) {
    var first = set.values().next().value;
    set.delete(first);
  }
}

async function withDialogGuard(fn) {
  if (dialogInFlight) return { ok: false, error: 'ipc.err.busy' };
  dialogInFlight = true;
  try {
    return await fn();
  } finally {
    dialogInFlight = false;
  }
}

function finishAiChat(requestId) {
  if (!aiChatInFlight) return;
  if (requestId && aiChatRequestId && String(requestId) !== aiChatRequestId) return;
  aiChatInFlight = false;
  aiChatRequestId = '';
  if (aiChatTimer) {
    clearTimeout(aiChatTimer);
    aiChatTimer = null;
  }
}

function openTerminalWindow(sessionInfo, deviceId, deviceName) {
  if (!sessionInfo || !sessionInfo.session_id) return false;
  if (terminalWindow && !terminalWindow.isDestroyed()) {
    terminalWindow.focus();
    return false;
  }
  terminalSession = {
    sessionId: String(sessionInfo.session_id),
    deviceId: String(deviceId || ''),
    deviceName: String(deviceName || deviceId || ''),
    createdAt: Date.now(),
    webContentsId: null,
  };
  try {
    // 仅非打包测试模式：模拟一次 BrowserWindow 初始化异常，验证失败回收。
    if (TEST_HOOKS && process.env.DIGITAL_LAB_TEST_TERMINAL_FAIL === '1' && !testTerminalFailUsed) {
      testTerminalFailUsed = true;
      throw new Error('synthetic terminal window failure');
    }
    terminalWindow = new BrowserWindow({
      width: 900,
      height: 600,
      minWidth: 600,
      minHeight: 400,
      show: false,
      title: 'DigitalLab Terminal',
      webPreferences: {
        preload: path.join(__dirname, 'preload-terminal.js'),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
        webSecurity: true,
        webviewTag: false,
        spellcheck: false,
      },
    });
    terminalSession.webContentsId = terminalWindow.webContents.id;
    terminalWindow.webContents.setWindowOpenHandler(function () { return { action: 'deny' }; });
    terminalWindow.webContents.on('will-navigate', function (event, url) {
      if (!isTerminalPage(url)) { try { event.preventDefault(); } catch (e) {} }
    });
    terminalWindow.on('closed', function () {
      closeTerminalSession(true);
      terminalWindow = null;
    });
    var loadPromise = terminalWindow.loadFile('terminal.html');
    if (loadPromise && typeof loadPromise.catch === 'function') {
      loadPromise.catch(function () { failTerminalWindow(); });
    }
    terminalWindow.webContents.on('did-fail-load', function () { failTerminalWindow(); });
    terminalWindow.webContents.on('render-process-gone', function () { failTerminalWindow(); });
    terminalWindow.once('ready-to-show', function () {
      if (terminalWindow && !terminalWindow.isDestroyed()) terminalWindow.show();
    });
    terminalWindow.webContents.on('did-finish-load', function () {
      if (!terminalWindow || terminalWindow.isDestroyed() || !terminalSession) return;
      terminalWindow.webContents.send('terminal-context', {
        sessionId: terminalSession.sessionId,
        deviceId: terminalSession.deviceId,
        deviceName: terminalSession.deviceName,
      });
    });
    return true;
  } catch (e) {
    failTerminalWindow();
    return false;
  }
}

function deviceFromConfig(name) {
  var devices = readUserConfig().nas_devices;
  if (!Array.isArray(devices)) return null;
  if (typeof name !== 'string') return null;
  for (var i = 0; i < devices.length; i++) {
    var d = devices[i];
    if (d && d.name === name) return d;
  }
  return null;
}

// U02：信任决定只能引用主进程生成的 challenge；renderer 不能提交任意 fingerprint。
function createTrustChallenge(event, deviceId, probe) {
  var device = deviceFromConfig(deviceId);
  if (!device) return null;
  var params = (probe && probe.error && probe.error.params) || probe || {};
  var fingerprint = String(params.fingerprint || params.new_fingerprint || '').trim();
  if (!fingerprint) return null;
  var oldFingerprint = String(params.old_fingerprint || params.trusted_fingerprint || '').trim();
  var id = crypto.randomUUID();
  if (trustChallenges.size >= TRUST_CHALLENGE_MAX) {
    var now = Date.now();
    for (var [cid, ch] of trustChallenges) {
      if (ch.used || ch.expiresAt < now) trustChallenges.delete(cid);
    }
    while (trustChallenges.size >= TRUST_CHALLENGE_MAX) {
      var oldest = trustChallenges.keys().next().value;
      trustChallenges.delete(oldest);
    }
  }
  trustChallenges.set(id, {
    id: id,
    senderId: event.sender.id,
    deviceId: String(deviceId),
    name: String(device.name || deviceId),
    host: String(device.host || params.host || ''),
    port: String(device.port || params.port || 22),
    keyType: String(params.key_type || params.keyType || ''),
    fingerprint: fingerprint,
    oldFingerprint: oldFingerprint,
    replace: !!(oldFingerprint && oldFingerprint !== fingerprint),
    expiresAt: Date.now() + 120000,
    used: false,
  });
  return id;
}

function getTrustChallenge(event, id) {
  var challenge = trustChallenges.get(String(id || ''));
  if (!challenge) return null;
  if (challenge.used || challenge.senderId !== event.sender.id || challenge.expiresAt < Date.now()) {
    trustChallenges.delete(challenge.id);
    return null;
  }
  return challenge;
}

function trustChallengeView(challenge) {
  return [
    '设备: ' + challenge.name,
    '目标: ' + challenge.host + ':' + challenge.port,
    '主机密钥类型: ' + (challenge.keyType || 'unknown'),
    '主机指纹: ' + challenge.fingerprint,
    challenge.oldFingerprint ? '旧指纹: ' + challenge.oldFingerprint : '旧指纹: 无',
    challenge.replace ? '此操作将更换已信任的主机密钥。' : '首次信任该主机。',
  ].join('\n');
}

async function nativeConfirm(title, detail) {
  // DL-SEC-02-A：可控原生对话框测试替身（仅测试模式生效，生产必须走真实对话框）。
  // 替身覆盖的是真实取消分支：命中后直接 return，绝不调用后端。
  if (TEST_HOOKS && (TEST_DIALOG_MODE === 'cancel' || TEST_DIALOG_MODE === 'confirm')) {
    var fakeAnswer = TEST_DIALOG_MODE === 'confirm';
    testReport({ kind: 'dialog', title: title, answer: fakeAnswer });
    return fakeAnswer;
  }
  try {
    var opts = {
      type: 'warning',
      title: 'DigitalLab',
      message: title,
      detail: String(detail || '').slice(0, 1200),
      buttons: [i18n.t('dlg.memoryDelete.cancel'), i18n.t('dlg.continue')],
      defaultId: 0,
      cancelId: 0,
      noLink: true,
    };
    var result = mainWindow ? await dialog.showMessageBox(mainWindow, opts) : await dialog.showMessageBox(opts);
    testReport({ kind: 'dialog', title: title, answer: result.response === 1 });
    return result.response === 1;
  } catch (e) {
    return false;
  }
}

function memoryItemDigest(item) {
  return crypto.createHash('sha256')
    .update(String((item && item.ts) || '') + '\0' + String((item && item.content) || ''))
    .digest('hex');
}

const API_VALIDATORS = {
  'hardware:get': function () { return null; },
  'config:get': function () { return null; },
  'config:reload': function () { return null; },
  'test:inject_state': function (a) { return isPlainObject(a.state) ? null : 'state'; },
  'memory:status': function () { return null; },
  'memory:choose_dir': function () { return null; },
  'ai:choose_ca_bundle': function () { return null; },
  'memory:clear': function () { return null; },
  'memory:dedupe': function () { return null; },
  'history:clear': function () { return null; },
  'app:open_external': function (a) {
    return (a.target === 'issues' || a.target === 'mailto') ? null : 'target';
  },
  'config:save_settings': function (a) {
    if (!isPlainObject(a.patch)) return 'patch';
    if (a.dirty !== undefined && (!Array.isArray(a.dirty) || a.dirty.length > 32)) return 'dirty';
    return null;
  },
  'config:save_device': function (a) {
    if (!isPlainObject(a.device)) return 'device';
    if (a.dirty !== undefined && (!Array.isArray(a.dirty) || a.dirty.length > 32)) return 'dirty';
    return null;
  },
  'config:delete_device': function (a) { return requiredString(a.name, 64) ? null : 'name'; },
  'config:clear_credential': function (a) {
    if (['ai_key', 'nas_password', 'auth_token'].indexOf(a.kind) < 0) return 'kind';
    if (a.kind === 'nas_password' && !requiredString(a.name, 64)) return 'name';
    return null;
  },
  'memory:list': function (a) { return (a.limit === undefined || validInt(a.limit, 1, 5000)) ? null : 'limit'; },
  'memory:delete': function (a) {
    if (!validInt(a.index, 0, 100000)) return 'index';
    return /^[a-f0-9]{64}$/i.test(String(a.expectedSha256 || '')) ? null : 'expectedSha256';
  },
  'history:list': function (a) { return (a.limit === undefined || validInt(a.limit, 1, 5000)) ? null : 'limit'; },
  'history:append': function (a) {
    if (a.role !== 'user' && a.role !== 'assistant') return 'role';
    return requiredString(a.content, 12000) ? null : 'content';
  },
  'ai:chat': function (a) {
    var msgProblem = validateMessages(a.messages);
    if (msgProblem) return msgProblem;
    if (a.provider !== 'ollama' && a.provider !== 'openai') return 'provider';
    if (['zh-CN', 'en-US', 'ja-JP'].indexOf(a.lang) < 0) return 'lang';
    return null;
  },
  'nas:test': function (a) { return requiredString(a.deviceId, 64) ? null : 'deviceId'; },
  'nas:probe': function (a) { return requiredString(a.deviceId, 64) ? null : 'deviceId'; },
  'nas:confirm_trust': function (a) {
    return requiredString(a.challengeId, 64) ? null : 'challengeId';
  },
  'terminal:open': function (a) {
    return (requiredString(a.deviceId, 64) && validInt(a.cols, 1, 500) && validInt(a.rows, 1, 500)) ? null : 'param';
  },
  'terminal:input': function (a) {
    return (requiredString(a.sessionId, 64) && typeof a.data === 'string' && a.data.length <= 8192) ? null : 'param';
  },
  'terminal:resize': function (a) {
    return (requiredString(a.sessionId, 64) && validInt(a.cols, 1, 500) && validInt(a.rows, 1, 500)) ? null : 'param';
  },
  'terminal:close': function (a) { return requiredString(a.sessionId, 64) ? null : 'sessionId'; },
  'terminal:attach': function (a) { return requiredString(a.sessionId, 64) ? null : 'sessionId'; },
};

const TERMINAL_API_OPS = new Set(['terminal:input', 'terminal:resize', 'terminal:close', 'terminal:attach']);

function registerApi(op, handler) {
  ipcMain.handle('api:' + op, async function (event, args) {
    var allowed = trustedSender(event) || (TERMINAL_API_OPS.has(op) && terminalSender(event));
    if (!allowed) {
      writeLog('blocked ipc op from untrusted sender: ' + op);
      return { ok: false, error: 'ipc.err.forbidden' };
    }
    var payload = isPlainObject(args) ? args : {};
    var validator = API_VALIDATORS[op];
    var problem = validator ? validator(payload) : null;
    if (problem) {
      return { ok: false, error: 'ipc.err.invalidParams', field: problem };
    }
    try {
      return await handler(payload, event);
    } catch (e) {
      return { ok: false, error: 'ipc.err.internal', detail: String((e && e.message) || e).slice(0, 120) };
    }
  });
}

function maskUrlForDialog(value) {
  // W-01：不能只显示 origin+path，否则仅 query/fragment 不同的两个配置看起来
  // 完全一样。参数值仍然隐藏；保留参数名并用短 SHA-256 指纹让用户能区分
  // 不同的 query/fragment，同时不把 token/密码直接放到对话框。
  var text = String(value || '');
  function digest(part) {
    try {
      return crypto.createHash('sha256').update(part).digest('hex').slice(0, 8);
    } catch (e) {
      return '????????';
    }
  }
  try {
    var u = new URL(text);
    var out = u.origin + u.pathname;
    if (u.search) {
      var names = [];
      u.searchParams.forEach(function (_v, k) {
        if (names.indexOf(k) < 0) names.push(k);
      });
      if (names.length) {
        out += '?' + names.map(function (k) { return k + '=***'; }).join('&');
      } else {
        out += '?***';
      }
      out += ' [q:' + digest(u.search) + ']';
    }
    if (u.hash) out += ' [f:' + digest(u.hash) + ']';
    return out.slice(0, 320);
  } catch (e) {
    // 不是合法 URL 时也不能把明显的 token/密码原样放进确认框。
    return text.replace(/([?&](?:token|key|api_key|password|secret|code)=)[^&\s#]+/gi, '$1***').slice(0, 200);
  }
}

registerApi('hardware:get', async function () {
  return latestState.hardware;
});

registerApi('config:get', async function () {
  return sendToPython({ cmd: 'get_config' });
});

registerApi('config:reload', async function () {
  return sendToPython({ cmd: 'reload_config' });
});

function canonicalizeSettingsPatch(patch) {
  // DL-SEC-06-03 / W-01：主进程必须用与后端一致的规范化结果做确认和写入。
  // 含点号的扁平键、空键、原型污染键一律拒绝；嵌套对象只保留普通对象/数组/原始值。
  var out = {};
  var leaves = 0;
  function walk(node, prefix, depth) {
    if (depth > 4) throw new Error('tooDeep');
    if (!isPlainObject(node)) throw new Error('notObject');
    Object.keys(node).forEach(function (key) {
      if (!key || key.indexOf('.') >= 0 || key === '__proto__' || key === 'constructor' || key === 'prototype') {
        throw new Error('ambiguousPath');
      }
      var value = node[key];
      if (isPlainObject(value)) {
        walk(value, prefix.concat([key]), depth + 1);
      } else {
        leaves += 1;
        if (leaves > 64) throw new Error('tooManyLeaves');
        var cur = out;
        for (var i = 0; i < prefix.length; i++) {
          if (!isPlainObject(cur[prefix[i]])) cur[prefix[i]] = {};
          cur = cur[prefix[i]];
        }
        cur[key] = value;
      }
    });
  }
  walk(patch, [], 0);
  return out;
}

function configValueAt(obj, dottedPath) {
  var cur = obj;
  var parts = dottedPath.split('.');
  for (var i = 0; i < parts.length; i++) {
    if (!isPlainObject(cur) || !Object.prototype.hasOwnProperty.call(cur, parts[i])) return undefined;
    cur = cur[parts[i]];
  }
  return cur;
}

function sensitiveSettingsChanges(patch, user, dirty) {
  var lines = [];
  var provider = configValueAt(patch, 'ai.provider');
  var oldProvider = configValueAt(user, 'ai.provider');
  if (provider !== undefined && provider !== oldProvider) {
    lines.push('AI 服务商: ' + String(oldProvider || '未设置') + ' → ' + String(provider));
  }
  ['ai.openai.base_url', 'ai.ollama.base_url'].forEach(function (path) {
    var value = configValueAt(patch, path);
    var oldValue = configValueAt(user, path);
    if (value !== undefined && value !== oldValue) {
      var prefix = path.indexOf('openai') >= 0 ? '云端 AI 地址: ' : 'Ollama 地址: ';
      lines.push(prefix + maskUrlForDialog(oldValue) + ' → ' + maskUrlForDialog(value));
    }
  });
  var allow = configValueAt(patch, 'ai.allow_insecure_http');
  if (Array.isArray(allow)) {
    var oldAllow = configValueAt(user, 'ai.allow_insecure_http');
    oldAllow = Array.isArray(oldAllow) ? oldAllow : [];
    var added = allow.filter(function (x) { return oldAllow.indexOf(x) < 0; });
    if (added.length) lines.push('新增内网/Tailscale HTTP 例外: ' + added.join(', '));
  }
  ['ai.ca_bundle', 'ai.memory.dir'].forEach(function (path) {
    var value = configValueAt(patch, path);
    var oldValue = configValueAt(user, path);
    if (value !== undefined && value !== oldValue) {
      var prefix = path === 'ai.ca_bundle' ? 'CA Bundle 路径: ' : 'AI 记忆目录: ';
      lines.push(prefix + String(oldValue || '自动/默认') + ' → ' + String(value || '自动/默认'));
    }
  });
  if (configValueAt(patch, 'ai.openai.api_key') !== undefined && Array.isArray(dirty) &&
      dirty.indexOf('ai.openai.api_key') >= 0) {
    lines.push('AI API Key: 将更新为新值（值不在对话框中显示）');
  }
  return lines;
}

registerApi('config:save_settings', async function (args) {
  var rawPatch = isPlainObject(args.patch) ? args.patch : {};
  var patch;
  try {
    patch = canonicalizeSettingsPatch(rawPatch);
  } catch (e) {
    return { ok: false, error: 'ipc.err.invalidParams', field: 'patch' };
  }
  var dirty = Array.isArray(args.dirty) ? args.dirty : [];
  var user = readUserConfig();
  var memoryDir = configValueAt(patch, 'ai.memory.dir');
  if (memoryDir !== undefined && !isApprovedUserPath('memory', memoryDir)) {
    return { ok: false, error: 'cfg.err.pathNotApproved', field: 'ai.memory.dir' };
  }
  var caBundle = configValueAt(patch, 'ai.ca_bundle');
  if (caBundle !== undefined && !isApprovedUserPath('ca', caBundle)) {
    return { ok: false, error: 'cfg.err.pathNotApproved', field: 'ai.ca_bundle' };
  }
  var confirmations = sensitiveSettingsChanges(patch, user, dirty);
  if (confirmations.length) {
    var ok = await nativeConfirm('确认修改敏感配置？',
      confirmations.join('\n') + '\n\n此操作会影响后续请求的目标或本机数据位置。');
    if (!ok) return { ok: false, canceled: true };
  }
  return sendToPython({ cmd: 'save_config_patch', patch: patch, dirty: dirty });
});

registerApi('config:save_device', async function (args) {
  var device = isPlainObject(args.device) ? args.device : {};
  var name = typeof device.name === 'string' ? device.name : '';
  var existing = deviceFromConfig(name);
  var lines = [];
  if (!existing) {
    lines.push('新增 NAS 设备: ' + name + '（' + String(device.host || '') + ':' + String(device.port || 22) + '）');
  } else if (String(device.host || '') !== String(existing.host || '') ||
             String(device.port || 22) !== String(existing.port || 22)) {
    lines.push('修改 NAS 连接目标: ' + name);
    lines.push('  ' + String(existing.host || '') + ':' + String(existing.port || 22) +
               ' → ' + String(device.host || '') + ':' + String(device.port || 22));
  }
  if (lines.length) {
    var ok = await nativeConfirm('确认修改 NAS 设备？', lines.join('\n') + '\n\n首次连接需要核对主机指纹。');
    if (!ok) return { ok: false, canceled: true };
  }
  return sendToPython({ cmd: 'save_device', device: args.device, dirty: args.dirty || [] });
});

registerApi('config:delete_device', async function (args) {
  var ok = await nativeConfirm('删除 NAS 设备？', '设备: ' + args.name + '\n删除后该设备的监控与终端配置将被移除。');
  if (!ok) return { ok: false, canceled: true };
  return sendToPython({ cmd: 'delete_device', name: args.name });
});

registerApi('config:clear_credential', async function (args) {
  var label = args.kind === 'ai_key' ? 'AI API Key' :
    (args.kind === 'nas_password' ? ('NAS 密码（' + (args.name || '') + '）') : '认证 Token');
  var ok = await nativeConfirm('清除凭据？', '将清除: ' + label + '\n此操作不可撤销，清除后需要重新输入。');
  if (!ok) return { ok: false, canceled: true };
  return sendToPython({ cmd: 'clear_credential', kind: args.kind, name: args.name });
});

registerApi('memory:choose_dir', async function () {
  // W-02：目录只能由主进程原生选择器产生；返回后加入本轮进程的批准集合。
  // W-09：同一时间只允许一个原生选择器，避免重复弹窗和状态堆积。
  return withDialogGuard(async function () {
    var result = await dialog.showOpenDialog(mainWindow || undefined, {
      title: '选择 AI 记忆目录',
      properties: ['openDirectory', 'createDirectory'],
    });
    if (result.canceled || !result.filePaths || !result.filePaths[0]) {
      return { ok: false, canceled: true };
    }
    var selected = String(result.filePaths[0]);
    rememberApproved(approvedMemoryDirs, selected, APPROVED_MEMORY_MAX);
    return { ok: true, path: selected };
  });
});

registerApi('ai:choose_ca_bundle', async function () {
  return withDialogGuard(async function () {
    var result = await dialog.showOpenDialog(mainWindow || undefined, {
      title: '选择 CA Bundle',
      properties: ['openFile'],
      filters: [{ name: 'Certificate bundle', extensions: ['pem', 'crt', 'cer'] }],
    });
    if (result.canceled || !result.filePaths || !result.filePaths[0]) {
      return { ok: false, canceled: true };
    }
    var selected = String(result.filePaths[0]);
    rememberApproved(approvedCaBundles, selected, APPROVED_CA_MAX);
    return { ok: true, path: selected };
  });
});

registerApi('memory:status', async function () {
  var res = await sendToPython({ cmd: 'get_ai_memory' });
  if (res && typeof res === 'object') {
    return { enabled: !!res.enabled, dir: res.dir || '', count: res.count || 0 };
  }
  return res;
});

registerApi('memory:list', async function (args) {
  var res = await sendToPython({ cmd: 'get_ai_memory' });
  if (res && Array.isArray(res.items)) {
    res.items = res.items.map(function (it) {
      return Object.assign({}, it, { sha256: memoryItemDigest(it) });
    });
    if (args.limit) res.items = res.items.slice(0, args.limit);
  }
  return res;
});

registerApi('memory:delete', async function (args, event) {
  // U02：最终授权由主进程执行；renderer 的 confirmMemoryDelete 不再是安全边界。
  var state = await sendToPython({ cmd: 'get_ai_memory' });
  var items = state && Array.isArray(state.items) ? state.items : [];
  var item = items[args.index];
  if (!item) return { ok: false, error: 'memory.err.invalidIndex' };
  var digest = memoryItemDigest(item);
  // 调用方必须提交 list 时看到的摘要；旧请求复用旧摘要会在确认前被拒绝，
  // 避免删除被删除条目的相邻项。
  if (digest !== String(args.expectedSha256 || '').toLowerCase()) {
    return { ok: false, error: 'memory.err.staleTarget' };
  }
  var preview = String(item.content || '').replace(/\s+/g, ' ').slice(0, 160);
  var ok = await nativeConfirm('删除 AI 记忆？', '将删除以下记忆条目，此操作不可撤销：\n' + preview + '\n\n索引: ' + args.index);
  if (!ok) return { ok: false, canceled: true };
  return sendToPython({ cmd: 'delete_ai_memory', index: args.index, expected_sha256: digest });
});

registerApi('memory:clear', async function () {
  var ok = await nativeConfirm('清空 AI 记忆？', '将删除本机保存的全部记忆条目，此操作不可撤销。');
  if (!ok) return { ok: false, canceled: true };
  return sendToPython({ cmd: 'clear_ai_memory' });
});

registerApi('memory:dedupe', async function () {
  var ok = await nativeConfirm('合并重复记忆？', '同一内容只保留最早一条，此操作不可撤销。');
  if (!ok) return { ok: false, canceled: true };
  return sendToPython({ cmd: 'dedupe_ai_memory' });
});

registerApi('history:list', async function (args) {
  // DL-SEC-05-04：sender 合法不等于数据范围合法。renderer 不能指定 sessionId，
  // 主进程只查询自己持有的当前会话；limit 仅做资源上限，不能扩大权限范围。
  // 返回字段仍最小化为 role/content/ts。
  var limit = Math.max(1, Math.min(100, Number(args.limit) || 50));
  var res = await sendToPython({
    cmd: 'chat_history_get',
    limit: limit,
    session_id: HISTORY_SESSION_ID,
  });
  if (res && Array.isArray(res.items)) {
    res.items = res.items.slice(-limit).map(function (it) {
      return { role: it && it.role, content: it && it.content, ts: it && it.ts };
    });
  }
  return res;
});

registerApi('history:append', async function (args) {
  return sendToPython({
    cmd: 'chat_history_append',
    role: args.role,
    content: args.content,
    session_id: HISTORY_SESSION_ID,
  });
});

registerApi('history:clear', async function () {
  // 只清除主进程持有的当前会话，不再清除其他会话。
  var ok = await nativeConfirm('清空当前对话历史？', '将删除当前会话保存在本机的对话记录，此操作不可撤销。');
  if (!ok) return { ok: false, canceled: true };
  return sendToPython({ cmd: 'chat_history_clear', session_id: HISTORY_SESSION_ID });
});

registerApi('ai:chat', async function (args) {
  // W-09：AI 请求有独立的 backend 线程与流式资源；同一时间只允许一个活动请求。
  if (aiChatInFlight) return { ok: false, error: 'ai.err.busy' };
  aiChatInFlight = true;
  aiChatRequestId = '';
  if (aiChatTimer) clearTimeout(aiChatTimer);
  aiChatTimer = setTimeout(function () {
    // 后端未发送完成事件时的兜底；不能让 in-flight 状态永久占用。
    aiChatInFlight = false;
    aiChatRequestId = '';
    aiChatTimer = null;
  }, 180000);
  try {
    var res = await sendToPython({ cmd: 'ai_chat', messages: args.messages, provider: args.provider, lang: args.lang });
    if (res && res.requestId) aiChatRequestId = String(res.requestId);
    if (!res || res.ok === false || res.streaming !== true) finishAiChat(aiChatRequestId);
    return res;
  } catch (e) {
    finishAiChat();
    throw e;
  }
});

registerApi('nas:test', async function (args, event) {
  if (nasProbeRateLimited(args.deviceId)) return { ok: false, error: 'nas.err.rateLimited' };
  var res = await sendToPython({ cmd: 'test_nas_connection', device_id: args.deviceId });
  if (res && res.error && (res.error.code === 'ssh.err.untrustedHost' || res.error.code === 'ssh.err.hostKeyChanged')) {
    var challengeId = createTrustChallenge(event, args.deviceId, res);
    if (challengeId) res.challengeId = challengeId;
  }
  return res;
});

registerApi('nas:probe', async function (args, event) {
  if (nasProbeRateLimited(args.deviceId)) return { ok: false, error: 'nas.err.rateLimited' };
  var res = await sendToPython({ cmd: 'ssh_probe', device_id: args.deviceId });
  if (res && res.ok && res.fingerprint && res.trusted !== true) {
    var challengeId = createTrustChallenge(event, args.deviceId, res);
    if (challengeId) res.challengeId = challengeId;
  }
  return res;
});

registerApi('nas:confirm_trust', async function (args, event) {
  var challenge = getTrustChallenge(event, args.challengeId);
  if (!challenge) return { ok: false, error: 'ssh.err.trustChallengeExpired' };
  // 一次性消耗，防止重放；取消后用户需要重新 probe。
  challenge.used = true;
  var confirmed = await nativeConfirm('确认 SSH 主机信任？', trustChallengeView(challenge));
  if (!confirmed) {
    trustChallenges.delete(challenge.id);
    return { ok: false, canceled: true };
  }
  var result = await sendToPython({
    cmd: 'ssh_confirm_trust',
    device_id: challenge.deviceId,
    fingerprint: challenge.fingerprint,
    replace: challenge.replace,
  });
  trustChallenges.delete(challenge.id);
  return result;
});

registerApi('terminal:open', async function (args) {
  var device = deviceFromConfig(args.deviceId);
  if (!device) return { ok: false, error: 'term.err.deviceNotConfigured' };
  if (terminalOpenInFlight || (terminalWindow && !terminalWindow.isDestroyed())) {
    return { ok: false, error: 'term.err.alreadyOpen' };
  }
  terminalOpenInFlight = true;
  try {
    var detail = '设备: ' + device.name + '\n目标: ' + String(device.host || '') + ':' + String(device.port || 22) +
      '\n未信任的主机不会收到认证凭据。\n终端将在独立窗口中运行。';
    var ok = await nativeConfirm('打开 SSH 终端？', detail);
    if (!ok) return { ok: false, canceled: true };
    var res = await sendToPython({
      cmd: 'ssh_terminal_init',
      device_id: args.deviceId,
      cols: args.cols,
      rows: args.rows,
      async: false,
    });
    if (!res || !res.session_id) return res || { ok: false, error: 'term.err.openFailed' };
    if (!openTerminalWindow(res, args.deviceId, device.name)) {
      // 窗口创建失败时立即关闭刚创建的 backend session，避免无主会话。
      sendToPython({ cmd: 'terminal_close', session_id: res.session_id }).catch(function () {});
      return { ok: false, error: 'term.err.openFailed' };
    }
    return { ok: true, sessionId: res.session_id, deviceId: args.deviceId };
  } finally {
    terminalOpenInFlight = false;
  }
});

registerApi('terminal:input', async function (args, event) {
  if (!terminalSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  if (!terminalSession || args.sessionId !== terminalSession.sessionId) {
    return { ok: false, error: 'term.err.sessionGone' };
  }
  if (typeof args.data !== 'string' || args.data.length === 0 || args.data.length > 8192) {
    return { ok: false, error: 'term.err.invalidInput' };
  }
  var now = Date.now();
  if (!terminalSession.inputWindowStart || now - terminalSession.inputWindowStart > 1000) {
    terminalSession.inputWindowStart = now;
    terminalSession.inputCount = 0;
  }
  terminalSession.inputCount = (terminalSession.inputCount || 0) + 1;
  if (terminalSession.inputCount > 200) return { ok: false, error: 'term.err.rateLimited' };
  return sendToPython({ cmd: 'terminal_input', session_id: args.sessionId, data: args.data });
});

registerApi('terminal:resize', async function (args, event) {
  if (!terminalSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  if (!terminalSession || args.sessionId !== terminalSession.sessionId) {
    return { ok: false, error: 'term.err.sessionGone' };
  }
  return sendToPython({ cmd: 'terminal_resize', session_id: args.sessionId, cols: args.cols, rows: args.rows });
});

registerApi('terminal:close', async function (args, event) {
  if (!terminalSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  if (!terminalSession || args.sessionId !== terminalSession.sessionId) {
    return { ok: false, error: 'term.err.sessionGone' };
  }
  var sessionId = args.sessionId;
  closeTerminalSession(false);
  await sendToPython({ cmd: 'terminal_close', session_id: sessionId });
  return { ok: true };
});

registerApi('terminal:attach', async function (args, event) {
  if (!terminalSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  if (!terminalSession || args.sessionId !== terminalSession.sessionId) {
    return { ok: false, error: 'term.err.sessionGone' };
  }
  return sendToPython({ cmd: 'terminal_attach', session_id: args.sessionId });
});

// 外部链接：只允许固定目的地（不接受渲染进程提交任意 URL）
var EXTERNAL_TARGETS = {
  issues: 'https://github.com/ZWWF0906/Digital-Lab/issues/new',
  mailto: 'mailto:ZWWF0906@outlook.com',
};
registerApi('app:open_external', async function (args) {
  var target = EXTERNAL_TARGETS[args.target];
  if (!target) return { ok: false, error: 'ipc.err.invalidParams' };
  try {
    await shell.openExternal(target);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: 'ipc.err.internal' };
  }
});

// 应用版本号（关于页动态显示）与退出：固定通道 + 来源校验
ipcMain.handle('get-app-version', function (event) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  // 仅非打包测试模式：验证 About 页在版本 IPC 失败时仍显示与产品一致的兜底版本。
  if (TEST_HOOKS && process.env.DIGITAL_LAB_TEST_VERSION_FAIL === '1') return null;
  try { return app.getVersion(); } catch (e) { return null; }
});

ipcMain.handle('quit-app', function (event) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  isQuitting = true;
  app.quit();
  return { ok: true };
});

// ── 硬件加速配置（直接读写 config.json，不经过 Python） ──
ipcMain.handle('get-hardware-accel', function(event) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden', enabled: true };
  try {
    var p = getHwAccelConfigPath();
    if (fs.existsSync(p)) {
      var cfg = JSON.parse(fs.readFileSync(p, 'utf-8').replace(/^\uFEFF/, ''));
      return { enabled: cfg.hardware_acceleration !== false };
    }
  } catch(e) {}
  return { enabled: true };
});

ipcMain.handle('set-hardware-accel', function(event, enabled) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  try {
    var p = getHwAccelConfigPath();
    var cfg = {};
    if (fs.existsSync(p)) {
      cfg = JSON.parse(fs.readFileSync(p, 'utf-8').replace(/^\uFEFF/, ''));
    }
    cfg.hardware_acceleration = !!enabled;
    fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf-8');
    return { ok: true, needRestart: true };
  } catch(e) {
    return { ok: false, error: e.message };
  }
});

// ── 开屏动画开关（应用级配置，与硬件加速同一份 config.json，键名 splash_animation） ──
ipcMain.handle('get-splash-animation', function(event) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden', enabled: true };
  try {
    var cfg = readAppConfig();
    return { enabled: cfg.splash_animation !== false };
  } catch (e) {}
  return { enabled: true };
});

ipcMain.handle('set-splash-animation', function(event, enabled) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
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
  if (!trustedSender(event)) { event.returnValue = true; return; }
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
  if (!trustedSender(event)) { event.returnValue = 'dark'; return; }
  var theme = 'dark';
  try {
    var cfg = readAppConfig();
    theme = (cfg.theme === 'light') ? 'light' : 'dark';
  } catch (e) {}
  event.returnValue = theme;
});

// ── 主题持久化（应用级配置，键名 theme）：供下次启动设置窗口底色，避免浅色主题下闪黑 ──
ipcMain.handle('set-theme', function(event, theme) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
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
  if (!trustedSender(event)) { event.returnValue = null; return; }
  event.returnValue = resolveConfiguredLanguage();
});

// 语言切换：校验必须在本语言清单里，非法值直接拒绝（返回 ok:false），不写文件
ipcMain.handle('set-language', function(event, lang) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
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

// ── 首次启动引导标志（应用级 config.json 的 onboarding_done，缺省 false）──
// 读：启动期同步读取，外壳要在开屏结束后立刻决定是否显示引导；
// 写：引导完成/稍后配置时置 true，设置面板"重新运行引导"时置回 false。
ipcMain.on('get-onboarding-done-sync', function(event) {
  if (!trustedSender(event)) { event.returnValue = true; return; }
  var done = false;
  try { done = readAppConfig().onboarding_done === true; } catch (e) {}
  event.returnValue = done;
});

ipcMain.handle('set-onboarding-done', function(event, done) {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
  try {
    var p = getHwAccelConfigPath();
    var cfg = readAppConfig();
    // 不传参数时按 true 处理（引导完成）；显式传 false 用于"重新运行引导"
    cfg.onboarding_done = (done === undefined) ? true : !!done;
    fs.writeFileSync(p, JSON.stringify(cfg, null, 2), 'utf-8');
    return { ok: true, onboarding_done: cfg.onboarding_done };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ── 快速部署占位：功能尚未实现，仅弹原生提示对话框 ──
ipcMain.handle('quick-deploy-soon', async (event) => {
  if (!trustedSender(event)) return { ok: false, error: 'ipc.err.forbidden' };
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

// C1 E2E：只注入测试状态，用于在真实 Electron renderer 中验证 U01 DOM 安全。
// 生产 app.isPackaged 为 true 时 TEST_HOOKS 恒为 false，本通道不会注册。
if (TEST_HOOKS) {
  registerApi('test:inject_state', async function (args) {
    if (!mainWindow || mainWindow.isDestroyed()) return { ok: false, error: 'no-window' };
    latestState = args.state;
    mainWindow.webContents.send('state-update', args.state);
    return { ok: true };
  });
}

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

// ── 去掉窗口菜单栏 ──
// 默认应用菜单会渲染出顶部的 File/Edit/View/Window 菜单条，这里置空去掉。
// 必须在 app.whenReady() 之前调用，晚于窗口创建就来不及了。
// 说明：托盘右键菜单是 createTray() 里独立的 Menu.buildFromTemplate 对象，不受影响；
// 文本框内的 Ctrl+C/V/X/A/Z 由 Chromium 的编辑命令处理，也不依赖应用菜单。
Menu.setApplicationMenu(null);

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
  if (TEST_APPDATA) { try { app.setPath('userData', path.join(TEST_APPDATA, 'digital-lab')); } catch (e) {} }
  // P0（S9）：统一权限与子窗口加固
  try {
    session.defaultSession.setPermissionRequestHandler(function (_wc, _permission, callback) {
      callback(false);
    });
    session.defaultSession.setPermissionCheckHandler(function () { return false; });
  } catch (e) {}
  app.on('web-contents-created', function (_event, contents) {
    contents.setWindowOpenHandler(function () {
      writeLog('blocked window.open (web-contents-created)');
      return { action: 'deny' };
    });
    contents.on('will-navigate', function (event, url) {
      if (!isTrustedPage(url)) {
        try { event.preventDefault(); } catch (e) {}
      }
    });
    contents.on('will-redirect', function (event, url) {
      if (!isTrustedPage(url)) {
        try { event.preventDefault(); } catch (e) {}
      }
    });
    contents.on('will-attach-webview', function (event) {
      try { event.preventDefault(); } catch (e) {}
    });
  });
  createWindow();
  createTray();
  startPython();

  // DL-SEC-02-A：测试模式按需创建不可信窗口（生产不生效）
  if (TEST_HOOKS && process.env.DIGITAL_LAB_UNTRUSTED_WINDOW === '1') {
    setTimeout(openUntrustedTestWindow, 2500);
  }

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
