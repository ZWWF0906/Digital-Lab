<h1 align="center">DigitalLab</h1>

<div align="center">

[简体中文](README.md) · [English](README.en-US.md) · [日本語](README.ja-JP.md)

</div>

<div align="center">

[![Version](https://img.shields.io/badge/version-1.6.0-blue)](https://github.com/ZWWF0906/Digital-Lab)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2B-lightgrey)](https://github.com/ZWWF0906/Digital-Lab)
[![Local-First](https://img.shields.io/badge/local--first-important)](https://github.com/ZWWF0906/Digital-Lab)
[![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20API-9cf)](https://github.com/ZWWF0906/Digital-Lab)
[![NAS](https://img.shields.io/badge/NAS-SSH%20monitor-orange)](https://github.com/ZWWF0906/Digital-Lab)

</div>

<div align="center">
  <a href="https://apps.microsoft.com/detail/9n0rtlx1bcp5?referrer=appbadge&mode=full" target="_blank" rel="noopener noreferrer">
	<img src="https://get.microsoft.com/images/zh-cn%20light.svg" width="200"/>
  </a>
</div>

个人数字实验室平台 — 面向个人设备管理、数据感知与 AI 扩展的桌面应用。本地优先、模块化、可扩展，将你的个人电脑转变为一个可编程、可感知、可对话的数字工作空间。

> **发布渠道**：DigitalLab 1.6.0 是最后一个通过 GitHub 提供独立安装包的版本。自 1.6.1 起，正式版本仅通过 Microsoft Store 发布；GitHub 继续作为源码、文档和协作平台。

---

## Features

### 仪表盘
CPU / 内存 / 磁盘 / 网络速度实时监控，迷你趋势线与健康状态灯一目了然。支持性能历史图表（24 小时平均值与峰值）、进程列表，以及 NAS 设备状态卡片。

### 设备中心
本机硬件信息全景展示：CPU 型号 / 核心 / 线程 / 频率，内存容量 / 类型 / 频率 / 插槽，GPU 型号 / 显存 / 温度 / 利用率，磁盘型号 / 容量 / 健康度 / 分区，显示器分辨率 / 刷新率，网络适配器状态，系统信息（OS 版本、运行时间）。

### SSH 终端
基于 xterm.js 的 Web 终端，通过 SSH 连接到 NAS 设备，支持多会话管理，CMD 风格深色主题。

### AI 助手
流式输出，支持 Ollama 本地模型或 OpenAI 兼容 API（如 DeepSeek）。多轮对话，Token 逐字渲染，自动注入当前系统状态作为对话上下文，可回答 CPU / 内存 / 磁盘 / 硬件 / NAS 相关问题。已修复中文乱码，推荐使用具备良好中文能力的模型（如 qwen2.5:7b-instruct-q4_K_M）。

### 设置面板
日志级别、监控阈值、NAS 设备管理、AI 提供商切换、硬件加速开关、浅色/深色主题切换（浅色基于 Emerald 设计体系，终端保持深色）。提供统一的问题反馈与举报入口（邮件 / GitHub Issues）。

---

## Architecture

```text
┌──────────────────────────────────────┐
│  Electron 主进程（main.js）           │
│  窗口管理 · 系统托盘 · IPC 通信        │
│         │ spawn                      │
│         ▼                            |
│  Python 子进程（main.py）             │
│  监控采集 · 硬件检测 · NAS SSH · AI   |
│         │                            │
│  stdin/stdout JSON Lines 协议        │
│  请求-响应：requestId 匹配            │
│  状态更新：广播模式                    │
└──────────────────────────────────────┘
```

---

## 核心设计原则

- **所有数据进入 system_state，所有 UI 只消费 system_state** — 单一数据源，前端与后端解耦
- **本地优先，模块化，可扩展** — 核心功能无需网络，面板按需加载
- **Electron 核心通信不依赖 HTTP** — 采用 JSON Lines IPC 协议，零网络开销；同时提供可选 Web Dashboard 服务
- **Privacy First** — 设备数据默认保存在本地，敏感配置存储于用户目录；AI/NAS 凭据以当前 Windows 用户的 DPAPI 密文保存，远程 AI 端点要求 HTTPS（本地 Ollama 的 loopback HTTP 除外）

---

## Roadmap

- [x] 系统实时监控 — v1.0.0
- [x] 硬件信息中心 — v1.0.0
- [x] NAS SSH 管理 — v1.0.0
- [x] AI Assistant — v1.0.0
- [x] Electron + Python 架构 — v1.0.0
- [x] 浅色主题与主题切换 — v1.1.0
- [x] 问题反馈与举报入口 — v1.1.0
- [ ] Agent 自动化能力
- [ ] 插件系统
- [ ] 更多 NAS 平台支持
- [x] Personal Digital Memory — v1.6.0
- [ ] 数据分析与时间线系统

---

## 安装说明

### 普通用户

1. **DigitalLab 1.6.0**：这是最后一个提供 GitHub 独立安装包的版本；从 [Releases](https://github.com/ZWWF0906/Digital-Lab/releases) 下载 `DigitalLab Setup.exe`。
2. **1.6.1 及以后**：正式版本仅通过 [Microsoft Store](https://apps.microsoft.com/detail/9n0rtlx1bcp5) 安装和更新，GitHub 不再提供独立安装包。
3. 安装程序需要管理员权限，并安装到 per-machine 目录；启动后在设置面板中添加 NAS 设备信息。
4. **无需安装 Python 或 Node.js**，所有运行时依赖已内置。

### 系统要求

| 要求 | 最低配置 |
|------|----------|
| 操作系统 | Windows 10 或更高版本 |
| 处理器 | x64 架构，双核 1.5 GHz |
| 内存 | 4 GB |
| 显卡 | Windows 10 兼容的显卡/显示驱动；硬件加速可在设置中关闭。DigitalLab 本身不要求特定显存；如使用本地 Ollama 模型，显存/内存需求取决于所运行的模型。 |
| 存储 | 2 GB 可用空间 |

---

## 开发构建

### 环境要求

- Node.js 18+
- Python 3.10+

### 开发模式

```bash
# 安装前端依赖
npm install

# 启动开发模式（自动启动 Python 子进程）
npm start
```

### 打包

```bash
# 打包 Python 后端为独立可执行文件
pyinstaller backend.spec

# 打包 Electron 桌面应用
npm run build
```

---

## 项目结构

```text
DigitalLab/
├── main.js / preload.js              # Electron 主进程与 IPC 桥接
├── preload-terminal.js / renderer-terminal.js
├── renderer.js / dashboard.html / terminal.html
├── styles.css / i18n.js / locales/   # 样式、国际化和三语资源
├── onboarding.js / splash.js / theme-init.js / lang-init.js / boot-text.js
├── core/                             # Python 后端
│   ├── config.py / secret_store.py   # 双文件配置与 DPAPI 凭据保护
│   ├── net_policy.py / path_policy.py / ssh_trust.py
│   ├── agent_tools.py                # 只读 Agent 工具基础设施（当前不暴露给模型）
│   ├── ai_client.py / ai_memory.py / chat_store.py
│   ├── nas_monitor.py / monitor.py / collector.py
│   └── ...                           # 硬件、状态、日志、快照等模块
├── panels/                           # 前端面板
│   ├── index.js / safe-dom.js
│   └── dashboard.js / device-center.js / ai-assistant.js / terminal.js / settings.js
├── build/                            # 图标、字体等打包资源
├── scripts/                          # build-windows.ps1 / build-backend.ps1
├── package.json / package-lock.json
├── backend.spec / requirements.txt
├── config.schema.json
├── README.md / README.en-US.md / README.ja-JP.md
├── CHANGELOG.md / CHANGELOG.zh-CN.md / CHANGELOG.ja-JP.md
├── PRIVACY.md
└── LICENSE
```

---

## 配置系统

DigitalLab 采用双层配置存储，将公开设置与敏感数据分离：

| 配置文件 | 位置 | 内容 |
|----------|------|------|
| `config.json` | `%APPDATA%\DigitalLab\` | 运行时公共配置：端口、阈值、日志级别、开关；首次运行后生成 |
| `user_config.json` | `%APPDATA%\DigitalLab\` | 敏感字段：`ai`、`nas_devices`、`auth_token`；值由 Windows DPAPI 保护为 `dpapi:v1:` 密文，不是明文 |

启动时会把旧版 `config.json`/`user_config.json` 中的明文凭据迁移为 DPAPI 密文；迁移失败时应用阻止使用未保护凭据，不会静默回退到明文。

---

## 窗口与托盘

- 窗口尺寸：1100 x 750，最小 900 x 600
- 单实例锁，防止多开
- 关闭按钮最小化到系统托盘，不退出
- 托盘菜单：显示主窗口 / 退出
- 硬件加速默认关闭（兼容虚拟机环境），可在设置中切换
- Python 崩溃自动重启，最多 3 次，超限后通知用户

---

## 测试阶段说明

- **SSH 终端** 与 **AI 助手** 目前处于测试阶段，首次进入时会弹窗提示
- SSH 会话暂不支持自动重连
- AI 助手当前为对话模式，不包含 Agent 工具调用能力
- NAS 终端依赖 SSH 服务，请确保目标设备已开启 SSH 并正确配置凭据

---

## 贡献

欢迎提交 Issue 和 Pull Request。

---

## 隐私政策

本应用遵循本地优先原则，详见 [PRIVACY.md](https://github.com/ZWWF0906/Digital-Lab/blob/main/PRIVACY.md)。

---

## 许可证

ISC License  2026 ZWWF0906
