// panels/hardware.js — 本地 PC 硬件信息 + NAS 设备硬件卡片
export async function init(container, api) {
  container.innerHTML = `
    <div class="section-title">本地设备</div>
    <div class="hardware-grid" id="hw-grid">
      <div class="hw-card"><div class="hw-icon">&#x1F5A5;</div><div class="hw-title">处理器</div><div class="hw-model">加载中...</div></div>
      <div class="hw-card"><div class="hw-icon">&#x1F3AE;</div><div class="hw-title">显卡</div><div class="hw-model">加载中...</div></div>
      <div class="hw-card"><div class="hw-icon">&#x1F4BE;</div><div class="hw-title">内存</div><div class="hw-model">加载中...</div></div>
      <div class="hw-card"><div class="hw-icon">&#x1F4BF;</div><div class="hw-title">硬盘</div><div class="hw-model">加载中...</div></div>
      <div class="hw-card"><div class="hw-icon">&#x2699;</div><div class="hw-title">系统</div><div class="hw-model">加载中...</div></div>
    </div>
    <div id="nas-hardware-section"></div>`;

  function renderLocal(hardware) {
    if (!hardware) return;
    const grid = document.getElementById('hw-grid');
    if (!grid) return;

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
        <div class="hw-model">${c.model}</div>
        <div class="hw-detail">${c.detail}</div>
      </div>`).join('');
  }

  function renderNas(nasData) {
    const section = document.getElementById('nas-hardware-section');
    if (!section) return;

    const entries = Object.entries(nasData || {});
    const onlineDevices = entries.filter(([, d]) => d.online !== false);

    if (onlineDevices.length === 0) {
      section.innerHTML = '';
      return;
    }

    const cards = onlineDevices.map(([name, dev]) => {
      const hardware = dev.hardware || {};

      // 硬件信息尚未采集
      if (!hardware.cpu_model) {
        return `
          <div class="hw-card nas-hw-card">
            <div class="hw-icon">\u{1F4E1}</div>
            <div class="hw-title">${name}</div>
            <div class="hw-model" style="font-size:0.8rem;color:var(--text-secondary)">${dev.host || ''}</div>
            <div class="nas-hw-rows">
              <div class="nas-hw-row"><span>硬件信息采集中...</span></div>
            </div>
          </div>`;
      }

      return `
        <div class="hw-card nas-hw-card">
          <div class="hw-icon">\u{1F4E1}</div>
          <div class="hw-title">${name}</div>
          <div class="hw-model" style="font-size:0.8rem;color:var(--text-secondary)">${dev.host || ''}</div>
          <div class="nas-hw-rows">
            <div class="nas-hw-row"><span>CPU</span><span>${hardware.cpu_model || '未知'}</span></div>
            <div class="nas-hw-row"><span>核心数</span><span>${hardware.cpu_cores || '未知'}</span></div>
            <div class="nas-hw-row"><span>内存</span><span>${hardware.memory_total || '未知'}</span></div>
            <div class="nas-hw-row"><span>磁盘</span><span>${hardware.disk_total || '未知'} (${hardware.disk_model || '未知'})</span></div>
            <div class="nas-hw-row"><span>系统</span><span>${hardware.os || '未知'}</span></div>
          </div>
        </div>`;
    }).join('');

    section.innerHTML = `
      <div class="section-title" style="margin-top:28px">NAS 设备</div>
      <div class="hardware-grid">${cards}</div>`;
  }

  // First load from cache
  const hw = await api.getHardware();
  renderLocal(hw);

  // Subscribe to state updates for all data
  const unsubscribe = api.onStateUpdate((state) => {
    if (state.hardware) renderLocal(state.hardware);
    if (state.nas) renderNas(state.nas);
  });

  return () => unsubscribe();
}