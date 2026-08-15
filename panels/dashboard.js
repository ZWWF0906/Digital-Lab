// panels/dashboard.js — 5 Metric Cards + NAS Cards + 可折叠硬件/进程子区域
const METRICS = [
  { key: 'cpu', label: 'CPU', unit: '%', icon: '\u25C9', threshold: [60, 85] },
  { key: 'memory', label: '内存', unit: '%', icon: '\u25A0', threshold: [70, 90] },
  { key: 'disk', label: '磁盘', unit: '%', icon: '\u25A3', threshold: [75, 92] },
  { key: 'network', label: '网络', unit: 'Mbps', icon: '\u21CC', threshold: [] },
  { key: 'gpu', label: 'GPU', unit: '%', icon: '\u25C7', threshold: [70, 88] },
];

function statusColor(value, thresholds) {
  if (!thresholds.length) return 'var(--accent)';
  if (value >= thresholds[1]) return 'var(--accent-pink)';
  if (value >= thresholds[0]) return '#fbbf24';
  return 'var(--accent)';
}

function statusClass(value, thresholds) {
  if (!thresholds.length) return 'ok';
  if (value >= thresholds[1]) return 'danger';
  if (value >= thresholds[0]) return 'warn';
  return 'ok';
}

function trendPolyline(points, width, height, maxVal) {
  if (!points || points.length < 2) return '';
  const xStep = width / (points.length - 1);
  const max = Math.max(maxVal || 1, ...points, 1);
  const yScale = height / max;
  return points.map((v, i) => {
    const x = i * xStep;
    const y = height - (v * yScale);
    return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${Math.max(0, y).toFixed(1)}`;
  }).join(' ');
}

function fmtBytes(n) {
  if (!n) return '0 B';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + ' ' + u[i];
}

function renderProcesses(processes) {
  const tbody = document.getElementById('proc-tbody');
  if (!tbody) return;
  if (!processes || !processes.length) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
    return;
  }
  tbody.innerHTML = processes.map(p => `
    <tr>
      <td class="proc-name">${(p.name || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</td>
      <td class="proc-num">${(p.cpu || 0).toFixed(1)}</td>
      <td class="proc-num">${(p.memory || 0).toFixed(1)}</td>
      <td class="proc-num">${fmtBytes(p.rss)}</td>
      <td class="proc-pid">${p.pid}</td>
    </tr>`).join('');
}

function renderHardwareLocal(hardware) {
  const grid = document.getElementById('hw-grid');
  if (!grid || !hardware) return;

  const cards = [];
  const cpu = hardware.cpu;
  if (cpu) {
    cards.push({
      icon: '\u{1F5A5}', title: '处理器',
      model: cpu.model || '未知',
      detail: (cpu.cores ? `${cpu.cores} 核 · ${cpu.threads} 线程` : '') +
              (cpu.freq_current ? ` · ${cpu.freq_current} GHz` : ''),
    });
  }
  const gpu = hardware.gpu;
  if (gpu) {
    cards.push({
      icon: '\u{1F3AE}', title: '显卡',
      model: gpu.name || '未检测到',
      detail: (gpu.vram_gb ? `${gpu.vram_gb} GB` : '') +
              (gpu.vram_type ? ` ${gpu.vram_type}` : ''),
    });
  }
  const mem = hardware.memory;
  if (mem) {
    cards.push({
      icon: '\u{1F4BE}', title: '内存',
      model: `${mem.total_gb || '-'} GB`,
      detail: `${mem.type || ''} ${mem.frequency || ''}`,
    });
  }
  const disk = hardware.disk;
  if (disk) {
    cards.push({
      icon: '\u{1F4BF}', title: '硬盘',
      model: `${disk.capacity_gb || '-'} GB`,
      detail: disk.model ? disk.model.slice(0, 30) : (disk.type || ''),
    });
  }
  const sys = hardware.system;
  if (sys) {
    cards.push({
      icon: '\u2699', title: '系统',
      model: sys.os || '未知',
      detail: sys.edition || '',
    });
  }

  grid.innerHTML = cards.map(c => `
    <div class="hw-card">
      <div class="hw-icon">${c.icon}</div>
      <div class="hw-title">${c.title}</div>
      <div class="hw-model">${c.model.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</div>
      <div class="hw-detail">${c.detail}</div>
    </div>`).join('');
}

function renderHardwareNas(nasData) {
  const section = document.getElementById('nas-hw-section');
  if (!section) return;

  const entries = Object.entries(nasData || {});
  const onlineDevices = entries.filter(([, d]) => d.online !== false);

  if (onlineDevices.length === 0) {
    section.innerHTML = '';
    return;
  }

  const cards = onlineDevices.map(([name, dev]) => {
    const hw = dev.hardware || {};
    if (!hw.cpu_model) {
      return `
        <div class="hw-card nas-hw-card">
          <div class="hw-icon">\u{1F4E1}</div>
          <div class="hw-title">${name}</div>
          <div class="hw-model" style="font-size:0.8rem;color:var(--text-secondary)">${dev.host || ''}</div>
          <div class="nas-hw-rows"><div class="nas-hw-row"><span>硬件信息采集中...</span></div></div>
        </div>`;
    }
    return `
      <div class="hw-card nas-hw-card">
        <div class="hw-icon">\u{1F4E1}</div>
        <div class="hw-title">${name}</div>
        <div class="hw-model" style="font-size:0.8rem;color:var(--text-secondary)">${dev.host || ''}</div>
        <div class="nas-hw-rows">
          <div class="nas-hw-row"><span>CPU</span><span>${hw.cpu_model || '未知'}</span></div>
          <div class="nas-hw-row"><span>核心数</span><span>${hw.cpu_cores || '未知'}</span></div>
          <div class="nas-hw-row"><span>内存</span><span>${hw.memory_total || '未知'}</span></div>
          <div class="nas-hw-row"><span>磁盘</span><span>${hw.disk_total || '未知'} (${hw.disk_model || '未知'})</span></div>
          <div class="nas-hw-row"><span>系统</span><span>${hw.os || '未知'}</span></div>
        </div>
      </div>`;
  }).join('');

  section.innerHTML = `<div class="hardware-grid">${cards}</div>`;
}

export function init(container, api) {
  const buffers = {};
  METRICS.forEach(m => { buffers[m.key] = []; });

  function cardHTML(m) {
    const id = `card-${m.key}`;
    return `
      <div class="metric-card" id="${id}">
        <div class="mc-header">
          <span class="mc-status" id="${id}-status"></span>
          <span class="mc-label">${m.icon} ${m.label}</span>
        </div>
        <div class="mc-value-row">
          <span class="mc-value" id="${id}-val">--</span>
          <span class="mc-unit">${m.unit}</span>
        </div>
        <div class="mc-bar-wrap">
          <div class="mc-bar" id="${id}-bar"></div>
        </div>
        <svg class="mc-trend" id="${id}-trend" viewBox="0 0 200 40" preserveAspectRatio="none">
          <path fill="none" stroke="var(--accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <div class="mc-info" id="${id}-info"></div>
      </div>`;
  }

  container.innerHTML = `
    <div class="section-title">\u5b9e\u65f6\u76d1\u63a7</div>
    <div class="metrics-grid" id="metrics-grid">
      ${METRICS.map(cardHTML).join('')}
    </div>
    <div class="section-title" style="margin-top:28px">NAS \u8bbe\u5907</div>
    <div class="metrics-grid" id="nas-grid"></div>
    <div class="section-title" style="margin-top:28px">\u672c\u5730\u8be6\u60c5</div>
    <div class="collapsible-section" id="cs-hardware">
      <div class="collapsible-header" id="ch-hardware">
        <span>\u786c\u4ef6\u4fe1\u606f</span>
        <span class="collapsible-chevron">\u25B8</span>
      </div>
      <div class="collapsible-body" id="cb-hardware">
        <div class="hardware-grid" id="hw-grid">
          <div class="hw-card"><div class="hw-icon">\u{1F5A5}</div><div class="hw-title">处理器</div><div class="hw-model">加载中...</div></div>
          <div class="hw-card"><div class="hw-icon">\u{1F3AE}</div><div class="hw-title">显卡</div><div class="hw-model">加载中...</div></div>
          <div class="hw-card"><div class="hw-icon">\u{1F4BE}</div><div class="hw-title">内存</div><div class="hw-model">加载中...</div></div>
          <div class="hw-card"><div class="hw-icon">\u{1F4BF}</div><div class="hw-title">硬盘</div><div class="hw-model">加载中...</div></div>
          <div class="hw-card"><div class="hw-icon">\u2699</div><div class="hw-title">系统</div><div class="hw-model">加载中...</div></div>
        </div>
        <div id="nas-hw-section"></div>
      </div>
    </div>
    <div class="collapsible-section" id="cs-processes">
      <div class="collapsible-header" id="ch-processes">
        <span>\u8fdb\u7a0b Top 15</span>
        <span class="collapsible-chevron">\u25B8</span>
      </div>
      <div class="collapsible-body" id="cb-processes">
        <div class="process-panel">
          <table>
            <thead>
              <tr><th>名称</th><th>CPU %</th><th>内存 %</th><th>RSS</th><th>PID</th></tr>
            </thead>
            <tbody id="proc-tbody">
              <tr><td colspan="5" style="text-align:center;color:var(--text-tertiary);padding:24px">加载中...</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>`;

  // ── 可折叠区域交互 ──
  function toggleSection(headerId, bodyId) {
    const header = document.getElementById(headerId);
    const body = document.getElementById(bodyId);
    const chevron = header?.querySelector('.collapsible-chevron');
    if (!header || !body) return;
    const isOpen = body.classList.toggle('open');
    header.classList.toggle('open', isOpen);
    if (chevron) chevron.textContent = isOpen ? '\u25BE' : '\u25B8';
  }

  document.getElementById('ch-hardware')?.addEventListener('click', () => toggleSection('ch-hardware', 'cb-hardware'));
  document.getElementById('ch-processes')?.addEventListener('click', () => toggleSection('ch-processes', 'cb-processes'));

  // 默认展开硬件信息
  toggleSection('ch-hardware', 'cb-hardware');

  const unsubscribe = api.onStateUpdate((state) => {
    const monitor = state.monitor || {};
    const hardware = state.hardware || {};
    const nas = state.nas || {};

    // Update local metric cards
    METRICS.forEach((m) => {
      let val = 0;
      let info = '';

      if (m.key === 'network') {
        val = monitor.network_speed || 0;
        info = '';
      } else if (m.key === 'gpu') {
        const gpu = hardware.gpu || {};
        val = gpu.utilization || 0;
        info = gpu.name ? `${gpu.name.slice(0, 18)}` : '';
      } else if (m.key === 'cpu') {
        val = monitor.cpu || 0;
        const cpu = hardware.cpu || {};
        info = cpu.freq_current ? `${cpu.freq_current}` : '';
      } else if (m.key === 'memory') {
        val = monitor.memory || 0;
        const mem = hardware.memory || {};
        info = mem.total_gb ? `${mem.total_gb} GB` : '';
      } else if (m.key === 'disk') {
        val = monitor.disk || 0;
        const dsk = hardware.disk || {};
        info = dsk.capacity_gb ? `${dsk.capacity_gb} GB` : '';
      }

      val = Math.min(Math.max(val, 0), 100);

      buffers[m.key].push(val);
      if (buffers[m.key].length > 60) buffers[m.key].shift();

      const stEl = document.getElementById(`card-${m.key}-status`);
      if (stEl) stEl.className = `mc-status ${statusClass(val, m.threshold)}`;

      const valEl = document.getElementById(`card-${m.key}-val`);
      if (valEl) {
        valEl.style.color = statusColor(val, m.threshold);
        valEl.textContent = val.toFixed(1);
      }

      const barEl = document.getElementById(`card-${m.key}-bar`);
      if (barEl) {
        barEl.style.width = `${val}%`;
        barEl.style.background = statusColor(val, m.threshold);
      }

      const trendEl = document.getElementById(`card-${m.key}-trend`);
      if (trendEl) {
        const poly = trendEl.querySelector('path');
        if (poly) {
          poly.setAttribute('d', trendPolyline(buffers[m.key], 200, 40, 100));
          poly.setAttribute('stroke', statusColor(val, m.threshold));
        }
      }

      const infoEl = document.getElementById(`card-${m.key}-info`);
      if (infoEl) infoEl.textContent = info;
    });

    // Update NAS cards
    const nasGrid = document.getElementById('nas-grid');
    if (nasGrid) {
      const nasEntries = Object.entries(nas);
      if (nasEntries.length === 0) {
        nasGrid.innerHTML = '<div class="mc-empty">\u672a\u914d\u7f6e NAS \u8bbe\u5907\uff0c\u8bf7\u5728\u8bbe\u7f6e\u4e2d\u6dfb\u52a0</div>';
        nasGrid.removeAttribute('data-animated');
      } else {
        nasGrid.innerHTML = nasEntries.map(([name, dev]) => {
          const online = dev.online !== false;
          const cpu = dev.cpu != null ? dev.cpu : 0;
          const mem = dev.memory?.percent ?? 0;
          const disk = dev.disk?.percent ?? 0;
          const opacity = online ? '' : 'style="opacity:0.35"';
          const status = online
            ? '<span class="mc-status ok"></span>'
            : '<span class="mc-status danger"></span>';

          return `
            <div class="metric-card nas-card" ${opacity}>
              <div class="mc-header">
                ${status}
                <span class="mc-label">\u{1F4E1} ${name}</span>
                ${!online ? '<button class="nas-retry-btn" data-device="${name}">\u91cd\u8bd5</button>' : ''}
              </div>
              <div class="mc-multi">
                <div class="mc-mini">
                  <span class="mc-mini-label">CPU</span>
                  <span class="mc-mini-val" style="color:${statusColor(cpu, [60,85])}">${cpu.toFixed(1)}%</span>
                  <div class="mc-bar-wrap"><div class="mc-bar" style="width:${cpu}%;background:${statusColor(cpu, [60,85])}"></div></div>
                </div>
                <div class="mc-mini">
                  <span class="mc-mini-label">\u5185\u5b58</span>
                  <span class="mc-mini-val" style="color:${statusColor(mem, [70,90])}">${mem.toFixed(1)}%</span>
                  <div class="mc-bar-wrap"><div class="mc-bar" style="width:${mem}%;background:${statusColor(mem, [70,90])}"></div></div>
                </div>
                <div class="mc-mini">
                  <span class="mc-mini-label">\u78c1\u76d8</span>
                  <span class="mc-mini-val" style="color:${statusColor(disk, [75,92])}">${disk.toFixed(1)}%</span>
                  <div class="mc-bar-wrap"><div class="mc-bar" style="width:${disk}%;background:${statusColor(disk, [75,92])}"></div></div>
                </div>
              </div>
              <div class="mc-info">
                ${dev.temperature != null ? `\u{1F321} ${dev.temperature}°C` : ''}
                ${dev.uptime ? ` | \u23F1 ${dev.uptime}` : ''}
                ${!online && dev.last_error ? ` | \u26A0 ${dev.last_error.slice(0, 30)}` : ''}
              </div>
            </div>`;
        }).join('');

        nasGrid.querySelectorAll('.nas-retry-btn').forEach(btn => {
          btn.addEventListener('click', () => {
            btn.textContent = '\u91cd\u8bd5\u4e2d...';
            btn.disabled = true;
            setTimeout(() => { btn.textContent = '\u91cd\u8bd5'; btn.disabled = false; }, 3000);
          });
        });
        nasGrid.setAttribute('data-animated', '1');
      }
    }

    // Update hardware section
    if (state.hardware) renderHardwareLocal(state.hardware);
    if (state.nas) renderHardwareNas(state.nas);

    // Update process table
    const procs = monitor.processes || [];
    renderProcesses(procs);
  });

  return () => unsubscribe();
}