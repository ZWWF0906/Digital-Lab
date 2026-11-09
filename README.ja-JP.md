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
	<img src="https://get.microsoft.com/images/ja%20light.svg" width="200"/>
  </a>
</div>

個人向けデジタルラボプラットフォーム — 個人のデバイス管理、データ感知、AI 拡張のためのデスクトップアプリ。ローカル優先・モジュール式・拡張可能で、あなたのパソコンをプログラミング可能で感知可能、対話可能なデジタルワークスペースに変えます。

> **リリースチャネル**：DigitalLab 1.6.0 は GitHub で単体インストーラーを提供する最後のバージョンです。1.6.1 以降の正式版は Microsoft Store のみで配布され、GitHub はソース、ドキュメント、コラボレーションの場として継続します。

---

## Features

### ダッシュボード
CPU / メモリ / ディスク / ネットワーク速度のリアルタイム監視。ミニトレンドラインとヘルス状態ランプで一目で把握できます。性能履歴グラフ（24 時間の平均値とピーク値）、プロセス一覧、NAS デバイスのステータスカードに対応しています。

### デバイスセンター
本機のハードウェア情報を一覧表示：CPU モデル / コア / スレッド / 周波数、メモリ容量 / 種類 / 周波数 / スロット、GPU モデル / ビデオメモリ / 温度 / 使用率、ディスク モデル / 容量 / 健全性 / パーティション、ディスプレイ解像度 / リフレッシュレート、ネットワークアダプターの状態、システム情報（OS バージョン、稼働時間）。

### SSH ターミナル
xterm.js ベースの Web ターミナル。SSH 経由で NAS デバイスに接続し、マルチセッション管理に対応、CMD 風のダークテーマ。

### AI アシスタント
ストリーミング出力に対応し、Ollama のローカルモデルまたは OpenAI 互換 API（DeepSeek など）を利用できます。マルチターン対話、Token の逐次レンダリング、現在のシステム状態を会話コンテキストとして自動注入し、CPU / メモリ / ディスク / ハードウェア / NAS に関する質問に回答できます。中国語の文字化けは修正済みで、中国語能力の高いモデル（qwen2.5:7b-instruct-q4_K_M など）の使用を推奨します。

### 設定パネル
ログレベル、監視しきい値、NAS デバイス管理、AI プロバイダーの切り替え、ハードウェアアクセラレーションのオン/オフ、ライト/ダークテーマの切り替え（ライトは Emerald デザインシステムに基づき、ターミナルはダークのまま）。フィードバックと報告の統合窓口（メール / GitHub Issues）を提供します。

---

## Architecture

```text
┌──────────────────────────────────────┐
│  Electron メインプロセス（main.js）   │
│  ウィンドウ・システムトレイ・IPC 通信  │
│         │ spawn                      │
│         ▼                            |
│  Python サブプロセス（main.py）       │
│  監視収集 · ハードウェア · NAS · AI   |
│         │                            │
│  stdin/stdout JSON Lines プロトコル  │
│  リクエスト-応答：requestId の照合    │
│  状態更新：ブロードキャスト方式        │
└──────────────────────────────────────┘
```

---

## コア設計原則

- **すべてのデータは system_state に入り、すべての UI は system_state のみを消費する** — 単一のデータソースにより、フロントエンドとバックエンドを分離
- **ローカル優先、モジュール式、拡張可能** — コア機能にネットワークは不要で、パネルは必要に応じて読み込み
- **Electron のコア通信は HTTP に依存しない** — JSON Lines IPC プロトコルを採用し、ネットワークオーバーヘッドはゼロ。同時にオプションの Web Dashboard サービスも提供
- **Privacy First** — デバイスデータは既定でローカルに保存され、機密設定はユーザーディレクトリに保存; AI/NAS 認証情報は現在の Windows ユーザーの DPAPI で保護され、リモート AI エンドポイントは HTTPS を要求します（ローカル Ollama の loopback HTTP を除く）

---

## Roadmap

- [x] システムリアルタイム監視 — v1.0.0
- [x] ハードウェア情報センター — v1.0.0
- [x] NAS SSH 管理 — v1.0.0
- [x] AI Assistant — v1.0.0
- [x] Electron + Python アーキテクチャ — v1.0.0
- [x] ライトテーマとテーマ切り替え — v1.1.0
- [x] フィードバックと報告の窓口 — v1.1.0
- [ ] Agent 自動化機能
- [ ] プラグインシステム
- [ ] より多くの NAS プラットフォーム対応
- [x] Personal Digital Memory — v1.6.0
- [ ] データ分析とタイムラインシステム

---

## インストール

### 一般ユーザー

1. **DigitalLab 1.6.0**：GitHub で単体インストーラーを提供する最後のバージョンです。[Releases](https://github.com/ZWWF0906/Digital-Lab/releases) から `DigitalLab Setup.exe` をダウンロードしてください。
2. **1.6.1 以降**：正式版は [Microsoft Store](https://apps.microsoft.com/detail/9n0rtlx1bcp5) からのみインストール・更新できます。GitHub では単体インストーラーを提供しません。
3. インストーラーには管理者権限が必要で、per-machine にインストールされます。起動後、設定パネルで NAS デバイス情報を追加してください。
4. **Python や Node.js のインストールは不要**。すべての実行時依存関係は内蔵されています。

### システム要件

| 要件 | 最低構成 |
|------|----------|
| オペレーティングシステム | Windows 10 以降 |
| プロセッサ | x64 アーキテクチャ、デュアルコア 1.5 GHz |
| メモリ | 4 GB |
| グラフィックス | Windows 10 対応の GPU / ディスプレイドライバー。ハードウェアアクセラレーションは設定でオフにできます。DigitalLab 自体は特定の VRAM を要求しません。ローカル Ollama モデルを使う場合の GPU / VRAM 要件はモデルに依存します。 |
| ストレージ | 2 GB の空き容量 |

---

## 開発ビルド

### 環境要件

- Node.js 18+
- Python 3.10+

### 開発モード

```bash
# フロントエンドの依存関係をインストール
npm install

# 開発モードを起動（Python サブプロセスを自動起動）
npm start
```

### パッケージング

```bash
# Python バックエンドを単体の実行ファイルにパッケージング
pyinstaller backend.spec

# Electron デスクトップアプリをビルド
npm run build
```

---

## プロジェクト構成

```text
DigitalLab/
├── main.js / preload.js              # Electron メインプロセスと IPC ブリッジ
├── preload-terminal.js / renderer-terminal.js
├── renderer.js / dashboard.html / terminal.html
├── styles.css / i18n.js / locales/   # スタイル、i18n、三言語リソース
├── onboarding.js / splash.js / theme-init.js / lang-init.js / boot-text.js
├── core/                             # Python バックエンド
│   ├── config.py / secret_store.py   # 二層設定と DPAPI 認証情報保護
│   ├── net_policy.py / path_policy.py / ssh_trust.py
│   ├── agent_tools.py                # 読み取り専用 Agent ツール基盤（モデルには未公開）
│   ├── ai_client.py / ai_memory.py / chat_store.py
│   ├── nas_monitor.py / monitor.py / collector.py
│   └── ...                           # ハードウェア、状態、ログ、スナップショットなど
├── panels/                           # フロントエンドパネル
│   ├── index.js / safe-dom.js
│   └── dashboard.js / device-center.js / ai-assistant.js / terminal.js / settings.js
├── build/                            # アイコン、フォント、パッケージ用リソース
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

## 設定システム

DigitalLab は二層の設定ストレージを採用し、公開設定と機密データを分離しています：

| 設定ファイル | 場所 | 内容 |
|----------|------|------|
| `config.json` | `%APPDATA%\DigitalLab\` | 実行時の公開設定：ポート、しきい値、ログレベル、スイッチ。初回実行後に生成されます |
| `user_config.json` | `%APPDATA%\DigitalLab\` | 機密フィールド：`ai`、`nas_devices`、`auth_token`。値は Windows DPAPI により `dpapi:v1:` の暗号文として保護され、平文ではありません |

起動時に旧版の `config.json`/`user_config.json` にある平文認証情報を DPAPI 暗号文へ移行します。移行に失敗した場合、アプリは未保護の認証情報の使用をブロックし、平文へ静かにフォールバックしません。

---

## ウィンドウとタスクトレイ

- ウィンドウサイズ：1100 x 750、最小 900 x 600
- 単一インスタンスロックで多重起動を防止
- 閉じるボタンはシステムトレイに最小化し、終了しません
- トレイメニュー：メインウィンドウを表示 / 終了
- ハードウェアアクセラレーションは既定でオフ（仮想マシン環境との互換性のため）。設定で切り替え可能
- Python のクラッシュ時は自動再起動、最大 3 回。上限を超えるとユーザーに通知

---

## テスト段階の注意事項

- **SSH ターミナル** と **AI アシスタント** は現在テスト段階にあり、初回アクセス時にダイアログで通知されます
- SSH セッションは現時点で自動再接続に対応していません
- AI アシスタントは現在対話モードであり、Agent ツール呼び出し機能は含まれていません
- NAS ターミナルは SSH サービスに依存します。対象デバイスで SSH が有効になっていること、および認証情報が正しく設定されていることを確認してください

---

## コントリビュート

Issue と Pull Request を歓迎します。

---

## プライバシーポリシー

本アプリはローカル優先の原則に従います。詳細は [PRIVACY.md](https://github.com/ZWWF0906/Digital-Lab/blob/main/PRIVACY.md) をご覧ください。

---

## ライセンス

ISC License  2026 ZWWF0906
