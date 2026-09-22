// panels/settings.js — 设置面板：NAS 设备管理、AI 配置、采集设置
// 语言切换会触发整面板重绘，用它记住重绘前停留的分页，重绘后回到同一分页
let pendingTabRestore = null;

// 文案走 i18n：i18n.js 由 dashboard.html 在 <head> 里以经典脚本加载，暴露 window.DigitalLabI18n。
// 通用词（确定/取消/删除/关闭/提示/保存失败/未知错误）统一用 common.*，
// 提示弹窗文案三处共用 common.tip.*；AI 提供方名称复用 ai.provider.*，不重复定义。
const T = (key, params) => (
  (typeof window !== 'undefined' && window.DigitalLabI18n)
    ? window.DigitalLabI18n.t(key, params)
    : key
);

// 后端错误转文案（双兼容）：
//   新后端：{error: {code, params}}（或直接 {code, params}）→ 查词典
//   旧后端：{error: "字符串"} 或 {ok:false, message: "字符串"} → 原样显示
// 任何分支都不返回空白，避免"错误提示消失"。
function backendErrorText(obj) {
  if (!obj) return '';
  const err = (obj.error !== undefined) ? obj.error : null;
  if (err && typeof err === 'object' && err.code) return T(err.code, err.params || {}) || String(err.code);
  if (typeof err === 'string' && err) return err;
  if (obj.code) return T(obj.code, obj.params || {}) || String(obj.code);   // 直接传 {code, params}
  if (typeof obj.message === 'string' && obj.message) return obj.message;   // 旧后端 {ok:false, message}
  return '';
}

export function init(container, api) {
  let config = {};
  let currentTab = pendingTabRestore || 'nas';
  pendingTabRestore = null;

  container.innerHTML = `
    <div class="settings-container">
      <div class="settings-tabs">
        <div class="settings-tab active" data-tab="nas">${T('set.tab.nas')}</div>
        <div class="settings-tab" data-tab="ai">${T('set.tab.ai')}</div>
        <div class="settings-tab" data-tab="collect">${T('set.tab.collect')}</div>
        <div class="settings-tab" data-tab="software">${T('set.tab.software')}</div>
        <div class="settings-tab" data-tab="about">${T('set.tab.about')}</div>
      </div>
      <div class="settings-panel active" id="sp-nas"></div>
      <div class="settings-panel" id="sp-ai"></div>
      <div class="settings-panel" id="sp-collect"></div>
      <div class="settings-panel" id="sp-software"></div>
      <div class="settings-panel" id="sp-about"></div>
    </div>
  `;

  const tabEls = container.querySelectorAll('.settings-tab');
  const panelEls = {
    nas: container.querySelector('#sp-nas'),
    ai: container.querySelector('#sp-ai'),
    collect: container.querySelector('#sp-collect'),
    software: container.querySelector('#sp-software'),
    about: container.querySelector('#sp-about'),
  };

  // ── Tab 切换 ──
  if (currentTab !== 'nas') {
    // 语言切换重绘后回到原来停留的分页
    tabEls.forEach(t => t.classList.toggle('active', t.dataset.tab === currentTab));
    Object.values(panelEls).forEach(p => p.classList.remove('active'));
    panelEls[currentTab]?.classList.add('active');
  }
  tabEls.forEach(tab => {
    tab.addEventListener('click', () => {
      currentTab = tab.dataset.tab;
      tabEls.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      Object.values(panelEls).forEach(p => p.classList.remove('active'));
      panelEls[currentTab]?.classList.add('active');
      renderTab(currentTab);
    });
  });

  // ── 渲染各标签页 ──
  function renderTab(tab) {
    switch (tab) {
      case 'nas': renderNasTab(); break;
      case 'ai': renderAiTab(); break;
      case 'collect': renderCollectTab(); break;
      case 'software': renderSoftwareTab(); break;
      case 'about': renderAboutTab(); break;
    }
  }

  // ── NAS 设备管理 ──

  /** 设备编辑模态对话框 */
  function showDeviceModal(deviceIndex) {
    // 移除已有模态框
    const existing = document.querySelector('.modal-overlay');
    if (existing) existing.remove();

    const isEdit = deviceIndex !== null && deviceIndex !== undefined;
    const device = isEdit && config.nas_devices ? (config.nas_devices[deviceIndex] || {}) : {};

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-content">
        <div class="modal-header">
          <span class="modal-title">${isEdit ? T('set.dev.editTitle') : T('set.dev.addTitle')}</span>
          <button class="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="settings-row">
            <label>${T('set.dev.name')}</label>
            <input type="text" class="modal-dev-name" value="${escapeAttr(device.name || '')}" placeholder="${T('set.dev.namePh')}" />
          </div>
          <div class="settings-row">
            <label>${T('set.dev.host')}</label>
            <input type="text" class="modal-dev-host" value="${escapeAttr(device.host || '')}" placeholder="${T('set.dev.hostPh')}" />
          </div>
          <div class="settings-row">
            <label>${T('set.dev.port')}</label>
            <input type="number" class="modal-dev-port" value="${device.port || 22}" />
          </div>
          <div class="settings-row">
            <label>${T('set.dev.username')}</label>
            <input type="text" class="modal-dev-user" value="${escapeAttr(device.username || '')}" placeholder="${T('set.dev.userPh')}" />
          </div>
          <div class="settings-row">
            <label>${T('set.dev.password')}</label>
            <input type="password" class="modal-dev-pass" value="${escapeAttr(device.password || '')}" placeholder="${T('set.dev.passPh')}" />
          </div>
          ${isEdit ? `
          <div class="settings-actions" style="margin-top:6px">
            <button class="test-conn-btn modal-test-btn">${T('set.dev.test')}</button>
            <span class="test-result" id="modal-test-result"></span>
          </div>` : ''}
        </div>
        <div class="modal-footer">
          <button class="btn-secondary modal-cancel-btn">${T('common.cancel')}</button>
          <button class="btn-primary modal-save-btn">${isEdit ? T('set.dev.saveEdit') : T('set.dev.addTitle')}</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    // 关闭函数
    const closeModal = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKeyDown);
    };
    const onKeyDown = (e) => { if (e.key === 'Escape') closeModal(); };

    // 点击遮罩关闭
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });

    // ESC 关闭
    document.addEventListener('keydown', onKeyDown);

    // 关闭按钮
    overlay.querySelector('.modal-close-btn').addEventListener('click', closeModal);
    overlay.querySelector('.modal-cancel-btn').addEventListener('click', closeModal);

    // 保存按钮
    overlay.querySelector('.modal-save-btn').addEventListener('click', async () => {
      const newDevice = {
        name: overlay.querySelector('.modal-dev-name')?.value?.trim() || '',
        host: overlay.querySelector('.modal-dev-host')?.value?.trim() || '',
        port: parseInt(overlay.querySelector('.modal-dev-port')?.value) || 22,
        username: overlay.querySelector('.modal-dev-user')?.value?.trim() || '',
        password: overlay.querySelector('.modal-dev-pass')?.value || '',
      };

      if (!config.nas_devices) config.nas_devices = [];

      if (isEdit) {
        config.nas_devices[deviceIndex] = newDevice;
      } else {
        config.nas_devices.push(newDevice);
      }

      closeModal();
      renderNasTab();
      await saveConfig();
    });

    // 测试连接按钮（仅编辑模式）
    if (isEdit) {
      overlay.querySelector('.modal-test-btn')?.addEventListener('click', async () => {
        const btn = overlay.querySelector('.modal-test-btn');
        const resultEl = overlay.querySelector('#modal-test-result');
        const device = {
          name: overlay.querySelector('.modal-dev-name')?.value?.trim() || '',
          host: overlay.querySelector('.modal-dev-host')?.value?.trim() || '',
          port: parseInt(overlay.querySelector('.modal-dev-port')?.value) || 22,
          username: overlay.querySelector('.modal-dev-user')?.value?.trim() || '',
          password: overlay.querySelector('.modal-dev-pass')?.value || '',
        };
        btn.classList.add('testing');
        btn.textContent = T('set.dev.testing');
        if (resultEl) resultEl.textContent = '';
        try {
          const res = await api.sendCommand({ cmd: 'test_nas_connection', device });
          if (resultEl) {
            resultEl.textContent = res.ok
              ? T('set.dev.testOk')
              : T('set.dev.testFail', { message: backendErrorText(res) || T('set.dev.connFailed') });
            resultEl.style.color = res.ok ? 'var(--accent)' : 'var(--accent-pink)';
          }
        } catch (e) {
          if (resultEl) {
            resultEl.textContent = T('set.dev.testFail', { message: e.message });
            resultEl.style.color = 'var(--accent-pink)';
          }
        }
        btn.classList.remove('testing');
        btn.textContent = T('set.dev.test');
      });
    }

    // 自动聚焦第一个输入框
    setTimeout(() => {
      overlay.querySelector('.modal-dev-name')?.focus();
    }, 150);
  }

  function renderNasTab() {
    const devices = config.nas_devices || [];
    const mockEnabled = config.nas_mock_enabled === true;
    const el = panelEls.nas;

    // 构建设备卡片 HTML
    let deviceCardsHtml = '';
    if (devices.length > 0) {
      deviceCardsHtml = devices.map((d, i) => {
        const hasName = d.name && d.name.trim();
        const hasHost = d.host && d.host.trim();
        const label = hasName ? d.name : (hasHost ? d.host : T('set.nas.unnamed'));
        const sub = hasHost ? `${d.host}${d.port && d.port !== 22 ? ':' + d.port : ''}` : (hasName ? T('set.nas.noHost') : '');

        return `
        <div class="nas-device-card" data-index="${i}">
          <div class="nas-device-summary">
            <span class="nas-device-dot"></span>
            <div class="nas-device-info">
              <div class="nas-device-name">${escapeHtml(label)}</div>
              ${sub ? `<div class="nas-device-sub">${escapeHtml(sub)}</div>` : ''}
            </div>
            <div class="nas-device-actions">
              <button class="nas-action-btn btn-edit-nas" data-index="${i}">${T('set.nas.edit')}</button>
              <button class="nas-action-btn nas-action-del btn-del-nas" data-index="${i}">${T('common.delete')}</button>
            </div>
          </div>
        </div>`;
      }).join('');
    }

    el.innerHTML = `
      <div class="settings-group">
        <div class="settings-group-title">${T('set.nas.list')}</div>
        <div id="nas-device-list">
          ${devices.length === 0 ? `<div class="nas-empty-hint">${T('set.nas.empty')}</div>` : deviceCardsHtml}
        </div>
        <div class="settings-actions" style="margin-top:12px">
          <button class="btn-primary" id="btn-add-device">${T('set.nas.addBtn')}</button>
          <button class="btn-secondary" id="btn-save-nas">${T('set.nas.saveAll')}</button>
        </div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">${T('set.nas.mockTitle')}</div>
        <div class="settings-row" style="justify-content:space-between">
          <div>
            <div style="font-size:0.85rem;color:var(--text-primary);margin-bottom:2px">Mock-NAS</div>
            <div style="font-size:0.7rem;color:var(--text-tertiary)">${T('set.nas.mockDesc')}</div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="mock-nas-toggle" ${mockEnabled ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
        </div>
      </div>
    `;

    // ── 事件绑定 ──
    el.querySelector('#btn-add-device')?.addEventListener('click', () => {
      showDeviceModal(null);
    });

    el.querySelector('#btn-save-nas')?.addEventListener('click', async () => {
      await saveConfig();
    });

    // 编辑按钮 → 弹出模态框
    el.querySelectorAll('.btn-edit-nas').forEach(btn => {
      btn.addEventListener('click', () => {
        const idx = parseInt(btn.dataset.index);
        showDeviceModal(idx);
      });
    });

    // 删除按钮
    el.querySelectorAll('.btn-del-nas').forEach(btn => {
      btn.addEventListener('click', async () => {
        const idx = parseInt(btn.dataset.index);
        config.nas_devices.splice(idx, 1);
        renderNasTab();
        await saveConfig();
      });
    });

    // Mock-NAS 开关
    el.querySelector('#mock-nas-toggle')?.addEventListener('change', async (e) => {
      config.nas_mock_enabled = e.target.checked;
      await saveConfig();
    });
  }

  // ── AI 配置 ──
  function renderAiTab() {
    const ai = config.ai || {};
    const ollama = ai.ollama || {};
    const openai = ai.openai || {};
    const memory = ai.memory || {};
    const el = panelEls.ai;
    el.innerHTML = `
      <div class="settings-group">
        <div class="settings-group-title">${T('set.ai.providerTitle')}</div>
        <div class="settings-row">
          <label>${T('set.ai.defaultModel')}</label>
          <select id="ai-provider-sel">
            <option value="ollama" ${ai.provider === 'ollama' ? 'selected' : ''}>${T('ai.provider.ollama')}</option>
            <option value="openai" ${ai.provider === 'openai' ? 'selected' : ''}>${T('ai.provider.cloud')}</option>
          </select>
        </div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">${T('ai.provider.ollama')}</div>
        <div class="settings-row"><label>${T('set.ai.addr')}</label><input type="text" id="ai-ollama-url" value="${escapeAttr(ollama.base_url || '')}" placeholder="http://localhost:11434" /></div>
        <div class="settings-row"><label>${T('set.ai.model')}</label><input type="text" id="ai-ollama-model" value="${escapeAttr(ollama.model || '')}" placeholder="llama3" /></div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">${T('ai.provider.cloud')}</div>
        <div class="settings-row"><label>API Key</label><input type="password" id="ai-openai-key" value="${escapeAttr(openai.api_key || '')}" placeholder="sk-..." /></div>
        <div class="settings-row"><label>${T('set.ai.addr')}</label><input type="text" id="ai-openai-url" value="${escapeAttr(openai.base_url || '')}" placeholder="https://api.example.com/v1" /></div>
        <div class="settings-row"><label>${T('set.ai.model')}</label><input type="text" id="ai-openai-model" value="${escapeAttr(openai.model || '')}" placeholder="gpt-4o / deepseek-chat / ..." /></div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">${T('set.ai.memoryTitle')}</div>
        <div class="settings-row" style="justify-content:space-between">
          <div>
            <div style="font-size:0.85rem;color:var(--text-primary);margin-bottom:2px">${T('set.ai.memoryEnable')}</div>
            <div style="font-size:0.7rem;color:var(--text-tertiary)">${T('set.ai.memoryEnableHint')}</div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="ai-memory-toggle" ${memory.enabled === true ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="settings-row">
          <label>${T('set.ai.memoryDir')}</label>
          <input type="text" id="ai-memory-dir" value="${escapeAttr(memory.dir || '')}" placeholder="${T('set.ai.memoryDirPh')}" readonly />
          <button class="btn-secondary" id="btn-ai-memory-dir">${T('set.ai.chooseDir')}</button>
        </div>
        <div class="settings-actions" style="margin-top:8px">
          <button class="btn-secondary" id="btn-ai-memory-list">${T('set.ai.viewMemory')}</button>
          <button class="btn-secondary" id="btn-ai-memory-clear">${T('set.ai.clearMemory')}</button>
        </div>
        <div id="ai-memory-list" style="margin-top:10px"></div>
      </div>
      <div class="settings-actions">
        <button class="btn-primary" id="btn-save-ai">${T('set.ai.save')}</button>
      </div>
    `;

    el.querySelector('#btn-save-ai')?.addEventListener('click', async () => {
      // 配置尚未加载完成时先补载，避免用空输入覆盖后端已有配置
      if (!config || !config.ai) { await loadConfig(); }
      if (!config.ai) config.ai = {};
      const pickAi = (sel) => (el.querySelector(sel)?.value || '').trim();
      const prevOllama = config.ai.ollama || {};
      const prevOpenai = config.ai.openai || {};
      config.ai.provider = el.querySelector('#ai-provider-sel')?.value || 'ollama';
      // 输入框为空时保留原值，不覆盖
      config.ai.ollama = {
        base_url: pickAi('#ai-ollama-url') || prevOllama.base_url || '',
        model: pickAi('#ai-ollama-model') || prevOllama.model || '',
      };
      config.ai.openai = {
        api_key: pickAi('#ai-openai-key') || prevOpenai.api_key || '',
        base_url: pickAi('#ai-openai-url') || prevOpenai.base_url || '',
        model: pickAi('#ai-openai-model') || prevOpenai.model || '',
      };
      // AI 记忆：开关与目录随 AI 配置一起写回（目录变化时后端会自动迁移旧文件）
      if (!config.ai.memory) config.ai.memory = {};
      config.ai.memory.enabled = !!(el.querySelector('#ai-memory-toggle')?.checked);
      config.ai.memory.dir = (el.querySelector('#ai-memory-dir')?.value || '').trim();
      await saveConfig();
      window.dispatchEvent(new CustomEvent('ai-config-updated', { detail: { provider: config.ai.provider } }));
    });

    // 记忆：目录选择 / 查看列表 / 清空
    el.querySelector('#btn-ai-memory-dir')?.addEventListener('click', showMemoryDirModal);
    el.querySelector('#btn-ai-memory-list')?.addEventListener('click', refreshMemoryList);
    el.querySelector('#btn-ai-memory-clear')?.addEventListener('click', async () => {
      const confirmed = await confirmMemoryDelete();
      if (!confirmed) return;   // 取消或关闭对话框：什么都不做
      try {
        const res = await api.sendCommand({ cmd: 'clear_ai_memory' });
        const ok = !!(res && res.ok);
        showToast(ok ? T('set.mem.cleared') : T('set.mem.clearFailed'), !ok);
      } catch (e) {
        showToast(T('set.mem.clearFailedDetail', { message: e.message }), true);
      }
      refreshMemoryList();
    });
  }

  // ── AI 记忆：目录选择对话框（无原生目录选择 API，改为手动输入绝对路径） ──
  function showMemoryDirModal() {
    const existing = document.querySelector('.modal-overlay');
    if (existing) existing.remove();

    const current = (config.ai && config.ai.memory && config.ai.memory.dir) || '';
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-content" style="max-width:460px">
        <div class="modal-header">
          <span class="modal-title">${T('set.memDir.title')}</span>
          <button class="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="settings-row">
            <label>${T('set.memDir.label')}</label>
            <input type="text" class="modal-mem-dir" value="${escapeAttr(current)}" placeholder="${T('set.memDir.ph')}" />
          </div>
          <div style="color:var(--text-tertiary);font-size:0.72rem;line-height:1.6;margin-top:8px">
            ${T('set.memDir.hint1')}<br/>
            ${T('set.memDir.hint2')}
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary modal-cancel-btn">${T('common.cancel')}</button>
          <button class="btn-primary modal-save-btn">${T('common.ok')}</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const closeModal = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKeyDown);
    };
    const onKeyDown = (e) => { if (e.key === 'Escape') closeModal(); };
    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeModal(); });
    document.addEventListener('keydown', onKeyDown);
    overlay.querySelector('.modal-close-btn').addEventListener('click', closeModal);
    overlay.querySelector('.modal-cancel-btn').addEventListener('click', closeModal);
    overlay.querySelector('.modal-save-btn').addEventListener('click', () => {
      const value = overlay.querySelector('.modal-mem-dir')?.value?.trim() || '';
      const input = panelEls.ai.querySelector('#ai-memory-dir');
      if (input) input.value = value;
      closeModal();
      showToast(T('set.memDir.updated'));
    });
  }

  // ── AI 记忆：原生警告对话框确认（不可逆操作，最大化注意力） ──
  async function confirmMemoryDelete() {
    try {
      if (!api || typeof api.confirmMemoryDelete !== 'function') {
        console.warn(T('log.aiMemory.noConfirmApi'));
        return false;
      }
      const r = await api.confirmMemoryDelete();
      return !!(r && r.confirmed);
    } catch (e) {
      console.warn(T('log.aiMemory.confirmFailed', { error: e.message }));
      return false;
    }
  }

  // ── AI 记忆：列表渲染与单条删除 ──
  async function refreshMemoryList() {
    // 配置未加载完成时先补载：加载完成会触发面板重渲染，必须在重渲染之后再取容器
    if (!config || !config.ai) {
      try { await loadConfig(); } catch (e) { /* 忽略，继续按当前 DOM 渲染 */ }
    }
    let box = panelEls.ai.querySelector('#ai-memory-list');
    if (!box) return;
    box.innerHTML = `<div style="color:var(--text-tertiary);font-size:0.75rem;padding:6px 0">${T('set.mem.loading')}</div>`;
    let data = null;
    try {
      data = await api.sendCommand({ cmd: 'get_ai_memory' });
    } catch (e) {
      data = null;
    }
    // 取数据期间面板可能再次重渲染，重新取一次容器再写入，避免写进已脱离 DOM 的节点
    box = panelEls.ai.querySelector('#ai-memory-list');
    if (!box) return;
    if (!data || data.error) {
      box.innerHTML = `<div style="color:var(--text-tertiary);font-size:0.75rem;padding:6px 0">${T('set.mem.readFailed')}</div>`;
      return;
    }
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) {
      box.innerHTML = `<div style="color:var(--text-tertiary);font-size:0.75rem;padding:6px 0">${T('set.mem.empty')}</div>`;
      return;
    }
    box.innerHTML = items.map(it => `
      <div class="nas-device-card" style="margin-bottom:6px">
        <div class="nas-device-summary">
          <div class="nas-device-info">
            <div class="nas-device-name" style="font-weight:400">${escapeHtml(it.content || '')}</div>
            <div class="nas-device-sub">${escapeHtml(it.ts || '')}</div>
          </div>
          <div class="nas-device-actions">
            <button class="nas-action-btn nas-action-del btn-del-memory" data-index="${it.index}">${T('common.delete')}</button>
          </div>
        </div>
      </div>
    `).join('');
    box.querySelectorAll('.btn-del-memory').forEach(btn => {
      btn.addEventListener('click', async () => {
        const idx = parseInt(btn.dataset.index, 10);
        const confirmed = await confirmMemoryDelete();
        if (!confirmed) return;   // 取消或关闭对话框：不删除
        try {
          const res = await api.sendCommand({ cmd: 'delete_ai_memory', index: idx });
          const ok = !!(res && res.ok);
          showToast(ok ? T('set.mem.deleted') : T('set.mem.deleteFailed'), !ok);
        } catch (e) {
          showToast(T('set.mem.deleteFailedDetail', { message: e.message }), true);
        }
        refreshMemoryList();
      });
    });
  }

  // ── 采集设置 ──
  function renderCollectTab() {
    const el = panelEls.collect;
    const localInterval = config.monitor_interval || 1;
    const nasInterval = config.nas_interval || 15;
    el.innerHTML = `
      <div class="settings-group">
        <div class="settings-group-title">${T('set.collect.params')}</div>
        <div class="settings-row"><label>${T('set.collect.localInterval')}</label><input type="number" id="cfg-local-interval" value="${localInterval}" min="1" max="60" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">${T('set.collect.seconds')}</span></div>
        <div class="settings-row"><label>${T('set.collect.nasInterval')}</label><input type="number" id="cfg-nas-interval" value="${nasInterval}" min="5" max="300" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">${T('set.collect.seconds')}</span></div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">${T('set.collect.thresholds')}</div>
        <div class="settings-row"><label>${T('set.collect.cpuAlarm')}</label><input type="number" id="cfg-cpu-threshold" value="${config.monitor_threshold_cpu || 80}" min="10" max="100" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">%</span></div>
        <div class="settings-row"><label>${T('set.collect.memAlarm')}</label><input type="number" id="cfg-mem-threshold" value="${config.monitor_threshold_memory || 85}" min="10" max="100" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">%</span></div>
        <div class="settings-row"><label>${T('set.collect.diskAlarm')}</label><input type="number" id="cfg-disk-threshold" value="${config.monitor_threshold_disk || 90}" min="10" max="100" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">%</span></div>
      </div>
      <div class="settings-actions">
        <button class="btn-primary" id="btn-save-collect">${T('set.collect.save')}</button>
      </div>
    `;

    el.querySelector('#btn-save-collect')?.addEventListener('click', async () => {
      config.monitor_interval = parseInt(el.querySelector('#cfg-local-interval')?.value) || 1;
      config.nas_interval = parseInt(el.querySelector('#cfg-nas-interval')?.value) || 15;
      config.monitor_threshold_cpu = parseInt(el.querySelector('#cfg-cpu-threshold')?.value) || 80;
      config.monitor_threshold_memory = parseInt(el.querySelector('#cfg-mem-threshold')?.value) || 85;
      config.monitor_threshold_disk = parseInt(el.querySelector('#cfg-disk-threshold')?.value) || 90;
      await saveConfig();
    });
  }

  // ── 软件设置 ──
  async function renderSoftwareTab() {
    const el = panelEls.software;
    try {
      const result = await api.getHardwareAccel();
      const hwEnabled = result && result.enabled !== false;
      const curTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      let splashOn = true;
      try {
        const sr = await api.getSplashAnimation();
        splashOn = !sr || sr.enabled !== false;
      } catch (e) { /* 读不到就按开启显示 */ }
      const i18nApi = (typeof window !== 'undefined' && window.DigitalLabI18n) ? window.DigitalLabI18n : null;
      const localeList = (typeof window !== 'undefined' && window.DigitalLabLocales && Array.isArray(window.DigitalLabLocales.LANGUAGES))
        ? window.DigitalLabLocales.LANGUAGES
        : [{ code: 'zh-CN', name: '简体中文', nativeName: '简体中文' }];
      const curLang = (i18nApi && i18nApi.getLanguage()) || 'zh-CN';
      el.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">${T('set.soft.display')}</div>
          <div class="settings-row">
            <label>${T('set.soft.hwAccel')}</label>
            <div class="toggle-switch-wrapper">
              <label class="toggle-switch">
                <input type="checkbox" id="cfg-hw-accel"${hwEnabled ? ' checked' : ''} />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">${T('set.soft.hwAccelHint')}</div>
          <div class="settings-row" style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <label>${T('set.soft.theme')}</label>
            <select id="cfg-theme-select">
              <option value="dark"${curTheme === 'dark' ? ' selected' : ''}>${T('set.soft.themeDark')}</option>
              <option value="light"${curTheme === 'light' ? ' selected' : ''}>${T('set.soft.themeLight')}</option>
            </select>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">${T('set.soft.themeHint')}</div>
          <div class="settings-row" style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <label>${T('set.soft.splash')}</label>
            <div class="toggle-switch-wrapper">
              <label class="toggle-switch">
                <input type="checkbox" id="cfg-splash-animation"${splashOn ? ' checked' : ''} />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">${T('set.soft.splashHint')}</div>
          <div class="settings-row" style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <label>${T('set.language')}</label>
            <select id="cfg-language-select">
              ${localeList.map((l) => `<option value="${l.code}"${l.code === curLang ? ' selected' : ''}>${l.nativeName || l.name || l.code}</option>`).join('')}
            </select>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">${T('set.languageHint')}</div>
          <div class="settings-row" style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <label>${T('set.soft.onboarding')}</label>
            <button class="btn-secondary" id="btn-rerun-onboarding">${T('set.soft.rerunOnboarding')}</button>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">${T('set.soft.onboardingHint')}</div>
        </div>
      `;

      const themeSel = el.querySelector('#cfg-theme-select');
      if (themeSel) {
        themeSel.addEventListener('change', () => {
          applyTheme(themeSel.value);
        });
      }

      const splashToggle = el.querySelector('#cfg-splash-animation');
      if (splashToggle) {
        splashToggle.addEventListener('change', async () => {
          const newVal = splashToggle.checked;
          try {
            const r = await api.setSplashAnimation(newVal);
            if (r && r.ok) {
              showToast(newVal ? T('set.soft.splashOn') : T('set.soft.splashOff'));
            } else {
              showToast(T('common.saveFailed', { message: (r && r.error) || T('common.unknownError') }), true);
              splashToggle.checked = !newVal;
            }
          } catch (e) {
            showToast(T('common.saveFailed', { message: e.message }), true);
            splashToggle.checked = !newVal;
          }
        });
      }

      // 重新运行引导：把 onboarding_done 置回 false，并立即打开引导覆盖层
      const rerunBtn = el.querySelector('#btn-rerun-onboarding');
      if (rerunBtn) {
        rerunBtn.addEventListener('click', async () => {
          try {
            if (api && typeof api.setOnboardingDone === 'function') await api.setOnboardingDone(false);
          } catch (e) {}
          try {
            if (window.DigitalLabOnboarding && typeof window.DigitalLabOnboarding.open === 'function') {
              window.DigitalLabOnboarding.open();
            }
          } catch (e) {}
        });
      }

      const langSel = el.querySelector('#cfg-language-select');
      if (langSel) {
        langSel.addEventListener('change', async () => {
          const next = langSel.value;
          if (!i18nApi || typeof i18nApi.setLanguage !== 'function') return;
          const ok = i18nApi.setLanguage(next);
          if (!ok) {
            showToast(T('common.saveFailed', { message: T('set.lang.unsupported', { lang: next }) }), true);
            langSel.value = curLang;
            return;
          }
          try { localStorage.setItem('digitallab-lang', next); } catch (e) {}
          document.documentElement.setAttribute('lang', next);
          pendingTabRestore = currentTab; // 让外层重绘后回到当前分页
          try { if (api && typeof api.setLanguage === 'function') await api.setLanguage(next); } catch (e) {}
          window.dispatchEvent(new CustomEvent('language-changed', { detail: next }));
        });
      }

      const toggle = el.querySelector('#cfg-hw-accel');
      if (toggle) {
        toggle.addEventListener('change', async () => {
          const newVal = toggle.checked;
          try {
            const r = await api.setHardwareAccel(newVal);
            if (r && r.ok) {
              showToast(newVal ? T('set.soft.hwOn') : T('set.soft.hwOff'));
            } else {
              showToast(T('common.saveFailed', { message: (r && r.error) || T('common.unknownError') }), true);
              toggle.checked = !newVal;
            }
          } catch (e) {
            showToast(T('common.saveFailed', { message: e.message }), true);
            toggle.checked = !newVal;
          }
        });
      }
    } catch (e) {
      el.innerHTML = `<div class="settings-group"><div class="settings-group-title">${T('set.soft.display')}</div><div class="settings-row"><label>${T('set.soft.hwAccel')}</label><span style="color:var(--text-tertiary);font-size:0.85rem">${T('set.soft.loadFailed')}</span></div></div>`;
    }
  }

  // ── 关于 ──
  function renderAboutTab() {
    const el = panelEls.about;
    el.innerHTML = `
      <div class="settings-group" style="text-align:center;padding:32px">
        <div style="font-size:1.4rem;font-weight:300;margin-bottom:8px">DigitalLab 1.4.0</div>
        <div style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:20px">${T('set.about.slogan')}</div>
        <div style="color:var(--text-tertiary);font-size:0.75rem;line-height:1.8">
          <div>${T('set.about.features')}</div>
          <div style="margin-top:12px">${T('set.about.author')}</div>
          <div>© 2026 ZWWF0906</div>
          <div style="margin-top:12px">${T('set.about.license')}</div>
        </div>
        <div style="margin-top:24px">
          <button class="btn-primary" id="btn-feedback">${T('set.about.feedback')}</button>
        </div>
      </div>
    `;
    el.querySelector('#btn-feedback').addEventListener('click', showFeedbackModal);
  }

  // ── 问题反馈对话框 ──
  function showFeedbackModal() {
    // 移除已有模态框（复用设备模态框类，保持深色主题一致）
    const existing = document.querySelector('.modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal-content" style="max-width:420px">
        <div class="modal-header">
          <span class="modal-title">${T('set.fb.title')}</span>
          <button class="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div style="color:var(--text-secondary);font-size:0.9rem;margin-bottom:16px;text-align:center">${T('set.fb.choose')}</div>
          <div style="color:var(--text-tertiary);font-size:0.75rem;margin-bottom:16px;text-align:center;line-height:1.6">${T('set.fb.note1')}<br/>${T('set.fb.note2')}</div>
          <button class="btn-primary" id="feedback-mail" style="width:100%;margin-bottom:10px">${T('set.fb.mail')}</button>
          <button class="btn-secondary" id="feedback-github" style="width:100%">${T('set.fb.github')}</button>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary modal-cancel-btn" style="width:100%">${T('set.fb.close')}</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);

    const closeModal = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKeyDown);
    };
    const onKeyDown = (e) => { if (e.key === 'Escape') closeModal(); };

    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', onKeyDown);

    overlay.querySelector('.modal-close-btn').addEventListener('click', closeModal);
    overlay.querySelector('.modal-cancel-btn').addEventListener('click', closeModal);

    // 邮件反馈：调起默认邮件客户端
    overlay.querySelector('#feedback-mail').addEventListener('click', () => {
      const subject = encodeURIComponent(T('set.fb.mailSubject'));
      window.location.href = 'mailto:ZWWF0906@outlook.com?subject=' + subject;
    });

    // GitHub 反馈：打开 Issues 创建页
    overlay.querySelector('#feedback-github').addEventListener('click', () => {
      window.open('https://github.com/ZWWF0906/Digital-Lab/issues/new', '_blank');
    });
  }

  // ── 保存配置 ──
  async function saveConfig() {
    try {
      const result = await api.saveConfig(config);
      if (result.ok) {
        showToast(T('set.saved'));
        // 通知 Python 重载配置（含 NAS 监控重启）
        try {
          const reloadResult = await api.sendCommand({ cmd: 'reload_config' });
          if (reloadResult && reloadResult.warnings && reloadResult.warnings.length > 0) {
            showToast(T('set.savedPartial'), true);
            console.warn('reload_config warnings:', reloadResult.warnings);
          }
        } catch (reloadErr) {
          // 重载失败不阻塞保存成功提示，但给出警告
          console.warn('reload_config failed:', reloadErr);
        }
      } else {
        showToast(T('common.saveFailed', { message: backendErrorText(result) || T('common.unknownError') }), true);
      }
    } catch (e) {
      showToast(T('common.saveFailed', { message: e.message }), true);
    }
  }

  function showToast(msg, isError = false) {
    const existing = container.querySelector('.toast');
    if (existing) existing.remove();
    const toast = document.createElement('div');
    toast.className = 'toast' + (isError ? ' toast-error' : '');
    toast.textContent = msg;
    toast.style.cssText = `
      position:fixed;bottom:24px;right:24px;padding:10px 20px;border-radius:10px;
      background:${isError?'rgba(244,63,94,0.15)':'rgba(0,229,160,0.1)'};
      border:1px solid ${isError?'var(--accent-pink)':'var(--accent)'};
      color:${isError?'var(--accent-pink)':'var(--accent)'};
      font-size:0.85rem;z-index:999;animation:fadeInUp 0.3s var(--ease-smooth);
    `;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
  }

  // ── 主题切换（深色/浅色，localStorage 持久化） ──
  function applyTheme(theme) {
    if (theme !== 'light' && theme !== 'dark') theme = 'dark';
    const root = document.documentElement;
    root.classList.add('theme-switching');
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem('digitallab-theme', theme); } catch (e) {}
    // 同步写进应用级配置：下次启动 main.js 读它决定窗口底色，避免浅色主题下闪黑
    try { if (api && typeof api.setTheme === 'function') api.setTheme(theme); } catch (e) {}
    setTimeout(() => root.classList.remove('theme-switching'), 350);
    showToast(theme === 'light' ? T('set.soft.themeLightDone') : T('set.soft.themeDarkDone'));
  }

  // ── 加载配置 ──
  async function loadConfig() {
    try {
      const data = await api.getConfig();
      if (data && !data.error) {
        config = data;
      }
    } catch (e) {
      console.error(T('log.config.loadFailed', { error: e.message }));
    }
    renderTab(currentTab);
  }

  loadConfig();

  return () => {
    // cleanup
  };
}

function escapeHtml(str) {
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function escapeAttr(str) {
  return String(str).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}