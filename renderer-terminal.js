// renderer-terminal.js — C1 U02 独立 Terminal WebContents。
// 只使用 preload-terminal.js 暴露的最小能力；不访问 dashboard 的 digitalLab bridge。
import { Terminal } from './node_modules/@xterm/xterm/lib/xterm.mjs';
import { FitAddon } from './node_modules/@xterm/addon-fit/lib/addon-fit.mjs';

const api = window.terminalAPI;
const view = document.getElementById('terminal-view');
const status = document.getElementById('terminal-status');
const head = document.getElementById('terminal-head');
let context = null;
let term = null;
let fit = null;
let lastInputAt = 0;

function setStatus(text) {
  if (status) status.textContent = String(text == null ? '' : text);
}

function fitTerminal() {
  if (!term || !fit) return;
  try { fit.fit(); } catch (e) {}
  if (context && term.cols && term.rows) {
    api.resize(context.sessionId, term.cols, term.rows).catch(() => {});
  }
}

function startTerminal(ctx) {
  if (!ctx || !ctx.sessionId || !api) return;
  context = ctx;
  if (head) head.textContent = 'DigitalLab Terminal — ' + String(ctx.deviceName || ctx.deviceId || 'NAS');
  term = new Terminal({
    cursorBlink: true,
    fontFamily: '"JetBrains Mono", monospace',
    fontSize: 13,
    theme: { background: '#0c0c0c', foreground: '#cccccc' },
  });
  fit = new FitAddon();
  term.loadAddon(fit);
  term.open(view);
  fitTerminal();
  term.focus();
  term.onData((data) => {
    if (!context || !data) return;
    const now = Date.now();
    if (now - lastInputAt < 15) return; // 基础频率限制；主进程还会再次限速
    lastInputAt = now;
    api.input(context.sessionId, String(data).slice(0, 8192)).catch(() => {});
  });
  const ro = new ResizeObserver(() => fitTerminal());
  ro.observe(view);
  window.addEventListener('beforeunload', () => {
    try { api.close(context.sessionId); } catch (e) {}
  }, { once: true });
  api.attach(context.sessionId).then((res) => {
    if (res && res.buffer) term.write(String(res.buffer));
    setStatus(res && res.alive ? 'Connected' : 'Session closed');
  }).catch(() => setStatus('Attach failed'));
}

if (api) {
  api.onContext(startTerminal);
  api.onData((msg) => {
    if (!term || !context || !msg || msg.session_id !== context.sessionId) return;
    if (msg.closed === true) {
      context = null;
      setStatus('Session closed');
      return;
    }
    term.write(String(msg.data == null ? '' : msg.data));
  });
} else {
  setStatus('Terminal bridge unavailable');
}
