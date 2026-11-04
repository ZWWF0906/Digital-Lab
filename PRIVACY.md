# DigitalLab 隐私政策 / Privacy Policy

最后更新：2026-11-04 / Last updated: 2026-11-04

[简体中文](#简体中文) · [English](#english) · [日本語](#日本語)

---

<a id="简体中文"></a>

## 简体中文

# DigitalLab 隐私政策

最后更新：2026-11-04

## 核心原则：本地优先，远程传输只发生在你主动使用云端 AI 或配置 NAS 时

DigitalLab 以本地运行为主：硬件与性能数据在本机采集、在本机展示与保存；监控数据、配置与 AI 数据默认只写在本机。应用不具备遥测、用户行为追踪或后台数据上传功能。

需要区分三种会离开本机的情形：

1. 本地 Ollama 模型：请求只发往本机 `localhost`，不离开本机。
2. 云端 AI 模型（OpenAI 兼容 API，例如 DeepSeek）：仅在你使用 AI 助手功能时，本次请求的内容会发送到你配置的服务端点，由该服务商处理并受其隐私政策约束。
3. NAS 设备：仅在你配置了 NAS 后，应用通过 SSH 连接你局域网内的设备，数据在局域网内传输。

除上述情形外，应用不会主动向远程服务器发送数据。本文档只描述当前版本实际实现的行为；应用未实现日志脱敏，未对凭据做加密存储，也未强制 HTTPS（详见"敏感信息保护"）。

## 收集的信息

DigitalLab 在本机采集以下信息，用于仪表盘展示、本地分析与 AI 助手提供上下文：

1. **本机硬件信息**：CPU 型号与频率、内存容量与类型、GPU 型号与显存、磁盘型号与容量、显示器规格、网络适配器信息、系统型号与制造商。
2. **系统性能数据**：CPU 使用率、内存占用率、磁盘使用率、网络速度、进程列表（PID、名称、CPU 和内存占用）。
3. **NAS 设备数据**：你主动配置的 NAS 设备的 CPU、内存、磁盘、Docker 容器状态（通过 SSH 连接采集，数据存储在本机）。
4. **AI 对话历史**：你与 AI 助手的对话内容（仅在你主动使用 AI 功能时产生）。默认保存在本机文件 `%APPDATA%\DigitalLab\memory\chat_history.jsonl`，重启应用后恢复；可在设置面板的"对话历史"中设置保存开关、保留条数上限（超出后按最旧裁剪）或一键清空。
   - 关闭"保存对话历史"只是停止把新消息写入该本地文件，不会删除已有记录（需手动清空或删除文件）。
   - 关闭"保存对话历史"不会停止 AI 请求：你当前发送的消息与会话内已有的对话内容仍会随本次请求发送给所选 AI 服务商。
   - 对话历史文件本身不会被整体上传到任何服务器。
5. **AI 记忆（可选，默认关闭）**：仅在你在设置中开启记忆后，你在对话中明确表达、值得长期记住的偏好（如称呼、设备名、使用习惯）会持久化保存在 `%APPDATA%\DigitalLab\memory\ai_memory.jsonl`。开启记忆并使用云端模型时，这些记忆内容会随请求发送至该云服务商。关闭记忆后：不再写入新的记忆，已保存的记忆文件不会被读取或注入对话，但文件本身仍保留在本机，需在设置中删除或清空。
6. **AI 请求上下文（仅在使用 AI 功能时生成）**：发送给所选 AI 服务商的请求包含四部分：静态提示词（角色设定、使用规则、输出格式约束；开启记忆时还含记忆指令）、记忆内容（仅开启记忆时，最近若干条，按时间与标识确定性排序）、实时系统状态摘要（CPU/内存/磁盘使用率，CPU/GPU/内存/硬盘的型号与容量，已配置 NAS 设备的名称、在线状态、CPU/内存/磁盘占用与温度）、以及对话内容（你当前发送的消息与会话内已有的对话，后端只保留最近 16 条）。
   - 使用本地 Ollama 时，上述内容只在本机处理。
   - 使用云端模型时，上述内容会发送至你配置的服务端点。
   - 不随请求发送：NAS 主机地址与登录凭据、完整进程列表与命令行、日志内容、AI 记忆的标识/类别/标签/来源字段、API Key 本身（API Key 仅用于请求头认证）。

**AI 记忆与对话历史是两个相互独立的功能**：记忆开关控制长期记忆的读取、注入与持久化，默认关闭；对话历史保存开关控制本地聊天记录写入，默认开启。关闭其中一个不会关闭另一个，也不会停止 AI 请求。

## 数据存储位置

数据存储在用户可写目录，主要位置如下：

```
%APPDATA%\DigitalLab\
├── config.json               # 公共配置
├── user_config.json           # 敏感配置（AI 配置与 API Key、NAS 设备与凭据、认证 Token 字段）
├── logs/
│   ├── cache/
│   │   └── hardware.json      # 硬件信息缓存
│   └── monitor/
│       ├── monitor.db         # 性能快照数据库（SQLite）
│       ├── daemon.log         # 监控日志
│       └── daemon.pid         # 监控守护进程 PID
├── memory/
│   ├── chat_history.jsonl     # AI 对话历史（默认开启，可设上限或清空）
│   └── ai_memory.jsonl        # AI 长期记忆（默认关闭，开启后生成）
└── tools/ experiments/ notes/ archive/ interface/   # 预留目录（当前版本未实际写入业务数据）

%APPDATA%\digital-lab\
└── config.json                # 界面偏好（主题、语言、开屏动画开关、引导完成状态）
```

程序目录内也会写入运行数据（开发模式下是源码目录，安装后是安装目录内）：

- `memory\daily.jsonl`：按日性能汇总
- `snapshots\`：性能快照
- `reports\`：报告
- `launchers.json`：快捷启动器配置

说明：对话历史与 AI 记忆的保存目录可在设置中修改（对应 `ai.history.dir` 与 `ai.memory.dir`），修改后以上述你选择的目录为准。上表中的 `memory\` 是 AI 数据目录，与程序目录下用于按日汇总的 `memory\` 不是同一目录。

## 日志

DigitalLab 在本机记录运行日志，用于故障排查和性能分析：

- `%APPDATA%\DigitalLab\logs\monitor\daemon.log`：JSON Lines 格式的监控日志，记录时间戳、级别、事件消息与相关字段（如进程 PID、采集计数、指标阈值、NAS 设备名称与主机地址）。
- `%APPDATA%\digital-lab\digital-lab.log`：界面进程日志，记录窗口生命周期、异常与 I/O 错误摘要。
- `%APPDATA%\DigitalLab\logs\cache\hardware.json`：硬件信息缓存，避免每次启动重复采集。

日志仅写入本机用户可写目录，不包含 AI 对话内容与请求上下文，不上传至任何服务器，也不用于用户行为分析。日志未做脱敏处理。删除 `%APPDATA%\DigitalLab\logs\` 目录与 `%APPDATA%\digital-lab\digital-lab.log` 即可清除。

## 不主动收集的信息

DigitalLab 不主动采集以下信息：

- 个人身份信息（姓名、邮箱、手机号）
- 浏览器历史、Cookie 或密码
- 文件内容（仅统计磁盘使用率，不扫描文件内容）
- 屏幕截图或键盘记录
- 位置信息
- 联系人或通讯录

但你主动输入的信息不受此限：你在对话中提到的个人信息、在设置中填写的称呼与设备名，会按"收集的信息"与"数据存储位置"所述保存在本机；使用云端模型时，对话内容与 AI 请求上下文会随请求发送给你选择的服务商。请勿在对话或配置中填写你不希望发送给云服务商的敏感信息。

## 敏感信息保护

以下信息视为敏感数据，存储在 `%APPDATA%\DigitalLab\user_config.json`，与公共配置 `config.json` 分离，也不包含在安装包中：

- **AI 服务 API Key**：用于向你所配置的 AI 端点进行身份认证，以 HTTP 请求头（`Authorization: Bearer`）形式随请求发送；不会写入提示词、系统消息或对话正文。传输是否加密取决于你配置的 `base_url`，应用未强制 HTTPS，请使用 https 端点并自行确认其安全性。
- **NAS 设备 SSH 凭据（用户名、密码）**：仅用于通过 SSH 连接你配置的 NAS，用于采集监控数据与建立终端会话；不随 AI 请求发送，也不进入 AI 请求上下文（上下文只含 NAS 名称、在线状态与负载指标）。
- **认证 Token**：`user_config.json` 中可能出现该字段（早期版本写入），当前版本未发现实际使用；如存在可手动删除该字段。

补充说明：这些凭据会通过本机 IPC 传给应用自身的渲染进程，以便设置界面显示与编辑（输入框以密码类型掩码显示）；这是本机进程间传递，不是远程传输。凭据以明文形式保存在 `user_config.json` 中（未加密），请按敏感文件保管、不要分享。

## 第三方服务说明

DigitalLab 在你主动配置后可能连接以下第三方服务：

1. **Ollama（本地模型）**：AI 助手功能，连接 `localhost:11434`，数据不离开本机。
2. **云端模型（OpenAI 兼容 API，例如 DeepSeek）**：AI 助手功能。发送内容包括：对话内容、提示词模板、实时系统状态摘要（CPU/内存/磁盘使用率、硬件型号与容量、NAS 名称与负载）、（开启 AI 记忆时的）长期记忆内容；API Key 作为请求头用于认证。该部分数据由你选择的服商处理，受其隐私政策约束。
3. **NAS 设备**：通过 SSH 连接你局域网内的设备，数据在局域网内传输。

以上连接均为你主动配置或主动使用后触发，默认不连接任何远程服务。

## 数据删除方法

### 通过应用内删除

- **对话历史**：设置 → AI 助手 → 对话历史。可关闭保存（停止写入新记录）、设置保留条数上限（超出按最旧裁剪）、一键清空全部历史（不可恢复）。当前界面未提供单条删除入口（后端存在对应接口）。
- **AI 记忆**：设置 → AI 助手 → AI 记忆。可关闭记忆、查看条目、逐条删除、清空全部；另有"清理重复"可合并重复条目（同一内容保留最早一条）。若你改过记忆目录，请同时删除旧目录中的文件。
- **其他配置**（AI 提供方与 Key、监控阈值、设备列表、主题、语言等）：只能逐项修改，或按下面的方式手动删除数据目录。

### 手动删除

- `%APPDATA%\DigitalLab\`：公共与敏感配置、监控日志与快照数据库、AI 对话历史、AI 记忆
- `%APPDATA%\digital-lab\`：界面偏好（主题、语言、开屏动画开关、引导完成状态）与界面日志
- 程序目录内的 `memory\`、`snapshots\`、`reports\` 与 `launchers.json`：按日汇总、性能快照、报告、快捷启动器配置

卸载应用不会自动删除上面两个 `%APPDATA%` 目录，需要手动删除；程序目录内的这些文件会随安装目录一起被卸载程序移除。

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

Last updated: 2026-11-04

In case of any discrepancy or ambiguity between this English translation and the Simplified Chinese version, the Simplified Chinese version (PRIVACY.md) shall prevail.

## Core Principle: Local-First, Remote Transfer Only When You Use Cloud AI or Configure NAS

DigitalLab runs primarily on the local machine: hardware and performance data are collected, displayed and stored locally; monitoring data, configuration and AI data are written locally by default. The application has no telemetry, no user behavior tracking and no background upload.

There are three situations in which data leaves the machine:

1. Local Ollama model: requests go only to local `localhost` and do not leave the machine.
2. Cloud AI model (OpenAI-compatible API, for example DeepSeek): only when you use the AI assistant, the content of this request is sent to the endpoint you configured, processed by that provider and subject to its privacy policy.
3. NAS devices: only after you configure a NAS, the application connects over SSH to devices in your local network; data is transmitted within the local network.

Outside these situations, the application does not proactively send data to remote servers. This document describes only behavior actually implemented in the current version; the application does not implement log redaction, does not encrypt credentials at rest, and does not enforce HTTPS (see "Sensitive Information Protection").

## Information Collected

DigitalLab collects the following information on the local machine, used for dashboard display, local analysis and providing context to the AI assistant:

1. **Local hardware information**: CPU model and frequency, memory capacity and type, GPU model and VRAM, disk model and capacity, monitor specifications, network adapter information, system model and manufacturer.
2. **System performance data**: CPU usage, memory usage, disk usage, network speed, process list (PID, name, CPU and memory usage).
3. **NAS device data**: CPU, memory, disk and Docker container status of NAS devices you configured (collected through SSH; data stored locally).
4. **AI conversation history**: conversation content between you and the AI assistant (generated only when you use the AI feature). By default it is stored in the local file `%APPDATA%\DigitalLab\memory\chat_history.jsonl` and restored after a restart; the Chat History section in Settings lets you toggle saving, set a retention limit (oldest entries are trimmed beyond it) or clear everything.
   - Turning off "Save chat history" only stops new messages from being written to that local file; existing records are not deleted (clear them or delete the file manually).
   - Turning off "Save chat history" does not stop AI requests: the message you send now and the conversation content already in the session are still sent to the selected AI provider with this request.
   - The history file itself is never uploaded as a whole to any server.
5. **AI memory (optional, off by default)**: only after you enable memory in Settings, preferences you explicitly expressed and that are worth remembering long-term (such as how you are addressed, device names, usage habits) are persisted in `%APPDATA%\DigitalLab\memory\ai_memory.jsonl`. When memory is enabled and a cloud model is used, these memory entries are sent to that provider with the request. When memory is disabled: no new memory is written, the stored file is neither read nor injected into conversations, but the file remains on this machine until you delete or clear it in Settings.
6. **AI request context (created only when the AI feature is used)**: a request sent to the selected AI provider contains four parts: the static prompt (role, usage rules, output format constraints; plus memory instructions when memory is enabled), memory content (only when memory is enabled; the most recent entries, deterministically sorted by time and identifier), a real-time system status summary (CPU/memory/disk usage, CPU/GPU/memory/disk models and capacities, and the names, online state, CPU/memory/disk usage and temperature of configured NAS devices), and the conversation content (the message you send now plus the conversation already in the session; the backend keeps only the last 16 messages).
   - With local Ollama, the above is processed only on this machine.
   - With a cloud model, the above is sent to the endpoint you configured.
   - Not sent with requests: NAS host addresses and login credentials, the full process list and command lines, log contents, AI memory id/kind/tags/source fields, and the API Key itself (the API Key is used only for request-header authentication).

**AI memory and chat history are two independent features**: the memory switch controls reading, injection and persistence of long-term memory and is off by default; the history switch controls local chat record writing and is on by default. Turning one off does not turn off the other and does not stop AI requests.

## Data Storage Locations

Data is stored in user-writable directories, mainly:

```
%APPDATA%\DigitalLab\
├── config.json               # Public configuration
├── user_config.json           # Sensitive configuration (AI settings and API Key, NAS devices and credentials, authentication token field)
├── logs/
│   ├── cache/
│   │   └── hardware.json      # Hardware information cache
│   └── monitor/
│       ├── monitor.db         # Performance snapshot database (SQLite)
│       ├── daemon.log         # Monitoring log
│       └── daemon.pid         # Monitoring daemon PID
├── memory/
│   ├── chat_history.jsonl     # AI conversation history (on by default; limit or clear)
│   └── ai_memory.jsonl        # AI long-term memory (off by default; created after enabling)
└── tools/ experiments/ notes/ archive/ interface/   # Reserved directories (no business data written in the current version)

%APPDATA%\digital-lab\
└── config.json                # Interface preferences (theme, language, splash animation toggle, onboarding completion state)
```

The program directory also receives runtime data (the source directory in development, the installation directory after installation):

- `memory\daily.jsonl`: daily performance aggregates
- `snapshots\`: performance snapshots
- `reports\`: reports
- `launchers.json`: quick-launcher configuration

Note: the storage directories of chat history and AI memory can be changed in Settings (`ai.history.dir` and `ai.memory.dir`); after that, the directory you chose applies. The `memory\` in the table above is the AI data directory and is not the same as the `memory\` used for daily aggregates inside the program directory.

## Logging

DigitalLab writes runtime logs on the local machine for troubleshooting and performance analysis:

- `%APPDATA%\DigitalLab\logs\monitor\daemon.log`: JSON Lines monitoring log with timestamps, levels, event messages and related fields (such as process PID, collection counts, metric thresholds, and NAS device names and host addresses).
- `%APPDATA%\digital-lab\digital-lab.log`: interface process log recording window lifecycle, exceptions and I/O error summaries.
- `%APPDATA%\DigitalLab\logs\cache\hardware.json`: hardware cache, to avoid re-collecting on every start.

Logs are written only to user-writable directories on the local machine, contain no AI conversation content or request context, are not uploaded to any server, and are not used for user behavior analysis. Logs are not redacted. Delete the `%APPDATA%\DigitalLab\logs\` directory and `%APPDATA%\digital-lab\digital-lab.log` to clear them.

## Information Not Proactively Collected

DigitalLab does not proactively collect:

- Personally identifiable information (name, email address, phone number)
- Browser history, cookies or passwords
- File contents (only disk usage is counted; file contents are not scanned)
- Screenshots or keystroke logging
- Location information
- Contacts or address book

Information you enter yourself is different: personal information you mention in conversation or fill in under Settings (such as how you are addressed, device names) is stored on this machine as described in "Information Collected" and "Data Storage Locations"; when a cloud model is used, the conversation content and AI request context are sent with the request to the provider you chose. Do not type sensitive information you do not want sent to a cloud provider into the conversation or configuration.

## Sensitive Information Protection

The following information is treated as sensitive and stored in `%APPDATA%\DigitalLab\user_config.json`, separate from the public `config.json`, and is not included in the installer:

- **AI service API Key**: used to authenticate to the AI endpoint you configured and sent as an HTTP request header (`Authorization: Bearer`); it is never written into prompts, system messages or conversation text. Whether the transport is encrypted depends on the `base_url` you configured; the application does not enforce HTTPS, so use an https endpoint and verify its security yourself.
- **NAS device SSH credentials (username, password)**: used only to connect over SSH to the NAS you configured, for collecting monitoring data and establishing terminal sessions; they are not sent with AI requests and do not enter the AI request context (the context contains only NAS names, online state and load metrics).
- **Authentication Token**: the field may exist in `user_config.json` (written by early versions); no actual use was found in the current version. If present, you may delete it.

Additional note: these credentials are passed through local IPC to the application's own renderer process so the settings UI can display and edit them (inputs are masked as password fields); this is local inter-process transfer, not remote transfer. Credentials are stored in plain text in `user_config.json` (not encrypted); treat the file as sensitive and do not share it.

## Third-Party Services

DigitalLab may connect to the following third-party services after you actively configure them:

1. **Ollama (local model)**: AI assistant feature, connects to `localhost:11434`; data does not leave the local machine.
2. **Cloud model (OpenAI-compatible API, for example DeepSeek)**: AI assistant feature. The data sent includes the conversation content, the prompt template, the real-time system status summary (CPU/memory/disk usage, hardware models and capacities, NAS names and load) and (when AI memory is enabled) long-term memory entries; the API Key is used as a request header for authentication. That portion of the data is processed by the provider you chose and is subject to its privacy policy.
3. **NAS devices**: connects over SSH to devices in your local network; data is transmitted within the local network.

All of the above connections are triggered only after you configure or actively use them; by default, no remote service is connected.

## How to Delete Data

### Deleting Through the Application

- **Chat history**: Settings → AI assistant → Chat History. You can turn saving off (stops writing new records), set a retention limit (oldest entries are trimmed beyond it), or clear all history (irreversible). The current UI does not offer per-message deletion (a backend endpoint exists).
- **AI memory**: Settings → AI assistant → AI Memory. You can disable memory, view entries, delete entries one by one, or clear everything; there is also "Clean Duplicates", which merges duplicate entries (keeping the earliest of identical content). If you changed the memory directory, also delete the files in the old directory.
- **Other settings** (AI provider and Key, monitoring thresholds, device list, theme, language, and so on): they can only be changed item by item, or removed by manually deleting the data directories described below.

### Manual Deletion

- `%APPDATA%\DigitalLab\`: public and sensitive configuration, monitoring logs and snapshot database, AI conversation history, AI memory
- `%APPDATA%\digital-lab\`: interface preferences (theme, language, splash animation toggle, onboarding completion state) and interface logs
- `memory\`, `snapshots\`, `reports\` and `launchers.json` inside the program directory: daily aggregates, performance snapshots, reports and launcher configuration

Uninstalling the application does not automatically delete the two `%APPDATA%` directories listed above; they must be deleted manually. The files inside the program directory are removed together with the installation directory by the uninstaller.

## Policy Changes

If this privacy policy is updated, the "Last updated" date at the top of this file will be revised accordingly, and the update will be released together with an application version. Major changes involving how data is processed will be announced in the application or in the release notes of the project repository. Continuing to use the updated version constitutes acceptance of the revised policy.

## Language

This document is a translation of the Simplified Chinese original. In case of any discrepancy or ambiguity, the Simplified Chinese version (PRIVACY.md) shall prevail.

## Contact

For privacy-related questions, please contact:

- GitHub Issues: https://github.com/ZWWF0906/Digital-Lab/issues
- Email: ZWWF0906@outlook.com

---

<a id="日本語"></a>

## 日本語

# DigitalLab プライバシーポリシー

最終更新：2026-11-04

## 基本方針：ローカル優先、クラウド AI の利用時と NAS 設定時のみ外部へ送信

DigitalLab は基本的にローカル環境で動作します。ハードウェアとパフォーマンスのデータは端末上で収集・表示・保存され、監視データ・設定・AI データは既定で端末上にのみ書き込まれます。本アプリにはテレメトリー、ユーザー行動の追跡、バックグラウンド送信機能はありません。

データが端末外へ出るのは次の三つの場合です。

1. ローカルの Ollama モデル：リクエストは本機の `localhost` にのみ送られ、端末外へは出ません。
2. クラウド AI モデル（OpenAI 互換 API、例：DeepSeek）：ユーザーが AI アシスタント機能を使用した場合に限り、今回のリクエスト内容が設定したエンドポイントへ送信され、当該サービス提供者が処理し、そのプライバシーポリシーに従います。
3. NAS デバイス：ユーザーが NAS を設定した場合に限り、アプリは SSH でローカルネットワーク内のデバイスへ接続し、データはローカルネットワーク内で転送されます。

上記以外の状況では、アプリが能動的に遠隔サーバーへデータを送信することはありません。本文書は現行バージョンで実際に実装されている動作のみを記載します。ログのマスキング、認証情報の暗号化保存、HTTPS の強制はいずれも実装されていません（「機密情報の保護」参照）。

## 収集する情報

DigitalLab は以下の情報を端末上で収集し、ダッシュボード表示、ローカル分析、AI アシスタントへのコンテキスト提供に使用します。

1. **端末のハードウェア情報**：CPU のモデルと周波数、メモリの容量と種類、GPU のモデルと VRAM、ディスクのモデルと容量、ディスプレイの仕様、ネットワークアダプターの情報、システムのモデルと製造元。
2. **システムのパフォーマンスデータ**：CPU 使用率、メモリ使用率、ディスク使用率、ネットワーク速度、プロセス一覧（PID、名前、CPU とメモリの使用量）。
3. **NAS デバイスのデータ**：ユーザーが設定した NAS の CPU、メモリ、ディスク、Docker コンテナの状態（SSH 接続で収集し、データは端末上に保存）。
4. **AI の対話履歴**：ユーザーと AI アシスタントの対話内容（AI 機能を使用した場合にのみ生成）。既定では本機のファイル `%APPDATA%\DigitalLab\memory\chat_history.jsonl` に保存され、再起動後に復元されます。設定パネルの「会話履歴」で保存のオン/オフ、保存件数の上限（超えた分は古い順に削除）、一括消去ができます。
   - 「会話履歴を保存」をオフにすると、新しいメッセージをそのローカルファイルへ書き込まなくなるだけで、既存の記録は削除されません（手動で消去するかファイルを削除してください）。
   - 「会話履歴を保存」をオフにしても AI リクエストは停止しません。今回送信するメッセージとセッション内の既存の対話内容は、今回のリクエストとして選択した AI サービス提供者へ送信されます。
   - 履歴ファイルそのものが丸ごとサーバーへ送信されることはありません。
5. **AI メモリ（オプション、既定はオフ）**：設定でメモリを有効にした場合に限り、ユーザーが明示的に述べ、長期的に記憶する価値がある好み（呼称、デバイス名、使用習慣など）が `%APPDATA%\DigitalLab\memory\ai_memory.jsonl` に永続保存されます。メモリを有効にしてクラウドモデルを使用する場合、これらの内容はリクエストとともに当該提供者へ送信されます。メモリを無効にすると、新しいメモリは書き込まれず、保存済みファイルも読み出し・対話への注入は行いませんが、ファイル自体は本機に残るため、設定から削除または消去してください。
6. **AI リクエストのコンテキスト（AI 機能を使用した場合にのみ生成）**：選択した AI サービス提供者へ送信するリクエストは四つの部分から成ります。静的プロンプト（役割設定、利用ルール、出力形式の制約。メモリ有効時は記憶指示も含む）、メモリ内容（メモリ有効時のみ。最近の数件を時刻と識別子で決定的に並べたもの）、リアルタイムのシステム状態の要約（CPU/メモリ/ディスク使用率、CPU/GPU/メモリ/ディスクの型番と容量、設定済み NAS の名前・オンライン状態・CPU/メモリ/ディスク使用率・温度）、対話内容（今回送信するメッセージとセッション内の既存の対話。バックエンドは直近 16 件のみ保持）。
   - ローカルの Ollama を使用する場合、上記は本機内でのみ処理されます。
   - クラウドモデルを使用する場合、上記は設定したエンドポイントへ送信されます。
   - リクエストに含まれないもの：NAS のホストアドレスとログイン情報、プロセス一覧全体とコマンドライン、ログ内容、AI メモリの id/種類/タグ/取得元の各フィールド、API Key そのもの（API Key はリクエストヘッダーの認証にのみ使用）。

**AI メモリと会話履歴は互いに独立した機能です**：メモリのオン/オフは長期メモリの読み出し・注入・永続化を制御し、既定はオフです。会話履歴の保存オン/オフはローカルの会話記録の書き込みを制御し、既定はオンです。一方をオフにしても他方はオフにならず、AI リクエストも停止しません。

## データの保存場所

データはユーザーが書き込み可能なディレクトリに保存されます。主な場所は次のとおりです。

```
%APPDATA%\DigitalLab\
├── config.json               # 公開設定
├── user_config.json           # 機密設定（AI 設定と API Key、NAS デバイスと認証情報、認証トークンのフィールド）
├── logs/
│   ├── cache/
│   │   └── hardware.json      # ハードウェア情報のキャッシュ
│   └── monitor/
│       ├── monitor.db         # パフォーマンススナップショットのデータベース（SQLite）
│       ├── daemon.log         # 監視ログ
│       └── daemon.pid         # 監視デーモンの PID
├── memory/
│   ├── chat_history.jsonl     # AI の対話履歴（既定で有効、上限設定・消去が可能）
│   └── ai_memory.jsonl        # AI の長期メモリ（既定で無効、有効化後に生成）
└── tools/ experiments/ notes/ archive/ interface/   # 予約ディレクトリ（現行版では業務データを書き込みません）

%APPDATA%\digital-lab\
└── config.json                # インターフェース設定（テーマ、言語、起動スプラッシュのオン/オフ、初回ガイドの完了状態）
```

プログラムディレクトリにも実行データが書き込まれます（開発時はソースディレクトリ、インストール後はインストール先ディレクトリ）。

- `memory\daily.jsonl`：日次パフォーマンス集計
- `snapshots\`：パフォーマンススナップショット
- `reports\`：レポート
- `launchers.json`：クイックランチャー設定

注：会話履歴と AI メモリの保存先は設定で変更できます（`ai.history.dir` と `ai.memory.dir`）。変更後は選択したディレクトリが適用されます。上表の `memory\` は AI データ用ディレクトリであり、プログラムディレクトリ内の日次集計用 `memory\` とは別物です。

## ログ

DigitalLab はトラブルシューティングとパフォーマンス分析のため、端末上に実行ログを記録します。

- `%APPDATA%\DigitalLab\logs\monitor\daemon.log`：JSON Lines 形式の監視ログ。タイムスタンプ、レベル、イベントメッセージ、および関連フィールド（プロセスの PID、収集回数、指標のしきい値、NAS デバイス名とホストアドレスなど）。
- `%APPDATA%\digital-lab\digital-lab.log`：インターフェースプロセスのログ。ウィンドウのライフサイクル、例外、I/O エラーの要約を記録します。
- `%APPDATA%\DigitalLab\logs\cache\hardware.json`：起動のたびに再収集しないためのハードウェアキャッシュ。

ログは端末上のユーザー書き込み可能ディレクトリにのみ書き込まれ、AI の対話内容やリクエストコンテキストを含まず、どのサーバーにも送信されず、ユーザー行動の分析にも使用されません。ログはマスキングされていません。`%APPDATA%\DigitalLab\logs\` ディレクトリと `%APPDATA%\digital-lab\digital-lab.log` を削除すると消去できます。

## 能動的に収集しない情報

DigitalLab は以下を能動的に収集しません。

- 個人を特定できる情報（氏名、メールアドレス、電話番号）
- ブラウザの履歴、Cookie、パスワード
- ファイルの内容（ディスク使用率を集計するのみで、内容は走査しません）
- スクリーンショットやキーボード入力の記録
- 位置情報
- 連絡先やアドレス帳

ただし、ユーザー自身が入力した情報は別です。対話中に述べた個人情報や設定で入力した呼称・デバイス名は、「収集する情報」と「データの保存場所」に従って端末上に保存され、クラウドモデルを使用する場合は対話内容と AI リクエストのコンテキストが選択した提供者へ送信されます。クラウド提供者へ送信したくない機密情報は、対話や設定に入力しないでください。

## 機密情報の保護

以下の情報は機密データとして扱い、公開設定 `config.json` とは分離して `%APPDATA%\DigitalLab\user_config.json` に保存し、インストーラーにも含めません。

- **AI サービスの API Key**：設定した AI エンドポイントへの認証に使用し、HTTP リクエストヘッダー（`Authorization: Bearer`）として送信されます。プロンプト、システムメッセージ、対話本文には書き込まれません。通信が暗号化されるかは設定した `base_url` に依存し、アプリは HTTPS を強制しません。https のエンドポイントを使用し、安全性はご自身で確認してください。
- **NAS デバイスの SSH 認証情報（ユーザー名、パスワード）**：設定した NAS への SSH 接続（監視データの収集、ターミナルセッションの確立）にのみ使用し、AI リクエストには送信されず、AI リクエストのコンテキストにも含まれません（コンテキストに含まれるのは NAS の名前、オンライン状態、負荷指標のみ）。
- **認証トークン**：`user_config.json` にこのフィールドが存在する場合があります（初期バージョンが書き込んだもの）。現行バージョンでは実際の使用は確認されていません。存在する場合は手動で削除できます。

補足：これらの認証情報は、設定画面で表示・編集するために本機の IPC 経由でアプリ自身のレンダラープロセスへ渡されます（入力欄はパスワード型でマスク表示）。これは本機内のプロセス間受け渡しであり、遠隔送信ではありません。認証情報は `user_config.json` に平文で保存されます（暗号化なし）。機密ファイルとして扱い、共有しないでください。

## 第三者サービスについて

DigitalLab は、ユーザーが自ら設定した場合に限り、以下の第三者サービスへ接続することがあります。

1. **Ollama（ローカルモデル）**：AI アシスタント機能で `localhost:11434` に接続します。データは端末外へ出ません。
2. **クラウドモデル（OpenAI 互換 API、例：DeepSeek）**：AI アシスタント機能。送信内容は、対話内容、プロンプトテンプレート、リアルタイムのシステム状態の要約（CPU/メモリ/ディスク使用率、ハードウェアの型番と容量、NAS の名前と負荷）、（AI メモリ有効時の）長期メモリの内容です。API Key は認証用のリクエストヘッダーとして使用されます。この部分のデータは選択した提供者が処理し、そのプライバシーポリシーに従います。
3. **NAS デバイス**：ローカルネットワーク内のデバイスへ SSH で接続し、データはローカルネットワーク内でのみ転送されます。

上記の接続は、ユーザーが設定または能動的に使用した後にのみ発生し、既定ではどの遠隔サービスにも接続しません。

## データの削除方法

### アプリ内からの削除

- **会話履歴**：設定 → AI アシスタント → 会話履歴。保存のオン/オフ（新しい記録の書き込み停止）、保存件数の上限（超えた分は古い順に削除）、すべて消去（取り消し不可）ができます。現行の画面には 1 件ずつの削除入口はありません（バックエンドには対応するインターフェースがあります）。
- **AI メモリ**：設定 → AI アシスタント → AI メモリ。メモリのオン/オフ、項目の表示、1 件ずつの削除、すべて消去が可能です。さらに「重複を整理」で重複した項目を統合できます（同じ内容は最も古い 1 件を保持）。メモリの保存先を変更した場合は、旧ディレクトリのファイルも削除してください。
- **その他の設定**（AI プロバイダーと Key、監視しきい値、デバイス一覧、テーマ、言語など）：項目ごとに変更するか、以下に示すデータの保存場所を手動で削除してください。

### 手動での削除

- `%APPDATA%\DigitalLab\`：公開・機密設定、監視ログとスナップショットのデータベース、AI の対話履歴、AI メモリ
- `%APPDATA%\digital-lab\`：インターフェース設定（テーマ、言語、起動スプラッシュのオン/オフ、初回ガイドの完了状態）とインターフェースログ
- プログラムディレクトリ内の `memory\`、`snapshots\`、`reports\` と `launchers.json`：日次集計、パフォーマンススナップショット、レポート、クイックランチャー設定

アプリをアンインストールしても上記 2 つの `%APPDATA%` ディレクトリは自動削除されません。手動で削除してください。プログラムディレクトリ内のファイルは、アンインストーラによってインストールディレクトリとともに削除されます。

## ポリシーの変更

本プライバシーポリシーを更新する場合は、本ファイル冒頭の「最終更新」の日付を合わせて変更し、アプリのバージョンとともに公開します。データの取り扱い方法に関わる重大な変更は、アプリ内またはプロジェクトリポジトリのリリースノートで通知します。更新後のバージョンを引き続き使用することにより、改訂後のポリシーに同意したものとみなされます。

## 連絡先

プライバシーに関するご質問は、以下までご連絡ください。

- GitHub Issues: https://github.com/ZWWF0906/Digital-Lab/issues
- メール: ZWWF0906@outlook.com

この文書は簡体字中国語版の翻訳です。解釈に相違や曖昧さがある場合は、簡体字中国語版（PRIVACY.md）が優先されます。
