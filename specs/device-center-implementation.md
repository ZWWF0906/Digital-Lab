# Device Center v1.0 — 代码审查与实施计划

> 审查日期: 2026-08-11 | 基于实际仓库代码逐文件审查

---

## 1. 代码结构审查

### 1.1 数据流验证

追踪 `system_state.nas["客厅NAS"]` → 前端渲染的完整链路：

```
nas_monitor._collect_nas()
  → system_state.update("nas", name, data)          # system_state.py L48-52
    → ns["客厅NAS"] = {cpu, memory, disk, ...}      # 任意嵌套 dict，无 schema 限制
      ↓
main.py _format_state() L563:
  snap = system_state.snapshot()                     # 深拷贝全量 _system_state
  → L600: "nas": snap.get("nas", {})                # ⚡ 全量透传，不筛选字段
    → print(json.dumps(payload), flush=True)          # L636-638（略）
      ↓
main.js rl.on('line') L62-100:
  → JSON.parse → latestState = data                 # L93: 全量缓存
    → mainWindow.webContents.send('state-update', data)  # L99: 全量推送
      ↓
preload.js onStateUpdate(callback) L4-7:
  → callback(data)                                   # 透传完整 state 对象
    ↓
dashboard.js / device-center.js:
  → state.nas["客厅NAS"].cpu                         # 直接读取
```

**验证结论**：`"nas": snap.get("nas", {})` 在 L600 做全量透传，`nas_monitor` 写入 `data` 的任何新字段都会自动出现在前端 `state.nas[name]` 中。**零后端修改即可支持字段扩展。**

### 1.2 关键代码点确认

| 文件:行号 | 代码 | 对 Device Center 的影响 |
|-----------|------|------------------------|
| `nas_monitor.py:168-173` | `top -bn1 \| head -5` 采集 CPU | **需要改**：改为完整 `top -bn1`，同时用于 CPU + 进程解析 |
| `main.py:600` | `"nas": snap.get("nas", {})` | **无需改**：全量透传，`processes`/`docker` 自动包含 |
| `main.py:584-601` | `_format_state()` 显式构造 monitor | **无需改**：只影响 `monitor` 命名空间，不影响 `nas` |
| `system_state.py:48-52` | `update(key, sub_key, value)` | **无需改**：`value` 接受任意 dict |
| `main.js:93` | `latestState = data` | **无需改**：全量缓存 |
| `main.js:99` | `send('state-update', data)` | **无需改**：全量推送 |
| `preload.js:4-7` | `onStateUpdate(callback)` | **无需改**：透传 |
| `dashboard.html:91-93` | `switch-panel` 事件监听 | **可复用**：Local PC 卡片导航到 Dashboard |
| `config.json:24-31` | NAS 设备 `enabled` 字段缺失 | **注意**：不添加则 NAS 监控不启动 |

### 1.3 `config.json` NAS 设备 enabled 问题

```json
"nas_devices": [
    {
      "name": "客厅NAS",
      "host": "100.93.189.99",
      "port": 22,
      "username": "root",
      "password": "968828"
      // ← 缺少 "enabled": true
    }
]
```

`start_nas_monitor()` L284:
```python
if not device.get("enabled", False):
    continue  # ← 跳过未启用的设备
```

`enabled` 默认为 `False`，所以当前配置下 NAS 监控不会启动。需要在配置中添加 `"enabled": true`，或修改 `start_nas_monitor` 的默认值。

---

## 2. 文件分类

### 2.1 必须修改文件

| 文件 | 修改内容 | 风险 |
|------|---------|------|
| **`core/nas_monitor.py`** | 1. 合并 CPU + 进程采集为一次 `top -bn1` 调用<br>2. 新增 `_parse_processes()` 函数<br>3. 新增 `_parse_docker_stats()` 函数<br>4. 添加 Docker 30s 低频采集逻辑 | 低 — 仅扩展采集步骤，不改变现有解析逻辑 |
| **`panels/device-center.js`** | 新建文件，实现设备卡片 + NAS 详情区域 | 无 — 新文件，不影响现有面板 |
| **`panels/index.js`** | 新增 import + 注册 `device-center` 面板 | 低 — 仅新增一行注册 |
| **`styles.css`** | 新增 `.device-grid`、`.device-card`、`.device-detail` 等样式 | 低 — 纯新增，不修改现有样式 |

### 2.2 可选修改文件

| 文件 | 修改内容 | 理由 |
|------|---------|------|
| **`config.json`** | 给 NAS 设备添加 `"enabled": true` | 否则 NAS 监控不启动，Device Center 看不到 NAS 数据 |

### 2.3 禁止修改文件

| 文件 | 原因 |
|------|------|
| `system_state.py` | `update("nas", name, data)` 已支持任意嵌套 dict |
| `main.py` | `_format_state()` L600 全量透传 `nas`，无需修改 |
| `main.js` | `latestState` + `state-update` 全量推送，无需修改 |
| `preload.js` | `onStateUpdate` 透传完整 state，无需修改 |
| `dashboard.js` | 只读 `dev.cpu/memory/disk`，新增字段不影响 |
| `processes.js` | 只读 `state.monitor.processes`，职责不变 |
| `dashboard.html` | `switch-panel` 事件已存在，直接复用 |
| `collector.py` | 不涉及 NAS 数据采集 |
| `dashboard_server.py` | Web dashboard 不涉及 Device Center |

---

## 3. 需求与现有架构冲突点

### 冲突 1: `top -bn1` 重复调用（中等）

**现状**：CPU 采集执行 `top -bn1 | head -5`（L169），进程采集需执行完整 `top -bn1`。

**冲突**：两次 SSH 调用同一命令，浪费往返时间。

**解决**：改为一次完整 `top -bn1`，`_parse_cpu()` 从完整输出中提取 idle 值（函数已支持，无需修改），`_parse_processes()` 从同一输出中解析进程列表。

**注意**：`head -5` 去掉后，`_parse_cpu()` 接收完整 `top` 输出。验证 `_parse_cpu` 对完整输出的兼容性——`re.search(r'(\d+\.?\d*)\s*id', full_output)` 在完整输出中同样能匹配到 Cpu(s) 行，因为 idle 行始终在输出前面。

### 冲突 2: NAS 进程数据格式与本地进程不完全一致（低）

**本地进程**（`main.py` L588-597）：
```json
{"pid": "1234", "name": "chrome", "cpu": 5.2, "memory": 320.5, "rss": 336076800}
```

**NAS 进程**（Spec 设计）：
```json
{"pid": "1234", "name": "smbd", "cpu": 2.1, "memory": 1.5, "command": "/usr/sbin/smbd"}
```

**冲突**：本地进程有 `rss`（内存字节），NAS 进程有 `command`（命令行）。字段不一致。

**解决**：这不是真正的冲突。两个进程列表在**不同上下文**中渲染——本地进程在 Process Panel，NAS 进程在 Device Center 详情。各自使用自己的字段即可。1.0 不需要统一进程模型。

### 冲突 3: CSS 类名 `.device-item` 已存在（低）

**现状**：`styles.css` L907-927 有 `.device-item` 和 `.device-item-header`（Settings 面板的 NAS 设备配置项）。

**冲突**：Spec 新增 `.device-card`、`.device-grid`、`.device-detail`。与现有 `.device-item` 命名相近但不冲突。

**解决**：无需修改。`.device-card` 和 `.device-item` 是不同的 CSS 类，用于不同上下文。

### 冲突 4: Dashboard 已有 NAS 卡片（信息重复，设计意图）

**现状**：`dashboard.js` 已渲染 NAS 设备卡片（CPU/内存/磁盘迷你指标 + 温度 + uptime）。

**冲突**：Device Center 也会渲染 NAS 设备卡片（CPU/内存/磁盘摘要），存在信息重复。

**解决**：这是**设计意图，非冲突**。两种视图定位不同：
- Dashboard：全局健康摘要（NAS 卡片是其中一部分）
- Device Center：设备管理入口（卡片可点击展开详情）

1.0 保持 Dashboard NAS 卡片不变。后续可根据用户反馈决定是否从 Dashboard 移除 NAS 卡片。

---

## 4. 确认：无阻塞问题

| 检查项 | 状态 |
|--------|------|
| system_state 支持字段扩展 | 通过 — `update("nas", name, data)` 已支持任意嵌套 |
| state-update 广播机制支持新字段 | 通过 — L600 全量透传 `nas` |
| 前端 `onStateUpdate` 接收新字段 | 通过 — 透传完整对象 |
| 现有面板不受影响 | 通过 — Dashboard/Process 只读已知字段 |
| 无新增通信链路 | 通过 — 复用 SSH + system_state + state-update |
| 前端跨面板导航机制 | 通过 — `switch-panel` 事件已存在 |
| CSS 无命名冲突 | 通过 — 新增类名不冲突 |
| `_parse_cpu()` 兼容完整 `top` 输出 | 通过 — 正则从完整输出中仍能匹配 |

**结论：无阻塞问题，可以进入实施。**

---

## 5. 实施计划

### Phase 1: 后端（`nas_monitor.py`）

| 步骤 | 操作 | 行号范围 |
|------|------|---------|
| 1.1 | 新增 `_parse_processes(top_output)` 函数 | 在 `_parse_load` 之后 |
| 1.2 | 新增 `_parse_docker_stats(stats_output)` 函数 | 在 `_parse_processes` 之后 |
| 1.3 | 修改 CPU 采集：`top -bn1` 替代 `top -bn1 \| head -5` | L168-173 |
| 1.4 | 在 CPU 采集后添加进程解析（复用同一 `top_output`） | 在 L173 之后 |
| 1.5 | 添加 Docker 低频采集（30s 间隔，维护 `last_docker_collect` 时间戳） | 在 uptime 采集之后（L222 之后） |
| 1.6 | Docker 失败时保留旧数据（不清空 `data["docker"]`） | 在 Docker 采集的 except 块中 |

### Phase 2: 前端面板（`device-center.js` 新建）

| 步骤 | 操作 |
|------|------|
| 2.1 | 创建 `panels/device-center.js`，导出 `init(container, api)` |
| 2.2 | 构建 HTML 骨架：section-title + device-grid + device-detail |
| 2.3 | 实现 `mapDevices(state)` — 将 `monitor` + `nas` 映射为统一设备列表 |
| 2.4 | 实现设备卡片渲染（复现 `.metric-card` 样式） |
| 2.5 | Local PC 卡片点击 → `switch-panel` 事件导航到 Dashboard |
| 2.6 | NAS 卡片点击 → 展开/切换详情区域 |
| 2.7 | 实现 NAS 详情区域：资源指标卡（CPU/内存/磁盘 + 进度条） |
| 2.8 | 实现 NAS 详情区域：进程 TOP15 表 |
| 2.9 | 实现 NAS 详情区域：Docker 容器表 + 统计行 |
| 2.10 | 订阅 `api.onStateUpdate`，增量更新卡片和已展开详情 |
| 2.11 | 返回 cleanup 函数（取消订阅） |

### Phase 3: 集成

| 步骤 | 操作 |
|------|------|
| 3.1 | `panels/index.js` 注册 Device Center 面板 |
| 3.2 | `styles.css` 新增样式（device-grid, device-card, device-detail, detail-header, detail-gauges, detail-section, docker-table, docker-stat） |
| 3.3 | `config.json` 添加 `"enabled": true` 到 NAS 设备配置 |

### Phase 4: 验证

| 步骤 | 验证方法 |
|------|---------|
| 4.1 | 启动应用，确认侧栏有"设备中心"导航项 |
| 4.2 | 进入 Device Center，确认 Local PC + NAS 设备卡片显示 |
| 4.3 | 点击 Local PC 卡片，确认导航到 Dashboard |
| 4.4 | 点击 NAS 卡片，确认展开详情（资源指标 + 进程表 + Docker 表） |
| 4.5 | 等待 15 秒，确认数据自动刷新 |
| 4.6 | 切换面板离开再回来，确认无内存泄漏 |
| 4.7 | 确认 Dashboard / Process Panel 功能正常 |

---

## 6. 关键数据流（实施参考）

### NAS 进程数据写入

```
_collect_nas() 采集循环:
  exec_command("top -bn1")
    → top_output = stdout.read()
    → cpu = _parse_cpu(top_output)        # 100 - idle%
    → processes = _parse_processes(top_output)  # TOP15
    → data["cpu"] = cpu
    → data["processes"] = processes
  system_state.update("nas", name, data)
```

### Docker 数据写入

```
_collect_nas() 采集循环:
  if now - last_docker_collect >= 30:
    exec_command("docker stats --no-stream --format '{{json .}}'")
      → containers = _parse_docker_stats(output)
      → data["docker"] = {
          "containers": [...],
          "total_containers": N,
          "running": M,
          "last_updated": "..."
        }
    last_docker_collect = now
  system_state.update("nas", name, data)
```

### 前端设备映射

```
state = { monitor: {...}, nas: {...} }

devices = [
  { id: "local", name: "本地主机", type: "PC", cpu: state.monitor.cpu, ... },
  ...Object.entries(state.nas).map(([name, data]) => ({
    id: `nas-${name}`,
    name,
    type: "NAS",
    cpu: data.cpu ?? 0,
    memory: data.memory?.percent ?? 0,
    disk: data.disk?.percent ?? 0,
    temperature: data.temperature,
    uptime: data.uptime,
    processes: data.processes || [],
    docker: data.docker || null,
  })),
]
```

### Local PC 卡片导航

```javascript
deviceGrid.addEventListener('click', (e) => {
  const card = e.target.closest('.device-card');
  if (!card) return;
  const deviceId = card.dataset.deviceId;
  if (deviceId === 'local') {
    window.dispatchEvent(new CustomEvent('switch-panel', { detail: 'dashboard' }));
    return;
  }
  toggleDetail(deviceId);
});
```