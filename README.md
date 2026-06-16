实在是无聊，什么也不做显得我太浪费时间，于是就诞生了这个无聊的东西。我更希望做些什么来证明我存在过，用力地活过。软件目前是超级残废状态，至少我认为这是一个没有任何实际作用的东西。那么，屏幕前的你，祝你开心，我们后会有期！    --2026.6.16 ZWWF
---

## Digital Lab — 个人数字实验室

一个集硬件信息采集、系统实时监控、Web 仪表盘、桌面 GUI 于一体的综合工具箱。这里要感谢Deepseek提供的强大代码能力支持:)

### 快速开始

```bash
需提前安装好Python，系统版本至少是Windows 7
pip install -r requirements.txt
python main.py                     # 交互式菜单
python main.py dashboard           # Web 仪表盘 → http://127.0.0.1:8080
python main.py monitor --live      # 终端实时监控面板
python main.py monitor --daemon    # 启动后台守护进程
python main.py gui                 # 桌面 GUI 控制台
```

### 主要功能

| 模块 | 说明 |
|------|------|
| **Web 仪表盘** | 基于 Flask 的浏览器控制面板，支持深色/浅色主题切换，实时展示 CPU/内存/磁盘使用率、硬件信息、进程列表 |
| **系统监控** | 通过 psutil 采集 CPU/内存/磁盘/网络实时数据，支持终端动态刷新面板 (`--live`) |
| **硬件信息** | 自动识别处理器、显卡、内存、磁盘、显示器面板型号、网卡等完整硬件配置 |
| **后台守护** | 可启动后台进程定时采集监控数据并存入 SQLite 数据库，支持查看运行状态 |
| **告警系统** | CPU/内存/磁盘使用率超过阈值自动触发告警，支持手动测试 |
| **历史对比** | 当前实时数据与 1 小时 / 24 小时 / 7 天前的均值及峰值对比 |
| **进程管理** | 展示占用 CPU 最高的进程列表，含 PID、内存占用 |
| **快照管理** | 创建系统快照、对比两次快照差异、生成 HTML 快照报告 |
| **报告生成** | 按时间范围（1h/6h/24h/7d）统计均值/峰值/最低值，matplotlib 图表 + HTML 输出 |
| **快捷启动** | 管理常用应用的快捷方式，一键 Launch |
| **桌面 GUI** | Tkinter 桌面控制台，提供硬件概览和监控面板 |
| **一键重启** | 杀进程 + 清缓存 + 重启仪表盘和守护进程 |

### 项目结构

```
DigitalLab/
├── main.py                # CLI 入口，交互式菜单
├── core/                  # 核心模块
│   ├── dashboard_server.py  # Web 仪表盘服务端
│   ├── monitor.py           # 系统监控采集引擎
│   ├── hardware.py          # 硬件信息采集
│   ├── gui.py               # Tkinter 桌面 GUI
│   ├── reporter.py          # 报告生成
│   ├── snapshot.py          # 快照管理
│   ├── launcher.py          # 快捷启动
│   └── daemon.py            # 守护进程管理
├── interface/             # 前端模板
├── desktop/               # 桌面快捷方式脚本
├── config.json            # 项目配置
└── requirements.txt       # 依赖清单
```

### 环境要求

- Windows 7/8/10/11 x64
- Python 3.7+
- 可选：`nvidia-ml-py`（NVIDIA GPU 温度/利用率）、`pyamdgpuinfo`（AMD GPU 信息）

### 使用许可

© 2026 赵展铖 | 赞助者: Ave Mujica — Oblivionis
