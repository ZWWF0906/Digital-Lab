// locales/en-US.js — English dictionary (self-registering)
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(require('./index.js')); }
  else { factory(root.DigitalLabLocales); }
})(typeof self !== 'undefined' ? self : this, function (Locales) {
  'use strict';

  var dict = {
    // ── Shared words (used by several panels) ──
    'common.ok':            'OK',
    'common.cancel':        'Cancel',
    'common.delete':        'Delete',
    'common.close':         'Close',
    'common.tip.title':     'Notice',
    'common.tip.body':      'This feature is still in testing and may behave unexpectedly',
    'common.saveFailed':    'Save failed: {message}',
    'common.unknownError':  'Unknown error',

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
    'boot.detail.timeout':        'Timed out',

    // Dashboard panel (panels/dashboard.js)
    'dash.section.realtime': 'Realtime Monitoring',
    'dash.section.nas':      'NAS Devices',
    'dash.section.local':    'Local Details',
    'dash.metric.cpu':       'CPU',
    'dash.metric.gpu':       'GPU',
    'dash.metric.memory':    'Memory',
    'dash.metric.disk':      'Disk',
    'dash.metric.network':   'Network',
    'dash.hw.title':         'Hardware Info',
    'dash.proc.title':       'Top 15 Processes',
    'dash.hw.cpu':           'Processor',
    'dash.hw.gpu':           'Graphics Card',
    'dash.hw.memory':        'Memory',
    'dash.hw.disk':          'Drive',
    'dash.hw.system':        'System',
    'dash.hw.cpuDetail':     '{cores} cores · {threads} threads',
    'dash.nasHw.collecting': 'Collecting hardware info...',
    'dash.nasHw.cores':      'Cores',
    'dash.unknown':          'Unknown',
    'dash.notDetected':      'Not detected',
    'dash.loading':          'Loading...',
    'dash.proc.name':        'Name',
    'dash.proc.memory':      'Memory %',
    'dash.proc.empty':       'No data',
    'dash.nas.empty':        'No NAS device configured, add one in Settings',
    'dash.nas.retry':        'Retry',
    'dash.nas.retrying':     'Retrying...',

    // Device Center panel (panels/device-center.js)
    'dev.section.overview':  'Device Overview',
    'dev.device.local':      'Local Host',
    'dev.card.memory':       'Memory',
    'dev.card.disk':         'Disk',
    'dev.section.processes': 'Top 15 Processes',
    'dev.empty':             'No data',
    'dev.col.name':          'Name',
    'dev.col.memory':        'Memory %',
    'dev.col.command':       'Command',
    'dev.docker.title':      'Docker Containers',
    'dev.col.image':         'Image',
    'dev.col.status':        'Status',
    // NAS info line and Docker summary: full-sentence templates
    'dev.nas.temperature':   'Temp: {temp}°C',
    'dev.nas.uptime':        'Uptime: {uptime}',
    'dev.docker.summary':    '● Running: {running} ● Total: {total}',

    // Terminal panel (panels/terminal.js) — tip modal text now shared via common.tip.*
    'term.placeholder.title': 'NAS Terminal',
    'term.placeholder.desc':  'No NAS device available',
    'term.placeholder.btn':   'Add a NAS in Settings',
    'term.offline':          'NAS devices are currently offline',
    // In-terminal notice lines: full-sentence templates; the [ERROR] prefix and ANSI codes stay in code
    'term.connecting':       'Connecting to {name}...',
    'term.error.unknown':    'Connection failed, unknown error',
    'term.error.ssh':        'SSH connection failed: {message}',

    // AI assistant panel (panels/ai-assistant.js) — tip modal text now shared via common.tip.*
    'ai.provider.ollama':   'Ollama Local',
    'ai.provider.cloud':    'Cloud API',
    'ai.btn.settings':      'Settings',
    'ai.btn.deploy':        'Quick Deploy',
    'ai.btn.send':          'Send',
    'ai.greeting':          'Hi! I am the DigitalLab AI assistant. Pick a model to start chatting.',
    'ai.input.placeholder': 'Type a message... (Enter to send)',
    'ai.context.title':     'System Status',
    'ai.ctx.performance':   'Performance',
    'ai.ctx.memoryRow':     'Memory: {value}%',
    'ai.ctx.diskRow':       'Disk: {value}%',
    'ai.ctx.hardware':      'Hardware',
    'ai.ctx.memoryGb':      'Memory: {value} GB',
    'ai.ctx.system':        'System: {os} {edition}',
    'ai.ctx.unknown':       'Unknown',
    'ai.ctx.none':          'None',
    'ai.ctx.nas':           'NAS Devices',
    'ai.memory.remembered': 'Remembered: {item}',
    'ai.status.thinking':   'Thinking...',
    'ai.emptyReply':        '(No text output this time)',

    // Settings panel (panels/settings.js)
    'set.tab.nas':        'NAS Devices',
    'set.tab.ai':         'AI Config',
    'set.tab.collect':    'Collection',
    'set.tab.software':   'Software',
    'set.tab.about':      'About',
    // NAS devices tab
    'set.nas.list':       'NAS Devices',
    'set.nas.empty':      'No devices yet — use the button below to add one',
    'set.nas.addBtn':     '+ Add Device',
    'set.nas.saveAll':    'Save All',
    'set.nas.unnamed':    'Unnamed device',
    'set.nas.noHost':     'No host configured',
    'set.nas.edit':       'Edit',
    'set.nas.mockTitle':  'Sample NAS',
    'set.nas.mockDesc':   'For development testing; simulates real NAS data',
    // Device editor dialog
    'set.dev.editTitle':  'Edit Device',
    'set.dev.addTitle':   'Add Device',
    'set.dev.saveEdit':   'Save Changes',
    'set.dev.name':       'Name',
    'set.dev.host':       'Host',
    'set.dev.port':       'Port',
    'set.dev.username':   'Username',
    'set.dev.password':   'Password',
    'set.dev.namePh':     'Device name',
    'set.dev.hostPh':     'IP address',
    'set.dev.userPh':     'SSH username',
    'set.dev.passPh':     'SSH password',
    'set.dev.test':       'Test Connection',
    'set.dev.testing':    'Testing...',
    'set.dev.testOk':     '✓ Connected',
    'set.dev.testFail':   '✗ {message}',
    'set.dev.connFailed': 'Connection failed',
    // AI config tab (provider names reuse ai.provider.*, no duplicate keys)
    'set.ai.providerTitle':    'AI Provider',
    'set.ai.defaultModel':     'Default Model',
    'set.ai.addr':             'Address',
    'set.ai.model':            'Model',
    'set.ai.memoryTitle':      'AI Memory',
    'set.ai.memoryEnable':     'Enable AI Memory',
    'set.ai.memoryEnableHint': 'When enabled, the AI remembers the long-term preferences you confirm',
    'set.ai.memoryDir':        'Storage Directory',
    'set.ai.memoryDirPh':      'Default %APPDATA%\\DigitalLab\\memory',
    'set.ai.chooseDir':        'Choose Directory',
    'set.ai.viewMemory':       'View Memory',
    'set.ai.clearMemory':      'Clear Memory',
    'set.ai.save':             'Save AI Config',
    // Memory directory dialog
    'set.memDir.title':   'Choose Memory Storage Directory',
    'set.memDir.label':   'Directory',
    'set.memDir.ph':      'Leave empty to use the default directory',
    'set.memDir.hint1':   'Enter an absolute path; leave it empty to use the default %APPDATA%\\DigitalLab\\memory.',
    'set.memDir.hint2':   'After you change the directory and save, existing memory files are copied to the new directory and the old files are kept.',
    'set.memDir.updated': 'Directory updated; takes effect after saving',
    // Memory list
    'set.mem.loading':            'Loading...',
    'set.mem.readFailed':         'Failed to read memory',
    'set.mem.empty':              'No memories yet',
    'set.mem.deleted':            'Memory entry deleted',
    'set.mem.deleteFailed':       'Delete failed',
    'set.mem.deleteFailedDetail': 'Delete failed: {message}',
    'set.mem.cleared':            'Memory cleared',
    'set.mem.clearFailed':        'Clear failed',
    'set.mem.clearFailedDetail':  'Clear failed: {message}',
    // Collection tab
    'set.collect.params':        'Collection Parameters',
    'set.collect.localInterval': 'Local Collection Interval',
    'set.collect.nasInterval':   'NAS Collection Interval',
    'set.collect.seconds':       's',
    'set.collect.thresholds':    'Monitoring Thresholds',
    'set.collect.cpuAlarm':      'CPU Alert',
    'set.collect.memAlarm':      'Memory Alert',
    'set.collect.diskAlarm':     'Disk Alert',
    'set.collect.save':          'Save Collection Settings',
    // Software tab (the language row keeps phase 1's set.language / set.languageHint)
    'set.soft.display':          'Display',
    'set.soft.hwAccel':          'Hardware Acceleration',
    'set.soft.hwAccelHint':      'Turning this off can fix the window not showing in virtual machines, at the cost of performance. A restart is required after changing it.',
    'set.soft.theme':            'Theme',
    'set.soft.themeDark':        'Dark (default)',
    'set.soft.themeLight':       'Light',
    'set.soft.themeHint':        'Applies immediately and is saved automatically; the terminal panel stays dark in the light theme.',
    'set.soft.splash':           'Splash Animation',
    'set.soft.splashHint':       'When off, the app goes straight to the main window; takes effect on the next start.',
    'set.soft.loadFailed':       'Load failed',
    'set.soft.splashOn':         'Splash animation enabled; takes effect on the next start',
    'set.soft.splashOff':        'Splash animation disabled; takes effect on the next start',
    'set.soft.hwOn':             'Hardware acceleration enabled; restart the app to apply',
    'set.soft.hwOff':            'Hardware acceleration disabled; restart the app to apply',
    'set.soft.themeLightDone':   'Switched to the light theme',
    'set.soft.themeDarkDone':    'Switched to the dark theme',
    'set.lang.unsupported':      'Unsupported language: {lang}',
    // About tab
    'set.about.slogan':   'Personal Digital Laboratory',
    'set.about.features': 'Dashboard · Terminal · AI Assistant · System Monitoring',
    'set.about.author':   'Author: ZWWF0906',
    'set.about.license':  'DigitalLab is open-source software licensed under MIT',
    'set.about.feedback': 'Feedback',
    // Feedback dialog
    'set.fb.title':       'Feedback & Reports',
    'set.fb.choose':      'Choose how to send feedback',
    'set.fb.note1':       'If you come across inappropriate AI-generated content, please report it here as well',
    'set.fb.note2':       'We will look into it as soon as we receive your feedback',
    'set.fb.mail':        '✉ Email Feedback',
    'set.fb.github':      'GitHub Feedback',
    'set.fb.close':       'Close',
    'set.fb.mailSubject': 'DigitalLab Feedback',
    // Save result toasts
    'set.saved':        'Configuration saved',
    'set.savedPartial': 'Configuration saved, but some components failed to reload',

    // Shell (dashboard.html)
    'nav.hint.terminalNoNas': 'Add and connect a NAS device in Settings first',
    'boot.fail.preload':      'Preload failed. Please restart the app',
    'boot.fail.panel':        'Failed to load panel',

    // Developer console logs (DevTools only, but still go through the dictionary)
    'log.aiMemory.passthrough':   '[AI memory] passthrough path: ai_done.memory count={count}',
    'log.aiMemory.fallback':      '[AI memory] fallback path: new list entries={count}',
    'log.aiMemory.noConfirmApi':  '[AI memory] preload does not provide confirmMemoryDelete; delete cancelled',
    'log.aiMemory.confirmFailed': '[AI memory] delete confirmation call failed; delete cancelled: {error}',
    'log.deploy.noApi':           '[Quick deploy] preload does not provide confirmQuickDeploy',
    'log.deploy.dialogFailed':    '[Quick deploy] dialog call failed: {error}',
    'log.config.loadFailed':      'Failed to load configuration: {error}'
  };

  if (Locales && Locales.register) { Locales.register('en-US', dict); }
  return dict;
});
