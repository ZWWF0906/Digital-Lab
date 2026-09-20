// panels/index.js — Panel registry
// 面板名走 i18n：i18n.js 由 dashboard.html 在 <head> 里以经典脚本加载，暴露 window.DigitalLabI18n。
// 名称在渲染时取（getPanelName），语言切换后重建侧栏即可拿到新语言文案。
import { init as initDashboard } from './dashboard.js';
import { init as initDeviceCenter } from './device-center.js';
import { init as initAi } from './ai-assistant.js';
import { init as initTerminal } from './terminal.js';
import { init as initSettings } from './settings.js';

const t = (key, params) => (
  (typeof window !== 'undefined' && window.DigitalLabI18n)
    ? window.DigitalLabI18n.t(key, params)
    : key
);

export const PANELS = [
  { id: 'dashboard',      nameKey: 'nav.dashboard',    icon: '\u25C9', init: initDashboard },
  { id: 'device-center',  nameKey: 'nav.deviceCenter', icon: '\u2302', init: initDeviceCenter },
  { id: 'terminal',       nameKey: 'nav.terminal',     icon: '\u2263', init: initTerminal },
  { id: 'ai',             nameKey: 'nav.ai',           icon: '\u2726', init: initAi },
  { id: 'settings',       nameKey: 'nav.settings',     icon: '\u2699', init: initSettings },
];

export function getPanelById(id) {
  return PANELS.find(p => p.id === id);
}

// 取当前语言下的面板名（语言切换后重新调用即可得到新文案）
export function getPanelName(id) {
  const p = getPanelById(id);
  return p ? t(p.nameKey) : '';
}
