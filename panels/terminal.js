// panels/terminal.js — NAS-exclusive SSH terminal
// 标准 xterm.js + addon-fit 集成（参考 webssh / node-pty 成熟方案）：
//   - term.onData 只负责将用户输入发送到后端，禁止本地回显
//   - 终端输出完全依赖后端转发的远端 SSH stdout
//   - 建立连接时携带真实终端尺寸（后端据此创建 PTY），之后 ResizeObserver 持续同步
//   - 断开/切换/卸载时清理全部监听器并关闭后端会话
import { Terminal } from '../node_modules/@xterm/xterm/lib/xterm.mjs';
import { FitAddon } from '../node_modules/@xterm/addon-fit/lib/addon-fit.mjs';

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
        <span class="modal-title">提示</span>
        <button class="modal-close-btn">&times;</button>
      </div>
      <div class="modal-tip-body">功能仍在测试阶段，可能会出现异常</div>
      <div class="modal-tip-footer">
        <button class="modal-tip-btn">确定</button>
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
  let sessions = [];
  let activeSessionId = null;
  // 当前正在运行的会话运行状态：持有该会话的全部监听器句柄，切换/卸载时统一清理
  let active = null;
  let unsubscribe = null;
  let lastOnlineNames = [];
  let initGeneration = 0;  // 中止过期的建立连接调用
  let currentMode = null;

  function getOnlineNasDevices(nasState) {
    if (!nasState || typeof nasState !== 'object') return [];
    return Object.entries(nasState)
      .filter(([, d]) => d.online === true)
      .map(([name]) => name)
      .sort();
  }

  function onlineNamesChanged(devices) {
    if (devices.length !== lastOnlineNames.length) return true;
    return devices.some((n, i) => n !== lastOnlineNames[i]);
  }

  // 关闭当前会话的后端连接 + 清理全部监听器和定时器
  function teardownActive() {
    if (active) {
      if (active.sessionId) {
        const s = sessions.find(x => x.id === active.id);
        if (s) s.sessionId = null;
        api.sendCommand({ cmd: 'terminal_close', session_id: active.sessionId }).catch(() => {});
      }
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

  function showPlaceholder(message) {
    teardownActive();
    initGeneration++;  // 中止任何正在运行的连接流程
    const desc = message || '暂无可用 NAS 设备';
    container.innerHTML = `
      <div class="terminal-placeholder">
        <div class="terminal-placeholder-icon">\u2263</div>
        <div class="terminal-placeholder-title">NAS 终端</div>
        <div class="terminal-placeholder-desc">${desc}</div>
        <button class="terminal-placeholder-btn">前往设置添加 NAS</button>
      </div>`;

    const btn = container.querySelector('.terminal-placeholder-btn');
    if (btn) {
      btn.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('switch-panel', { detail: 'settings' }));
      });
    }
    currentMode = 'placeholder';
  }

  function showTerminal(deviceNames) {
    teardownActive();
    initGeneration++;  // 中止任何正在运行的旧连接流程

    sessions = deviceNames.map(name => ({
      id: `nas-${name}`,
      name: name,
      sessionId: null,
    }));

    container.innerHTML = `
      <div class="terminal-container">
        <div class="terminal-tabs" id="term-tabs"></div>
        <div class="terminal-body" id="term-body"></div>
      </div>`;

    if (sessions.length > 0) {
      activeSessionId = sessions[0].id;
      renderTabs();
      openSession(sessions[0]);
    }
    currentMode = 'terminal';
  }

  function renderTabs() {
    const tabs = document.getElementById('term-tabs');
    if (!tabs) return;
    tabs.innerHTML = sessions.map(s => `
      <div class="terminal-tab ${s.id === activeSessionId ? 'active' : ''}"
           data-session="${s.id}">${s.name}</div>
    `).join('');

    tabs.querySelectorAll('.terminal-tab').forEach(tab => {
      tab.addEventListener('click', () => switchSession(tab.dataset.session));
    });
  }

  function switchSession(sessionId) {
    if (sessionId === activeSessionId) return;
    activeSessionId = sessionId;
    renderTabs();
    // 正确关闭上一个标签的后端会话，再建立新会话
    teardownActive();
    const session = sessions.find(s => s.id === sessionId);
    if (session) openSession(session);
  }

  async function openSession(session) {
    const gen = initGeneration;
    const body = document.getElementById('term-body');
    if (!body || gen !== initGeneration) return;

    body.innerHTML = '';

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
    fit.fit();

    term = t;
    fitAddon = fit;

    const act = {
      id: session.id,
      sessionId: null,
      onDataDisposable: null,
      outputUnsub: null,
      resizeObserver: null,
      resizeTimer: null,
    };
    active = act;

    // 输入：仅转发到后端，禁止本地回显
    act.onDataDisposable = t.onData((data) => {
      if (!act.sessionId) return;
      api.sendCommand({
        cmd: 'terminal_input',
        session_id: act.sessionId,
        data: data,
      }).catch(() => {});
    });

    // 输出：完全依赖后端转发的 SSH stdout
    if (api.onTerminalData) {
      act.outputUnsub = api.onTerminalData((data) => {
        if (gen !== initGeneration) return;  // 过期回调静默忽略
        if (act.sessionId && data.session_id === act.sessionId && term === t) {
          t.write(data.data);
        }
      });
    }

    // 尺寸同步：防抖后 fit + 通知后端 resize_pty
    const ro = new ResizeObserver(() => {
      if (gen !== initGeneration) return;
      clearTimeout(act.resizeTimer);
      act.resizeTimer = setTimeout(() => {
        if (gen !== initGeneration || term !== t || !act.sessionId) return;
        try { fit.fit(); } catch (e) {}
        api.sendCommand({
          cmd: 'terminal_resize',
          session_id: act.sessionId,
          cols: t.cols,
          rows: t.rows,
        }).catch(() => {});
      }, 80);
    });
    ro.observe(body);
    act.resizeObserver = ro;

    // 建立 SSH 会话：携带真实终端尺寸，后端据此创建 PTY
    try {
      t.writeln(`\u6b63\u5728\u8fde\u63a5 ${session.name}...`);
      const resp = await api.sendCommand({
        cmd: 'ssh_terminal_init',
        host: session.name,
        cols: t.cols,
        rows: t.rows,
      });
      if (gen !== initGeneration || active !== act) {
        // 流程已被中止：关闭本次新建的后端会话
        if (resp && resp.session_id) {
          api.sendCommand({ cmd: 'terminal_close', session_id: resp.session_id }).catch(() => {});
        }
        return;
      }
      if (resp && resp.session_id) {
        act.sessionId = resp.session_id;
        session.sessionId = resp.session_id;
      } else if (resp && resp.error) {
        t.writeln(`\x1b[31m[ERROR] ${resp.error}\x1b[0m`);
      } else {
        t.writeln(`\x1b[31m[ERROR] \u8fde\u63a5\u5931\u8d25\uff0c\u672a\u77e5\u9519\u8bef\x1b[0m`);
      }
    } catch (e) {
      if (gen !== initGeneration || active !== act) return;
      t.writeln(`\x1b[31m[ERROR] SSH \u8fde\u63a5\u5931\u8d25: ${e.message}\x1b[0m`);
    }
  }

  // 订阅 NAS 状态：在线设备变化时重建终端
  unsubscribe = api.onStateUpdate((state) => {
    const nas = state.nas || {};
    const onlineDevices = getOnlineNasDevices(nas);

    if (onlineDevices.length === 0) {
      const hasAnyNas = nas && Object.keys(nas).length > 0;
      const message = hasAnyNas ? 'NAS 设备当前离线' : '暂无可用 NAS 设备';
      lastOnlineNames = [];
      if (currentMode !== 'placeholder') {
        showPlaceholder(message);
      }
    } else {
      if (currentMode !== 'terminal' || onlineNamesChanged(onlineDevices)) {
        lastOnlineNames = [...onlineDevices];
        showTerminal(onlineDevices);
      }
    }
  });

  // 面板卸载时清理
  return () => {
    if (unsubscribe) {
      try { unsubscribe(); } catch (e) {}
      unsubscribe = null;
    }
    initGeneration++;
    teardownActive();
  };
}