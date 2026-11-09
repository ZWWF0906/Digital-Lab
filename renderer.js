import { PANELS, getPanelById, getPanelName } from './panels/index.js';

    // 外壳自己的文案也走 i18n（词典与 t() 由 <head> 里的 i18n.js 提供）
    const T = (key, params) => (
      (typeof window !== 'undefined' && window.DigitalLabI18n)
        ? window.DigitalLabI18n.t(key, params)
        : key
    );

    const api = window.digitalLab;
    if (!api) {
      document.body.innerHTML = `<div style="display:flex;align-items:center;justify-content:center;height:100vh;color:#f43f5e;font-size:16px;font-family:system-ui,sans-serif;background:#0f1419">${T('boot.fail.preload')}</div>`;
      throw new Error('window.digitalLab not available');
    }
    let currentPanelId = null;
    let currentCleanup = null;
    // 1.5.0 面板保活：终端面板切换时不销毁容器（detach 到隐藏容器，切回 attach），
    // 其余面板维持原有的"切换即销毁重建"语义。
    const KEEP_ALIVE_PANELS = { terminal: true };
    const panelCache = new Map();   // id -> { id, container, hooks }
    let currentEntry = null;
    let panelHold = null;
    function getPanelHold() {
      if (!panelHold) {
        panelHold = document.createElement('div');
        panelHold.id = 'panel-hold';
        panelHold.style.display = 'none';
        document.body.appendChild(panelHold);
      }
      return panelHold;
    }
    function runHooksCleanup(entry) {
      if (!entry) return;
      const hooks = entry.hooks;
      try {
        if (typeof hooks === 'function') hooks();
        else if (hooks && typeof hooks.cleanup === 'function') hooks.cleanup();
      } catch (e) {}
    }

    // Build sidebar navigation（面板名走 i18n，语言切换时整块重建）
    const nav = document.getElementById('sidebar-nav');
    function buildNav() {
      nav.innerHTML = '';
      PANELS.forEach(panel => {
        const item = document.createElement('div');
        item.className = 'nav-item';
        item.dataset.panelId = panel.id;
        // 终端默认禁用，等首次状态更新确认有在线 NAS 后再启用
        if (panel.id === 'terminal') {
          item.classList.add('disabled');
          item.title = T('nav.hint.terminalNoNas');
        }
        item.innerHTML = `<span class="nav-icon">${panel.icon}</span>${getPanelName(panel.id)}`;
        item.addEventListener('click', () => {
          if (item.classList.contains('disabled')) {
            if (panel.id === 'terminal') {
              const toast = document.createElement('div');
              toast.className = 'nav-toast';
              toast.textContent = T('nav.hint.terminalNoNas');
              item.appendChild(toast);
              setTimeout(() => toast.remove(), 2000);
            }
            return;
          }
          switchPanel(panel.id);
        });
        nav.appendChild(item);
      });
    }
    buildNav();

    // Terminal nav item: disable when no online NAS
    api.onStateUpdate((state) => {
      const terminalItem = nav.querySelector('[data-panel-id="terminal"]');
      if (!terminalItem) return;
      const nas = state.nas || {};
      const hasOnline = Object.values(nas).some(d => d.online === true);
      if (hasOnline) {
        terminalItem.classList.remove('disabled');
        terminalItem.title = '';
      } else {
        terminalItem.classList.add('disabled');
        terminalItem.title = T('nav.hint.terminalNoNas');
      }
    });

    async function switchPanel(id) {
      if (id === currentPanelId) return;

      // 卸载上一个面板：保活面板只 detach 并移入隐藏容器；其余面板按原语义销毁
      if (currentEntry) {
        const entry = currentEntry;
        currentEntry = null;
        if (KEEP_ALIVE_PANELS[entry.id] && entry.hooks && typeof entry.hooks.detach === 'function') {
          try { entry.hooks.detach(); } catch (e) {}
          getPanelHold().appendChild(entry.container);
        } else {
          runHooksCleanup(entry);
          panelCache.delete(entry.id);
          if (entry.container && entry.container.parentNode) {
            entry.container.parentNode.removeChild(entry.container);
          }
        }
      }

      // Update nav highlight
      document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
      const navItem = document.querySelector(`[data-panel-id="${id}"]`);
      if (navItem) navItem.classList.add('active');

      // Render panel
      const main = document.getElementById('main-content');
      const panel = getPanelById(id);
      if (!panel) return;

      // 保活面板若已有容器：挂回主区并 attach，不重新 init（因此不会重连）
      const cached = panelCache.get(id);
      if (cached && KEEP_ALIVE_PANELS[id]) {
        main.appendChild(cached.container);
        currentEntry = cached;
        currentPanelId = id;
        if (cached.hooks && typeof cached.hooks.attach === 'function') {
          try { cached.hooks.attach(); } catch (e) {}
        }
        return;
      }

      // Clear and create container
      main.innerHTML = '';
      const container = document.createElement('div');
      container.className = 'panel active';
      container.id = `panel-${id}`;
      main.appendChild(container);

      try {
        const hooks = await panel.init(container, api);
        currentCleanup = hooks;
        currentEntry = { id: id, container: container, hooks: hooks };
        panelCache.set(id, currentEntry);
        currentPanelId = id;
      } catch (e) {
        console.error(`Failed to init panel ${id}:`, e);
        container.innerHTML = `<div style="text-align:center;padding:40px;color:var(--text-tertiary)">${T('boot.fail.panel')}</div>`;
      }
    }

    // Default: activate dashboard
    switchPanel('dashboard');

    // 跨面板导航（AI 设置按钮等）
    window.addEventListener('switch-panel', (e) => {
      switchPanel(e.detail);
    });

    // 首次启动引导：开屏结束（含"开屏动画已关闭"的分支）后判定一次。
    // 读取标志与显示覆盖层都在引导模块里，这里只负责触发，避免两处判定条件。
    function maybeOpenOnboarding() {
      try {
        if (window.DigitalLabOnboarding && typeof window.DigitalLabOnboarding.openIfNeeded === 'function') {
          window.DigitalLabOnboarding.openIfNeeded();
        }
      } catch (e) {}
    }
    window.addEventListener('splash-finished', maybeOpenOnboarding);
    // 开屏被关闭时事件发生在解析期（早于本监听注册），用标记补一次判定
    if (window.__splashFinished) maybeOpenOnboarding();

    // 语言切换：重建侧栏文案，并重刷当前面板（面板内容每次都是整块重建，重跑一次 init 即可）
    // 保活面板例外：它有 onLanguageChanged 钩子，自行刷新文案，容器与会话都不重建（不重连）
    window.addEventListener('language-changed', () => {
      buildNav();
      const id = currentPanelId;
      if (!id) return;
      const entry = currentEntry;
      if (KEEP_ALIVE_PANELS[id] && entry && entry.hooks && typeof entry.hooks.onLanguageChanged === 'function') {
        try { entry.hooks.onLanguageChanged(); } catch (e) {}
        return;
      }
      setTimeout(() => {
        if (currentEntry) {
          const stale = currentEntry;
          currentEntry = null;
          runHooksCleanup(stale);
          panelCache.delete(stale.id);
          if (stale.container && stale.container.parentNode) {
            stale.container.parentNode.removeChild(stale.container);
          }
        }
        currentPanelId = null;   // 绕开 switchPanel 的同名守卫，强制重新 init
        switchPanel(id);
      }, 0);
    });
