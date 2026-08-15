// panels/processes.js — Top 15 processes table
export function init(container, api) {
  function fmtBytes(n) {
    if (!n) return '0 B';
    const u = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return n.toFixed(1) + ' ' + u[i];
  }

  container.innerHTML = `
    <div class="section-title">进程 Top 15</div>
    <div class="process-panel">
      <table>
        <thead>
          <tr><th>名称</th><th>CPU %</th><th>内存 %</th><th>RSS</th><th>PID</th></tr>
        </thead>
        <tbody id="proc-tbody">
          <tr><td colspan="5" style="text-align:center;color:var(--text-tertiary);padding:24px">加载中...</td></tr>
        </tbody>
      </table>
    </div>`;

  function render(processes) {
    const tbody = document.getElementById('proc-tbody');
    if (!tbody) return;
    if (!processes || !processes.length) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-tertiary);padding:24px">暂无数据</td></tr>';
      return;
    }
    tbody.innerHTML = processes.map(p => `
      <tr>
        <td class="proc-name">${p.name || ''}</td>
        <td class="proc-num">${(p.cpu || 0).toFixed(1)}</td>
        <td class="proc-num">${(p.memory || 0).toFixed(1)}</td>
        <td class="proc-num">${fmtBytes(p.rss)}</td>
        <td class="proc-pid">${p.pid}</td>
      </tr>`).join('');
  }

  const unsubscribe = api.onStateUpdate((state) => {
    const procs = state.monitor?.processes || [];
    render(procs);
  });

  return () => unsubscribe();
}