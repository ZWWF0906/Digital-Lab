// panels/device-center.js — 多设备总览中心
// Device Center ≠ Gateway，不是快捷链接中心，是设备状态聚合中心

function statusColor(value, thresholds) {
  if (!thresholds || !thresholds.length) return 'var(--accent)';
  if (value >= thresholds[1]) return 'var(--accent-pink)';
  if (value >= thresholds[0]) return 'var(--accent-amber)';
  return 'var(--accent)';
}

function statusClass(value, thresholds) {
  if (!thresholds || !thresholds.length) return 'ok';
  if (value >= thresholds[1]) return 'danger';
  if (value >= thresholds[0]) return 'warn';
  return 'ok';
}

function deviceCardHTML(device) {
  const online = device.online !== false;
  const status = online
    ? '<span class="mc-status ok"></span>'
    : '<span class="mc-status danger"></span>';
  const opacity = online ? '' : 'style="opacity:0.4"';

  // NAS 额外信息
  let extraInfo = '';
  if (device.type === 'NAS') {
    const parts = [];
    if (device.temperature != null) parts.push(`\u{1F321} ${device.temperature}\u00B0C`);
    if (device.uptime) parts.push(`\u23F1 ${device.uptime}`);
    extraInfo = parts.length ? `<div class="dc-card-extra">${parts.join(' | ')}</div>` : '';
  }

  return `
    <div class="device-card metric-card ${device.type === 'NAS' && !online ? 'offline' : ''}"
         data-device-id="${device.id}" ${opacity}>
      <div class="mc-header">
        ${status}
        <span class="mc-label">${device.type === 'PC' ? '\u{1F4BB}' : '\u{1F4E1}'} ${device.name}</span>
        <span class="dc-card-type">${device.type}</span>
      </div>
      <div class="mc-multi">
        <div class="mc-mini">
          <span class="mc-mini-label">CPU</span>
          <span class="mc-mini-val" style="color:${statusColor(device.cpu, [60, 85])}">${device.cpu.toFixed(1)}%</span>
          <div class="mc-bar-wrap"><div class="mc-bar" style="width:${device.cpu}%;background:${statusColor(device.cpu, [60, 85])}"></div></div>
        </div>
        <div class="mc-mini">
          <span class="mc-mini-label">\u5185\u5b58</span>
          <span class="mc-mini-val" style="color:${statusColor(device.memory, [70, 90])}">${device.memory.toFixed(1)}%</span>
          <div class="mc-bar-wrap"><div class="mc-bar" style="width:${device.memory}%;background:${statusColor(device.memory, [70, 90])}"></div></div>
        </div>
        <div class="mc-mini">
          <span class="mc-mini-label">\u78c1\u76d8</span>
          <span class="mc-mini-val" style="color:${statusColor(device.disk, [75, 92])}">${device.disk.toFixed(1)}%</span>
          <div class="mc-bar-wrap"><div class="mc-bar" style="width:${device.disk}%;background:${statusColor(device.disk, [75, 92])}"></div></div>
        </div>
      </div>
      ${extraInfo}
    </div>`;
}

function detailHTML(device) {
  const online = device.online !== false;
  if (!online) return '';

  // 资源指标卡（含 ID 锚点供 updateDetail 定位）
  const gaugesHTML = `
    <div class="metrics-grid detail-gauges">
      <div class="metric-card">
        <div class="mc-header"><span class="mc-status ${statusClass(device.cpu, [60, 85])}" id="dc-cpu-status"></span><span class="mc-label">CPU</span></div>
        <div class="mc-value-row"><span class="mc-value" id="dc-cpu-val" style="color:${statusColor(device.cpu, [60, 85])}">${device.cpu.toFixed(1)}</span><span class="mc-unit">%</span></div>
        <div class="mc-bar-wrap"><div class="mc-bar" id="dc-cpu-bar" style="width:${device.cpu}%;background:${statusColor(device.cpu, [60, 85])}"></div></div>
      </div>
      <div class="metric-card">
        <div class="mc-header"><span class="mc-status ${statusClass(device.memory, [70, 90])}" id="dc-mem-status"></span><span class="mc-label">\u5185\u5b58</span></div>
        <div class="mc-value-row"><span class="mc-value" id="dc-mem-val" style="color:${statusColor(device.memory, [70, 90])}">${device.memory.toFixed(1)}</span><span class="mc-unit">%</span></div>
        <div class="mc-bar-wrap"><div class="mc-bar" id="dc-mem-bar" style="width:${device.memory}%;background:${statusColor(device.memory, [70, 90])}"></div></div>
      </div>
      <div class="metric-card">
        <div class="mc-header"><span class="mc-status ${statusClass(device.disk, [75, 92])}" id="dc-disk-status"></span><span class="mc-label">\u78c1\u76d8</span></div>
        <div class="mc-value-row"><span class="mc-value" id="dc-disk-val" style="color:${statusColor(device.disk, [75, 92])}">${device.disk.toFixed(1)}</span><span class="mc-unit">%</span></div>
        <div class="mc-bar-wrap"><div class="mc-bar" id="dc-disk-bar" style="width:${device.disk}%;background:${statusColor(device.disk, [75, 92])}"></div></div>
      </div>
    </div>`;

  // NAS 额外信息
  let nasInfoHTML = '';
  if (device.type === 'NAS') {
    nasInfoHTML = '<div class="mc-info" id="dc-nas-info" style="margin-bottom:16px"></div>';
  }

  // 进程表
  const processes = device.processes || [];
  let processTableHTML = '<div class="section-title" style="margin-top:20px">\u8fdb\u7a0b TOP15</div>';
  if (processes.length === 0) {
    processTableHTML += '<div class="mc-empty" id="dc-process-empty">\u6682\u65e0\u6570\u636e</div>';
  } else {
    processTableHTML += `
      <div class="process-panel" style="margin-bottom:16px">
        <table>
          <thead><tr><th>PID</th><th>\u540d\u79f0</th><th>CPU %</th><th>\u5185\u5b58 %</th><th>\u547d\u4ee4</th></tr></thead>
          <tbody id="dc-process-tbody"></tbody>
        </table>
      </div>`;
  }

  // Docker 容器表（仅 NAS）
  let dockerHTML = '';
  if (device.type === 'NAS') {
    dockerHTML = `
      <div class="section-title">Docker \u5bb9\u5668</div>
      <div class="process-panel">
        <table>
          <thead><tr><th>\u540d\u79f0</th><th>\u955c\u50cf</th><th>\u72b6\u6001</th></tr></thead>
          <tbody id="dc-docker-tbody"></tbody>
        </table>
      </div>
      <div class="mc-info" id="dc-docker-summary" style="margin-top:8px;text-align:right"></div>`;
  }

  return `
    <div class="device-detail" id="dc-detail-content">
      <div class="detail-header">
        <span>\u{1F4E1} ${device.name}</span>
        <span style="font-size:0.75rem;color:var(--text-tertiary)">${device.type}</span>
        <button class="detail-close-btn" id="dc-detail-close">\u2715</button>
      </div>
      ${nasInfoHTML}
      ${gaugesHTML}
      ${processTableHTML}
      ${dockerHTML}
    </div>`;
}

/**
 * 更新已存在的详情 DOM（不重建，不触发动画）。
 * 仅修改数值、颜色、进度条和表格内容。
 */
function updateDetail(device) {
  // ── CPU 指标 ──
  const cpuVal = document.getElementById('dc-cpu-val');
  const cpuBar = document.getElementById('dc-cpu-bar');
  const cpuSt = document.getElementById('dc-cpu-status');
  if (cpuVal) {
    cpuVal.textContent = device.cpu.toFixed(1);
    cpuVal.style.color = statusColor(device.cpu, [60, 85]);
  }
  if (cpuBar) {
    cpuBar.style.width = `${device.cpu}%`;
    cpuBar.style.background = statusColor(device.cpu, [60, 85]);
  }
  if (cpuSt) cpuSt.className = `mc-status ${statusClass(device.cpu, [60, 85])}`;

  // ── 内存指标 ──
  const memVal = document.getElementById('dc-mem-val');
  const memBar = document.getElementById('dc-mem-bar');
  const memSt = document.getElementById('dc-mem-status');
  if (memVal) {
    memVal.textContent = device.memory.toFixed(1);
    memVal.style.color = statusColor(device.memory, [70, 90]);
  }
  if (memBar) {
    memBar.style.width = `${device.memory}%`;
    memBar.style.background = statusColor(device.memory, [70, 90]);
  }
  if (memSt) memSt.className = `mc-status ${statusClass(device.memory, [70, 90])}`;

  // ── 磁盘指标 ──
  const diskVal = document.getElementById('dc-disk-val');
  const diskBar = document.getElementById('dc-disk-bar');
  const diskSt = document.getElementById('dc-disk-status');
  if (diskVal) {
    diskVal.textContent = device.disk.toFixed(1);
    diskVal.style.color = statusColor(device.disk, [75, 92]);
  }
  if (diskBar) {
    diskBar.style.width = `${device.disk}%`;
    diskBar.style.background = statusColor(device.disk, [75, 92]);
  }
  if (diskSt) diskSt.className = `mc-status ${statusClass(device.disk, [75, 92])}`;

  // ── NAS 额外信息 ──
  if (device.type === 'NAS') {
    const nasInfo = document.getElementById('dc-nas-info');
    if (nasInfo) {
      const parts = [];
      if (device.temperature != null) parts.push(`\u{1F321} \u6e29\u5ea6: ${device.temperature}\u00B0C`);
      if (device.uptime) parts.push(`\u23F1 \u8fd0\u884c: ${device.uptime}`);
      if (device.host) parts.push(`\u{1F310} ${device.host}`);
      nasInfo.textContent = parts.join(' | ');
    }
  }

  // ── 进程表 ──
  const processTbody = document.getElementById('dc-process-tbody');
  if (processTbody) {
    const processes = device.processes || [];
    processTbody.innerHTML = processes.map(p => `
      <tr>
        <td class="proc-pid">${p.pid || ''}</td>
        <td class="proc-name">${p.name || ''}</td>
        <td class="proc-num">${(p.cpu || 0).toFixed(1)}</td>
        <td class="proc-num">${(p.memory || 0).toFixed(1)}</td>
        <td class="proc-name" style="max-width:260px">${p.command || ''}</td>
      </tr>`).join('');
  }

  // ── Docker 表 ──
  if (device.type === 'NAS') {
    const dockerTbody = document.getElementById('dc-docker-tbody');
    const dockerSummary = document.getElementById('dc-docker-summary');
    const docker = device.docker;
    if (dockerTbody && docker && docker.containers && docker.containers.length > 0) {
      dockerTbody.innerHTML = docker.containers.map(c => `
        <tr>
          <td class="proc-name">${c.name || ''}</td>
          <td class="proc-name" style="max-width:260px">${c.image || ''}</td>
          <td><span class="mc-status ${c.status && c.status.toLowerCase().startsWith('up') ? 'ok' : 'danger'}"></span> ${c.status || ''}</td>
        </tr>`).join('');
      if (dockerSummary) {
        dockerSummary.textContent = `\u25CF \u8fd0\u884c\u4e2d: ${docker.running || 0} \u25CF \u603b\u8ba1: ${docker.total_containers || 0}`;
      }
    }
  }
}

function mapDevices(state) {
  const devices = [];
  const monitor = state.monitor || {};

  // Local PC
  devices.push({
    id: 'local',
    name: '\u672c\u5730\u4e3b\u673a',
    type: 'PC',
    online: true,
    cpu: monitor.cpu || 0,
    memory: monitor.memory || 0,
    disk: monitor.disk || 0,
    processes: monitor.processes || [],
  });

  // NAS devices
  const nas = state.nas || {};
  for (const [name, data] of Object.entries(nas)) {
    devices.push({
      id: `nas-${name}`,
      name,
      type: 'NAS',
      online: data.online !== false,
      host: data.host,
      cpu: data.cpu ?? 0,
      memory: data.memory?.percent ?? 0,
      disk: data.disk?.percent ?? 0,
      temperature: data.temperature,
      uptime: data.uptime,
      processes: data.processes || [],
      docker: data.docker || null,
    });
  }

  return devices;
}

export function init(container, api) {
  let latestState = null;
  let selectedDeviceId = null;
  let detailInitialized = false;  // 详情 DOM 是否已创建（首次渲染后为 true）

  container.innerHTML = `
    <div class="section-title">\u8bbe\u5907\u603b\u89c8</div>
    <div class="device-grid" id="dc-grid"></div>
    <div id="dc-detail"></div>`;

  const deviceGrid = document.getElementById('dc-grid');
  const detailContainer = document.getElementById('dc-detail');

  function renderDevices(state) {
    const devices = mapDevices(state);
    // 设备卡片：直接更新 innerHTML（首次渲染后有 data-animated 标记，跳过入场动画）
    deviceGrid.innerHTML = devices.map(deviceCardHTML).join('');
    deviceGrid.setAttribute('data-animated', '1');

    // 如果当前有选中设备
    if (selectedDeviceId) {
      const selectedDevice = devices.find(d => d.id === selectedDeviceId);
      if (!selectedDevice) return;

      if (detailInitialized) {
        // 后续更新：只改数值，不重建 DOM，不触发动画
        updateDetail(selectedDevice);
      } else {
        // 首次渲染：创建完整 DOM，播放进入动画
        createDetail(selectedDevice);
      }
    }
  }

  function createDetail(device) {
    detailContainer.innerHTML = detailHTML(device);
    // 首次填充数据（detailHTML 中 tbody 为空，由 updateDetail 填充）
    updateDetail(device);
    detailInitialized = true;

    // 关闭按钮
    const closeBtn = document.getElementById('dc-detail-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => {
        selectedDeviceId = null;
        detailInitialized = false;
        detailContainer.innerHTML = '';
        deviceGrid.querySelectorAll('.device-card.selected').forEach(el => el.classList.remove('selected'));
      });
    }
  }

  // 设备卡片点击
  deviceGrid.addEventListener('click', (e) => {
    const card = e.target.closest('.device-card');
    if (!card) return;
    const deviceId = card.dataset.deviceId;

    // Local PC → 导航到 Dashboard
    if (deviceId === 'local') {
      window.dispatchEvent(new CustomEvent('switch-panel', { detail: 'dashboard' }));
      return;
    }

    // 离线设备不可展开
    if (card.classList.contains('offline')) return;

    // 切换选中
    if (selectedDeviceId === deviceId) {
      // 再次点击 → 折叠
      selectedDeviceId = null;
      detailInitialized = false;
      detailContainer.innerHTML = '';
      deviceGrid.querySelectorAll('.device-card.selected').forEach(el => el.classList.remove('selected'));
      return;
    }

    // 选中新设备 → 重置初始化标志，触发完整重建
    selectedDeviceId = deviceId;
    detailInitialized = false;
    deviceGrid.querySelectorAll('.device-card.selected').forEach(el => el.classList.remove('selected'));
    card.classList.add('selected');

    // 渲染详情（优先使用缓存数据）
    const devices = latestState ? mapDevices(latestState) : [];
    const device = devices.find(d => d.id === deviceId);
    if (device) {
      createDetail(device);
    }
  });

  // 订阅状态更新
  const unsubscribe = api.onStateUpdate((state) => {
    latestState = state;
    renderDevices(state);
  });

  return () => unsubscribe();
}