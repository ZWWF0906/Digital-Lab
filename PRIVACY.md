# DigitalLab 隐私政策 / Privacy Policy

最后更新：2026-09-10 / Last updated: 2026-09-10

[简体中文](#简体中文) · [English](#english) · [日本語](#日本語)

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

---

<a id="日本語"></a>

## 日本語

# DigitalLab プライバシーポリシー

最終更新：2026-09-10

## 基本方針：ローカル優先

DigitalLab は「ローカル優先」の方針に従います。すべてのデータ収集・保存・処理はユーザーの端末上で行われ、ユーザーデータを遠隔のサーバーへ能動的に送信することはありません。本アプリにはテレメトリー、ユーザー行動の追跡、バックグラウンドでのデータ送信機能はありません。

## 収集する情報

DigitalLab は以下の情報を端末上で収集し、ダッシュボードでの表示とローカルでの分析にのみ使用します。

1. **端末のハードウェア情報**：CPU のモデルと周波数、メモリの容量と種類、GPU のモデルと VRAM、ディスクのモデルと容量、ディスプレイの仕様、ネットワークアダプターの情報、システムのモデルと製造元
2. **システムのパフォーマンスデータ**：CPU 使用率、メモリ使用率、ディスク使用率、ネットワーク速度、プロセス一覧（PID、名前、CPU とメモリの使用量）
3. **NAS デバイスのデータ**：ユーザーが自ら設定した NAS デバイスの CPU、メモリ、ディスク、Docker コンテナの状態（SSH 接続で収集し、データは端末上に保存されます）
4. **AI の対話記録**：ユーザーと AI アシスタントの対話内容（ユーザーが AI 機能を自ら使用した場合にのみ生成され、端末上のメモリに保存され、アプリを終了すると消去されます）
   - **AI メモリ（オプション）**：ユーザーが設定パネルで AI メモリを有効にした場合に限り、対話の中でユーザーが明示的に述べ、長期的に記憶する価値があると判断された好み（呼称、デバイス名、使用習慣など）が `%APPDATA%\DigitalLab\memory\ai_memory.jsonl` に永続保存されます。このデータが端末外へ出ることはなく、どのサーバーにも送信されません。設定パネルからいつでも 1 件ずつ削除するか、すべて消去できます。AI メモリを無効にしている間は対話内容を一切永続化せず、保存済みのメモリも読み出しや対話への注入を行いません。AI メモリを有効にしてクラウドモデルを使用する場合、これらのメモリは対話内容とともに当該クラウドサービス提供者へ送信されます。

## データの保存場所

すべてのデータはユーザーが書き込み可能なディレクトリに保存されます。

```
%APPDATA%\DigitalLab\
├── config.json              # 公開設定
├── user_config.json          # 機密設定（API Key、NAS の認証情報）
├── logs/
│   ├── cache/
│   │   └── hardware.json     # ハードウェア情報のキャッシュ
│   └── monitor/
│       ├── monitor.db        # パフォーマンススナップショットのデータベース（SQLite）
│       └── daemon.log        # 監視ログ
└── memory/
    └── ai_memory.jsonl       # AI の長期メモリ（AI メモリを有効にした場合のみ生成）
```

レジストリは使用せず、システムディレクトリへの書き込みも、隠しサービスの作成も行いません。

## ログ

DigitalLab はトラブルシューティングとパフォーマンス分析のため、端末上に実行ログを記録します。

- `logs/monitor/daemon.log`：JSON Lines 形式の監視ログ。タイムスタンプ、レベル、イベントメッセージ、および関連するフィールド（プロセスの PID、収集回数、指標のしきい値、NAS デバイス名とホストアドレスなど）を記録します
- `logs/cache/hardware.json`：起動のたびに同じ情報を収集し直さないためのハードウェア情報キャッシュ

ログは端末上のユーザー書き込み可能ディレクトリにのみ書き込まれ、AI の対話内容を含まず、どのサーバーにも送信されず、ユーザー行動の分析にも使用されません。`%APPDATA%\DigitalLab\logs\` ディレクトリを削除すると、すべてのログを消去できます。

## 収集しない情報

DigitalLab は以下の情報を収集しません。

- 個人を特定できる情報（氏名、メールアドレス、電話番号）
- ブラウザの履歴、Cookie、パスワード
- ファイルの内容（ディスク使用率を集計するのみで、ファイルの内容は走査しません）
- スクリーンショットやキーボード入力の記録
- 位置情報
- 連絡先やアドレス帳

## 機密情報の保護

以下の情報は機密データとして扱い、`%APPDATA%\DigitalLab\user_config.json` に保存して公開設定とは分離します。

- AI サービスの API Key
- NAS デバイスの SSH 認証情報（ユーザー名、パスワード）
- 認証トークン

機密設定は、アプリに同梱される `config.json` には書き込まれず、インストーラーにも含まれず、どのサーバーにも送信されません。

## 第三者サービスについて

DigitalLab は、ユーザーが自ら設定した場合に限り、以下の第三者サービスへ接続することがあります。

1. **Ollama**（ローカルモデル）：AI アシスタント機能で `localhost:11434` に接続します。データは端末外へ出ません
2. **OpenAI API**（クラウドモデル）：AI アシスタント機能で、ユーザーが入力した対話内容のみが API 経由で OpenAI へ送信され、その部分のデータは OpenAI のプライバシーポリシーに従います
3. **NAS デバイス**：ユーザーのローカルネットワーク内のデバイスへ SSH で接続し、データはローカルネットワーク内のみで転送されます

上記の接続はすべてユーザーが自ら設定した後にのみ発生し、既定ではどの遠隔サービスにも接続しません。

## データの削除方法

### アプリ内からの削除

DigitalLab の設定画面で設定を消去すると、アプリのデータがリセットされます。

### 手動での削除

以下のディレクトリを削除すると、DigitalLab のすべてのデータを消去できます。

```
%APPDATA%\DigitalLab\
```

アプリをアンインストールしてもユーザーデータディレクトリは自動削除されません。手動で削除してください。

## ポリシーの変更

本プライバシーポリシーを更新する場合は、本ファイル冒頭の「最終更新」の日付を合わせて変更し、アプリのバージョンとともに公開します。データの取り扱い方法に関わる重大な変更は、アプリ内またはプロジェクトリポジトリのリリースノートで通知します。更新後のバージョンを引き続き使用することにより、改訂後のポリシーに同意したものとみなされます。

## 連絡先

プライバシーに関するご質問は、以下までご連絡ください。

- GitHub Issues: https://github.com/ZWWF0906/Digital-Lab/issues
- メール: ZWWF0906@outlook.com

この文書は簡体字中国語版の翻訳です。解釈に相違や曖昧さがある場合は、簡体字中国語版（PRIVACY.md）が優先されます。
