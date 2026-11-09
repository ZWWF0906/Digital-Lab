// 开屏覆盖层静态文案替换：解析到这里就同步跑完（首帧前），语言来自 <head> 里已定好的 i18n 实例。
    (function () {
      var I = window.DigitalLabI18n;
      if (!I || typeof I.t !== 'function') return;
      var root = document.getElementById('boot-splash');
      if (!root) return;
      var nodes = root.querySelectorAll('[data-i18n]');
      for (var i = 0; i < nodes.length; i++) {
        nodes[i].textContent = I.t(nodes[i].getAttribute('data-i18n'));
      }
    })();
