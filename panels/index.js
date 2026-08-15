// panels/index.js — Panel registry
import { init as initDashboard } from './dashboard.js';
import { init as initDeviceCenter } from './device-center.js';
import { init as initAi } from './ai-assistant.js';
import { init as initTerminal } from './terminal.js';
import { init as initSettings } from './settings.js';

export const PANELS = [
  { id: 'dashboard',      name: '仪表盘',   icon: '\u25C9', init: initDashboard },
  { id: 'device-center',  name: '设备中心', icon: '\u2302', init: initDeviceCenter },
  { id: 'terminal',       name: '终端',     icon: '\u2263', init: initTerminal },
  { id: 'ai',             name: 'AI 助手',  icon: '\u2726', init: initAi },
  { id: 'settings',       name: '设置',     icon: '\u2699', init: initSettings },
];

export function getPanelById(id) {
  return PANELS.find(p => p.id === id);
}