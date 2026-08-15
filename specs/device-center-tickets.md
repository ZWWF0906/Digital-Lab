# Device Center v1.0 — 实现任务

> 基于 specs/device-center-v1.md | 日期: 2026-08-11

---

## Ticket 1: NAS Monitor — 新增进程采集

**文件**: `core/nas_monitor.py`  
**优先级**: P0  
**依赖**: 无

### 任务

1. 新增 `_parse_processes(top_output: str) -> list[dict]` 函数
   - 解析 `top -bn1` 输出
   - 找到 PID USER ... COMMAND 标题行
   - 提取前 15 个进程的：pid, name, cpu, memory, command
   - 返回列表，每个元素为 dict

2. 在 `_collect_nas()` 的采集循环中，在温度采集之后、uptime 采集之前，新增进程采集步骤
   - SSH 执行 `top -bn1`
   - 调用 `_parse_processes()` 解析
   - 写入 `data["processes"]`

### 验证
```python
# 检查 system_state
from core.system_state import system_state
nas = system_state.get("nas", {})
dev = nas.get("客厅NAS", {})
assert "processes" in dev
assert len(dev["processes"]) > 0
assert "pid" in dev["processes"][0]
```

---

## Ticket 2: NAS Monitor — 新增 Docker 容器采集

**文件**: `core/nas_monitor.py`  
**优先级**: P0  
**依赖**: 无

### 任务

1. 新增 `_parse_docker_stats(stats_output: str) -> list[dict]` 函数
   - 解析 `docker stats --no-stream --format '{{json .}}'` 输出
   - 每行一个 JSON 对象
   - 提取：Name, Container (前 12 字符作为 ID), CPUPerc, MemUsage, MemPerc, NetIO, BlockIO
   - 返回列表，每元素为 `{"name": ..., "image": ..., "status": "running", "cpu": ..., "memory": ...}`

2. 在 `_collect_nas()` 中实现 Docker 低频采集
   - 维护 `last_docker_collect` 时间戳变量
   - 每 30 秒执行一次 Docker 采集
   - 采集失败时保留上次数据（不清空）
   - 写入 `data["docker"]`，包含 containers 列表和 total_containers/running 统计

3. Docker 命令不可用时静默跳过（NAS 可能未安装 Docker）

### 验证
```python
nas = system_state.get("nas", {})
dev = nas.get("客厅NAS", {})
docker = dev.get("docker", {})
assert "containers" in docker
assert "total_containers" in docker
assert "running" in docker
```

---

## Ticket 3: 创建 Device Center 面板

**文件**: `panels/device-center.js`（新建）  
**优先级**: P0  
**依赖**: Ticket 1, Ticket 2（数据就绪）

### 任务

1. 导出 `init(container, api)` 函数
   - 返回 cleanup 函数

2. 构建 HTML 骨架
   ```html
   <div class="section-title">设备总览</div>
   <div class="device-grid" id="dc-grid"></div>
   <div class="device-detail" id="dc-detail" style="display:none"></div>
   ```

3. 实现设备卡片渲染函数 `renderDevices(state)`
   - 从 `state.monitor` 提取 Local PC 数据
   - 从 `state.nas` 提取所有 NAS 设备数据
   - 映射为统一设备卡片结构
   - 渲染到 `#dc-grid`

4. 实现设备卡片 HTML 模板
   - 在线状态指示灯（`.mc-status`）
   - 设备名称 + 设备类型
   - CPU / 内存 / 磁盘 迷你指标（复用 `.mc-mini` 样式）
   - NAS 卡片额外显示温度和 uptime
   - 离线设备添加 `.offline` 类（半透明）

5. 订阅 `api.onStateUpdate` 实时更新卡片

### 设备卡片映射逻辑

```javascript
function mapDevices(state) {
  const devices = [];
  // Local PC
  const m = state.monitor || {};
  devices.push({
    id: 'local',
    name: '本地主机',
    type: 'PC',
    online: true,
    cpu: m.cpu || 0,
    memory: m.memory || 0,
    disk: m.disk || 0,
  });
  // NAS devices
  const nas = state.nas || {};
  for (const [name, data] of Object.entries(nas)) {
    devices.push({
      id: `nas-${name}`,
      name,
      type: 'NAS',
      online: data.online !== false,
      cpu: data.cpu ?? 0,
      memory: data.memory?.percent ?? 0,
      disk: data.disk?.percent ?? 0,
      temperature: data.temperature,
      uptime: data.uptime,
    });
  }
  return devices;
}
```

---

## Ticket 4: Device Center — 设备详情区域

**文件**: `panels/device-center.js`  
**优先级**: P0  
**依赖**: Ticket 3

### 任务

1. 实现设备卡片点击事件
   - 点击选中设备（高亮 `.selected`）
   - 再次点击已选中设备 → 折叠详情
   - 点击其他设备 → 切换详情

2. 实现详情区域渲染函数 `renderDetail(deviceId, state)`
   - 根据 `deviceId` 获取对应设备数据
   - 离线设备不展开详情

3. 详情区域布局：
   ```
   ┌─ 详情标题栏 ──────────────────────────┐
   │ 客厅NAS  [在线]  [关闭]                 │
   ├────────────────────────────────────────┤
   │  [CPU 卡片]  [内存 卡片]  [磁盘 卡片]   │
   │  CPU: 8.5%   内存: 26.3%  磁盘: 24.0%  │
   │  + 温度 45°C  + uptime             │
   ├────────────────────────────────────────┤
   │  进程 TOP15                            │
   │  PID  | 名称 | CPU% | 内存% | 命令     │
   ├────────────────────────────────────────┤
   │  Docker 容器                           │
   │  名称 | 镜像 | 状态 | CPU | 内存       │
   │  运行中: 3 / 总计: 5                   │
   └────────────────────────────────────────┘
   ```

4. 资源指标卡片（CPU/内存/磁盘）
   - 复用现有 `.metric-card` 样式
   - 包含数值、进度条、趋势线（可选）

5. 进程 TOP15 表格
   - 复用现有 `table` 样式
   - 列：PID, 名称, CPU%, 内存%, 命令
   - Local PC 数据来自 `state.monitor.processes`
   - NAS 数据来自 `state.nas[name].processes`

6. Docker 容器表格
   - 列：名称, 状态, CPU%, 内存
   - 底部统计行：运行中/总计
   - 仅 NAS 设备显示

7. 详情区域状态更新
   - 已打开的详情在 `state-update` 时自动刷新数据
   - 不重新渲染整个 DOM，增量更新数值

---

## Ticket 5: 面板注册

**文件**: `panels/index.js`  
**优先级**: P0  
**依赖**: Ticket 3

### 任务

1. 新增 import：`import { init as initDeviceCenter } from './device-center.js';`
2. 在 PANELS 数组中添加：
   ```javascript
   { id: 'device-center', name: '设备中心', icon: '\u2302', init: initDeviceCenter },
   ```
3. 插入位置：在 `dashboard` 之后、`hardware` 之前（第 2 位）

---

## Ticket 6: Device Center 样式

**文件**: `styles.css`  
**优先级**: P1  
**依赖**: Ticket 3, Ticket 4

### 任务

1. `.device-grid` — 设备卡片网格
   ```css
   .device-grid {
     display: grid;
     grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
     gap: 14px;
     margin-bottom: 20px;
   }
   ```

2. `.device-card` — 设备卡片
   - 复用 `.metric-card` 基础样式
   - 新增 `.device-card.selected` 选中态：`border-color: var(--accent); box-shadow: 0 0 20px rgba(0,229,160,0.08);`
   - 新增 `.device-card.offline` 离线态：`opacity: 0.4; pointer-events: none;`
   - 新增 `.device-card-header`、`.device-card-type`、`.device-card-metrics`

3. `.device-detail` — 详情区域
   ```css
   .device-detail {
     background: var(--bg-secondary);
     border: 1px solid var(--border);
     border-radius: var(--radius-md);
     padding: 20px;
     margin-top: 4px;
     animation: fadeInUp 0.3s var(--ease-smooth);
   }
   ```

4. `.detail-header` — 详情标题栏
   - flex 布局，左侧设备名 + 在线状态，右侧关闭按钮
   - 关闭按钮复用 `.test-conn-btn` 样式

5. `.detail-gauges` — 资源指标行
   - 三列 grid，复用 `.metrics-grid` 样式

6. `.detail-section` — 详情子区域
   - 标题 + 内容，间距 16px

7. `.docker-table` — Docker 容器表
   - 复用现有 `table` 样式

8. `.docker-stat` — Docker 统计行
   - 小字体，居中或右对齐

---

## 执行顺序

```
Ticket 1 (进程采集)
  ↘
Ticket 2 (Docker 采集) → Ticket 3 (面板骨架) → Ticket 4 (详情区域) → Ticket 5 (注册) → Ticket 6 (样式)
```

建议按 Phase 执行：
- **Phase 1**: Ticket 1 + Ticket 2（后端，可并行）
- **Phase 2**: Ticket 3 + Ticket 4（前端核心，顺序依赖）
- **Phase 3**: Ticket 5 + Ticket 6（集成 + 样式，可并行）
- **Phase 4**: 端到端验证