# Device Center v1.0 — 架构审查

> 审查日期: 2026-08-11 | 审查范围: specs/device-center-v1.md

---

## 审查结论

**无阻塞问题。** 3 个需修改点，均为最小改动。

---

## 1. 是否破坏现有 Digital Lab 架构

### 影响面分析

| 现有组件 | 是否受影响 | 原因 |
|----------|-----------|------|
| `system_state.py` | 否 | `update("nas", name, data)` 将完整 dict 写入，新增字段自动透传，无需修改 |
| `main.py` | 否 | `snapshot()` 返回 `_system_state` 深拷贝后 `json.dumps` 广播，新增字段自动包含 |
| `main.js` (Electron) | 否 | `latestState = data` 全量缓存，`state-update` 全量推送，无字段过滤 |
| `preload.js` | 否 | `onStateUpdate` 透传完整 state 对象，无字段选择 |
| `dashboard.js` | 否 | 只读 `dev.cpu` / `dev.memory` / `dev.disk`，新增 `processes`/`docker` 字段不影响 |
| `processes.js` | 否 | 只读 `state.monitor.processes`，不访问 `state.nas` |
| `dashboard_server.py` | 否 | `/api/current` 返回 `system_state.snapshot()`，不涉及 NAS 采集 |

**结论：零破坏。** 仅 `nas_monitor.py` 一个文件变更，新增字段对现有消费者完全透明。

---

## 2. system_state 数据结构是否合理

### 现状

```python
# monitor（本机）— 扁平值
"monitor": {"cpu": 12.5, "memory": 63.2, "disk": 45.0, "processes": [...]}

# nas（远程）— 嵌套结构
"nas": {"客厅NAS": {"cpu": 8.5, "memory": {"percent": 26.3, ...}, "disk": {"percent": 24.0, ...}}}
```

### 新增字段

```python
"nas": {"客厅NAS": {
    ...现有字段...
    "processes": [{"pid": ..., "name": ..., "cpu": ..., "memory": ..., "command": ...}],
    "docker": {"containers": [...], "total_containers": 5, "running": 3, "last_updated": "..."},
}}
```

### 分析

- **`processes` 字段**：与 `monitor.processes` 结构一致（pid/name/cpu/memory/command），合理
- **`docker` 字段**：嵌套 dict，与 `memory`/`disk` 模式一致，合理
- **monitor vs nas 路径不一致**：这是已知技术债，用户已明确 "1.0暂保持，后续统一设备模型"，本次不解决
- **快照体积**：`processes`（15 条 × ~200B = 3KB）+ `docker`（5-10 容器 × ~300B = 1.5-3KB），总计约 5-6KB 增量。每 2 秒广播一次，可忽略

**结论：合理。** 无结构问题。

---

## 3. NAS Monitor 扩展是否会增加采集负担

### ⚠️ 发现问题：`top -bn1` 重复调用

**现状**（L168-173）：
```python
# 采集 CPU — 执行 top -bn1 | head -5
_, stdout, _ = client.exec_command("top -bn1 | head -5", timeout=10)
cpu_output = stdout.read().decode("utf-8", errors="replace")
cpu = _parse_cpu(cpu_output)
```

**Spec 新增**（进程采集）：
```python
# 采集进程 — 再次执行 top -bn1（完整输出）
_, stdout, _ = client.exec_command("top -bn1", timeout=10)
top_output = stdout.read().decode("utf-8", errors="replace")
processes = _parse_processes(top_output)
```

**问题**：每轮采集对同一台 NAS 执行两次 `top -bn1`（一次 head -5，一次完整），SSH 往返翻倍。

**影响**：`top -bn1` 是 NAS 采集中最重的命令（需采样约 1-2 秒），双重调用会将单设备采集时间从 ~3s 增加到 ~5s。

### 修复方案

**合并为一次 `top -bn1` 调用**，CPU 解析和进程解析复用同一份输出：

```python
# 采集 CPU + 进程（一次 top -bn1 调用）
try:
    _, stdout, _ = client.exec_command("top -bn1", timeout=10)
    top_output = stdout.read().decode("utf-8", errors="replace")

    # CPU 解析（复用 _parse_cpu，从完整输出中提取 idle）
    cpu = _parse_cpu(top_output)
    if cpu is not None:
        data["cpu"] = cpu

    # 进程解析
    processes = _parse_processes(top_output)
    if processes:
        data["processes"] = processes
except Exception as e:
    log_warn(f"NAS [{name}] CPU/进程采集失败", error=str(e))
```

**变更量**：删除原有 `top -bn1 | head -5` 调用块，替换为上述合并块。`_parse_cpu()` 无需修改（它从完整输出中匹配 `id` 字段，`head -5` 只是减少传输量，不影响解析）。

---

## 4. Device Center 是否与 Dashboard / Process 面板产生职责冲突

### 功能矩阵

| 功能 | Dashboard | Process Panel | Device Center (spec) |
|------|-----------|---------------|---------------------|
| 本机 CPU/内存/磁盘 指标卡 | 是（含趋势线） | 否 | 是（设备卡片摘要） |
| NAS CPU/内存/磁盘 卡片 | 是（迷你卡片） | 否 | 是（设备卡片 + 详情指标卡） |
| 本机进程 TOP15 | 否 | 是 | **是（Local PC 详情）** |
| NAS 进程 TOP15 | 否 | 否 | 是（NAS 详情） |
| Docker 容器 | 否 | 否 | 是（NAS 详情） |
| GPU / 硬件信息 | 是（GPU 卡片） | 否 | **是（Local PC 详情）** |

### ⚠️ 发现问题：Local PC 详情与现有面板功能重叠

Spec 中 Local PC 详情区域包含：
- CPU/内存/磁盘 指标卡 → **Dashboard 已有**
- 进程 TOP15 表 → **Process Panel 已有**
- 趋势线 → **Dashboard 已有**
- GPU / 硬件信息 → **Hardware 面板已有**

这导致 Device Center 的 Local PC 详情几乎是把 Dashboard + Process Panel + Hardware 的内容重新实现一遍。用户没有理由在 Device Center 里查看本机详情——这些信息在专用面板中展示得更好。

### 修复方案

**Local PC 卡片不展开详情，点击后导航到 Dashboard。**

```javascript
// 设备卡片点击处理
function handleDeviceClick(deviceId) {
  if (deviceId === 'local') {
    // Local PC → 跳转到 Dashboard（已有完整信息）
    window.dispatchEvent(new CustomEvent('switch-panel', { detail: 'dashboard' }));
    return;
  }
  // NAS 设备 → 展开详情
  toggleDeviceDetail(deviceId);
}
```

**变更量**：Device Center 中 Local PC 卡片的点击行为从"展开详情"改为"导航到 Dashboard"。Dashboard 的 `dashboard.html` 已有 `switch-panel` 事件监听（L91-93），无需额外修改。

**好处**：
- 消除职责冲突，Device Center 聚焦"其他设备"（当前即 NAS）
- 减少前端代码量（不需要实现 Local PC 详情区域）
- 符合用户定义的流程：`Dashboard 查看状态 → Device Center 选择设备 → 查看详情`

---

## 5. 是否存在过度设计

### 逐项检查

| 设计项 | 判断 | 理由 |
|--------|------|------|
| Docker 容器表（名称/镜像/状态/CPU/内存） | 合理 | 容器状态是 NAS 的核心信息，6 列表格不复杂 |
| 详情趋势线 | **过度** | Dashboard 已有趋势线，详情区域用进度条即可 |
| `refresh_nas` IPC 命令 | 已标注可选 | Spec 5.3 节已说明 1.0 可省略，无需修改 |
| 9 个新 CSS 类 | 合理 | 新面板需要卡片/详情/表格样式，9 个类是最小集 |
| 前端设备统一视图映射 | 合理 | 纯前端映射，不增加后端复杂度 |

### ⚠️ 发现问题：详情趋势线冗余

Spec 布局图中详情资源指标卡包含"█▆▃▅▂"趋势线。Dashboard 是趋势线的主场，Device Center 详情不需要。

### 修复方案

详情指标卡使用**进度条**（`.mc-bar`），不用趋势线。进度条已在 Dashboard NAS 卡片中使用（`.mc-mini .mc-bar-wrap`），样式可直接复用。

---

## 汇总：需要修改的 3 个点

| # | 问题 | 严重程度 | 修改方案 | 影响范围 |
|---|------|---------|---------|---------|
| 1 | `top -bn1` 重复调用 | 中 | 合并 CPU + 进程采集为一次 `top -bn1` | `nas_monitor.py` L168-173 |
| 2 | Local PC 详情与 Dashboard/Process 面板冲突 | 中 | Local PC 卡片点击导航到 Dashboard，不做详情 | `device-center.js` 点击逻辑 |
| 3 | 详情趋势线冗余 | 低 | 详情指标卡用进度条代替趋势线 | `device-center.js` + `styles.css` |

### 修改后 Device Center 详情区域范围

```
NAS 设备详情：
  ├── 资源指标卡（CPU/内存/磁盘 + 进度条）
  ├── NAS 信息（温度、uptime、负载）
  ├── 进程 TOP15 表
  └── Docker 容器表

Local PC：
  └── 卡片点击 → 导航到 Dashboard（无详情）
```

---

## 最终裁决

**无阻塞问题，可以进入 `/implement`。** 3 个修改点均为最小改动，建议在实现时直接应用修正方案，无需重写 Spec。