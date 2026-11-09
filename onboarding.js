// 首次启动引导：三步（选语言 / 配设备 / 查连接）。
    // 只依赖 <head> 的 i18n 与 preload 暴露的 API，不碰 styles.css、不改任何面板。
    (function () {
      'use strict';
      var root = document.getElementById('onboarding');
      if (!root) return;
      var api = window.digitalLab;

      var T = function (key, params) {
        return (window.DigitalLabI18n && window.DigitalLabI18n.t) ? window.DigitalLabI18n.t(key, params) : key;
      };
      // 后端错误对象/字符串转文案（与 settings.js / terminal.js 同一套双兼容规则）
      function backendErrorText(obj) {
        if (!obj) return '';
        var err = (obj.error !== undefined) ? obj.error : null;
        if (err && typeof err === 'object' && err.code) return T(err.code, err.params || {}) || String(err.code);
        if (typeof err === 'string' && err) return err;
        if (obj.code) return T(obj.code, obj.params || {}) || String(obj.code);
        if (typeof obj.message === 'string' && obj.message) return obj.message;
        return '';
      }

      var el = {
        steps: root.querySelector('#ob-steps'),
        langs: root.querySelector('#ob-langs'),
        panes: root.querySelectorAll('.ob-pane'),
        devName: root.querySelector('#ob-dev-name'),
        devHost: root.querySelector('#ob-dev-host'),
        devPort: root.querySelector('#ob-dev-port'),
        devUser: root.querySelector('#ob-dev-user'),
        devPass: root.querySelector('#ob-dev-pass'),
        devMsg: root.querySelector('#ob-dev-msg'),
        status: root.querySelector('#ob-status'),
        checkMsg: root.querySelector('#ob-check-msg'),
        later: root.querySelector('#ob-later'),
        later3: root.querySelector('#ob-later-3'),
        noNas: root.querySelector('#ob-no-nas'),
        start: root.querySelector('#ob-start'),
        sub: root.querySelector('.ob-sub'),
        back: root.querySelector('#ob-back'),
        retry: root.querySelector('#ob-retry'),
        next: root.querySelector('#ob-next')
      };

      var STEP_KEYS = ['onboard.step.language', 'onboard.step.device', 'onboard.step.check'];
      var step = 1;
      var opened = false;       // 幂等：splash-finished 可能被派发两次
      var finished = false;
      var busy = false;
      var device = null;        // 第 2 步保存下来的设备记录
      var savedAt = 0;          // 保存时刻：只认这之后采集到的新状态，避免旧设备残留的 online=true 被当成通过
      var testOk = false;       // 一次测试是否 ok
      var onlineSeen = false;   // 状态帧里该设备是否 online（且是保存之后的新数据）
      var unsubState = null;
      var waitTimer = null;

      // ── 文案：所有带 data-ob / data-ob-ph 的节点按当前语言重填 ──
      function applyTexts() {
        var i, n;
        var nodes = root.querySelectorAll('[data-ob]');
        for (i = 0; i < nodes.length; i++) {
          n = nodes[i];
          n.textContent = T(n.getAttribute('data-ob'));
        }
        var phs = root.querySelectorAll('[data-ob-ph]');
        for (i = 0; i < phs.length; i++) {
          n = phs[i];
          n.setAttribute('placeholder', T(n.getAttribute('data-ob-ph')));
        }
        root.setAttribute('aria-label', T('onboard.title'));
        renderSteps();
        renderLangs();
        renderFoot();
        updateStatus();
      }

      function renderSteps() {
        var html = '';
        for (var i = 0; i < STEP_KEYS.length; i++) {
          var cls = 'ob-chip' + (step === i + 1 ? ' is-active' : (step > i + 1 ? ' is-done' : ''));
          html += '<span class="' + cls + '">' + (i + 1) + '. ' + T(STEP_KEYS[i]) + '</span>';
        }
        el.steps.innerHTML = html;
      }

      // ── 第 1 步：语言（清单来自 DigitalLabLocales.LANGUAGES，不写死）──
      function renderLangs() {
        var L = (window.DigitalLabLocales && window.DigitalLabLocales.LANGUAGES) || [];
        var cur = (window.DigitalLabI18n && window.DigitalLabI18n.getLanguage) ? window.DigitalLabI18n.getLanguage() : '';
        var html = '';
        for (var i = 0; i < L.length; i++) {
          var active = (L[i].code === cur);
          html += '<button class="ob-lang' + (active ? ' is-active' : '') + '" data-code="' + L[i].code + '">' +
                  '<span>' + (L[i].nativeName || L[i].name || L[i].code) + '</span>' +
                  '<span class="ob-lang-tick">' + (active ? '\u2713' : '') + '</span></button>';
        }
        el.langs.innerHTML = html;
        var btns = el.langs.querySelectorAll('.ob-lang');
        for (var k = 0; k < btns.length; k++) {
          btns[k].addEventListener('click', function () { switchLanguage(this.getAttribute('data-code')); });
        }
      }

      // 复用设置面板那 5 步：i18n 切换 → localStorage → html lang → 主进程 → language-changed
      function switchLanguage(code) {
        var I = window.DigitalLabI18n;
        if (!I || typeof I.setLanguage !== 'function') return;
        if (!I.setLanguage(code)) return;
        try { localStorage.setItem('digitallab-lang', code); } catch (e) {}
        document.documentElement.setAttribute('lang', code);
        try { if (api && typeof api.setLanguage === 'function') api.setLanguage(code); } catch (e) {}
        window.dispatchEvent(new CustomEvent('language-changed', { detail: code }));
      }

      function renderFoot() {
        // 第 4 页（收尾页）由该页自己的"开始使用"按钮负责，底部整排按钮全部隐藏
        el.later.style.display = (step === 1) ? '' : 'none';
        el.back.style.display = (step > 1 && step < 4) ? '' : 'none';
        el.retry.style.display = (step === 3) ? '' : 'none';
        el.later3.style.display = (step === 3) ? '' : 'none';
        el.next.style.display = (step === 4) ? 'none' : '';
        el.next.textContent = T(step === 3 ? 'onboard.btn.finish' : 'onboard.btn.next');
        el.next.disabled = busy || (step === 3 && !isPassed());
        el.retry.disabled = busy;
      }

      function setPane() {
        for (var i = 0; i < el.panes.length; i++) {
          el.panes[i].classList.toggle('is-active', Number(el.panes[i].getAttribute('data-pane')) === step);
        }
        // 收尾页隐藏卡片头部那句"三步完成初始设置"（主标题保留）；回到其它步骤恢复显示
        if (el.sub) el.sub.style.display = (step === 4) ? 'none' : '';
      }

      function setMsg(node, text, kind) {
        node.textContent = text || '';
        node.classList.remove('is-error', 'is-ok');
        if (kind) node.classList.add(kind);
      }

      function isPassed() { return !!(testOk && onlineSeen); }

      // ── 第 3 步状态行：未通过时分两行（连接测试 / 设备在线），通过后合成一句 ──
      function statusLine(on, fail, text) {
        return '<div class="ob-status-line"><span class="ob-status-dot' + (on ? (fail ? ' is-fail' : ' is-ok') : '') + '">\u25CF</span><span>' + text + '</span></div>';
      }

      function updateStatus() {
        if (!el.status) return;
        if (step !== 3 || !device) { el.status.innerHTML = ''; return; }
        if (isPassed()) { el.status.innerHTML = statusLine(true, false, T('onboard.check.pass')); return; }
        var html = statusLine(testOk, !testOk, testOk ? T('onboard.check.testPass') : T('onboard.check.fail'));
        html += statusLine(onlineSeen, false, onlineSeen ? T('onboard.check.online') : T('onboard.check.waiting'));
        el.status.innerHTML = html;
      }

      // ── 第 2 步：保存设备（只做新增；同名则覆盖，避免重复）──
      function collectDevice() {
        return {
          name: (el.devName.value || '').trim(),
          host: (el.devHost.value || '').trim(),
          port: parseInt(el.devPort.value, 10) || 22,
          username: (el.devUser.value || '').trim(),
          password: el.devPass.value || ''
        };
      }

      async function saveDevice() {
        var rec = collectDevice();
        if (!rec.name || !rec.host) { setMsg(el.devMsg, T('onboard.dev.needFields'), 'is-error'); return false; }
        busy = true; setMsg(el.devMsg, T('onboard.dev.saving'), ''); renderFoot();
        try {
          // P0：保存为受管设备（密码只在本次输入时提交），再让后端重载配置
          var payload = { name: rec.name, host: rec.host, port: rec.port, username: rec.username };
          if (rec.password) payload.password = rec.password;
          var r = await api.saveDevice(payload, ['password']);
          if (!r || r.ok === false) {
            setMsg(el.devMsg, T('common.saveFailed', { message: backendErrorText(r) || T('common.unknownError') }), 'is-error');
            busy = false; renderFoot(); return false;
          }
          // 让后端重启 NAS 采集线程，新设备才会出现在状态帧里
          try { await api.reloadConfig(); } catch (e) {}
          device = rec;
          savedAt = Date.now();   // 之后的状态帧才算"这台设备的新数据"
          setMsg(el.devMsg, '', '');
          busy = false; renderFoot();
          return true;
        } catch (e) {
          setMsg(el.devMsg, T('common.saveFailed', { message: e.message }), 'is-error');
          busy = false; renderFoot();
          return false;
        }
      }

      // ── 第 3 步：测试连接 + 等设备上线 ──
      function subscribeState() {
        if (unsubState || !api || typeof api.onStateUpdate !== 'function') return;
        try {
          unsubState = api.onStateUpdate(function (state) {
            if (!device || !state || !state.nas) return;
            var d = state.nas[device.name];
            if (!d || d.online !== true) return;
            // 只认"保存/测试之后"采集到的新数据：
            // 同名设备在改动主机前可能还留着上一轮的 online=true 与 last_updated，
            // 若直接采信，改成一个连不上的地址也会被判成通过。
            if (d.last_updated) {
              var lu = Date.parse(d.last_updated);
              if (!isNaN(lu) && lu < savedAt - 3000) return;
            }
            if (!onlineSeen) {
              onlineSeen = true;
              renderFoot(); updateStatus();
            }
          });
        } catch (e) {}
      }

      function startWait() {
        if (waitTimer) { clearTimeout(waitTimer); waitTimer = null; }
        waitTimer = setTimeout(function () {
          waitTimer = null;
          if (!onlineSeen && step === 3) {
            setMsg(el.checkMsg, T('onboard.check.timeout'), '');
            updateStatus();
          }
        }, 15000);
      }

      async function runTest() {
        if (!device) return;
        busy = true; testOk = false; onlineSeen = false;
        setMsg(el.checkMsg, T('onboard.check.testing'), '');
        renderFoot(); updateStatus();
        subscribeState();
        try {
          var res = await api.testNasConnection(device.name);
          testOk = !!(res && res.ok === true);
          if (!testOk) {
            var detail = backendErrorText(res);
            setMsg(el.checkMsg, detail || T('set.dev.connFailed'), 'is-error');
          } else {
            setMsg(el.checkMsg, '', '');   // 通过后由状态行表达"等待上线"，避免重复
          }
        } catch (e) {
          testOk = false;
          setMsg(el.checkMsg, T('net.connectFailed', { detail: e.message }), 'is-error');
        }
        busy = false; renderFoot(); updateStatus();
        if (!onlineSeen) startWait();
      }

      // ── 流程控制 ──
      function goStep(n) {
        step = Math.min(3, Math.max(1, n));
        setPane(); renderSteps(); renderFoot(); updateStatus();
        if (step === 3 && device) runTest();
      }

      async function next() {
        if (busy) return;
        if (step === 1) { goStep(2); return; }
        if (step === 2) {
          var okSave = await saveDevice();
          if (okSave) goStep(3);
          return;
        }
        finish();   // 第 3 步：完成（仅在通过时可用）
      }

      function cleanup() {
        if (waitTimer) { clearTimeout(waitTimer); waitTimer = null; }
        if (unsubState) { try { unsubState(); } catch (e) {} unsubState = null; }
      }

      function close() {
        opened = false;
        root.classList.remove('is-open');
        cleanup();
      }

      // 所有出口（完成 / 稍后配置 / 我没有 NAS / 跳过此步 / Esc）都先切到收尾页，不直接关闭：
      // 用户点"开始使用"才算真正结束，比自动消失更有掌控感，也不会显得引导被草草跳过。
      function finish() {
        if (finished || step === 4) return;
        step = 4;
        setPane();
        renderSteps();
        renderFoot();
      }

      // 收尾页的"开始使用"：写入 onboarding_done=true（表示用户已看过引导，否则每次启动都会再弹一次）并关闭覆盖层
      function dismiss() {
        if (finished) return;
        finished = true;
        try { if (api && typeof api.setOnboardingDone === 'function') api.setOnboardingDone(true); } catch (e) {}
        close();
      }

      // 外壳在 'splash-finished' 后调用；幂等
      function openIfNeeded() {
        if (opened) return;
        var done = false;
        try { done = !!(api && typeof api.getOnboardingDoneSync === 'function' && api.getOnboardingDoneSync()); } catch (e) {}
        if (done) return;
        open();
      }

      function open() {
        opened = true;
        finished = false;
        step = 1;
        device = null; testOk = false; onlineSeen = false;
        setMsg(el.devMsg, '', ''); setMsg(el.checkMsg, '', '');
        applyTexts();
        setPane();
        root.classList.add('is-open');
        try { el.devName.focus(); } catch (e) {}
      }

      el.next.addEventListener('click', next);
      el.back.addEventListener('click', function () { goStep(step - 1); });
      el.retry.addEventListener('click', function () { runTest(); });
      el.later.addEventListener('click', finish);
      el.later3.addEventListener('click', finish);
      // 第 2 步出口：没有 NAS 的用户可直接结束引导，之后仍走本机监控
      el.noNas.addEventListener('click', finish);
      // 收尾页：唯一真正关闭引导的入口
      el.start.addEventListener('click', dismiss);
      root.addEventListener('keydown', function (e) {
        if (e.key !== 'Escape') return;
        if (step === 4) dismiss(); else finish();   // 收尾页按 Esc 等同点"开始使用"
      });

      // 语言切换（无论来自引导本身还是设置面板）→ 重填文案
      window.addEventListener('language-changed', function () { if (opened) applyTexts(); });

      // 供外壳与设置面板调用（设置面板的"重新运行引导"）
      window.DigitalLabOnboarding = {
        openIfNeeded: openIfNeeded,
        open: open,
        close: close,
        isOpen: function () { return opened; }
      };

      applyTexts();   // 先把文案填好（此时仍隐藏）
    })();
