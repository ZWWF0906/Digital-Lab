// i18n.js — 多语言机制：t(key, params) / setLanguage(lang) / getLanguage()
// 渲染进程（经典脚本，暴露 window.DigitalLabI18n）与主进程（require）共用同一份实现。
// 不硬编码任何语言代码：语言清单、默认语言、词典全部来自 locales/index.js。
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(require('./locales/index.js')); }
  else { root.DigitalLabI18n = factory(root.DigitalLabLocales); }
})(typeof self !== 'undefined' ? self : this, function (Locales) {
  'use strict';

  // 清单不可用时退化为"原样返回 key"，避免整个应用起不来
  if (!Locales) {
    Locales = {
      LANGUAGES: [],
      hasLanguage: function () { return false; },
      getDict: function () { return {}; },
      ensureLoaded: function () { return true; },
      getDefaultLanguage: function () { return 'zh-CN'; }
    };
  }

  var current = Locales.getDefaultLanguage();
  var warned = {};   // 同一个缺失 key 只警告一次，避免刷屏

  function interpolate(text, params) {
    return String(text).replace(/\{(\w+)\}/g, function (whole, name) {
      var v = params[name];
      return (v === undefined || v === null) ? whole : String(v);
    });
  }

  function t(key, params) {
    var dict = Locales.getDict(current) || {};
    var s = dict[key];
    if (s === undefined || s === null) {
      if (!warned[key]) {
        warned[key] = true;
        try { console.warn('[i18n] missing key: ' + key + ' (' + current + ')'); } catch (e) {}
      }
      return key;   // 缺失时返回 key 本身，便于定位
    }
    return params ? interpolate(s, params) : s;
  }

  function setLanguage(lang) {
    if (!Locales.hasLanguage(lang)) { return false; }        // 不在清单里就忽略
    if (Locales.ensureLoaded && !Locales.ensureLoaded(lang)) { return false; }
    current = lang;
    return true;
  }

  function getLanguage() { return current; }
  function getLanguages() { return Locales.LANGUAGES || []; }

  return { t: t, setLanguage: setLanguage, getLanguage: getLanguage, getLanguages: getLanguages };
});
