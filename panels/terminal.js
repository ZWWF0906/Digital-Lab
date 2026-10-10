// panels/terminal.js — NAS-exclusive SSH terminal
// 标准 xterm.js + addon-fit 集成（参考 webssh / node-pty 成熟方案）：
//   - term.onData 只负责将用户输入发送到后端，禁止本地回显
//   - 终端输出完全依赖后端转发的远端 SSH stdout
//   - 建立连接时携带真实终端尺寸（后端据此创建 PTY），之后 ResizeObserver 持续同步
// 1.5.0 生命周期约定（面板保活）：
//   - detach()：只标记"已离开屏幕"，保留 xterm 实例、监听器与后端会话
//   - attach()：回到屏幕后重新 fit 并向后端同步尺寸，用 terminal_attach 确认会话仍在
//   - 只有设备被删除或会话被确认为不存在时，才真正发 terminal_close
//   - 后端为每个会话保留 256KB 输出环形缓冲，重附着时直接回放
import { Terminal } from '../node_modules/@xterm/xterm/lib/xterm.mjs';
import { FitAddon } from '../node_modules/@xterm/addon-fit/lib/addon-fit.mjs';

// 文案走 i18n：i18n.js 由 dashboard.html 在 <head> 里以经典脚本加载，暴露 window.DigitalLabI18n。
// 本文件的中文原先一部分写成 \uXXXX 转义，迁移与复查都不要只搜字面中文。
// 取名 T 而不是 t：mountTerminal() 里的 xterm 实例就叫 t，会把同名助手遮住。
const T = (key, params) => (
  (typeof window !== 'undefined' && window.DigitalLabI18n)
    ? window.DigitalLabI18n.t(key, params)
    : key
);

// 离线防抖：连续 N 次状态更新都报离线，才在界面上提示离线；连接始终保留
const OFFLINE_CONFIRM = 3;
// 小于这个列数视为"容器不可见"的退化尺寸，不向后端同步（隐藏窗口时会量到 0）
const MIN_COLS = 10;

// 终端里的报错行：ANSI 红色（\x1b[31m ... \x1b[0m）只包在文案外面，颜色码不进词典。
// 前缀 [ERROR] 保持英文常量：全仓没有任何代码解析它（无 startsWith/indexOf/正则匹配），
// 它只是给人看的行首标记；只有后面的说明文字走 i18n。
function errorLine(message) {
  return `\x1b[31m[ERROR] ${message}\x1b[0m`;
}

// 后端错误转文案（双兼容）：
//   新后端：{code, params} → 查词典（code 与词典 key 同名，缺 key 时 t() 返回 key 本身）
//   旧后端：直接给字符串（例如 "未找到设备配置: Mock-NAS"）→ 原样显示，绝不是空白
function backendErrorText(err) {
  if (err && typeof err === 'object' && err.code) {
    return T(err.code, err.params || {}) || String(err.code);
  }
  return String(err == null ? '' : err);
}

const TERM_STYLE = `
  .xterm { padding: 12px; }
  .xterm .xterm-viewport { background-color: #0c0c0c !important; }
  .xterm .composition-view { background: #0c0c0c !important; color: #cccccc !important; }
  .xterm-viewport::-webkit-scrollbar { width: 8px; }
  .xterm-viewport::-webkit-scrollbar-track { background: #0c0c0c; }
  .xterm-viewport::-webkit-scrollbar-thumb { background: #3a3a3a; border-radius: 0; }
  .xterm-viewport::-webkit-scrollbar-thumb:hover { background: #555; }
  .xterm-screen { outline: none !important; }
`;

let termStyleInserted = false;

let shownTip = false;

function showTipModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-content modal-tip">
      <div class="modal-header">
        <span class="modal-title">${T('common.tip.title')}</span>
        <button class="modal-close-btn">&times;</button>
      </div>
      <div class="modal-tip-body">${T('common.tip.body')}</div>
      <div class="modal-tip-footer">
        <button class="modal-tip-btn">${T('common.ok')}</button>
      </div>
    </div>`;

  const close = () => overlay.remove();
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close();
  });
  overlay.querySelector('.modal-close-btn').addEventListener('click', close);
  overlay.querySelector('.modal-tip-btn').addEventListener('click', close);

  document.body.appendChild(overlay);
}

export function init(container, api) {
  if (!shownTip) {
    shownTip = true;
    showTipModal();
  }

  if (!termStyleInserted) {
    const style = document.createElement('style');
    style.textContent = TERM_STYLE;
    document.head.appendChild(style);
    termStyleInserted = true;
  }

  let term = null;
  let fitAddon = null;
  // 标签状态：每个在线/曾在线设备一条，sessionId 一旦建立就跨面板切换保留
  let sessions = [];
  let activeSessionId = null;
  // 当前屏幕上的传输绑定：持有 xterm 与该会话的监听器
  let active = null;
  let unsubscribe = null;
  let lastOnlineNames = [];
  let offlineKey = '';     // 已确认离线的会话集合指纹：只有集合变化才重画标签（避免每秒重绘）
  let initGeneration = 0;  // 中止过期的建立连接调用
  let currentMode = null;
  let detached = false;    // 面板已离开屏幕（detach 后仍保留会话与实例）
  let skeletonBuilt = false;

  // mock 设备（nas_mock_enabled=true 时由后端生成）没有 nas_devices 配置条目，
  // 连它必然报"未找到设备配置"；1.5.0 起后端给这类设备带 is_mock 标记，
  // 旧后端则用 Mock- 前缀兜底识别。终端不展示 mock 设备，仪表盘/设备中心不受影响。
  function isMockDevice(name, data) {
    if (data && data.is_mock === true) return true;
    return typeof name === 'string' && name.indexOf('Mock-') === 0;
  }

  function getOnlineNasDevices(nasState) {
    if (!nasState || typeof nasState !== 'object') return [];
    return Object.entries(nasState)
      .filter(([name, d]) => d && d.online === true && !isMockDevice(name, d))
      .map(([name]) => name)
      .sort();
  }

  function findEntry(name) {
    return sessions.find(s => s.name === name);
  }

  function ensureSkeleton() {
    if (skeletonBuilt && container.querySelector('.terminal-container')) return;
    container.innerHTML = `
      <div class="terminal-container">
        <div class="terminal-tabs" id="term-tabs"></div>
        <div class="terminal-body" id="term-body"></div>
      </div>`;
    skeletonBuilt = true;
  }

  // 只拆前端传输（xterm + 监听器 + 观察器），不发送 terminal_close：
  // 后端会话与 256KB 环形缓冲继续存活，重附着时回放。
  function teardownTransport() {
    if (active) {
      if (active.onDataDisposable) {
        try { active.onDataDisposable.dispose(); } catch (e) {}
        active.onDataDisposable = null;
      }
      if (active.outputUnsub) {
        try { active.outputUnsub(); } catch (e) {}
        active.outputUnsub = null;
      }
      if (active.resizeObserver) {
        try { active.resizeObserver.disconnect(); } catch (e) {}
        active.resizeObserver = null;
      }
      if (active.resizeTimer) {
        clearTimeout(active.resizeTimer);
        active.resizeTimer = null;
      }
      active = null;
    }
    if (term) {
      try { term.dispose(); } catch (e) {}
      term = null;
    }
    fitAddon = null;
  }

  // 真正关闭某个设备的会话：仅用于设备从配置中删除，或用户显式关闭标签
  function closeEntry(entry) {
    if (!entry) return;
    if (entry.sessionId) {
      api.sendCommand({ cmd: 'terminal_close', session_id: entry.sessionId }).catch(() => {});
      entry.sessionId = null;
    }
    if (active && active.id === entry.id) teardownTransport();
    sessions = sessions.filter(s => s !== entry);
    if (activeSessionId === entry.id) {
      activeSessionId = sessions.length ? sessions[0].id : null;
    }
    renderTabs();
  }

  function showPlaceholder(message) {
    teardownTransport();
    initGeneration++;
    skeletonBuilt = false;
    const desc = message || T('term.placeholder.desc');
    container.innerHTML = `
      <div class="terminal-placeholder">
        <div class="terminal-placeholder-icon">\u2263</div>
        <div class="terminal-placeholder-title">${T('term.placeholder.title')}</div>
        <div class="terminal-placeholder-desc">${desc}</div>
        <button class="terminal-placeholder-btn">${T('term.placeholder.btn')}</button>
      </div>`;

    const btn = container.querySelector('.terminal-placeholder-btn');
    if (btn) {
      btn.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('switch-panel', { detail: 'settings' }));
      });
    }
    currentMode = 'placeholder';
  }

  function renderTabs() {
    const tabs = document.getElementById('term-tabs');
    if (!tabs) return;
    tabs.innerHTML = sessions.map(s => `
      <div class="terminal-tab ${s.id === activeSessionId ? 'active' : ''}"
           data-session="${s.id}"
           title="${(s.offlineStrikes || 0) >= OFFLINE_CONFIRM ? T('term.offline') : ''}">${s.name}</div>
    `).join('');

    tabs.querySelectorAll('.terminal-tab').forEach(tab => {
      tab.addEventListener('click', () => switchSession(tab.dataset.session));
    });
  }

  function sendResize() {
    if (!term || !active || !active.sessionId) return;
    if (detached || (typeof document !== 'undefined' && document.hidden)) return;
    if (!term.cols || term.cols < MIN_COLS) return;
    api.sendCommand({
      cmd: 'terminal_resize',
      session_id: active.sessionId,
      cols: term.cols,
      rows: term.rows,
    }).catch(() => {});
  }

  function createTerminal() {
    const body = document.getElementById('term-body');
    if (!body) return null;
    const t = new Terminal({
      cursorBlink: true,
      cursorStyle: 'underline',
      fontSize: 14,
      fontFamily: "'Consolas', 'Courier New', monospace",
      theme: {
        background: '#0c0c0c',
        foreground: '#cccccc',
        cursor: '#ffffff',
        selectionBackground: '#264f78',
        black: '#0c0c0c',
        red: '#e74856',
        green: '#16c60c',
        yellow: '#f9f1a5',
        blue: '#3b78ff',
        magenta: '#b4009e',
        cyan: '#61d6d6',
        white: '#f2f2f2',
        brightBlack: '#767676',
        brightRed: '#e74856',
        brightGreen: '#16c60c',
        brightYellow: '#f9f1a5',
        brightBlue: '#3b78ff',
        brightMagenta: '#b4009e',
        brightCyan: '#61d6d6',
        brightWhite: '#f2f2f2',
      },
    });

    const fit = new FitAddon();
    t.loadAddon(fit);
    t.open(body);
    try { fit.fit(); } catch (e) {}

    term = t;
    fitAddon = fit;
    return t;
  }

  // 绑定输入/输出/尺寸监听（重附着与新连接共用）
  function bindTransport(entry, t, gen) {
    const act = {
      id: entry.id,
      sessionId: entry.sessionId,
      onDataDisposable: null,
      outputUnsub: null,
      resizeObserver: null,
      resizeTimer: null,
    };
    active = act;

    act.onDataDisposable = t.onData((data) => {
      if (!act.sessionId) return;
      api.sendCommand({
        cmd: 'terminal_input',
        session_id: act.sessionId,
        data: data,
      }).catch(() => {});
    });

    if (api.onTerminalData) {
      act.outputUnsub = api.onTerminalData((data) => {
        if (gen !== initGeneration) return;  // 过期回调静默忽略
        if (act.sessionId && data.session_id === act.sessionId && term === t) {
          t.write(data.data);
        }
      });
    }

    const ro = new ResizeObserver(() => {
      if (gen !== initGeneration) return;
      clearTimeout(act.resizeTimer);
      act.resizeTimer = setTimeout(() => {
        if (gen !== initGeneration || term !== t || !act.sessionId) return;
        if (detached || (typeof document !== 'undefined' && document.hidden)) return;
        if (!t.cols || t.cols < MIN_COLS) return;   // 隐藏或退化尺寸不同步，避免打乱远端
        try { fitAddon.fit(); } catch (e) {}
        api.sendCommand({
          cmd: 'terminal_resize',
          session_id: act.sessionId,
          cols: t.cols,
          rows: t.rows,
        }).catch(() => {});
      }, 80);
    });
    ro.observe(document.getElementById('term-body') || container);
    act.resizeObserver = ro;
    return act;
  }

  // 新建 SSH 会话（1.5.1：异步建链，命令通道不再被网络等待阻塞）
  async function openEntry(entry) {
    const gen = initGeneration;
    ensureSkeleton();
    const body = document.getElementById('term-body');
    if (!body || gen !== initGeneration) return;
    body.innerHTML = '';
    const t = createTerminal();
    if (!t) return;
    bindTransport(entry, t, gen);

    let settled = false;
    let pendingUnsub = null;
    let pendingTimer = null;

    function cleanupPending() {
      if (pendingUnsub) { try { pendingUnsub(); } catch (e) {} pendingUnsub = null; }
      if (pendingTimer) { clearTimeout(pendingTimer); pendingTimer = null; }
    }

    function applyError(err) {
      if (gen !== initGeneration || !active || active.id !== entry.id) return;
      t.writeln(errorLine(backendErrorText(err)));
    }

    function acceptSession(sessionId) {
      if (settled) return;
      settled = true;
      cleanupPending();
      if (gen !== initGeneration || !active || active.id !== entry.id) {
        // 流程已过期：关掉刚建好的后端会话，避免泄漏
        api.sendCommand({ cmd: 'terminal_close', session_id: sessionId }).catch(() => {});
        return;
      }
      entry.sessionId = sessionId;
      if (active) active.sessionId = sessionId;
      try { fitAddon.fit(); } catch (e) {}
      sendResize();
    }

    // 后端在 async 模式下立即返回 pending，真正的 session_id 通过这个通道回传
    if (api.onTerminalConnectResult) {
      pendingUnsub = api.onTerminalConnectResult((data) => {
        if (!data || data.host !== entry.name) return;
        if (data.ok && data.session_id) {
          acceptSession(data.session_id);
        } else {
          settled = true;
          cleanupPending();
          applyError(data.error || { code: 'term.error.unknown' });
        }
      });
    }
    // 兜底超时：事件丢失时不至于永远停在"连接中"
    pendingTimer = setTimeout(() => {
      if (settled) return;
      settled = true;
      cleanupPending();
      if (gen === initGeneration && active && active.id === entry.id) {
        t.writeln(errorLine(T('term.error.timeout')));
      }
    }, 25000);

    try {
      t.writeln(T('term.connecting', { name: entry.name }));
      const resp = await api.sendCommand({
        cmd: 'ssh_terminal_init',
        host: entry.name,
        cols: t.cols,
        rows: t.rows,
        async: true,
      });
      if (resp && resp.session_id) {
        acceptSession(resp.session_id);   // 旧后端：同步返回 session_id，直接接受
        return;
      }
      if (resp && resp.pending) return;   // 新后端：等 terminal-connect-result 事件
      settled = true;
      cleanupPending();
      applyError((resp && resp.error) || { code: 'term.error.unknown' });
    } catch (e) {
      settled = true;
      cleanupPending();
      if (gen !== initGeneration || !active || active.id !== entry.id) return;
      t.writeln(errorLine(T('term.error.ssh', { message: e.message })));
    }
  }

  // 重附着已有会话：先向后端确认会话仍在，再回放环形缓冲
  async function attachEntry(entry) {
    const gen = initGeneration;
    ensureSkeleton();
    const body = document.getElementById('term-body');
    if (!body || gen !== initGeneration) return;
    body.innerHTML = '';
    const t = createTerminal();
    if (!t) return;
    bindTransport(entry, t, gen);

    try {
      const resp = await api.sendCommand({ cmd: 'terminal_attach', session_id: entry.sessionId });
      if (gen !== initGeneration || !active || active.id !== entry.id) return;
      if (resp && resp.ok && resp.alive) {
        if (resp.buffer) t.write(resp.buffer);
        try { fitAddon.fit(); } catch (e) {}
        sendResize();
        return;
      }
      // 会话已不存在（后端重启、连接中断、被清理）：清掉旧 id 后重连
      entry.sessionId = null;
      if (resp && resp.error) t.writeln(errorLine(backendErrorText(resp.error)));
      teardownTransport();
      await openEntry(entry);
    } catch (e) {
      if (gen !== initGeneration || !active || active.id !== entry.id) return;
      entry.sessionId = null;
      teardownTransport();
      await openEntry(entry);
    }
  }

  function switchSession(sessionId) {
    if (sessionId === activeSessionId) return;
    activeSessionId = sessionId;
    renderTabs();
    const entry = sessions.find(s => s.id === sessionId);
    if (!entry) return;
    teardownTransport();   // 只拆前端，后端会话保留
    if (entry.sessionId) {
      attachEntry(entry);
    } else {
      openEntry(entry);
    }
  }

  // 订阅 NAS 状态：只做增量维护，绝不用"在线集合变化"去重建已有会话
  unsubscribe = api.onStateUpdate((state) => {
    const nas = (state && state.nas) || {};
    const knownNames = Object.keys(nas);
    const onlineDevices = getOnlineNasDevices(nas);

    // 1) 设备已从配置删除 → 关闭它的会话并移除标签
    for (const entry of [...sessions]) {
      if (!knownNames.includes(entry.name)) closeEntry(entry);
    }

    // 2) 新增在线设备 → 只补标签，不动其它会话
    let added = false;
    for (const name of onlineDevices) {
      if (!findEntry(name)) {
        sessions.push({ id: `nas-${name}`, name: name, sessionId: null, offlineStrikes: 0, notified: false });
        added = true;
      }
    }
    lastOnlineNames = [...onlineDevices];

    // 3) 离线防抖：只累计连续次数用于提示，连接一律保留
    for (const entry of sessions) {
      const d = nas[entry.name];
      const isOnline = !!(d && d.online === true);
      if (isOnline) {
        entry.offlineStrikes = 0;
        entry.notified = false;
      } else {
        entry.offlineStrikes = (entry.offlineStrikes || 0) + 1;
        if (entry.offlineStrikes >= OFFLINE_CONFIRM && !entry.notified && active && active.id === entry.id && term) {
          entry.notified = true;
          term.writeln(T('term.offline'));
        }
      }
    }
    const nextOfflineKey = sessions
      .filter(s => (s.offlineStrikes || 0) >= OFFLINE_CONFIRM)
      .map(s => s.id)
      .sort()
      .join(',');
    if (nextOfflineKey !== offlineKey) {
      offlineKey = nextOfflineKey;
      renderTabs();
    }

    // 4) 没有任何设备：显示占位（此时也确实没有会话可保）
    if (sessions.length === 0) {
      const hasAnyNas = knownNames.length > 0;
      const message = hasAnyNas ? T('term.offline') : T('term.placeholder.desc');
      if (currentMode !== 'placeholder') showPlaceholder(message);
      return;
    }

    // 5) 有设备：只在必要时建立首个会话，已建立的会话保持不变
    if (currentMode !== 'terminal') {
      currentMode = 'terminal';
      ensureSkeleton();
    }
    if (added) renderTabs();
    if (!activeSessionId) {
      activeSessionId = sessions[0].id;
      renderTabs();
      if (sessions[0].sessionId) {
        attachEntry(sessions[0]);
      } else {
        openEntry(sessions[0]);
      }
    }
  });

  // ── 面板保活接口 ──
  return {
    // 离开屏幕：什么都不拆，只标记状态（xterm、监听器、后端会话全部保留）
    detach() {
      detached = true;
    },
    // 回到屏幕：重新 fit + 同步尺寸，并确认会话仍在
    attach() {
      detached = false;
      requestAnimationFrame(() => {
        if (!term) return;
        if (detached) return;
        try { fitAddon.fit(); } catch (e) {}
        sendResize();
      });
    },
    // 语言切换：不重建会话；占位文案与标签提示按新语言刷新
    onLanguageChanged() {
      if (currentMode === 'placeholder') {
        const hasAnyNas = lastOnlineNames.length > 0 || sessions.length > 0;
        showPlaceholder(hasAnyNas ? T('term.offline') : T('term.placeholder.desc'));
        return;
      }
      renderTabs();
    },
    // 面板被真正丢弃时才走到这里：只拆前端，不关闭后端会话
    cleanup() {
      if (unsubscribe) {
        try { unsubscribe(); } catch (e) {}
        unsubscribe = null;
      }
      initGeneration++;
      teardownTransport();
    },
  };
}
