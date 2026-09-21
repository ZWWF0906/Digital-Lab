// panels/ai-assistant.js — AI 助手面板：流式对话、模型切换、系统上下文

// 文案走 i18n：i18n.js 由 dashboard.html 在 <head> 里以经典脚本加载，暴露 window.DigitalLabI18n。
const T = (key, params) => (
  (typeof window !== 'undefined' && window.DigitalLabI18n)
    ? window.DigitalLabI18n.t(key, params)
    : key
);

// 错误标记：这是前端与 Python 之间的"协议"标记，不是界面文案，所以不进词典、也不翻译。
//   后端：新版本已改为结构化 error（{"code","params"}），不再发这个前缀；
//        旧版 backend.exe（core/ai_client.py 早期版本）仍会把 [错误] 拼在 ai_done.text 前面。
//   前端：保留 ERR_MARK 与 startsWith 判断作为旧后端的兼容回退，两条路都映射到同一套词典文案。
// 阶段 4b 建议：等旧后端彻底退出后，这个常量与回退分支就可以删掉。
const ERR_MARK = '[错误]';

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
  let memSnapshot = null;   // 发送前的记忆条目快照（用于“已记住”提示兜底）

  // ── 渲染 ──
  container.innerHTML = `
    <div class="ai-chat">
      <div class="ai-chat-header">
        <div class="provider-toggle" id="ai-provider">
          <button class="provider-option${provider === 'ollama' ? ' active' : ''}" data-provider="ollama">${T('ai.provider.ollama')}</button>
          <button class="provider-option${provider === 'openai' ? ' active' : ''}" data-provider="openai">${T('ai.provider.cloud')}</button>
        </div>
        <button class="ai-settings-btn" id="ai-settings-btn">${T('ai.btn.settings')}</button>
        <button class="ai-settings-btn" id="ai-deploy-btn">${T('ai.btn.deploy')}</button>
        <span style="flex:1"></span>
        <span style="font-size:0.7rem;color:var(--text-tertiary)" id="ai-status"></span>
      </div>
      <div style="display:flex;flex:1;min-height:0;gap:0;">
        <div style="flex:1;display:flex;flex-direction:column;min-width:0;">
          <div class="ai-messages" id="ai-messages">
            <div class="ai-msg assistant">
              <div class="ai-msg-bubble">${T('ai.greeting')}</div>
            </div>
          </div>
          <div class="ai-input-row">
            <input type="text" class="ai-input" id="ai-input" placeholder="${T('ai.input.placeholder')}" />
            <button class="ai-send-btn" id="ai-send-btn">${T('ai.btn.send')}</button>
          </div>
        </div>
        <div class="ai-context-panel" id="ai-context">
          <div class="ai-context-title">${T('ai.context.title')}</div>
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
  const deployBtn = container.querySelector('#ai-deploy-btn');
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
      nasHtml = `<div class="ai-ctx-section">${T('ai.ctx.nas')}</div>`;
      nasKeys.forEach(k => {
        const d = nas[k] || {};
        const online = d.online !== false;
        nasHtml += `<div class="ai-ctx-row"><span style="color:${online?'var(--accent)':'var(--accent-pink)'}">${online?'●':'○'}</span> ${k}: CPU ${d.cpu||'--'}% MEM ${d.memory?.percent??'--'}%</div>`;
      });
    }

    contextBody.innerHTML = `
      <div class="ai-ctx-section">${T('ai.ctx.performance')}</div>
      <div class="ai-ctx-row">CPU: ${m.cpu||'--'}%</div>
      <div class="ai-ctx-row">${T('ai.ctx.memoryRow', { value: m.memory||'--' })}</div>
      <div class="ai-ctx-row">${T('ai.ctx.diskRow', { value: m.disk||'--' })}</div>
      <div class="ai-ctx-section">${T('ai.ctx.hardware')}</div>
      <div class="ai-ctx-row">CPU: ${cpu.model||T('ai.ctx.unknown')}</div>
      <div class="ai-ctx-row">GPU: ${gpu.name||T('ai.ctx.none')}</div>
      <div class="ai-ctx-row">${T('ai.ctx.memoryGb', { value: mem.total_gb||'--' })}</div>
      <div class="ai-ctx-row">${T('ai.ctx.system', { os: sys.os||'', edition: sys.edition||'' })}</div>
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
    // 首个 token 到达即清空“思考中”状态，直接显示输出
    if (statusEl && statusEl.textContent) statusEl.textContent = '';
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

  // ── 记忆提示（弱化样式，复用思考内容的小灰字） ──
  function memKey(item) {
    return ((item && item.ts) || '') + '|' + ((item && item.content) || '');
  }

  function showMemoryHints(items) {
    if (!Array.isArray(items) || !items.length) return;
    items.forEach(item => {
      const tip = document.createElement('div');
      tip.className = 'ai-msg-thinking';
      tip.textContent = T('ai.memory.remembered', { item: item });
      messagesEl.appendChild(tip);
    });
    scrollBottom();
  }

  // 优先使用 ai_done.memory（需主进程转发）；未转发时用发送前后的记忆列表差异兜底
  async function resolveMemoryHints(data) {
    // 主进程已转发 memory 字段时走直通路径（空数组表示本轮无新记忆，无需回查）
    if (Array.isArray(data.memory)) {
      console.log(T('log.aiMemory.passthrough', { count: data.memory.length }));
      showMemoryHints(data.memory);
      return;
    }
    // 兼容未转发 memory 的旧主进程：用发送前后的记忆列表差异兜底
    if (!memSnapshot) return;
    try {
      const after = await api.sendCommand({ cmd: 'get_ai_memory' });
      if (!after || !after.enabled) return;
      const fresh = (after.items || [])
        .filter(it => !memSnapshot.has(memKey(it)))
        .map(it => it.content);
      console.log(T('log.aiMemory.fallback', { count: fresh.length }));
      showMemoryHints(fresh);
    } catch (e) { /* 静默失败，不影响对话 */ }
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
    statusEl.textContent = T('ai.status.thinking');

    // 系统提示（实时系统状态、输出格式约束与记忆注入）统一由 Python 侧构造，前端只发送对话历史
    const chatMessages = messages.map(m => ({ role: m.role, content: m.content }));

    // 记忆提示准备：仅在记忆开启时记录发送前的条目，供“已记住”提示兜底比对
    memSnapshot = null;
    try {
      const snap = await api.sendCommand({ cmd: 'get_ai_memory' });
      if (snap && snap.enabled) {
        memSnapshot = new Set((snap.items || []).map(memKey));
      }
    } catch (e) { memSnapshot = null; }

    try {
      // 界面语言随每次请求一起下发（无状态，避免后端记忆的语言漂移）：
      // 用 sendCommand 而不是 api.aiChat，是因为 aiChat 的签名固定为 (messages, provider)，
      // 而 preload 不在本轮允许改动的文件里；sendCommand 会把整个对象透传给后端。
      // 旧后端会忽略 lang 字段（回退中文），行为不受影响。
      const reqLang = (typeof window !== 'undefined' && window.DigitalLabI18n && window.DigitalLabI18n.getLanguage)
        ? window.DigitalLabI18n.getLanguage() : 'zh-CN';
      const result = (api && typeof api.sendCommand === 'function')
        ? await api.sendCommand({ cmd: 'ai_chat', messages: chatMessages, provider, lang: reqLang })
        : await api.aiChat(chatMessages, provider);   // 旧 preload 兜底
      if (result.error) {
        // result.error 是后端文案（阶段 4 范围），这里只补协议标记
        addMessage('assistant', `${ERR_MARK} ${result.error}`);
        finishStream();
      }
      // 流式输出由 onAiToken/onAiDone 回调处理
    } catch (e) {
      addMessage('assistant', `${ERR_MARK} ${e.message}`);
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

  // 快速部署：功能未实现，仅弹原生提示框；任何异常按"取消"处理（静默）
  if (deployBtn) {
    deployBtn.addEventListener('click', async () => {
      try {
        if (!api || typeof api.confirmQuickDeploy !== 'function') {
          console.warn(T('log.deploy.noApi'));
          return;
        }
        await api.confirmQuickDeploy();
      } catch (e) {
        console.warn(T('log.deploy.dialogFailed', { error: e.message }));
      }
    });
  }

  // ── API 监听 ──
  unsubState = api.onStateUpdate(updateContext);

  unsubToken = api.onAiToken((data) => {
    if (data.token) {
      appendToken(data.token, data.kind || 'content');
    }
  });

  unsubDone = api.onAiDone((data) => {
    statusEl.textContent = '';
    const text = data.text || '';
    // 错误两条路都要能显示（双兼容）：
    //   新后端：data.error = {code, params}，文案查词典（code 与词典 key 同名）
    //   旧后端：只给以 [错误] 开头的 text（backend.exe 未更新时）
    // 词典缺 key 时 t() 会返回 key 本身，所以不会出现空白气泡。
    const structured = (data.error && typeof data.error === 'object') ? data.error : null;
    if (structured) {
      const msg = structured.code ? T(structured.code, structured.params || {}) : '';
      addMessage('assistant', msg || T('common.unknownError'));
    } else if (text.startsWith(ERR_MARK)) {
      addMessage('assistant', text);
    } else if (streamingMsg && streamingMsg.contentBubble) {
      // 正常回复：用后端剥离标记后的文本覆盖流式显示与前端历史，避免 [记忆] 标记残留
      // 正文为空（例如模型只输出了记忆标记）时给占位，避免气泡空着；历史仍保存真实文本
      streamingMsg.contentBubble.textContent = (text && text.trim()) ? text : T('ai.emptyReply');
      const lastMsg = messages[messages.length - 1];
      if (lastMsg && lastMsg.role === 'assistant') lastMsg.content = text;
    }
    // 记忆写入提示：主进程未转发 memory 字段时由记忆列表差异兜底
    resolveMemoryHints(data);
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