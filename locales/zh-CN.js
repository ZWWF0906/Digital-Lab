// locales/zh-CN.js — 简体中文词典（自注册）
(function (root, factory) {
  if (typeof module === 'object' && module.exports) { module.exports = factory(require('./index.js')); }
  else { factory(root.DigitalLabLocales); }
})(typeof self !== 'undefined' ? self : this, function (Locales) {
  'use strict';

  var dict = {
    // ── 通用词（多面板共用） ──
    'common.ok':            '确定',
    'common.cancel':        '取消',
    'common.delete':        '删除',
    'common.close':         '关闭',
    'common.tip.title':     '提示',
    'common.tip.body':      '功能仍在测试阶段，可能会出现异常',
    'common.saveFailed':    '保存失败: {message}',
    'common.unknownError':  '未知错误',

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
    'boot.detail.timeout':        '超时未就绪',

    // 仪表盘面板（panels/dashboard.js）
    'dash.section.realtime': '实时监控',
    'dash.section.nas':      'NAS 设备',
    'dash.section.local':    '本地详情',
    'dash.metric.cpu':       'CPU',
    'dash.metric.gpu':       'GPU',
    'dash.metric.memory':    '内存',
    'dash.metric.disk':      '磁盘',
    'dash.metric.network':   '网络',
    'dash.hw.title':         '硬件信息',
    'dash.proc.title':       '进程 Top 15',
    'dash.hw.cpu':           '处理器',
    'dash.hw.gpu':           '显卡',
    'dash.hw.memory':        '内存',
    'dash.hw.disk':          '硬盘',
    'dash.hw.system':        '系统',
    'dash.hw.cpuDetail':     '{cores} 核 · {threads} 线程',
    'dash.nasHw.collecting': '硬件信息采集中...',
    'dash.nasHw.cores':      '核心数',
    'dash.unknown':          '未知',
    'dash.notDetected':      '未检测到',
    'dash.loading':          '加载中...',
    'dash.proc.name':        '名称',
    'dash.proc.memory':      '内存 %',
    'dash.proc.empty':       '暂无数据',
    'dash.nas.empty':        '未配置 NAS 设备，请在设置中添加',
    'dash.nas.retry':        '重试',
    'dash.nas.retrying':     '重试中...',

    // 设备中心面板（panels/device-center.js）
    'dev.section.overview':  '设备总览',
    'dev.device.local':      '本地主机',
    'dev.card.memory':       '内存',
    'dev.card.disk':         '磁盘',
    'dev.section.processes': '进程 TOP15',
    'dev.empty':             '暂无数据',
    'dev.col.name':          '名称',
    'dev.col.memory':        '内存 %',
    'dev.col.command':       '命令',
    'dev.docker.title':      'Docker 容器',
    'dev.col.image':         '镜像',
    'dev.col.status':        '状态',
    // NAS 信息行与 Docker 汇总：整句模板，占位符按名取值
    'dev.nas.temperature':   '温度: {temp}°C',
    'dev.nas.uptime':        '运行: {uptime}',
    'dev.docker.summary':    '● 运行中: {running} ● 总计: {total}',

    // 终端面板（panels/terminal.js）—— 提示弹窗文案已抽到 common.tip.* 共用
    'term.placeholder.title': 'NAS 终端',
    'term.placeholder.desc':  '暂无可用 NAS 设备',
    'term.placeholder.btn':   '前往设置添加 NAS',
    'term.offline':          'NAS 设备当前离线',
    // 终端内提示行：整句模板；[ERROR] 前缀与 ANSI 颜色码留在代码里，不进词典
    'term.connecting':       '正在连接 {name}...',
    'term.error.unknown':    '连接失败，未知错误',
    'term.error.ssh':        'SSH 连接失败: {message}',

    // AI 助手面板（panels/ai-assistant.js）—— 提示弹窗文案已抽到 common.tip.* 共用
    'ai.provider.ollama':   'Ollama 本地',
    'ai.provider.cloud':    '云端 API',
    'ai.btn.settings':      '设置',
    'ai.btn.deploy':        '快速部署',
    'ai.btn.send':          '发送',
    'ai.greeting':          '你好！我是 DigitalLab AI 助手。选择模型后即可开始对话。',
    'ai.input.placeholder': '输入消息... (Enter 发送)',
    'ai.context.title':     '系统状态',
    'ai.ctx.performance':   '性能',
    'ai.ctx.memoryRow':     '内存: {value}%',
    'ai.ctx.diskRow':       '磁盘: {value}%',
    'ai.ctx.hardware':      '硬件',
    'ai.ctx.memoryGb':      '内存: {value} GB',
    'ai.ctx.system':        '系统: {os} {edition}',
    'ai.ctx.unknown':       '未知',
    'ai.ctx.none':          '无',
    'ai.ctx.nas':           'NAS 设备',
    'ai.memory.remembered': '已记住：{item}',
    'ai.status.thinking':   '思考中...',
    'ai.emptyReply':        '（本次无正文输出）',

    // 设置面板（panels/settings.js）
    'set.tab.nas':        'NAS 设备',
    'set.tab.ai':         'AI 配置',
    'set.tab.collect':    '采集设置',
    'set.tab.software':   '软件',
    'set.tab.about':      '关于',
    // NAS 设备分页
    'set.nas.list':       'NAS 设备列表',
    'set.nas.empty':      '暂无设备，点击下方按钮添加',
    'set.nas.addBtn':     '+ 添加设备',
    'set.nas.saveAll':    '保存全部',
    'set.nas.unnamed':    '未命名设备',
    'set.nas.noHost':     '未配置主机',
    'set.nas.edit':       '编辑',
    'set.nas.mockTitle':  '示例 NAS',
    'set.nas.mockDesc':   '用于开发测试，模拟真实 NAS 数据',
    // 设备编辑对话框
    'set.dev.editTitle':  '编辑设备',
    'set.dev.addTitle':   '添加设备',
    'set.dev.saveEdit':   '保存修改',
    'set.dev.name':       '名称',
    'set.dev.host':       '主机',
    'set.dev.port':       '端口',
    'set.dev.username':   '用户名',
    'set.dev.password':   '密码',
    'set.dev.namePh':     '设备名称',
    'set.dev.hostPh':     'IP 地址',
    'set.dev.userPh':     'SSH 用户名',
    'set.dev.passPh':     'SSH 密码',
    'set.dev.test':       '测试连接',
    'set.dev.testing':    '测试中...',
    'set.dev.testOk':     '✓ 连接成功',
    'set.dev.testFail':   '✗ {message}',
    'set.dev.connFailed': '连接失败',
    // AI 配置分页（提供方名称复用 ai.provider.*，不重复定义）
    'set.ai.providerTitle':    'AI 提供方',
    'set.ai.defaultModel':     '默认模型',
    'set.ai.addr':             '地址',
    'set.ai.model':            '模型',
    'set.ai.memoryTitle':      'AI 记忆',
    'set.ai.memoryEnable':     '启用 AI 记忆',
    'set.ai.memoryEnableHint': '开启后，AI 会记住你确认过的长期偏好',
    'set.ai.memoryDir':        '存储目录',
    'set.ai.memoryDirPh':      '默认 %APPDATA%\\DigitalLab\\memory',
    'set.ai.chooseDir':        '选择目录',
    'set.ai.viewMemory':       '查看记忆',
    'set.ai.clearMemory':      '清空记忆',
    'set.ai.save':             '保存 AI 配置',
    // 记忆存储目录对话框
    'set.memDir.title':   '选择记忆存储目录',
    'set.memDir.label':   '目录',
    'set.memDir.ph':      '留空使用默认目录',
    'set.memDir.hint1':   '填写绝对路径；留空表示使用默认目录 %APPDATA%\\DigitalLab\\memory。',
    'set.memDir.hint2':   '更改目录并保存后，旧记忆文件会复制到新目录，旧文件保留。',
    'set.memDir.updated': '目录已更新，保存后生效',
    // 记忆列表
    'set.mem.loading':            '读取中...',
    'set.mem.readFailed':         '记忆读取失败',
    'set.mem.empty':              '暂无记忆',
    'set.mem.deleted':            '已删除该条记忆',
    'set.mem.deleteFailed':       '删除失败',
    'set.mem.deleteFailedDetail': '删除失败: {message}',
    'set.mem.cleared':            '记忆已清空',
    'set.mem.clearFailed':        '清空失败',
    'set.mem.clearFailedDetail':  '清空失败: {message}',
    // 采集设置分页
    'set.collect.params':        '采集参数',
    'set.collect.localInterval': '本地采集间隔',
    'set.collect.nasInterval':   'NAS 采集间隔',
    'set.collect.seconds':       '秒',
    'set.collect.thresholds':    '监控阈值',
    'set.collect.cpuAlarm':      'CPU 告警',
    'set.collect.memAlarm':      '内存告警',
    'set.collect.diskAlarm':     '磁盘告警',
    'set.collect.save':          '保存采集设置',
    // 软件分页（语言那一行沿用阶段 1 的 set.language / set.languageHint）
    'set.soft.display':          '显示',
    'set.soft.hwAccel':          '硬件加速',
    'set.soft.hwAccelHint':      '关闭后可解决虚拟机窗口不显示问题，但性能会降低。修改后需重启应用。',
    'set.soft.theme':            '主题',
    'set.soft.themeDark':        '深色（默认）',
    'set.soft.themeLight':       '浅色',
    'set.soft.themeHint':        '切换后即时生效并自动保存；浅色主题下终端面板仍保持深色。',
    'set.soft.splash':           '开屏动画',
    'set.soft.splashHint':       '关闭后启动直接进入主界面；下次启动生效。',
    'set.soft.loadFailed':       '加载失败',
    'set.soft.splashOn':         '开屏动画已开启，下次启动生效',
    'set.soft.splashOff':        '开屏动画已关闭，下次启动生效',
    'set.soft.hwOn':             '硬件加速已启用，请重启应用生效',
    'set.soft.hwOff':            '硬件加速已关闭，请重启应用生效',
    'set.soft.themeLightDone':   '已切换至浅色主题',
    'set.soft.themeDarkDone':    '已切换至深色主题',
    'set.lang.unsupported':      '不支持的语言 {lang}',
    // 关于分页
    'set.about.slogan':   '个人数字实验室',
    'set.about.features': '仪表盘 · 终端 · AI 助手 · 系统监控',
    'set.about.author':   '作者：ZWWF0906',
    'set.about.license':  'DigitalLab 开源软件，遵循 MIT 许可',
    'set.about.feedback': '问题反馈',
    // 问题反馈对话框
    'set.fb.title':       '问题反馈与举报',
    'set.fb.choose':      '请选择反馈方式',
    'set.fb.note1':       '如遇 AI 生成不当内容，请一并在此反馈',
    'set.fb.note2':       '我们将在收到反馈后尽快处理',
    'set.fb.mail':        '✉ 邮件反馈',
    'set.fb.github':      'GitHub 反馈',
    'set.fb.close':       '关闭',
    'set.fb.mailSubject': 'DigitalLab 问题反馈',
    // 保存结果提示
    'set.saved':        '配置已保存',
    'set.savedPartial': '配置已保存，部分组件重载异常',

    // 外壳（dashboard.html）
    'nav.hint.terminalNoNas': '请先在设置中添加并连接 NAS 设备',
    'boot.fail.preload':      '预加载失败，请重启应用',
    'boot.fail.panel':        '面板加载失败',

    // 开发者控制台日志（只在 DevTools 里可见，但同样走词典，保证中英一致）
    'log.aiMemory.passthrough':   '[AI记忆] 直通路径：ai_done.memory 条数={count}',
    'log.aiMemory.fallback':      '[AI记忆] 兜底路径：列表差异新增={count}',
    'log.aiMemory.noConfirmApi':  '[AI记忆] 当前 preload 未提供 confirmMemoryDelete，取消删除',
    'log.aiMemory.confirmFailed': '[AI记忆] 删除确认调用失败，取消删除: {error}',
    'log.deploy.noApi':           '[快速部署] 当前 preload 未提供 confirmQuickDeploy',
    'log.deploy.dialogFailed':    '[快速部署] 对话框调用失败: {error}',
    'log.config.loadFailed':      '加载配置失败: {error}',

    // ── 后端结构化错误（阶段 4a）：code 与后端返回的 code 完全同名 ──
    // AI 错误（core/ai_client.py 的 _err(...)）
    'ai.err.ollamaNotRunning':     '本地模型未接入，请确认 Ollama 服务已启动',
    'ai.err.cloudUnreachable':     '云端模型未接入，无法连接到 API 服务器',
    'ai.err.ollamaBadAddress':     '本地模型未接入，无法解析 Ollama 地址，请检查地址配置',
    'ai.err.cloudBadAddress':      '云端模型未接入，无法解析 API 地址，请检查地址配置',
    'ai.err.ollamaTimeout':        '本地模型响应超时，请检查 Ollama 服务是否正常运行',
    'ai.err.cloudTimeout':         '云端模型响应超时，请检查网络连接或稍后重试',
    'ai.err.tlsInvalid':           '安全连接失败，API 服务器证书无效',
    'ai.err.ollamaRequestFailed':  '本地模型请求失败（{detail}）',
    'ai.err.cloudRequestFailed':   '云端模型请求失败（{detail}）',
    'ai.err.notConfigured':        '未配置 AI 参数，请在设置面板中配置',
    'ai.err.ollamaModelMissing':   '本地模型未接入，模型 {model} 未找到，请确认已通过 ollama pull 下载',
    'ai.err.ollamaHttpError':      '本地模型未接入，服务返回异常 (HTTP {status})',
    'ai.err.cloudNoApiKey':        '云端模型未接入，请在设置中填写 API Key',
    'ai.err.cloudInvalidKey':      '云端模型未接入，API Key 无效或已过期，请检查设置',
    'ai.err.cloudNoBalance':       '云端模型欠费，请充值后重试',
    'ai.err.cloudNoPermission':    '云端模型未接入，API Key 无权限访问该模型',
    'ai.err.cloudRateLimited':     '云端模型请求过于频繁，请稍后重试',
    'ai.err.cloudUnavailable':     '云端模型服务暂时不可用，请稍后重试',
    'ai.err.cloudHttpError':       '云端模型返回异常 (HTTP {status})',
    'ai.err.internal':             'AI 请求内部错误：{detail}',
    // 终端错误（main.py 的 ssh_terminal_init）
    'term.err.deviceNotConfigured': '未找到设备配置: {host}',
    'term.err.deviceUserMissing':   '设备未配置用户名: {host}',
    // 通用网络错误（main.py 的 test_nas_connection）
    'net.connectFailed':            '连接失败: {detail}',
    // 配置重载（main.py 的 reload_config；当前界面不显示，留给后续使用）
    'cfg.reloaded':                 '配置已重载',
    'cfg.reloadedWithErrors':       '配置已重载（部分错误）'
  };

  if (Locales && Locales.register) { Locales.register('zh-CN', dict); }
  return dict;
});
