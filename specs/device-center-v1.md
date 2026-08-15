# Device Center v1.0 — 功能规格

> 状态: Draft | 日期: 2026-08-11 | 版本: 1.0

---

## 1. 概述

### 1.1 定位

Device Center 是 Digital Lab 的多设备总览中心。用户在此查看所有已接入设备（Local PC + NAS）的健康状态，选择设备后展开详情（CPU/内存/磁盘/进程/Docker）。

### 1.2 核心流程

```
Dashboard（全局健康摘要）
  → 点击侧栏 "设备中心"
    → Device Center（设备卡片网格 + 详情区域）
      → 点击设备卡片
        → 展开设备详情（资源状态 + 进程 TOP15 + Docker 容器）
```

### 1.3 范围边界

**1.0 包含：**
- Local PC 和 NAS 设备卡片（在线状态、CPU、内存、磁盘）
- 点击设备卡片展开详情区域
- NAS 详情：资源状态、进程 TOP15、Docker 容器状态
- 复用现有 `system_state` 数据链路，优先显示缓存数据
- 后台 SSH 刷新 NAS 详情数据

**1.0 不包含：**
- 插件化设备模型 / 通用 Device Capability 抽象
- 独立设备详情面板（详情在 Device Center 内展示）
- SSH 终端集成
- Web 服务快捷入口
- Docker 容器控制（启停/日志）
- 第三方设备类型（服务器、路由器等）
- 设备分组 / 标签 / 搜索

---

## 2. 数据模型

### 2.1 system_state 结构（现状 + 新增）

```python
system_state = {
    "monitor": {
        "cpu": 12.5,        # 本机 CPU 使用率 (%)
        "memory": 63.2,     # 本机内存使用率 (%)
        "disk": 45.0,       # 本机磁盘使用率 (%)
        "network_speed": 0, # 本机网络速度 (Mbps)
        "processes": [      # 本机进程 TOP15 (已有)
            {"pid": "1234", "name": "chrome", "cpu": 5.2, "memory": 320.5, "command": "..."},
        ],
    },
    "hardware": {
        "cpu": {"name": "...", "freq_current": "3.2 GHz", ...},
        "gpu": {"name": "...", "utilization": 15.0, ...},
        "memory": {"total_gb": 32, ...},
        "disk": {"capacity_gb": 512, ...},
    },
    "nas": {
        "客厅NAS": {
            "online": True,
            "name": "客厅NAS",
            "host": "100.93.189.99",
            "cpu": 8.5,
            "memory": {"used_gb": 4.2, "total_gb": 16.0, "percent": 26.3},
            "disk": {"used_gb": 120.0, "total_gb": 500.0, "percent": 24.0},
            "temperature": 45.0,
            "uptime": "12 days, 3:45",
            "load": {"load_1m": 0.15, "load_5m": 0.10, "load_15m": 0.05},
            "last_updated": "2026-08-11T10:30:00",
            "last_error": None,
            # ═══ 新增字段 ═══
            "processes": [   # NAS 进程 TOP15
                {"pid": "1234", "name": "smbd", "cpu": 2.1, "memory": 1.5, "command": "/usr/sbin/smbd"},
            ],
            "docker": {      # Docker 容器状态（低频采集）
                "containers": [
                    {"name": "portainer", "image": "portainer/portainer-ce", "status": "running", "cpu": 0.5, "memory": "128MiB"},
                    {"name": "filebrowser", "image": "filebrowser/filebrowser", "status": "running", "cpu": 0.1, "memory": "64MiB"},
                ],
                "total_containers": 5,
                "running": 3,
                "last_updated": "2026-08-11T10:30:00",
            },
        },
    },
}
```

### 2.2 前端设备统一视图

Device Center 前端将 `monitor`（本机）和 `nas`（远程）统一映射为设备卡片：

```javascript
// 设备卡片数据结构（前端映射）
const devices = [
  {
    id: "local",
    name: "本地主机",
    type: "PC",
    online: true,
    cpu: 12.5,
    memory: 63.2,
    disk: 45.0,
    // PC 特有
    gpu: 15.0,
    hardware: { ... },
    processes: [ ... ],
  },
  {
    id: "nas-客厅NAS",
    name: "客厅NAS",
    type: "NAS",
    online: true,
    host: "100.93.189.99",
    cpu: 8.5,
    memory: 26.3,
    disk: 24.0,
    // NAS 特有
    temperature: 45.0,
    uptime: "12 days, 3:45",
    processes: [ ... ],
    docker: { ... },
  },
];
```

---

## 3. 后端变更

### 3.1 NAS Monitor 扩展

**文件**: `core/nas_monitor.py`

#### 3.1.1 新增 NAS 进程采集

在现有采集循环中增加进程采集步骤：

```python
# 采集进程 TOP15（复用现有 top 命令）
try:
    _, stdout, _ = client.exec_command("top -bn1", timeout=10)
    top_output = stdout.read().decode("utf-8", errors="replace")
    processes = _parse_processes(top_output)
    if processes:
        data["processes"] = processes
except Exception as e:
    log_warn(f"NAS [{name}] 进程采集失败", error=str(e))
```

新增 `_parse_processes()` 函数：解析 `top -bn1` 输出，提取 PID、进程名、CPU%、内存%、命令行，返回 TOP15 列表。

#### 3.1.2 新增 Docker 容器状态采集（低频）

Docker 采集使用独立间隔（30-60 秒），与主采集周期（15 秒）分离：

```python
# 在 _collect_nas 线程中维护一个 docker_last_collect 时间戳
# 每 30 秒采集一次 Docker 状态

try:
    _, stdout, _ = client.exec_command(
        "docker stats --no-stream --format '{{json .}}' 2>/dev/null || echo '[]'",
        timeout=15,
    )
    docker_output = stdout.read().decode("utf-8", errors="replace")
    containers = _parse_docker_stats(docker_output)
    if containers:
        # 统计运行/总数
        running = sum(1 for c in containers if c.get("status") == "running")
        data["docker"] = {
            "containers": containers,
            "total_containers": len(containers),
            "running": running,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
except Exception as e:
    log_warn(f"NAS [{name}] Docker 采集失败", error=str(e))
```

新增 `_parse_docker_stats()` 函数：解析 Docker stats JSON 输出，提取容器名、镜像、状态、CPU%、内存使用量。

#### 3.1.3 采集周期

| 指标 | 周期 | 说明 |
|------|------|------|
| CPU / 内存 / 磁盘 / 温度 / uptime | 15 秒（可配置） | 现有周期，不变 |
| 进程 TOP15 | 15 秒 | 与主周期同步 |
| Docker 容器状态 | 30 秒（固定） | 低频采集，独立于主周期 |

### 3.2 无其他后端变更

- `system_state.py`：无需修改，现有 `update("nas", name, data)` 已支持任意嵌套数据
- `main.py`：无需修改，`--json-mode` 下已通过 `system_state.snapshot()` 广播全量状态
- `dashboard_server.py`：无需修改

---

## 4. 前端变更

### 4.1 新增面板：Device Center

**文件**: `panels/device-center.js`（新建）

#### 4.1.1 布局结构

```
┌─────────────────────────────────────────────────┐
│  设备中心                                        │
│                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐        │
│  │ ● 本地主机 │ │ ● 客厅NAS │ │ ○ 离线NAS │        │
│  │   PC      │ │   NAS    │ │   NAS    │        │
│  │ CPU 12.5% │ │ CPU 8.5% │ │ 离线      │        │
│  │ 内存 63%  │ │ 内存 26% │ │          │        │
│  └──────────┘ └──────────┘ └──────────┘        │
│                                                  │
│  ── 设备详情: 客厅NAS ──────────────────────────  │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐           │
│  │ CPU     │ │ 内存     │ │ 磁盘     │           │
│  │ 8.5%    │ │ 26.3%   │ │ 24.0%   │           │
│  │ █▆▃▅▂  │ │ █▆▃▅▂  │ │ █▆▃▅▂  │           │
│  └─────────┘ └─────────┘ └─────────┘           │
│                                                  │
│  ┌─ 进程 TOP15 ────────────────────────────────┐ │
│  │ PID   名称    CPU%   内存%   命令            │ │
│  │ 1234  smbd    2.1    1.5    /usr/sbin/smbd  │ │
│  │ ...                                        │ │
│  └────────────────────────────────────────────┘ │
│                                                  │
│  ┌─ Docker 容器 ───────────────────────────────┐ │
│  │ 名称        镜像              状态   CPU  内存 │
│  │ portainer   portainer/ce     运行   0.5% 128M│
│  │ filebrowser filebrowser/...  运行   0.1%  64M│
│  │ ● 运行中: 3  ● 总计: 5                      │
│  └────────────────────────────────────────────┘ │
│                                                  │
└─────────────────────────────────────────────────┘
```

#### 4.1.2 组件树

```
DeviceCenterPanel
├── SectionTitle ("设备总览")
├── DeviceGrid
│   ├── DeviceCard (Local PC)
│   │   ├── StatusDot (online)      ← 在线状态指示灯
│   │   ├── DeviceName ("本地主机")
│   │   ├── DeviceType ("PC")
│   │   └── MiniMetrics (CPU, 内存, 磁盘)
│   └── DeviceCard (NAS × N)
│       ├── StatusDot (online/offline)
│       ├── DeviceName ("客厅NAS")
│       ├── DeviceType ("NAS")
│       ├── MiniMetrics (CPU, 内存, 磁盘)
│       └── ExtraInfo (温度, uptime)
│
└── DeviceDetail (条件渲染)
    ├── DetailHeader (设备名称 + 关闭按钮)
    ├── ResourceGauges (CPU/内存/磁盘 三列卡片)
    ├── ProcessTable (TOP15)
    └── DockerTable (容器列表 + 统计)
```

#### 4.1.3 交互行为

| 交互 | 行为 |
|------|------|
| 点击设备卡片 | 展开/切换详情区域（再次点击同一设备可折叠） |
| 详情区域打开 | 立即显示缓存数据，同时后台请求 SSH 刷新 |
| 设备离线 | 卡片显示灰色 + 离线标记，详情区域不可展开 |
| 状态更新 | 订阅 `api.onStateUpdate`，增量更新卡片和详情 |
| 面板切换离开 | `cleanup()` 取消订阅，释放 DOM 引用 |

#### 4.1.4 缓存策略

```javascript
// 详情区域打开时
function openDeviceDetail(deviceId) {
  // 1. 立即渲染缓存数据（来自 state-update 的最新推送）
  renderDetail(latestState, deviceId);

  // 2. 后台通过 IPC 触发 NAS SSH 刷新（仅 NAS 设备）
  if (deviceId.startsWith('nas-')) {
    api.sendCommand({
      cmd: 'refresh_nas',
      device: deviceId.replace('nas-', ''),
    });
  }
}
```

### 4.2 面板注册

**文件**: `panels/index.js`

在 `PANELS` 数组中新增：

```javascript
import { init as initDeviceCenter } from './device-center.js';

// 插入到 dashboard 和 hardware 之间
{ id: 'device-center', name: '设备中心', icon: '\u2302', init: initDeviceCenter },
```

### 4.3 样式新增

**文件**: `styles.css`

新增 CSS 类：

| 类名 | 用途 |
|------|------|
| `.device-grid` | 设备卡片网格容器（2-3 列自适应） |
| `.device-card` | 设备卡片（复用现有 metric-card 风格） |
| `.device-card.selected` | 选中态（边框高亮 + 微弱发光） |
| `.device-detail` | 详情区域容器 |
| `.detail-header` | 详情标题栏（设备名 + 关闭按钮） |
| `.detail-gauges` | 详情资源指标行（三列） |
| `.detail-section` | 详情子区域（进程表 / Docker 表） |
| `.docker-table` | Docker 容器表格 |
| `.docker-stat` | Docker 统计摘要行 |

---

## 5. 数据流

### 5.1 State Update 流程（不变）

```
Python Collector (2s 周期)
  → system_state.snapshot()
    → print(json.dumps(snap), flush=True)
      → Electron main.js stdout readline
        → mainWindow.webContents.send('state-update', data)
          → preload.js onStateUpdate callback
            → Device Center panel 订阅者
```

### 5.2 NAS 进程/Docker 数据流（新增）

```
nas_monitor.py _collect_nas 线程
  ├── 15s 周期: CPU / 内存 / 磁盘 / 温度 / uptime / 进程 TOP15
  ├── 30s 周期: Docker 容器状态
  └── system_state.update("nas", name, data)
        ↓
  下一轮 Collector snapshot 自动包含新数据
        ↓
  Electron state-update 推送到前端
```

### 5.3 详情刷新流（新增，可选）

```
Device Center 前端
  → api.sendCommand({ cmd: 'refresh_nas', device: '客厅NAS' })
    → Electron IPC sendToPython
      → Python 处理（可选，触发一次立即采集）
        → __cmd_response__ 返回确认
          → 下一轮 state-update 自然包含最新数据
```

> 注：1.0 版本中，后台刷新可简化为依赖 15 秒自动采集周期，不新增 `refresh_nas` 命令。缓存数据在 15 秒内自动更新。

---

## 6. 实现任务清单

### Phase 1: 后端扩展

| # | 任务 | 文件 | 预估 |
|---|------|------|------|
| B1 | 新增 `_parse_processes()` 函数 | `core/nas_monitor.py` | 小 |
| B2 | 在 `_collect_nas()` 中添加进程采集步骤 | `core/nas_monitor.py` | 小 |
| B3 | 新增 `_parse_docker_stats()` 函数 | `core/nas_monitor.py` | 中 |
| B4 | 在 `_collect_nas()` 中添加 Docker 低频采集（30s 间隔） | `core/nas_monitor.py` | 中 |

### Phase 2: 前端面板

| # | 任务 | 文件 | 预估 |
|---|------|------|------|
| F1 | 创建 `device-center.js` 面板骨架 | `panels/device-center.js` | 中 |
| F2 | 实现设备卡片渲染（Local PC + NAS） | `panels/device-center.js` | 中 |
| F3 | 实现设备详情区域（资源指标 + 进程表 + Docker 表） | `panels/device-center.js` | 大 |
| F4 | 实现设备选择/展开交互 | `panels/device-center.js` | 中 |
| F5 | 注册面板到 `panels/index.js` | `panels/index.js` | 小 |

### Phase 3: 样式

| # | 任务 | 文件 | 预估 |
|---|------|------|------|
| S1 | 新增设备卡片样式 | `styles.css` | 小 |
| S2 | 新增详情区域样式 | `styles.css` | 中 |
| S3 | 新增进程表/Docker 表样式 | `styles.css` | 小 |

### Phase 4: 验证

| # | 任务 | 说明 |
|---|------|------|
| V1 | 验证 NAS 进程数据采集 | 检查 `system_state.nas["客厅NAS"].processes` 非空 |
| V2 | 验证 Docker 数据采集 | 检查 `system_state.nas["客厅NAS"].docker` 非空 |
| V3 | 验证 Device Center 面板渲染 | 设备卡片 + 详情区域正常显示 |
| V4 | 验证离线设备处理 | 断开 NAS 后卡片显示离线状态 |
| V5 | 验证面板切换 cleanup | 切换面板后无内存泄漏 / 无多余订阅 |

---

## 7. 验收标准

- [ ] 侧栏新增 "设备中心" 导航项，点击可进入
- [ ] 设备卡片网格显示 Local PC + 所有已配置 NAS 设备
- [ ] 每张卡片显示：在线状态指示灯、设备名、设备类型、CPU/内存/磁盘 摘要
- [ ] 点击 NAS 设备卡片展开详情区域：CPU/内存/磁盘 指标卡、进程 TOP15 表、Docker 容器表
- [ ] 点击 Local PC 设备卡片展开详情区域：CPU/内存/磁盘 指标卡、进程 TOP15 表（复用本机数据）
- [ ] 离线设备卡片显示灰色，不可展开详情
- [ ] 详情区域数据优先使用缓存，15 秒内自动更新
- [ ] 切换面板或关闭详情时正确清理订阅
- [ ] 现有 Dashboard / 进程列表 / 终端 / AI 助手 / 设置面板功能不受影响