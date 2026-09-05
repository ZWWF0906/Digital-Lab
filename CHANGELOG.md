# Changelog

## v1.1.1 - 2026-09-05

### Fixed

- Fixed Chinese-character garbling in AI chat replies

## v1.1.0 - 2026-09-04

### Added

- Light theme (white mode) with 300ms eased transition, deep color as default

- Theme switching control in Settings panel, persisted after restart

- Layered light surfaces (page / sidebar / card / hover) with WCAG-calibrated colors

- A 4-tier grey shadow system for light mode replacing dark glow language

- AI assistant system prompt with role definition and mandatory Chinese responses

- Incremental UTF-8 streaming decoder and repetition guard to prevent garbled or runaway model output

### Changed

- Recalibrated status colors (emerald/amber/red) for light background

- Terminal panel stays dark in both themes (theme-independent tokens)

- Neutral borders in light mode; emerald reserved for active and focus states

- Table zebra striping, row hover, and scrim rebuilt for readability in light mode

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

