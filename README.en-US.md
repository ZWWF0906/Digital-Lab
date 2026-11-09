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
	<img src="https://get.microsoft.com/images/en-us%20light.svg" width="200"/>
  </a>
</div>

A personal digital laboratory platform — a desktop application for personal device management, data awareness and AI extension. Local-first, modular and extensible, it turns your personal computer into a programmable, perceivable and conversational digital workspace.

> **Release channel**: DigitalLab 1.6.0 is the last version to provide a standalone installer via GitHub. From 1.6.1 onward, formal releases are distributed only through the Microsoft Store; GitHub continues as the source, documentation and collaboration platform.

---

## Features

### Dashboard
Realtime monitoring of CPU / memory / disk / network speed, with mini trend lines and health status lights at a glance. Supports performance history charts (24-hour averages and peaks), the process list, and NAS device status cards.

### Device Center
A complete view of local hardware information: CPU model / cores / threads / frequency, memory capacity / type / speed / slots, GPU model / VRAM / temperature / utilization, disk model / capacity / health / partitions, display resolution / refresh rate, network adapter status, and system information (OS version, uptime).

### Terminal
A web terminal built on xterm.js that connects to NAS devices over SSH, with multi-session support and a CMD-style dark theme.

### AI Assistant
Streaming output, with support for Ollama local models or OpenAI-compatible APIs (such as DeepSeek). Multi-turn conversations, character-by-character token rendering, automatic injection of the current system status as conversation context, and answers to CPU / memory / disk / hardware / NAS questions. The Chinese garbled-text issue has been fixed; a model with good Chinese capability is recommended (such as qwen2.5:7b-instruct-q4_K_M).

### Settings
Log level, monitoring thresholds, NAS device management, AI provider switching, hardware acceleration toggle, and light/dark theme switching (the light theme is based on the Emerald design system; the terminal stays dark). Provides a unified entry point for feedback and reports (email / GitHub Issues).

---

## Architecture

```text
┌──────────────────────────────────────┐
│  Electron main process (main.js)     │
│  Window management · Tray · IPC      │
│         │ spawn                      │
│         ▼                            |
│  Python child process (main.py)      │
│  Metrics · Hardware · NAS SSH · AI   |
│         │                            │
│  stdin/stdout JSON Lines protocol    │
│  Request/response: requestId match   │
│  State updates: broadcast mode       │
└──────────────────────────────────────┘
```

---

## Core Design Principles

- **All data flows into system_state, and every UI consumes only system_state** — a single source of truth that decouples the frontend from the backend
- **Local-first, modular, extensible** — core features work without a network, and panels load on demand
- **Electron core communication does not rely on HTTP** — it uses the JSON Lines IPC protocol with zero network overhead, while an optional Web Dashboard service is also provided
- **Privacy First** — device data is stored locally by default, and sensitive configuration lives in the user directory; AI/NAS credentials are protected with Windows DPAPI for the current user, and remote AI endpoints require HTTPS (local Ollama loopback HTTP is the exception)

---

## Roadmap

- [x] Realtime system monitoring — v1.0.0
- [x] Hardware information center — v1.0.0
- [x] NAS SSH management — v1.0.0
- [x] AI Assistant — v1.0.0
- [x] Electron + Python architecture — v1.0.0
- [x] Light theme and theme switching — v1.1.0
- [x] Feedback and report entry point — v1.1.0
- [ ] Agent automation capabilities
- [ ] Plugin system
- [ ] Support for more NAS platforms
- [x] Personal Digital Memory — v1.6.0
- [ ] Data analysis and timeline system

---

## Installation

### Regular Users

1. **DigitalLab 1.6.0**: this is the last version to provide a standalone GitHub installer. Download `DigitalLab Setup.exe` from [Releases](https://github.com/ZWWF0906/Digital-Lab/releases).
2. **1.6.1 and later**: formal releases are installed and updated only through the [Microsoft Store](https://apps.microsoft.com/detail/9n0rtlx1bcp5); GitHub no longer provides a standalone installer.
3. The installer requires administrator privileges and installs per-machine; after launching, add your NAS device information in the Settings panel.
4. **No need to install Python or Node.js** — all runtime dependencies are bundled.

### System Requirements

| Requirement | Minimum |
|------|----------|
| Operating system | Windows 10 or later |
| Processor | x64 architecture, dual-core 1.5 GHz |
| Memory | 4 GB |
| Graphics | A Windows 10-compatible GPU/display driver; hardware acceleration can be disabled in Settings. DigitalLab itself does not require a specific VRAM amount; if you use a local Ollama model, its GPU/VRAM requirements depend on the model. |
| Storage | 2 GB of available space |

---

## Development Build

### Environment Requirements

- Node.js 18+
- Python 3.10+

### Development Mode

```bash
# Install frontend dependencies
npm install

# Start development mode (automatically starts the Python subprocess)
npm start
```

### Packaging

```bash
# Package the Python backend into a standalone executable
pyinstaller backend.spec

# Package the Electron desktop application
npm run build
```

---

## Project Structure

```text
DigitalLab/
├── main.js / preload.js              # Electron main process and IPC bridge
├── preload-terminal.js / renderer-terminal.js
├── renderer.js / dashboard.html / terminal.html
├── styles.css / i18n.js / locales/   # Styles, i18n and three-language resources
├── onboarding.js / splash.js / theme-init.js / lang-init.js / boot-text.js
├── core/                             # Python backend
│   ├── config.py / secret_store.py   # Two-file config and DPAPI credential protection
│   ├── net_policy.py / path_policy.py / ssh_trust.py
│   ├── agent_tools.py                # Read-only Agent tool infrastructure (not exposed to the model yet)
│   ├── ai_client.py / ai_memory.py / chat_store.py
│   ├── nas_monitor.py / monitor.py / collector.py
│   └── ...                           # Hardware, state, logging, snapshots and more
├── panels/                           # Frontend panels
│   ├── index.js / safe-dom.js
│   └── dashboard.js / device-center.js / ai-assistant.js / terminal.js / settings.js
├── build/                            # Icons, fonts and packaging resources
├── scripts/                          # build-windows.ps1 / build-backend.ps1
├── package.json / package-lock.json
├── backend.spec / requirements.txt
├── config.schema.json
├── README.md / README.en-US.md / README.ja-JP.md
├── CHANGELOG.md / CHANGELOG.zh-CN.md / CHANGELOG.ja-JP.md
└── LICENSE
```

---

## Configuration System

DigitalLab uses two-layer configuration storage to separate public settings from sensitive data:

| Config file | Location | Contents |
|----------|------|------|
| `config.json` | `%APPDATA%\DigitalLab\` | Runtime public config: ports, thresholds, log level, toggles; created after first run |
| `user_config.json` | `%APPDATA%\DigitalLab\` | Sensitive fields: `ai`, `nas_devices`, `auth_token`; values are protected with Windows DPAPI as `dpapi:v1:` ciphertext, not plaintext |

At startup, legacy plaintext credentials in `config.json`/`user_config.json` are migrated to DPAPI ciphertext; if migration fails, the app blocks use of unprotected credentials rather than silently falling back to plaintext.

---

## Window and Tray

- Window size: 1100 x 750, minimum 900 x 600
- Single-instance lock to prevent multiple launches
- The close button minimizes to the system tray instead of quitting
- Tray menu: Show Main Window / Quit
- Hardware acceleration is off by default (for virtual machine compatibility) and can be toggled in Settings
- If Python crashes it restarts automatically, up to 3 times; the user is notified once the limit is exceeded

---

## Testing Phase Notes

- **Terminal** and **AI Assistant** are currently in the testing phase; a notice appears the first time you open them
- SSH sessions do not support automatic reconnection yet
- The AI Assistant currently works in conversation mode and does not include Agent tool-calling capabilities
- The NAS terminal relies on the SSH service; make sure SSH is enabled on the target device and the credentials are configured correctly

---

## Contributing

Issues and Pull Requests are welcome.

---

## Privacy Policy

This application follows a local-first principle; see [PRIVACY.md](https://github.com/ZWWF0906/Digital-Lab/blob/main/PRIVACY.md) for details.

---

## License

ISC License  2026 ZWWF0906
