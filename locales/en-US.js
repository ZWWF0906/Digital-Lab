// locales/en-US.js — English dictionary (self-registering)
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(require('./index.js')); }
  else { factory(root.DigitalLabLocales); }
})(typeof self !== 'undefined' ? self : this, function (Locales) {
  'use strict';

  var dict = {
    // Sidebar navigation (panels/index.js)
    'nav.dashboard':    'Dashboard',
    'nav.deviceCenter': 'Devices',
    'nav.terminal':     'Terminal',
    'nav.ai':           'AI Assistant',
    'nav.settings':     'Settings',

    // Main process: tray menu
    'tray.showMain':    'Show Main Window',
    'tray.quit':        'Quit',

    // Main process: quick deploy dialog
    'dlg.deploySoon.message': 'This feature is under development. Stay tuned.',
    'dlg.deploySoon.button':  'Got it',

    // Main process: AI memory deletion confirmation
    'dlg.memoryDelete.message': 'Warning: deleting the memory is irreversible and may involve important data. Please proceed with care.',
    'dlg.memoryDelete.delete':  'Delete',
    'dlg.memoryDelete.cancel':  'Cancel',

    // Settings panel: language
    'set.language':     'Language',
    'set.languageHint': 'Applies immediately and is saved automatically; kept after restart.',

    // Boot overlay (dashboard.html)
    'boot.selfCheck':      'Startup self-check',
    'boot.item.backend':   'Backend started',
    'boot.item.collector': 'Collector running',
    'boot.item.hardware':  'Hardware ready',
    'boot.item.nas':       'NAS connection',
    'boot.state.wait':     'Waiting',
    'boot.state.pass':     'Passed',
    'boot.state.fail':     'Failed',
    'boot.state.skip':     'Skipped',
    // Dependency details: full-sentence templates, placeholder is {count}
    'boot.detail.frame':          'State frame received',
    'boot.detail.hardwareCount':  '{count} items',
    'boot.detail.nasOnline':      '{count} online',
    'boot.detail.nasNoneOnline':  'No device online',
    'boot.detail.nasUnconfigured': 'No device configured',
    'boot.detail.nasNoState':     'No NAS status',
    'boot.detail.preloadDown':    'Preload unavailable',
    'boot.detail.timeout':        'Timed out'
  };

  if (Locales && Locales.register) { Locales.register('en-US', dict); }
  return dict;
});
