// panels/settings.js — 设置面板：NAS 设备管理、AI 配置、采集设置
export function init(container, api) {
  let config = {};
  let currentTab = 'nas';

  container.innerHTML = `
    <div class="settings-container">
      <div class="settings-tabs">
        <div class="settings-tab active" data-tab="nas">NAS 设备</div>
        <div class="settings-tab" data-tab="ai">AI 配置</div>
        <div class="settings-tab" data-tab="collect">采集设置</div>
        <div class="settings-tab" data-tab="software">软件</div>
        <div class="settings-tab" data-tab="about">关于</div>
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
          <span class="modal-title">${isEdit ? '编辑设备' : '添加设备'}</span>
          <button class="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="settings-row">
            <label>名称</label>
            <input type="text" class="modal-dev-name" value="${escapeAttr(device.name || '')}" placeholder="设备名称" />
          </div>
          <div class="settings-row">
            <label>主机</label>
            <input type="text" class="modal-dev-host" value="${escapeAttr(device.host || '')}" placeholder="IP 地址" />
          </div>
          <div class="settings-row">
            <label>端口</label>
            <input type="number" class="modal-dev-port" value="${device.port || 22}" />
          </div>
          <div class="settings-row">
            <label>用户名</label>
            <input type="text" class="modal-dev-user" value="${escapeAttr(device.username || '')}" placeholder="SSH 用户名" />
          </div>
          <div class="settings-row">
            <label>密码</label>
            <input type="password" class="modal-dev-pass" value="${escapeAttr(device.password || '')}" placeholder="SSH 密码" />
          </div>
          ${isEdit ? `
          <div class="settings-actions" style="margin-top:6px">
            <button class="test-conn-btn modal-test-btn">测试连接</button>
            <span class="test-result" id="modal-test-result"></span>
          </div>` : ''}
        </div>
        <div class="modal-footer">
          <button class="btn-secondary modal-cancel-btn">取消</button>
          <button class="btn-primary modal-save-btn">${isEdit ? '保存修改' : '添加设备'}</button>
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
        btn.textContent = '测试中...';
        if (resultEl) resultEl.textContent = '';
        try {
          const res = await api.sendCommand({ cmd: 'test_nas_connection', device });
          if (resultEl) {
            resultEl.textContent = res.ok ? '✓ 连接成功' : '✗ ' + (res.message || '连接失败');
            resultEl.style.color = res.ok ? 'var(--accent)' : 'var(--accent-pink)';
          }
        } catch (e) {
          if (resultEl) {
            resultEl.textContent = '✗ ' + e.message;
            resultEl.style.color = 'var(--accent-pink)';
          }
        }
        btn.classList.remove('testing');
        btn.textContent = '测试连接';
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
        const label = hasName ? d.name : (hasHost ? d.host : '未命名设备');
        const sub = hasHost ? `${d.host}${d.port && d.port !== 22 ? ':' + d.port : ''}` : (hasName ? '未配置主机' : '');

        return `
        <div class="nas-device-card" data-index="${i}">
          <div class="nas-device-summary">
            <span class="nas-device-dot"></span>
            <div class="nas-device-info">
              <div class="nas-device-name">${escapeHtml(label)}</div>
              ${sub ? `<div class="nas-device-sub">${escapeHtml(sub)}</div>` : ''}
            </div>
            <div class="nas-device-actions">
              <button class="nas-action-btn btn-edit-nas" data-index="${i}">编辑</button>
              <button class="nas-action-btn nas-action-del btn-del-nas" data-index="${i}">删除</button>
            </div>
          </div>
        </div>`;
      }).join('');
    }

    el.innerHTML = `
      <div class="settings-group">
        <div class="settings-group-title">NAS 设备列表</div>
        <div id="nas-device-list">
          ${devices.length === 0 ? '<div class="nas-empty-hint">暂无设备，点击下方按钮添加</div>' : deviceCardsHtml}
        </div>
        <div class="settings-actions" style="margin-top:12px">
          <button class="btn-primary" id="btn-add-device">+ 添加设备</button>
          <button class="btn-secondary" id="btn-save-nas">保存全部</button>
        </div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">示例 NAS</div>
        <div class="settings-row" style="justify-content:space-between">
          <div>
            <div style="font-size:0.85rem;color:var(--text-primary);margin-bottom:2px">Mock-NAS</div>
            <div style="font-size:0.7rem;color:var(--text-tertiary)">用于开发测试，模拟真实 NAS 数据</div>
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
        <div class="settings-group-title">AI 提供方</div>
        <div class="settings-row">
          <label>默认模型</label>
          <select id="ai-provider-sel">
            <option value="ollama" ${ai.provider === 'ollama' ? 'selected' : ''}>Ollama 本地</option>
            <option value="openai" ${ai.provider === 'openai' ? 'selected' : ''}>云端 API</option>
          </select>
        </div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">Ollama 本地</div>
        <div class="settings-row"><label>地址</label><input type="text" id="ai-ollama-url" value="${escapeAttr(ollama.base_url || '')}" placeholder="http://localhost:11434" /></div>
        <div class="settings-row"><label>模型</label><input type="text" id="ai-ollama-model" value="${escapeAttr(ollama.model || '')}" placeholder="llama3" /></div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">云端 API</div>
        <div class="settings-row"><label>API Key</label><input type="password" id="ai-openai-key" value="${escapeAttr(openai.api_key || '')}" placeholder="sk-..." /></div>
        <div class="settings-row"><label>地址</label><input type="text" id="ai-openai-url" value="${escapeAttr(openai.base_url || '')}" placeholder="https://api.example.com/v1" /></div>
        <div class="settings-row"><label>模型</label><input type="text" id="ai-openai-model" value="${escapeAttr(openai.model || '')}" placeholder="gpt-4o / deepseek-chat / ..." /></div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">AI 记忆</div>
        <div class="settings-row" style="justify-content:space-between">
          <div>
            <div style="font-size:0.85rem;color:var(--text-primary);margin-bottom:2px">启用 AI 记忆</div>
            <div style="font-size:0.7rem;color:var(--text-tertiary)">开启后，AI 会记住你确认过的长期偏好</div>
          </div>
          <label class="toggle-switch">
            <input type="checkbox" id="ai-memory-toggle" ${memory.enabled === true ? 'checked' : ''}>
            <span class="toggle-slider"></span>
          </label>
        </div>
        <div class="settings-row">
          <label>存储目录</label>
          <input type="text" id="ai-memory-dir" value="${escapeAttr(memory.dir || '')}" placeholder="默认 %APPDATA%\\DigitalLab\\memory" readonly />
          <button class="btn-secondary" id="btn-ai-memory-dir">选择目录</button>
        </div>
        <div class="settings-actions" style="margin-top:8px">
          <button class="btn-secondary" id="btn-ai-memory-list">查看记忆</button>
          <button class="btn-secondary" id="btn-ai-memory-clear">清空记忆</button>
        </div>
        <div id="ai-memory-list" style="margin-top:10px"></div>
      </div>
      <div class="settings-actions">
        <button class="btn-primary" id="btn-save-ai">保存 AI 配置</button>
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
        showToast(ok ? '记忆已清空' : '清空失败', !ok);
      } catch (e) {
        showToast('清空失败: ' + e.message, true);
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
          <span class="modal-title">选择记忆存储目录</span>
          <button class="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="settings-row">
            <label>目录</label>
            <input type="text" class="modal-mem-dir" value="${escapeAttr(current)}" placeholder="留空使用默认目录" />
          </div>
          <div style="color:var(--text-tertiary);font-size:0.72rem;line-height:1.6;margin-top:8px">
            填写绝对路径；留空表示使用默认目录 %APPDATA%\\DigitalLab\\memory。<br/>
            更改目录并保存后，旧记忆文件会复制到新目录，旧文件保留。
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary modal-cancel-btn">取消</button>
          <button class="btn-primary modal-save-btn">确定</button>
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
      showToast('目录已更新，保存后生效');
    });
  }

  // ── AI 记忆：原生警告对话框确认（不可逆操作，最大化注意力） ──
  async function confirmMemoryDelete() {
    try {
      if (!api || typeof api.confirmMemoryDelete !== 'function') {
        console.warn('[AI记忆] 当前 preload 未提供 confirmMemoryDelete，取消删除');
        return false;
      }
      const r = await api.confirmMemoryDelete();
      return !!(r && r.confirmed);
    } catch (e) {
      console.warn('[AI记忆] 删除确认调用失败，取消删除:', e);
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
    box.innerHTML = '<div style="color:var(--text-tertiary);font-size:0.75rem;padding:6px 0">读取中...</div>';
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
      box.innerHTML = '<div style="color:var(--text-tertiary);font-size:0.75rem;padding:6px 0">记忆读取失败</div>';
      return;
    }
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) {
      box.innerHTML = '<div style="color:var(--text-tertiary);font-size:0.75rem;padding:6px 0">暂无记忆</div>';
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
            <button class="nas-action-btn nas-action-del btn-del-memory" data-index="${it.index}">删除</button>
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
          showToast(ok ? '已删除该条记忆' : '删除失败', !ok);
        } catch (e) {
          showToast('删除失败: ' + e.message, true);
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
        <div class="settings-group-title">采集参数</div>
        <div class="settings-row"><label>本地采集间隔</label><input type="number" id="cfg-local-interval" value="${localInterval}" min="1" max="60" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">秒</span></div>
        <div class="settings-row"><label>NAS 采集间隔</label><input type="number" id="cfg-nas-interval" value="${nasInterval}" min="5" max="300" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">秒</span></div>
      </div>
      <div class="settings-group">
        <div class="settings-group-title">监控阈值</div>
        <div class="settings-row"><label>CPU 告警</label><input type="number" id="cfg-cpu-threshold" value="${config.monitor_threshold_cpu || 80}" min="10" max="100" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">%</span></div>
        <div class="settings-row"><label>内存告警</label><input type="number" id="cfg-mem-threshold" value="${config.monitor_threshold_memory || 85}" min="10" max="100" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">%</span></div>
        <div class="settings-row"><label>磁盘告警</label><input type="number" id="cfg-disk-threshold" value="${config.monitor_threshold_disk || 90}" min="10" max="100" /> <span style="font-size:0.7rem;color:var(--text-tertiary)">%</span></div>
      </div>
      <div class="settings-actions">
        <button class="btn-primary" id="btn-save-collect">保存采集设置</button>
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
      el.innerHTML = `
        <div class="settings-group">
          <div class="settings-group-title">显示</div>
          <div class="settings-row">
            <label>硬件加速</label>
            <div class="toggle-switch-wrapper">
              <label class="toggle-switch">
                <input type="checkbox" id="cfg-hw-accel"${hwEnabled ? ' checked' : ''} />
                <span class="toggle-slider"></span>
              </label>
            </div>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">关闭后可解决虚拟机窗口不显示问题，但性能会降低。修改后需重启应用。</div>
          <div class="settings-row" style="margin-top:14px;padding-top:14px;border-top:1px solid var(--border)">
            <label>主题</label>
            <select id="cfg-theme-select">
              <option value="dark"${curTheme === 'dark' ? ' selected' : ''}>深色（默认）</option>
              <option value="light"${curTheme === 'light' ? ' selected' : ''}>浅色</option>
            </select>
          </div>
          <div class="settings-hint" style="font-size:0.72rem;color:var(--text-tertiary);margin-top:4px">切换后即时生效并自动保存；浅色主题下终端面板仍保持深色。</div>
        </div>
      `;

      const themeSel = el.querySelector('#cfg-theme-select');
      if (themeSel) {
        themeSel.addEventListener('change', () => {
          applyTheme(themeSel.value);
        });
      }

      const toggle = el.querySelector('#cfg-hw-accel');
      if (toggle) {
        toggle.addEventListener('change', async () => {
          const newVal = toggle.checked;
          try {
            const r = await api.setHardwareAccel(newVal);
            if (r && r.ok) {
              showToast(`硬件加速已${newVal ? '启用' : '关闭'}，请重启应用生效`);
            } else {
              showToast('保存失败: ' + ((r && r.error) || '未知错误'), true);
              toggle.checked = !newVal;
            }
          } catch (e) {
            showToast('保存失败: ' + e.message, true);
            toggle.checked = !newVal;
          }
        });
      }
    } catch (e) {
      el.innerHTML = '<div class="settings-group"><div class="settings-group-title">显示</div><div class="settings-row"><label>硬件加速</label><span style="color:var(--text-tertiary);font-size:0.85rem">加载失败</span></div></div>';
    }
  }

  // ── 关于 ──
  function renderAboutTab() {
    const el = panelEls.about;
    el.innerHTML = `
      <div class="settings-group" style="text-align:center;padding:32px">
        <div style="font-size:1.4rem;font-weight:300;margin-bottom:8px">DigitalLab 1.1.1</div>
        <div style="color:var(--text-secondary);font-size:0.85rem;margin-bottom:20px">个人数字实验室</div>
        <div style="color:var(--text-tertiary);font-size:0.75rem;line-height:1.8">
          <div>仪表盘 · 终端 · AI 助手 · 系统监控</div>
          <div style="margin-top:12px">作者：ZWWF0906</div>
          <div>© 2026 ZWWF0906</div>
          <div style="margin-top:12px">DigitalLab 开源软件，遵循 MIT 许可</div>
        </div>
        <div style="margin-top:24px">
          <button class="btn-primary" id="btn-feedback">问题反馈</button>
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
          <span class="modal-title">问题反馈与举报</span>
          <button class="modal-close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div style="color:var(--text-secondary);font-size:0.9rem;margin-bottom:16px;text-align:center">请选择反馈方式</div>
          <div style="color:var(--text-tertiary);font-size:0.75rem;margin-bottom:16px;text-align:center;line-height:1.6">如遇 AI 生成不当内容，请一并在此反馈<br/>我们将在收到反馈后尽快处理</div>
          <button class="btn-primary" id="feedback-mail" style="width:100%;margin-bottom:10px">✉ 邮件反馈</button>
          <button class="btn-secondary" id="feedback-github" style="width:100%">GitHub 反馈</button>
        </div>
        <div class="modal-footer">
          <button class="btn-secondary modal-cancel-btn" style="width:100%">关闭</button>
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
      const subject = encodeURIComponent('DigitalLab 问题反馈');
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
        showToast('配置已保存');
        // 通知 Python 重载配置（含 NAS 监控重启）
        try {
          const reloadResult = await api.sendCommand({ cmd: 'reload_config' });
          if (reloadResult && reloadResult.warnings && reloadResult.warnings.length > 0) {
            showToast('配置已保存，部分组件重载异常', true);
            console.warn('reload_config warnings:', reloadResult.warnings);
          }
        } catch (reloadErr) {
          // 重载失败不阻塞保存成功提示，但给出警告
          console.warn('reload_config failed:', reloadErr);
        }
      } else {
        showToast('保存失败: ' + (result.error || '未知错误'), true);
      }
    } catch (e) {
      showToast('保存失败: ' + e.message, true);
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
    setTimeout(() => root.classList.remove('theme-switching'), 350);
    showToast(theme === 'light' ? '已切换至浅色主题' : '已切换至深色主题');
  }

  // ── 加载配置 ──
  async function loadConfig() {
    try {
      const data = await api.getConfig();
      if (data && !data.error) {
        config = data;
      }
    } catch (e) {
      console.error('加载配置失败:', e);
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