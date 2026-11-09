// panels/terminal.js — C1 U02
// Dashboard 不再持有 SSH 输入/attach 能力。这里只显示在线 NAS 并请求主进程
// 打开独立 Terminal BrowserWindow；真正的 xterm 与输入能力在 terminal.html 中。
const T = (key, params) => (
  (typeof window !== 'undefined' && window.DigitalLabI18n)
    ? window.DigitalLabI18n.t(key, params)
    : key
);

function textEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  el.textContent = String(text == null ? '' : text);
  return el;
}

export function init(container, api) {
  container.replaceChildren();
  container.appendChild(textEl('div', 'section-title', T('term.title') || 'SSH Terminal'));
  const note = textEl('div', 'mc-empty', T('term.placeholder.desc') || 'Open an online NAS device in a separate terminal window.');
  container.appendChild(note);
  const list = document.createElement('div');
  list.className = 'device-grid';
  container.appendChild(list);
  const status = textEl('div', 'mc-info', '');
  container.appendChild(status);

  let latestState = null;
  let busy = false;

  function render() {
    const nas = (latestState && latestState.nas) || {};
    const names = Object.keys(nas)
      .filter((name) => nas[name] && nas[name].online === true && !String(name).startsWith('Mock-'))
      .sort();
    list.replaceChildren();
    if (!names.length) {
      list.appendChild(textEl('div', 'mc-empty', T('term.placeholder.desc') || 'No online NAS device.'));
      return;
    }
    names.forEach((name) => {
      const card = document.createElement('div');
      card.className = 'device-card metric-card';
      const head = document.createElement('div');
      head.className = 'mc-header';
      head.appendChild(textEl('span', 'mc-label', '\u{1F4E1} ' + String(name)));
      card.appendChild(head);
      const btn = textEl('button', 'btn-secondary', T('term.placeholder.btn') || 'Open terminal');
      btn.addEventListener('click', async () => {
        if (busy) return;
        busy = true;
        btn.disabled = true;
        try {
          const res = await api.terminalOpen(name, 80, 24);
          if (res && res.ok) status.textContent = T('term.connectedHint') || 'Terminal opened in a separate window.';
          else if (res && res.canceled) status.textContent = '';
          else status.textContent = T('term.openFailed') || 'Unable to open terminal.';
        } catch (e) {
          status.textContent = T('term.openFailed') || 'Unable to open terminal.';
        }
        btn.disabled = false;
        busy = false;
      });
      card.appendChild(btn);
      list.appendChild(card);
    });
  }

  const unsubscribe = api.onStateUpdate((state) => {
    latestState = state;
    render();
  });
  return () => unsubscribe();
}
