// 主题初始化：在样式渲染前应用，深色为默认。
  // 权威源是应用级 config.json 的 theme（启动期一次 sendSync）；localStorage 只作快速缓存，
  // 两者不一致时以 config.json 为准并回写缓存（强制结束进程会让 localStorage 丢写，config.json 不会）。
  (function () {
    var t = 'dark';
    try { t = localStorage.getItem('digitallab-theme') || 'dark'; } catch (e) {}
    if (t !== 'light') t = 'dark';
    try {
      var api = window.digitalLab;
      if (api && typeof api.getThemeSync === 'function') {
        var t2 = api.getThemeSync();
        if (t2 === 'light' || t2 === 'dark') {
          if (t2 !== t) { try { localStorage.setItem('digitallab-theme', t2); } catch (e) {} }
          t = t2;
        }
      }
    } catch (e) {}
    document.documentElement.setAttribute('data-theme', t);
  })();
