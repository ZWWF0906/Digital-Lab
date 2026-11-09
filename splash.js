// 启动自检：真实状态驱动 + 固定节奏逐项点亮 + 超时兜底 + 淡出
    (function () {
      var root = document.getElementById('boot-splash');
      if (!root) return;
      // ── 开屏开关（应用级 config.json 的 splash_animation，默认开）──
      // 启动期同步读取（sendSync，一次）；关掉时直接移除覆盖层并短路，不装任何监听、不起跑动画。
      var splashEnabled = true;
      try {
        var bootApi = window.digitalLab;
        if (bootApi && typeof bootApi.getSplashAnimationSync === 'function') {
          splashEnabled = bootApi.getSplashAnimationSync() !== false;
        }
      } catch (e) {}
      if (!splashEnabled) {
        if (root.parentNode) root.parentNode.removeChild(root);
        // 开屏被关闭时没有淡出动画，这里必须派发同一个结束事件，
        // 否则"关掉开屏动画"的用户永远等不到引导（勘察报告里点出的最易漏分支）。
        // 注意：这个分支发生在解析期，外壳的监听还没装上，所以同时留一个标记，
        // 由外壳在注册监听后补查一次（见模块脚本里的 __splashFinished 判断）。
        window.__splashFinished = true;
        try { window.dispatchEvent(new CustomEvent('splash-finished')); } catch (e) {}
        return;
      }
      var SCRIPT_T0 = performance.now();   // 脚本起跑（探针与 10s 超时兜底的基准）
      var t0 = 0;                          // JS 时间线基准：判定"窗口可见"那一刻才赋值
      var KEYS = ['backend', 'collector', 'hardware', 'nas'];
      var REVEAL_AT = [2600, 3000, 3400, 3800];   // 第 1..4 项点亮时刻（相对页面加载，ms）
      var DEADLINE_MS = 10000;                    // 超时兜底
      var FINAL = { pass: 1, fail: 1, skip: 1 };
      // 覆盖层文案一律取 i18n（语言在 <head> 已定好，这里只是按当前语言取字符串）
      var I18N = window.DigitalLabI18n;
      var T = function (key, params) {
        return (I18N && typeof I18N.t === 'function') ? I18N.t(key, params) : key;
      };
      var LABEL = {
        wait: T('boot.state.wait'), pass: T('boot.state.pass'),
        fail: T('boot.state.fail'), skip: T('boot.state.skip')
      };
      var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
      var reduced = !!(mq && mq.matches);

      var items = {};
      KEYS.forEach(function (k) {
        items[k] = { el: document.getElementById('bs-check-' + k), state: 'wait', detail: '', shown: false };
      });

      var shownCount = 0, resolvedCount = 0, faded = false;

      function render(it) {
        if (!it.el) return;
        var st = it.el.querySelector('.bs-state');
        st.textContent = it.detail ? LABEL[it.state] + ' · ' + it.detail : LABEL[it.state];
        // 用 classList 增删，不要整串重写 className：否则每来一帧状态都会把 is-pop 抹掉，
        // 点亮反馈（光晕/位移）会在动画播到一半时被取消（实测取证见开发日志）。
        it.el.classList.toggle('is-shown', !!it.shown);
        it.el.classList.remove('st-wait', 'st-pass', 'st-fail', 'st-skip');
        it.el.classList.add('st-' + it.state);
      }

      function pop(it) {
        if (!it.el) return;
        it.el.classList.remove('is-pop');
        void it.el.offsetWidth;      // 触发重排，重放动画
        it.el.classList.add('is-pop');
      }

      function setState(k, state, detail) {
        var it = items[k];
        if (!it) return;
        var wasFinal = !!FINAL[it.state];
        it.state = state;
        it.detail = detail || '';
        render(it);
        if (!wasFinal && FINAL[state]) {
          resolvedCount++;
          pop(it);
          maybeFinish();
        }
      }

      function reveal(k) {
        var it = items[k];
        if (!it || it.shown) return;
        it.shown = true;
        render(it);
        shownCount++;
        if (FINAL[it.state]) pop(it);   // 数据早已就绪时，点亮这一刻补一次脉冲，用户能看到它"亮"起来
        maybeFinish();
      }

      function doFade() {
        if (faded) return;
        faded = true;
        root.classList.add('is-out');
        var done = function () {
          root.style.display = 'none';
          // 开屏真正结束（淡出动画结束或兜底超时）才派发：引导页据此决定是否显示。
          // 可能被调用两次（animationend + 超时兜底），监听方需要自己做幂等。
          window.__splashFinished = true;
          try { window.dispatchEvent(new CustomEvent('splash-finished')); } catch (e) {}
        };
        root.addEventListener('animationend', function (ev) {
          if (ev.animationName === 'bs-splashOut') done();   // 只认淡出动画，忽略呼吸/其它动画的结束
        });
        setTimeout(done, reduced ? 400 : 1200);   // 兜底：reduced-motion 下没有动画事件
      }

      function maybeFinish() {
        if (faded) return;
        if (shownCount < KEYS.length || resolvedCount < KEYS.length) return;
        if (!reduced) root.classList.add('is-breath');   // 收尾呼吸：与 400ms 停留同步，随后淡出
        setTimeout(doFade, reduced ? 800 : 400);   // 全部展示完后再停留一下，保证每项都看得清
      }

      // ── 真实状态判定 ──
      var seenFrame = false;
      function onState(state) {
        if (!state || typeof state !== 'object') return;
        if (!seenFrame) { seenFrame = true; setState('backend', 'pass', T('boot.detail.frame')); }

        var m = state.monitor || {};
        var cpu = typeof m.cpu === 'number' ? m.cpu : 0;
        if (cpu > 0) setState('collector', 'pass', 'CPU ' + cpu.toFixed(1) + '%');

        var hw = state.hardware, hwCount = 0;
        if (hw) hwCount = Array.isArray(hw) ? hw.length : Object.keys(hw).length;
        if (hwCount > 0) setState('hardware', 'pass', T('boot.detail.hardwareCount', { count: hwCount }));

        if (Object.prototype.hasOwnProperty.call(state, 'nas')) {
          var nas = state.nas || {}, names = Object.keys(nas);
          var online = names.filter(function (n) { return nas[n] && nas[n].online === true; }).length;
          setState('nas', 'pass', online
            ? T('boot.detail.nasOnline', { count: online })
            : (names.length ? T('boot.detail.nasNoneOnline') : T('boot.detail.nasUnconfigured')));
        } else {
          setState('nas', 'skip', T('boot.detail.nasNoState'));
        }
      }

      var api = window.digitalLab;
      if (api && typeof api.onStateUpdate === 'function') {
        try { api.onStateUpdate(onState); } catch (e) {}
      } else {
        KEYS.forEach(function (k) { setState(k, 'fail', T('boot.detail.preloadDown')); });
      }

      // ── 起跑判定：等"合成器真正开始出帧"的那一帧，而不是窗口一显示就起跑 ──
      // 诊断实测：show() 之后合成器还要 300~340ms 才恢复出帧（这期间窗口只有 Electron 底色），
      // 而旧的 focus / rAF 三帧信号在 show 那一刻就触发，动画时钟随即开始跑，
      // 用户看到内容时六边形已经画掉一段（动画"抢跑"）。
      // 现在改成盯 rAF 的"停摆-恢复"：连续超过 stallMs 没有 rAF 算停摆，恢复的那一帧才 arm。
      // 模式开关：ARM.mode = 'stall'（默认，停摆-恢复检测）| 'fixed'（备选，窗口显示后固定延时）。
      var ARM = {
        // 默认 stall。想切备选方案有两种办法：
        //   1) 直接把下面这行改成 mode: 'fixed'，重新打包；
        //   2) 不重新打包：在页面脚本之前设 window.__armModeWant = 'fixed'（调试/临时切换用）。
        mode: (window.__armModeWant === 'fixed' ? 'fixed' : 'stall'),
        stallMs: 150,       // 停摆判定阈值：连续多少毫秒没有 rAF 算停摆
        fixedMs: 1000,      // fixed 模式：窗口显示信号到达后延时多久 arm
        fallbackMs: 800,    // stall 模式硬兜底：窗口显示信号到达后最多再等多久就强制 arm
        safetyMs: 3000      // 兜底：窗口显示信号一直没出现时，首帧之后多久用它当锚点
      };

      var armed = false;
      function arm(reason) {
        if (armed) return;
        armed = true;
        t0 = performance.now();          // JS 时间线基准 = 判定可见这一刻
        root.classList.add('is-armed');  // CSS 动画从这一刻起跑（delay 重新计算）
        if (reduced) {
          // 减少动态效果：不提前显示，判定可见后一次性给出终态
          KEYS.forEach(function (k) { reveal(k); });
        } else {
          scheduleReveals();
        }
        maybeFinish();
      }

      // 逐项点亮对齐到"CSS 动画真正起跑"的那一刻。
      // 窗口刚显示时首帧开销（字体、模糊滤镜等）会让动画时钟比 is-armed 晚几十~几百毫秒，
      // 若直接把定时器挂在 arm 上，第一项可能在面板还没淡入时就点亮了。实测取证见开发日志。
      function scheduleReveals() {
        var hexEl = root.querySelector('.bs-hex');
        var anims = (hexEl && hexEl.getAnimations) ? hexEl.getAnimations() : [];
        var a = anims.length ? anims[0] : null;
        var pending = a && a.startTime === null;
        if (pending && performance.now() - t0 < 700) {   // 最多等 700ms，等不到就照常走
          requestAnimationFrame(scheduleReveals);
          return;
        }
        var offset = (a && a.startTime !== null) ? Math.max(0, a.startTime - t0) : 0;
        var base = t0 + offset;   // 目标绝对时刻（与 CSS 动画同一把尺子），不受本函数被调用的早晚影响
        KEYS.forEach(function (k, i) {
          setTimeout(function () { reveal(k); }, Math.max(0, base + REVEAL_AT[i] - performance.now()));
        });
      }

      // ── 窗口显示锚点 + rAF 停摆-恢复检测 ──
      // 锚点只用来定"窗口已显示"这一刻（给硬兜底计时、给停摆-恢复做闸门），它本身不再触发起跑。
      // 硬锚点的正式来源是主进程 show() 之后发来的 'window-shown' IPC；
      // 软锚点（focus）可能在窗口真正显示之前就到达，只能当近似。
      var anchorAt = 0, anchorHard = false, anchorTimer = 0, firstFrameAt = 0, lastFrameAt = 0;

      function scheduleFallback() {
        if (anchorTimer) { clearTimeout(anchorTimer); anchorTimer = 0; }
        var delay = (ARM.mode === 'fixed') ? ARM.fixedMs : ARM.fallbackMs;
        anchorTimer = setTimeout(function () {
          arm((ARM.mode === 'fixed' ? 'fixed' : 'fallback') + delay);
        }, delay);
      }

      // 锚点登记：记下硬/软锚点并（重新）安排兜底定时器。硬锚点只能被第一个硬锚点占据，
      // 所以 IPC 只认最先到的那一次。
      function anchor(why, hard) {
        hard = !!hard;
        if (anchorHard) { return; }              // 已经有准确锚点，不再改
        if (anchorAt && !hard) { return; }       // 软锚点不重复设；硬锚点可以覆盖软锚点并重新计时
        anchorAt = performance.now();
        anchorHard = hard;
        scheduleFallback();
      }

      // 锚点来源 1（硬，正式接口）：主进程 show() 之后发来的 'window-shown' IPC
      if (api && typeof api.onWindowShown === 'function') {
        try { api.onWindowShown(function () { anchor('ipc', true); }); } catch (e) {}
      }
      // 锚点来源 2（软）：窗口获得焦点
      window.addEventListener('focus', function () { anchor('focus', false); });

      function frameWatch(ts) {
        if (armed) return;
        var now = (typeof ts === 'number') ? ts : performance.now();
        if (!firstFrameAt) {
          firstFrameAt = now;
          // 锚点来源 3（软，最深兜底）：IPC 与 focus 都没有时，首帧之后用 safetyMs 兜一下
          setTimeout(function () { anchor('safety', false); }, ARM.safetyMs);
        }
        if (lastFrameAt) {
          var gap = now - lastFrameAt;
          if (gap > ARM.stallMs) {
            lastFrameAt = now;
            // 只在"确实已 show"（硬锚点）之后才认这次恢复：
            // 否则可能是加载期的空档（字体/首绘），认了就等于又抢跑一次。
            if (ARM.mode === 'stall' && anchorHard) { arm('stallResume'); return; }
          }
        }
        lastFrameAt = now;
        if (typeof requestAnimationFrame === 'function') { requestAnimationFrame(frameWatch); }
      }
      // 起跑前一直盯着帧（这段监测本身很轻：一帧一次比较，arm 之后立即退出）
      if (typeof requestAnimationFrame === 'function') { requestAnimationFrame(frameWatch); }

      // ── 超时兜底：10s 仍未完成的项目标红"失败"，覆盖层照常淡出 ──
      setTimeout(function () {
        if (!armed) arm('deadline');     // 兜底：直到此时还没判定过可见，也强制起跑
        KEYS.forEach(function (k) {
          var it = items[k];
          if (!it || !it.el) return;
          if (!it.shown) { it.shown = true; render(it); shownCount++; }
          if (!FINAL[it.state]) setState(k, 'fail', T('boot.detail.timeout'));
        });
        maybeFinish();
      }, Math.max(0, DEADLINE_MS - (performance.now() - SCRIPT_T0)));
    })();
