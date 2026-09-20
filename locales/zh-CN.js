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
    'set.languageHint': '切换后即时生效并自动保存；重启后保持。',

    // 启动开屏覆盖层（dashboard.html）
    'boot.selfCheck':      '启动自检',
    'boot.item.backend':   '后端已启动',
    'boot.item.collector': '采集器运行',
    'boot.item.hardware':  '硬件就绪',
    'boot.item.nas':       'NAS 连接',
    'boot.state.wait':     '等待中',
    'boot.state.pass':     '通过',
    'boot.state.fail':     '失败',
    'boot.state.skip':     '跳过',
    // 依赖项详情：整句模板，占位符用 {count}
    'boot.detail.frame':          '已收到状态帧',
    'boot.detail.hardwareCount':  '{count} 项',
    'boot.detail.nasOnline':      '在线 {count} 台',
    'boot.detail.nasNoneOnline':  '无在线设备',
    'boot.detail.nasUnconfigured': '未配置设备',
    'boot.detail.nasNoState':     '无 NAS 状态',
    'boot.detail.preloadDown':    '预加载不可用',
    'boot.detail.timeout':        '超时未就绪'
  };

  if (Locales && Locales.register) { Locales.register('zh-CN', dict); }
  return dict;
});
