# Changelog


## v1.0.0 - 2026-08-15


### Added

- Initial stable release
- Electron + Python hybrid architecture
- Real-time system monitoring (CPU, memory, disk, network)
- Hardware information center (CPU, GPU, memory, disk, display, network, system)
- NAS SSH management (remote terminal, performance monitoring)
- AI Assistant (Ollama / OpenAI compatible API, streaming output)
- Config management system (dual-layer storage, sensitive data isolation)
- System tray with hide-to-tray behavior
- Single instance lock
- Hardware acceleration toggle (off by default for VM compatibility)
- Python process auto-restart (max 3 retries)


### Architecture

- `system_state` unified data model
- JSON Lines IPC communication (stdin/stdout)
- Modular panel system (dashboard, device center, terminal, AI assistant, settings)
- Embedded Python backend
- Flask Web Dashboard (optional)


### Known limitations

- SSH terminal does not support automatic reconnect
- AI Assistant is conversation-only, does not include Agent tool calling capabilities
- NAS monitoring supports Linux-based NAS only (via SSH commands)
- Hardware acceleration disabled by default for compatibility with virtual machines