// locales/zh-CN.js — 简体中文词典（自注册）
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(require('./index.js')); }
  else { factory(root.DigitalLabLocales); }
})(typeof self !== 'undefined' ? self : this, function (Locales) {
  'use strict';

  var dict = {
    // 侧栏导航（panels/index.js）
    'nav.dashboard':    '仪表盘',
    'nav.deviceCenter': '设备中心',
    'nav.terminal':     '终端',
    'nav.ai':           'AI 助手',
    'nav.settings':     '设置',

    // 主进程：托盘菜单
    'tray.showMain':    '显示主窗口',
    'tray.quit':        '退出',

    // 主进程：快速部署对话框
    'dlg.deploySoon.message': '功能正在开发中，敬请期待',
    'dlg.deploySoon.button':  '知道了',

    // 主进程：AI 记忆删除确认
    'dlg.memoryDelete.message': '警告：删除记忆操作不可逆，可能涉及重要数据，谨慎操作！',
    'dlg.memoryDelete.delete':  '删除',
    'dlg.memoryDelete.cancel':  '取消',

    // 设置面板：语言
    'set.language':     '语言',
    'set.languageHint': '切换后即时生效并自动保存；重启后保持。'
  };

  if (Locales && Locales.register) { Locales.register('zh-CN', dict); }
  return dict;
});
