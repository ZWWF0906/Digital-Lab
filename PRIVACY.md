# DigitalLab 隐私政策 / Privacy Policy

最后更新：2026-09-10 / Last updated: 2026-09-10

[简体中文](#简体中文) · [English](#english)

---

<a id="简体中文"></a>

## 简体中文

# DigitalLab 隐私政策

最后更新：2026-09-10

## 核心原则：本地优先

DigitalLab 遵循"本地优先"原则。所有数据采集、存储和处理均在用户本机完成，不主动向任何远程服务器发送用户数据。应用不具备遥测、用户行为追踪或后台数据上传功能。

## 收集的信息

DigitalLab 在本机采集以下信息，仅用于仪表盘展示和本地分析：

1. **本机硬件信息**：CPU 型号与频率、内存容量与类型、GPU 型号与显存、磁盘型号与容量、显示器规格、网络适配器信息、系统型号与制造商
2. **系统性能数据**：CPU 使用率、内存占用率、磁盘使用率、网络速度、进程列表（PID、名称、CPU 和内存占用）
3. **NAS 设备数据**：用户主动配置的 NAS 设备的 CPU、内存、磁盘、Docker 容器状态（通过 SSH 连接采集，数据存储在本机）
4. **AI 对话记录**：用户与 AI 助手的对话内容（仅在用户主动使用 AI 功能时产生，存储在本机内存中，关闭应用后清除）
   - **AI 记忆（可选）**：仅在用户于设置面板开启记忆后，用户在对话中明确表达、值得长期记住的偏好（如称呼、设备名、使用习惯）会持久化保存在 `%APPDATA%\DigitalLab\memory\ai_memory.jsonl`。该数据不离开本机，不上传至任何服务器，可在设置面板随时逐条删除或全部清空。关闭记忆时不持久化任何对话内容，已保存的记忆也不会被读取或注入对话。开启记忆并使用云端模型时，这些记忆会随对话内容一并发送至该云服务商。

## 数据存储位置

所有数据存储在用户可写目录：

```
%APPDATA%\DigitalLab\
├── config.json              # 公共配置
├── user_config.json          # 敏感配置（API Key、NAS 凭据）
├── logs/
│   ├── cache/
│   │   └── hardware.json     # 硬件信息缓存
│   └── monitor/
│       ├── monitor.db        # 性能快照数据库（SQLite）
│       └── daemon.log        # 监控日志
└── memory/
    └── ai_memory.jsonl       # AI 长期记忆（仅开启记忆后生成）
```

不使用注册表、不写入系统目录、不创建隐藏服务。

## 日志

DigitalLab 在本机记录运行日志，用于故障排查和性能分析：

- `logs/monitor/daemon.log`：JSON Lines 格式的监控日志，记录时间戳、级别、事件消息及相关字段（如进程 PID、采集计数、指标阈值、NAS 设备名称与主机地址）
- `logs/cache/hardware.json`：硬件信息缓存，避免每次启动重复采集

日志仅写入本机用户可写目录，不包含 AI 对话内容，不上传至任何服务器，也不用于用户行为分析。删除 `%APPDATA%\DigitalLab\logs\` 目录即可清除全部日志。

## 不收集的信息

DigitalLab 不收集以下信息：

- 个人身份信息（姓名、邮箱、手机号）
- 浏览器历史、 cookie 或密码
- 文件内容（仅统计磁盘使用率，不扫描文件内容）
- 屏幕截图或键盘记录
- 位置信息
- 联系人或通讯录

## 敏感信息保护

以下信息被视为敏感数据，存储在 `%APPDATA%\DigitalLab\user_config.json` 中，与公共配置分离：

- AI 服务 API Key
- NAS 设备 SSH 凭据（用户名、密码）
- 认证 Token

敏感配置不写入随应用分发的 `config.json`，不包含在安装包中，不上传至任何服务器。

## 第三方服务说明

DigitalLab 在用户主动配置后可能连接以下第三方服务：

1. **Ollama**（本地模型）：AI 助手功能，连接 `localhost:11434`，数据不离开本机
2. **OpenAI API**（云端模型）：AI 助手功能，仅用户输入的对话内容通过 API 发送至 OpenAI，该部分数据受 OpenAI 隐私政策约束
3. **NAS 设备**：通过 SSH 连接用户局域网内的设备，数据仅在局域网内传输

以上连接均为用户主动配置后触发，默认不连接任何远程服务。

## 数据删除方法

### 通过应用内删除

在 DigitalLab 设置页面清除配置即可重置应用数据。

### 手动删除

删除以下目录即可清除所有 DigitalLab 数据：

```
%APPDATA%\DigitalLab\
```

卸载应用不会自动删除用户数据目录，用户需手动删除。

## 政策变更

本隐私政策如有更新，将同步修改本文件顶部的"最后更新"日期，并随应用版本一同发布。涉及数据处理方式的重大变更会在应用内或项目仓库的发布说明中提示。继续使用更新后的版本即表示接受修订后的政策。

## 联系方式

如有隐私相关问题，请联系：

- GitHub Issues: https://github.com/ZWWF0906/Digital-Lab/issues
- 邮箱: ZWWF0906@outlook.com

---

<a id="english"></a>

## English

# DigitalLab Privacy Policy

Last updated: 2026-09-10

In case of any discrepancy or ambiguity between this English translation and the Simplified Chinese version, the Simplified Chinese version (PRIVACY.md) shall prevail.

## Core Principle: Local-First

DigitalLab follows a "local-first" principle. All data collection, storage, and processing are performed on the user's own machine, and no user data is actively sent to any remote server. The application has no telemetry, no user behavior tracking, and no background data upload capability.

## Information Collected

DigitalLab collects the following information on the local machine, solely for dashboard display and local analysis:

1. **Local hardware information**: CPU model and frequency, memory capacity and type, GPU model and VRAM, disk model and capacity, monitor specifications, network adapter information, system model and manufacturer
2. **System performance data**: CPU usage, memory usage, disk usage, network speed, process list (PID, name, CPU and memory usage)
3. **NAS device data**: CPU, memory, disk, and Docker container status of NAS devices that the user has actively configured (collected through SSH connections; data is stored on the local machine)
4. **AI conversation records**: Conversation content between the user and the AI assistant (generated only when the user actively uses the AI feature; stored in local memory and cleared when the application is closed)
   - **AI memory (optional)**: Only after the user enables memory in the settings panel, preferences that the user has explicitly expressed in conversation and that are worth remembering long-term (such as how they are addressed, device names, and usage habits) are persisted in `%APPDATA%\DigitalLab\memory\ai_memory.jsonl`. This data does not leave the local machine and is not uploaded to any server, and it can be deleted item by item or cleared entirely at any time in the settings panel. When memory is disabled, no conversation content is persisted, and stored memories are neither read nor injected into conversations. When memory is enabled and a cloud model is used, these memories are sent to that cloud service provider together with the conversation content.

## Data Storage Locations

All data is stored in user-writable directories:

```
%APPDATA%\DigitalLab\
├── config.json              # Public configuration
├── user_config.json          # Sensitive configuration (API Key, NAS credentials)
├── logs/
│   ├── cache/
│   │   └── hardware.json     # Hardware information cache
│   └── monitor/
│       ├── monitor.db        # Performance snapshot database (SQLite)
│       └── daemon.log        # Monitoring log
└── memory/
    └── ai_memory.jsonl       # AI long-term memory (created only after memory is enabled)
```

No registry is used, no system directories are written to, and no hidden services are created.

## Logging

DigitalLab writes runtime logs on the local machine for troubleshooting and performance analysis:

- `logs/monitor/daemon.log`: Monitoring log in JSON Lines format, recording timestamps, levels, event messages, and related fields (such as process PID, collection counts, metric thresholds, and NAS device names and host addresses)
- `logs/cache/hardware.json`: Hardware information cache, to avoid collecting the same data again on every start

Logs are written only to user-writable directories on the local machine. They do not contain AI conversation content, are not uploaded to any server, and are not used for user behavior analysis. Delete the `%APPDATA%\DigitalLab\logs\` directory to clear all logs.

## Information Not Collected

DigitalLab does not collect the following information:

- Personally identifiable information (name, email address, phone number)
- Browser history, cookies, or passwords
- File contents (only disk usage is counted; file contents are not scanned)
- Screenshots or keystroke logging
- Location information
- Contacts or address book

## Sensitive Information Protection

The following information is treated as sensitive data, stored in `%APPDATA%\DigitalLab\user_config.json`, and kept separate from the public configuration:

- AI service API Key
- NAS device SSH credentials (username, password)
- Authentication Token

Sensitive configuration is not written into the `config.json` distributed with the application, is not included in the installer, and is not uploaded to any server.

## Third-Party Services

DigitalLab may connect to the following third-party services after the user actively configures them:

1. **Ollama** (local model): AI assistant feature, connects to `localhost:11434`; data does not leave the local machine
2. **OpenAI API** (cloud model): AI assistant feature; only the conversation content entered by the user is sent to OpenAI through the API, and that portion of the data is subject to OpenAI's privacy policy
3. **NAS devices**: Connects through SSH to devices within the user's local network; data is transmitted only within the local network

All of the above connections are triggered only after the user actively configures them; by default, no remote service is connected.

## How to Delete Data

### Deleting Through the Application

Clearing the configuration on the DigitalLab settings page resets the application data.

### Manual Deletion

Delete the following directory to clear all DigitalLab data:

```
%APPDATA%\DigitalLab\
```

Uninstalling the application does not automatically delete the user data directory; the user must delete it manually.

## Policy Changes

If this privacy policy is updated, the "Last updated" date at the top of this file will be revised accordingly, and the update will be released together with an application version. Major changes involving how data is processed will be announced in the application or in the release notes of the project repository. Continuing to use the updated version constitutes acceptance of the revised policy.

## Language

This document is a translation of the Simplified Chinese original. In case of any discrepancy or ambiguity, the Simplified Chinese version (PRIVACY.md) shall prevail.

## Contact

For privacy-related questions, please contact:

- GitHub Issues: https://github.com/ZWWF0906/Digital-Lab/issues
- Email: ZWWF0906@outlook.com
