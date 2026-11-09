// 语言初始化：与主题同一位置、同一时机（首帧前完成）。
  // 优先级：config.json（启动期一次 sendSync）→ localStorage 缓存 → 系统语言（locales/index.js 的默认语言函数）。
  (function () {
    try { if (window.DigitalLabLocales && window.DigitalLabLocales.preloadAll) { window.DigitalLabLocales.preloadAll(); } } catch (e) {}
    var lang = null;
    try {
      var api = window.digitalLab;
      if (api && typeof api.getLanguageSync === 'function') { lang = api.getLanguageSync(); }
    } catch (e) {}
    if (!lang) { try { lang = localStorage.getItem('digitallab-lang'); } catch (e) {} }
    if (!lang && window.DigitalLabLocales) { lang = window.DigitalLabLocales.getDefaultLanguage(); }
    var ok = false;
    try { ok = !!(window.DigitalLabI18n && window.DigitalLabI18n.setLanguage(lang)); } catch (e) {}
    if (!ok && window.DigitalLabI18n) { lang = window.DigitalLabI18n.getLanguage(); }
    try { localStorage.setItem('digitallab-lang', lang); } catch (e) {}
    document.documentElement.setAttribute('lang', lang);
  })();
