// 渲染进程安全输出工具（DL-SEC-02 / P0，S4）
// 目的：区分 HTML 文本上下文、属性上下文与 URL 上下文，避免"一个 escape 函数到处用"。
// 各面板统一从这里导入；dashboard.html 的内联脚本使用同名规则的本地实现。

const HTML_ESCAPES = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** HTML 文本上下文转义（可安全放进 innerHTML 的文本位置）。 */
export function escapeHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

/** HTML 属性上下文转义（双引号包裹的属性值）。 */
export function escapeAttr(value) {
  return escapeHtml(value);
}

/**
 * URL 上下文校验：只允许明确的协议与相对路径，拒绝 javascript:/data:/vbscript: 等。
 * 返回 '' 表示不安全（调用方应回退到纯文本或禁用链接）。
 */
export function safeUrl(value, allowedProtocols = ['https:', 'http:', 'mailto:']) {
  const raw = String(value == null ? '' : value).trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, 'https://local.invalid/');
    if (url.protocol === 'javascript:' || url.protocol === 'data:' || url.protocol === 'vbscript:') {
      return '';
    }
    if (!allowedProtocols.includes(url.protocol)) return '';
    return raw;
  } catch (e) {
    return '';
  }
}

/** 文本节点写入（最安全的默认渲染方式）。 */
export function setText(el, text) {
  if (!el) return;
  el.textContent = String(text == null ? '' : text);
}

/** 创建元素并安全设置属性/文本；attrs 中 textContent 会被当作文本写入。 */
export function createEl(tag, attrs = {}, children = []) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === 'textContent') {
      el.textContent = String(value == null ? '' : value);
    } else if (key === 'className' || key === 'class') {
      el.className = String(value == null ? '' : value);
    } else if (key === 'dataset' && value && typeof value === 'object') {
      for (const [dk, dv] of Object.entries(value)) el.dataset[dk] = String(dv == null ? '' : dv);
    } else if (value !== undefined && value !== null) {
      el.setAttribute(key, String(value));
    }
  }
  for (const child of children || []) {
    if (child == null) continue;
    el.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
  }
  return el;
}
