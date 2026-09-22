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
  <a href="https://apps.microsoft.com/detail/9n0rtlx1bcp5?referrer=appbadge&mode=full" target="_blank" rel="noopener noreferrer">
	<img src="https://get.microsoft.com/images/en-us%20light.svg" width="200"/>
  </a>
</div>

A personal digital laboratory platform — a desktop application for personal device management, data awareness and AI extension. Local-first, modular and extensible, it turns your personal computer into a programmable, perceivable and conversational digital workspace.

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
- **Privacy First** — device data is stored locally by default, and sensitive configuration lives in the user directory

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
- [ ] Personal Digital Memory
- [ ] Data analysis and timeline system

---

## Installation

### Regular Users

1. Download the latest `DigitalLab Setup.exe` from [Releases](https://github.com/ZWWF0906/Digital-Lab/releases)
2. Run the installer
3. After launching, add your NAS device information in the Settings panel
4. **No need to install Python or Node.js** — all dependencies are bundled

### System Requirements

| Requirement | Minimum |
|------|----------|
| Operating system | Windows 10 or later |
| Processor | x64 architecture, dual-core 1.5 GHz |
| Memory | 4 GB |
| Graphics | DirectX 9 support (turning off hardware acceleration is recommended for better compatibility); at least 1 GB or 2 GB of VRAM is recommended to enable local AI models |
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
├── main.js                 # Electron main process
├── preload.js              # IPC bridge
├── dashboard.html          # Main interface
├── styles.css              # Global styles (Emerald theme system: dark by default / light optional)
├── package.json            # Node project configuration
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation (Simplified Chinese)
├── README.en-US.md         # Project documentation (English)
├── README.ja-JP.md         # Project documentation (Japanese)
├── CHANGELOG.md            # Changelog (English)
├── CHANGELOG.zh-CN.md      # Changelog (Chinese)
├── CHANGELOG.ja-JP.md      # Changelog (Japanese)
├── config.json             # Public configuration
├── config.schema.json      # Configuration validation rules
├── core/                   # Python backend modules
│   ├── config.py           # Configuration loading and two-layer storage
│   ├── collector.py        # Dual-thread system monitoring collection
│   ├── monitor.py          # Performance monitoring daemon
│   ├── hardware.py         # Hardware information collection
│   ├── hardware_classifier.py  # Hardware model classification
│   ├── ai_client.py        # AI client (Ollama / OpenAI)
│   ├── ai_memory.py        # AI local memory (jsonl storage)
│   ├── nas_monitor.py      # NAS remote monitoring (SSH)
│   ├── logger.py           # Logging system
│   ├── system_state.py     # Global state management
│   ├── event_bus.py        # Event bus
│   ├── memory.py           # Conversation memory management
│   ├── snapshot.py         # Performance snapshot storage
│   ├── renderer.py         # CLI renderer
│   ├── reporter.py         # Chart generation
│   ├── launcher.py         # Quick launcher
│   └── daemon.py           # Daemon process management
└── panels/                 # Frontend panels
│   ├── index.js            # Panel registry
│   ├── dashboard.js        # Dashboard
│   ├── device-center.js    # Device Center
│   ├── ai-assistant.js     # AI Assistant
│   ├── terminal.js         # Terminal
│   └── settings.js         # Settings
```

---

## Configuration System

DigitalLab uses two-layer configuration storage to separate public settings from sensitive data:

| Config file | Location | Contents |
|----------|------|------|
| `config.json` | Shipped with the app | Public config: ports, thresholds, log level, toggles |
| `user_config.json` | `%APPDATA%\DigitalLab\` | Sensitive data: API Key, Token, NAS credentials |

On first run, if sensitive fields exist in `config.json` and `user_config.json` does not exist, the system automatically migrates the sensitive data to the user directory.

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
