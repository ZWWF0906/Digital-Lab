// panels/ai-assistant.js — AI 助手面板：流式对话、模型切换、系统上下文

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

export async function init(container, api) {
  if (!shownTip) {
    shownTip = true;
    showTipModal();
  }

  // ── 从配置读取模型选择 ──
  let provider = 'ollama';
  try {
    const cfg = await api.getConfig();
    if (cfg?.ai?.provider) provider = cfg.ai.provider;
  } catch (e) { /* 使用默认值 */ }

  let messages = [];
  let isStreaming = false;
  let currentRequestId = null;
  let latestState = { monitor: { cpu: 0, memory: 0, disk: 0 }, hardware: null, nas: {} };
  let unsubState = null;
  let unsubToken = null;
  let unsubDone = null;

  // ── 渲染 ──
  container.innerHTML = `
    <div class="ai-chat">
      <div class="ai-chat-header">
        <div class="provider-toggle" id="ai-provider">
          <button class="provider-option${provider === 'ollama' ? ' active' : ''}" data-provider="ollama">Ollama 本地</button>
          <button class="provider-option${provider === 'openai' ? ' active' : ''}" data-provider="openai">云端 API</button>
        </div>
        <button class="ai-settings-btn" id="ai-settings-btn">设置</button>
        <span style="flex:1"></span>
        <span style="font-size:0.7rem;color:var(--text-tertiary)" id="ai-status"></span>
      </div>
      <div style="display:flex;flex:1;min-height:0;gap:0;">
        <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
          <div class="ai-messages" id="ai-messages">
            <div class="ai-msg assistant">
              <div class="ai-msg-bubble">你好！我是 DigitalLab AI 助手。选择模型后即可开始对话。</div>
            </div>
          </div>
          <div class="ai-input-row">
            <input type="text" class="ai-input" id="ai-input" placeholder="输入消息... (Enter 发送)" />
            <button class="ai-send-btn" id="ai-send-btn">发送</button>
          </div>
        </div>
        <div class="ai-context-panel" id="ai-context">
          <div class="ai-context-title">系统状态</div>
          <div id="ai-context-body"></div>
        </div>
      </div>
    </div>
  `;

  // ── DOM 引用 ──
  const messagesEl = container.querySelector('#ai-messages');
  const inputEl = container.querySelector('#ai-input');
  const sendBtn = container.querySelector('#ai-send-btn');
  const providerSel = container.querySelector('#ai-provider');
  const statusEl = container.querySelector('#ai-status');
  const settingsBtn = container.querySelector('#ai-settings-btn');
  const contextBody = container.querySelector('#ai-context-body');

  // ── 系统上下文更新 ──
  function updateContext(state) {
    latestState = state;
    if (!contextBody) return;
    const m = state.monitor || {};
    const hw = state.hardware || {};
    const cpu = hw.cpu || {};
    const gpu = hw.gpu || {};
    const mem = hw.memory || {};
    const sys = hw.system || {};
    const nas = state.nas || {};

    let nasHtml = '';
    const nasKeys = Object.keys(nas);
    if (nasKeys.length > 0) {
      nasHtml = '<div class="ai-ctx-section">NAS 设备</div>';
      nasKeys.forEach(k => {
        const d = nas[k] || {};
        const online = d.status === 'online';
        nasHtml += `<div class="ai-ctx-row"><span style="color:${online?'var(--accent)':'var(--accent-pink)'}">${online?'●':'○'}</span> ${k}: CPU ${d.cpu||'--'}% MEM ${d.memory||'--'}%</div>`;
      });
    }

    contextBody.innerHTML = `
      <div class="ai-ctx-section">性能</div>
      <div class="ai-ctx-row">CPU: ${m.cpu||'--'}%</div>
      <div class="ai-ctx-row">内存: ${m.memory||'--'}%</div>
      <div class="ai-ctx-row">磁盘: ${m.disk||'--'}%</div>
      <div class="ai-ctx-section">硬件</div>
      <div class="ai-ctx-row">CPU: ${cpu.model||'未知'}</div>
      <div class="ai-ctx-row">GPU: ${gpu.name||'无'}</div>
      <div class="ai-ctx-row">内存: ${mem.total_gb||'--'} GB</div>
      <div class="ai-ctx-row">系统: ${sys.os||''} ${sys.edition||''}</div>
      ${nasHtml}
    `;
  }

  // ── 滚动到底部 ──
  function scrollBottom() {
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  // ── 创建消息 DOM 节点（增量渲染，避免 innerHTML 闪烁） ──
  function createMsgNode(role) {
    const div = document.createElement('div');
    div.className = `ai-msg ${role}`;
    const bubble = document.createElement('div');
    bubble.className = 'ai-msg-bubble';
    div.appendChild(bubble);
    return { container: div, bubble };
  }

  // 当前流式输出的 assistant 消息 DOM 引用
  let streamingMsg = null;
  let thinkingBubble = null;

  // ── 添加消息（非流式） ──
  function addMessage(role, content) {
    messages.push({ role, content });
    const { container, bubble } = createMsgNode(role);
    bubble.textContent = content;
    messagesEl.appendChild(container);
    scrollBottom();
  }

  // ── 追加 token 到流式消息（增量 DOM，不触发重绘） ──
  function appendToken(token, kind) {
    let msg = messages[messages.length - 1];
    if (!msg || msg.role !== 'assistant') {
      // 创建新的 assistant 消息
      msg = { role: 'assistant', content: '', thinking: '' };
      messages.push(msg);
      const { container, bubble } = createMsgNode('assistant');
      streamingMsg = container;
      streamingMsg.contentBubble = bubble;
      thinkingBubble = null;
      messagesEl.appendChild(container);
    }

    if (kind === 'thinking') {
      msg.thinking = (msg.thinking || '') + token;
      if (!thinkingBubble && streamingMsg) {
        thinkingBubble = document.createElement('div');
        thinkingBubble.className = 'ai-msg-thinking';
        streamingMsg.insertBefore(thinkingBubble, streamingMsg.contentBubble);
      }
      if (thinkingBubble) {
        thinkingBubble.textContent += token;
      }
    } else {
      msg.content += token;
      if (streamingMsg && streamingMsg.contentBubble) {
        streamingMsg.contentBubble.textContent += token;
      }
    }
    scrollBottom();
  }

  // ── 渲染消息列表（仅用于初始状态或错误恢复） ──
  function renderMessages() {
    if (!messagesEl) return;
    messagesEl.innerHTML = '';
    streamingMsg = null;
    thinkingBubble = null;
    messages.forEach(m => {
      const { container, bubble } = createMsgNode(m.role);
      bubble.textContent = m.content;
      if (m.thinking) {
        const thinkDiv = document.createElement('div');
        thinkDiv.className = 'ai-msg-thinking';
        thinkDiv.textContent = m.thinking;
        container.insertBefore(thinkDiv, bubble);
      }
      messagesEl.appendChild(container);
    });
    scrollBottom();
  }

  // ── 发送消息 ──
  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || isStreaming) return;

    inputEl.value = '';
    addMessage('user', text);
    isStreaming = true;
    sendBtn.disabled = true;
    inputEl.disabled = true;
    statusEl.textContent = '思考中...';

    // 构建系统上下文
    const ctx = latestState;
    const sysMsg = `当前系统状态：CPU ${ctx.monitor?.cpu||'--'}%, 内存 ${ctx.monitor?.memory||'--'}%, 磁盘 ${ctx.monitor?.disk||'--'}%。请基于此信息回答用户问题。
输出格式要求：不要使用 Markdown 代码块、HTML 标签、反引号、星号加粗等特殊格式字符。如需列举，用纯文本编号或缩进。代码或命令用引号包裹即可。数学公式用纯文本表达。保持简洁自然的纯文本风格。`;

    const chatMessages = [
      { role: 'system', content: sysMsg },
      ...messages.map(m => ({ role: m.role, content: m.content })),
    ];

    try {
      const result = await api.aiChat(chatMessages, provider);
      if (result.error) {
        addMessage('assistant', `[错误] ${result.error}`);
        finishStream();
      }
      // 流式输出由 onAiToken/onAiDone 回调处理
    } catch (e) {
      addMessage('assistant', `[错误] ${e.message}`);
      finishStream();
    }
  }

  function finishStream() {
    isStreaming = false;
    sendBtn.disabled = false;
    inputEl.disabled = false;
    statusEl.textContent = '';
    streamingMsg = null;
    thinkingBubble = null;
    inputEl.focus();
  }

  // ── 事件监听 ──
  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  providerSel.addEventListener('click', async (e) => {
    const btn = e.target.closest('.provider-option');
    if (!btn) return;
    provider = btn.dataset.provider;
    providerSel.querySelectorAll('.provider-option').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    // 同步保存到配置
    try {
      const cfg = await api.getConfig();
      if (!cfg.ai) cfg.ai = {};
      cfg.ai.provider = provider;
      await api.saveConfig(cfg);
    } catch (e) { /* 静默失败 */ }
  });

  settingsBtn.addEventListener('click', () => {
    // 切换到设置面板（通过全局事件）
    window.dispatchEvent(new CustomEvent('switch-panel', { detail: 'settings' }));
  });

  // ── API 监听 ──
  unsubState = api.onStateUpdate(updateContext);

  unsubToken = api.onAiToken((data) => {
    if (data.token) {
      appendToken(data.token, data.kind || 'content');
    }
  });

  unsubDone = api.onAiDone((data) => {
    statusEl.textContent = '';
    // 错误消息：ai_done.text 以 [错误] 开头表示异常
    const text = data.text || '';
    if (text.startsWith('[错误]')) {
      addMessage('assistant', text);
    }
    finishStream();
  });

  // ── 监听设置面板的配置变更 ──
  const onConfigUpdated = (e) => {
    const newProvider = e.detail?.provider;
    if (newProvider && newProvider !== provider) {
      provider = newProvider;
      providerSel.querySelectorAll('.provider-option').forEach(b => {
        b.classList.toggle('active', b.dataset.provider === provider);
      });
    }
  };
  window.addEventListener('ai-config-updated', onConfigUpdated);

  // ── 初始状态 ──
  api.getHardware().then(hw => {
    if (hw) updateContext({ ...latestState, hardware: hw });
  });

  // ── 清理 ──
  return () => {
    if (unsubState) unsubState();
    if (unsubToken) unsubToken();
    if (unsubDone) unsubDone();
    window.removeEventListener('ai-config-updated', onConfigUpdated);
  };
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}