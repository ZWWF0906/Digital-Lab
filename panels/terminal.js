// panels/terminal.js — NAS-exclusive SSH terminal
import { Terminal } from '../node_modules/@xterm/xterm/lib/xterm.mjs';
import { FitAddon } from '../node_modules/@xterm/addon-fit/lib/addon-fit.mjs';

const TERM_STYLE = `
  .xterm { padding: 12px; }
  .xterm .xterm-helper-textarea {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    left: 0 !important;
    top: 0 !important;
    overflow: hidden !important;
    clip: rect(0,0,0,0) !important;
    white-space: nowrap !important;
    border: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    opacity: 0.01 !important;
    background: transparent !important;
    color: transparent !important;
    outline: none !important;
    resize: none !important;
    pointer-events: auto !important;
    z-index: -5 !important;
  }
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
  let taObserver = null;
  let sessions = [];
  let activeSessionId = null;
  let currentMode = null;
  let unsubscribe = null;
  let lastOnlineNames = [];
  let initGeneration = 0;  // 中止过期的 initTerminal 调用

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

  function showPlaceholder(message) {
    cleanupTerminal();
    initGeneration++;  // 中止任何正在运行的 initTerminal
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
    cleanupTerminal();
    initGeneration++;  // 中止任何正在运行的旧 initTerminal

    sessions = deviceNames.map(name => ({
      id: `nas-${name}`,
      name: name,
      type: 'ssh',
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
      initTerminal(initGeneration);
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

  async function switchSession(sessionId) {
    if (sessionId === activeSessionId) return;
    activeSessionId = sessionId;
    renderTabs();
    await initTerminal(initGeneration);
  }

  async function initTerminal(gen) {
    const body = document.getElementById('term-body');
    if (!body || gen !== initGeneration) return;

    const session = sessions.find(s => s.id === activeSessionId);
    if (!session) return;

    // Clean up old terminal (the one being replaced, not the current)
    if (term) {
      // Close the old session's SSH connection
      const oldSessionId = session.sessionId;
      if (oldSessionId) {
        api.sendCommand({ cmd: 'terminal_close', session_id: oldSessionId }).catch(() => {});
        session.sessionId = null;
      }

      if (term._onDataDisposable) {
        try { term._onDataDisposable.dispose(); } catch (e) {}
        term._onDataDisposable = null;
      }
      if (term._cleanupOutput) {
        try { term._cleanupOutput(); } catch (e) {}
        term._cleanupOutput = null;
      }
      if (term._resizeObserver) {
        try { term._resizeObserver.disconnect(); } catch (e) {}
        term._resizeObserver = null;
      }
      try { term.dispose(); } catch (e) {}
      term = null;
    }

    body.innerHTML = '';
    await new Promise(r => requestAnimationFrame(r));
    if (gen !== initGeneration) return;  // 被中止

    term = new Terminal({
      cursorBlink: true,
      cursorStyle: 'underline',
      fontSize: 14,
      fontFamily: "'Consolas', 'Courier New', monospace",
      allowProposedApi: true,
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

    fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(body);

    // 强制隐藏 xterm 辅助 textarea（MutationObserver 守卫，防止被 xterm.js 重置）
    const HIDDEN_STYLE = 'position:absolute !important;width:1px !important;height:1px !important;' +
      'left:0 !important;top:0 !important;overflow:hidden !important;' +
      'clip:rect(0,0,0,0) !important;white-space:nowrap !important;' +
      'border:0 !important;padding:0 !important;margin:0 !important;' +
      'opacity:0.01 !important;background:transparent !important;' +
      'color:transparent !important;outline:none !important;resize:none !important;' +
      'pointer-events:auto !important;z-index:-5 !important;';
    const applyHiddenStyle = () => {
      const ta = body.querySelector('.xterm-helper-textarea');
      if (ta && ta.getAttribute('style') !== HIDDEN_STYLE) {
        ta.setAttribute('style', HIDDEN_STYLE);
      }
    };
    applyHiddenStyle();
    // MutationObserver 守卫：xterm.js 运行时可能重置 style，立即恢复
    const ta = body.querySelector('.xterm-helper-textarea');
    if (ta) {
      taObserver = new MutationObserver(() => applyHiddenStyle());
      taObserver.observe(ta, { attributes: true, attributeFilter: ['style'] });
    }

    fitAddon.fit();
    // 延迟再 fit 一次，确保 flex 布局计算完成后终端填满容器
    setTimeout(() => {
      if (gen === initGeneration && fitAddon) {
        try { fitAddon.fit(); } catch (e) {}
      }
    }, 100);

    // SSH session init
    if (!session.sessionId) {
      try {
        term.writeln(`\u6b63\u5728\u8fde\u63a5 ${session.name}...`);
        const resp = await api.sendCommand({
          cmd: 'ssh_terminal_init',
          host: session.name,
        });
        if (gen !== initGeneration) {  // 被中止
          if (resp && resp.session_id) {
            api.sendCommand({ cmd: 'terminal_close', session_id: resp.session_id }).catch(() => {});
          }
          try { term.dispose(); } catch (e) {}
          term = null;
          return;
        }
        if (resp && resp.session_id) {
          session.sessionId = resp.session_id;
          term.writeln(`\x1b[32m\u5df2\u8fde\u63a5 ${session.name}\x1b[0m`);
        } else if (resp && resp.error) {
          term.writeln(`\x1b[31m[ERROR] ${resp.error}\x1b[0m`);
          return;
        } else {
          term.writeln(`\x1b[31m[ERROR] \u8fde\u63a5\u5931\u8d25\uff0c\u672a\u77e5\u9519\u8bef\x1b[0m`);
          return;
        }
      } catch (e) {
        if (gen !== initGeneration) return;
        term.writeln(`\x1b[31m[ERROR] SSH \u8fde\u63a5\u5931\u8d25: ${e.message}\x1b[0m`);
        return;
      }
    }

    if (gen !== initGeneration) {  // 被中止
      try { term.dispose(); } catch (e) {}
      term = null;
      return;
    }

    // Terminal input
    term._onDataDisposable = term.onData((data) => {
      if (!session.sessionId) return;
      api.sendCommand({
        cmd: 'terminal_input',
        session_id: session.sessionId,
        data: data,
      }).catch(() => {});
    });

    // Terminal output
    if (api.onTerminalData) {
      const cleanup = api.onTerminalData((data) => {
        if (gen !== initGeneration) return;  // 过期回调静默忽略
        if (data.session_id === session.sessionId && term) {
          term.write(data.data);
        }
      });
      term._cleanupOutput = cleanup;
    }

    // Resize handler
    const resizeObserver = new ResizeObserver(() => {
      if (gen !== initGeneration) return;
      if (fitAddon) {
        try { fitAddon.fit(); } catch (e) {}
      }
      if (session.sessionId && term) {
        api.sendCommand({
          cmd: 'terminal_resize',
          session_id: session.sessionId,
          cols: term.cols,
          rows: term.rows,
        }).catch(() => {});
      }
    });
    resizeObserver.observe(body);
    term._resizeObserver = resizeObserver;
  }

  function cleanupTerminal() {
    if (taObserver) {
      try { taObserver.disconnect(); } catch (e) {}
      taObserver = null;
    }
    if (term) {
      if (term._cleanupOutput) {
        try { term._cleanupOutput(); } catch (e) {}
        term._cleanupOutput = null;
      }
      if (term._onDataDisposable) {
        try { term._onDataDisposable.dispose(); } catch (e) {}
        term._onDataDisposable = null;
      }
      if (term._resizeObserver) {
        try { term._resizeObserver.disconnect(); } catch (e) {}
        term._resizeObserver = null;
      }
      try { term.dispose(); } catch (e) {}
      term = null;
    }
    fitAddon = null;
    sessions.forEach(s => {
      if (s.sessionId) {
        api.sendCommand({ cmd: 'terminal_close', session_id: s.sessionId }).catch(() => {});
        s.sessionId = null;
      }
    });
    sessions = [];
    activeSessionId = null;
  }

  // Subscribe to state updates for reactive NAS status
  unsubscribe = api.onStateUpdate((state) => {
    const nas = state.nas || {};
    const onlineDevices = getOnlineNasDevices(nas);

    if (onlineDevices.length === 0) {
      // No online NAS
      const hasAnyNas = nas && Object.keys(nas).length > 0;
      const message = hasAnyNas ? 'NAS 设备当前离线' : '暂无可用 NAS 设备';
      lastOnlineNames = [];
      if (currentMode !== 'placeholder') {
        showPlaceholder(message);
      }
    } else {
      // Has online NAS
      if (currentMode !== 'terminal' || onlineNamesChanged(onlineDevices)) {
        lastOnlineNames = [...onlineDevices];
        showTerminal(onlineDevices);
      }
    }
  });

  return () => {
    if (unsubscribe) {
      try { unsubscribe(); } catch (e) {}
      unsubscribe = null;
    }
    cleanupTerminal();
  };
}