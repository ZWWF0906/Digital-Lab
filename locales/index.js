// locales/index.js — 语言清单 + 词典加载器（渲染进程与主进程共用一份）
//
// 扩展方式（新增一种语言只改两处，机制代码不动）：
//   1) 新建 locales/<code>.js，自注册词典：Locales.register('<code>', { ... })
//   2) 在下面 LANGUAGES 数组里加一行 { code, name, nativeName }
// 文件名必须与 code 一致（加载器按 'locales/' + code + '.js' 取文件）。
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(); }
  else { root.DigitalLabLocales = factory(); }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var LANGUAGES = [
    { code: 'zh-CN', name: '简体中文', nativeName: '简体中文' },
    { code: 'en-US', name: 'English',  nativeName: 'English'  },
    { code: 'ja-JP', name: 'Japanese', nativeName: '日本語'    }
  ];
  var FALLBACK = 'zh-CN';     // 词典缺失时的兜底语言
  var dicts = {};
  // 已请求、但脚本尚未执行完的词典：document.write 在解析期插入的脚本要等解析器走到才执行。
  // 这段时间里词典"马上就要有"，调用方可以照常切语言（首帧前一定已就绪）。
  var pending = {};

  function hasLanguage(code) {
    for (var i = 0; i < LANGUAGES.length; i++) { if (LANGUAGES[i].code === code) { return true; } }
    return false;
  }

  function register(code, dict) {
    if (hasLanguage(code) && dict) { dicts[code] = dict; delete pending[code]; }
    return dicts[code];
  }

  function getDict(code) {
    if (dicts[code]) { return dicts[code]; }
    if (pending[code]) { return {}; }   // 正在装载：先返回空表，避免临时拿兜底语言顶替
    return dicts[FALLBACK] || {};
  }

  function isLoaded(code) { return !!dicts[code]; }

  // 系统语言探测：渲染进程用 navigator，主进程/Node 用 Intl（同一份实现两边都能用）
  function systemLocale() {
    try { if (typeof navigator !== 'undefined' && navigator.language) { return navigator.language; } } catch (e) {}
    try { if (typeof Intl !== 'undefined' && Intl.DateTimeFormat) { return Intl.DateTimeFormat().resolvedOptions().locale; } } catch (e) {}
    return '';
  }

  // 默认语言规则：系统语言以 zh 开头用 zh-CN，以 ja 开头用 ja-JP，否则 en-US。
  // 加语言时改这一个函数即可（外加 LANGUAGES 一行与词典文件）。
  function getDefaultLanguage() {
    var l = String(systemLocale() || '').toLowerCase();
    if (l.indexOf('zh') === 0) { return 'zh-CN'; }
    if (l.indexOf('ja') === 0) { return 'ja-JP'; }
    return 'en-US';
  }

  // 载入词典文件：浏览器在解析期用 document.write 同步插入（保证首帧前可用）；Node 侧用 require。
  function loadDictFile(code) {
    if (!hasLanguage(code)) { return false; }
    if (isLoaded(code)) { return true; }
    if (pending[code]) { return true; }   // 已经插入过，不要重复 write
    try {
      if (typeof document !== 'undefined' && document.write && document.readyState === 'loading') {
        document.write('<script src="locales/' + code + '.js"><\/script>');
        // 解析期插入的脚本由解析器紧接着执行，早于页面末尾的 defer/module 脚本
        // （导航与各面板的首帧渲染都在那里），因此这里就按"可用"返回。
        pending[code] = true;
        return true;
      }
    } catch (e) {}
    try {
      if (typeof require === 'function') { require('./' + code + '.js'); return isLoaded(code); }
    } catch (e) {}
    return false;
  }

  function ensureLoaded(code) { return isLoaded(code) ? true : loadDictFile(code); }

  // 启动期把清单里的词典全部装好（语言很少，一次装完最省事，运行时切换就不需要再加载）
  function preloadAll() {
    for (var i = 0; i < LANGUAGES.length; i++) { if (!isLoaded(LANGUAGES[i].code)) { loadDictFile(LANGUAGES[i].code); } }
    return Object.keys(dicts);
  }

  return {
    LANGUAGES: LANGUAGES,
    FALLBACK: FALLBACK,
    hasLanguage: hasLanguage,
    isLoaded: isLoaded,
    register: register,
    getDict: getDict,
    ensureLoaded: ensureLoaded,
    preloadAll: preloadAll,
    getDefaultLanguage: getDefaultLanguage
  };
});
