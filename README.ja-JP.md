<h1 align="center">DigitalLab</h1>

<div align="center">

[简体中文](README.md) · [English](README.en-US.md) · [日本語](README.ja-JP.md)

</div>

<div align="center">

[![Version](https://img.shields.io/badge/version-1.4.0-blue)](https://github.com/ZWWF0906/Digital-Lab)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2B-lightgrey)](https://github.com/ZWWF0906/Digital-Lab)
[![Local-First](https://img.shields.io/badge/local--first-important)](https://github.com/ZWWF0906/Digital-Lab)
[![AI](https://img.shields.io/badge/AI-Ollama%20%7C%20API-9cf)](https://github.com/ZWWF0906/Digital-Lab)
[![NAS](https://img.shields.io/badge/NAS-SSH%20monitor-orange)](https://github.com/ZWWF0906/Digital-Lab)

</div>

<div align="center">
  <a href="https://apps.microsoft.com/detail/9n0rtlx1bcp5?referrer=appbadge&mode=full" target="_self">
    <img src="https://get.microsoft.com/images/zh-cn%20light.svg" width="200"/>
  </a>
</div>

個人向けデジタルラボプラットフォーム — 個人のデバイス管理、データ感知、AI 拡張のためのデスクトップアプリ。ローカル優先・モジュール式・拡張可能で、あなたのパソコンをプログラミング可能で感知可能、対話可能なデジタルワークスペースに変えます。

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
- **Privacy First** — デバイスデータは既定でローカルに保存され、機密設定はユーザーディレクトリに保存

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
- [ ] Personal Digital Memory
- [ ] データ分析とタイムラインシステム

---

## インストール

### 一般ユーザー

1. [Releases](https://github.com/ZWWF0906/Digital-Lab/releases) から最新の `DigitalLab Setup.exe` をダウンロード
2. インストーラーを実行
3. 起動後、設定パネルで NAS デバイス情報を追加
4. **Python や Node.js のインストールは不要**。すべての依存関係は内蔵されています

### システム要件

| 要件 | 最低構成 |
|------|----------|
| オペレーティングシステム | Windows 10 以降 |
| プロセッサ | x64 アーキテクチャ、デュアルコア 1.5 GHz |
| メモリ | 4 GB |
| グラフィックス | DirectX 9 対応（互換性向上のためハードウェアアクセラレーションをオフにすることを推奨）。ローカル AI 大規模モデルを有効にするには、1 GB または 2 GB 以上のビデオメモリを推奨 |
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
├── main.js                 # Electron メインプロセス
├── preload.js              # IPC ブリッジ
├── dashboard.html          # メイン画面
├── styles.css              # グローバルスタイル（Emerald テーマ体系：ダークが既定 / ライトは任意）
├── package.json            # Node プロジェクト設定
├── requirements.txt        # Python 依存関係
├── README.md               # プロジェクト説明（簡体字中国語）
├── README.en-US.md         # プロジェクト説明（英語）
├── README.ja-JP.md         # プロジェクト説明（日本語）
├── CHANGELOG.md            # 更新履歴（英語）
├── CHANGELOG.zh-CN.md      # 更新履歴（中国語）
├── CHANGELOG.ja-JP.md      # 更新履歴（日本語）
├── config.json             # 公開設定
├── config.schema.json      # 設定検証ルール
├── core/                   # Python バックエンドモジュール
│   ├── config.py           # 設定の読み込みと二層ストレージ
│   ├── collector.py        # 2 スレッドのシステム監視収集
│   ├── monitor.py          # パフォーマンス監視デーモン
│   ├── hardware.py         # ハードウェア情報の収集
│   ├── hardware_classifier.py  # ハードウェアモデルの分類
│   ├── ai_client.py        # AI クライアント（Ollama / OpenAI）
│   ├── ai_memory.py        # AI ローカルメモリ（jsonl 保存）
│   ├── nas_monitor.py      # NAS リモート監視（SSH）
│   ├── logger.py           # ログシステム
│   ├── system_state.py     # グローバル状態管理
│   ├── event_bus.py        # イベントバス
│   ├── memory.py           # 会話メモリ管理
│   ├── snapshot.py         # パフォーマンススナップショット保存
│   ├── renderer.py         # CLI レンダラー
│   ├── reporter.py         # グラフ生成
│   ├── launcher.py         # クイックランチャー
│   └── daemon.py           # デーモン管理
└── panels/                 # フロントエンドパネル
│   ├── index.js            # パネルレジストリ
│   ├── dashboard.js        # ダッシュボード
│   ├── device-center.js    # デバイスセンター
│   ├── ai-assistant.js     # AI アシスタント
│   ├── terminal.js         # SSH ターミナル
│   └── settings.js         # 設定パネル
```

---

## 設定システム

DigitalLab は二層の設定ストレージを採用し、公開設定と機密データを分離しています：

| 設定ファイル | 場所 | 内容 |
|----------|------|------|
| `config.json` | ソフトウェアに同梱 | 公開設定：ポート、しきい値、ログレベル、スイッチ |
| `user_config.json` | `%APPDATA%\DigitalLab\` | 機密データ：API Key、Token、NAS 認証情報 |

初回実行時、`config.json` に機密フィールドが存在し、かつ `user_config.json` が存在しない場合、システムは機密データを自動的にユーザーディレクトリへ移行します。

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
