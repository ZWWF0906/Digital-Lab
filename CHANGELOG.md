# Changelog

## v1.6.0 - 2026-11-09

### Added

- Native folder/file pickers for the AI memory directory and optional CA bundle

- Three-language messages for the new path, credential and AI stream safety errors

### Changed

- Runtime memory, reports and snapshots now live in the user data directory, never in the installation directory

- Saved AI/NAS credentials are protected with the Windows user-scoped secure storage; existing plaintext credentials are migrated automatically

- AI streaming responses have hard single-line, total-size and reasoning-channel limits

### Fixed

- Configuration changes can no longer use flat dotted keys to bypass the native sensitive-change confirmation

- AI memory directory and CA bundle paths reject UNC, device, traversal and symlink redirection; external paths come from the native picker

- Concurrent memory de-duplication and chat-history append/prune/clear operations no longer lose or overwrite entries; history writes are atomic and the 100-record display boundary is covered by tests

- Opening a terminal twice at the same time now produces one SSH session, without an orphan session

- Legacy NAS credentials in the old `config.json` are migrated to protected storage, removed from the legacy file, and are no longer used as a runtime fallback

- AI memory directory changes validate both the old and new locations; migration failures preserve the old directory and data, and an existing target is never overwritten

- A configured custom CA bundle that is missing or unreadable now fails the request instead of quietly falling back to system trust

- Terminal window construction or page-load failure now closes the backend SSH session; normal terminal connection remains unchanged

- Sensitive configuration confirmations distinguish query/fragment changes without displaying token values; high-cost AI requests, native pickers and trust-challenge state have local limits

- NAS `last_error` no longer exposes raw exception text; repeated connection probes are rate-limited

- The dashboard and terminal CSP no longer permits renderer network connections

- Corrected the open-source license label in the About page to ISC (aligned with LICENSE and package.json)

## v1.5.0 - 2026-10-09

### Added

- Terminal connections now persist: switching panels no longer reconnects, and hiding the window no longer drops the session

- AI chat history: conversations are saved in a local file, restored after a restart, and can be cleared in Settings

- AI memory entries now carry id, tag and source fields, preparing the ground for retrieval

### Fixed

- Log storm fixed: the EPIPE feedback loop is cut; the log rotates at 5MB and is deleted outright beyond 50MB

- The command channel is no longer blocked by network waits: SSH connects and connection tests now run asynchronously

- State broadcasts are deduplicated and panels skip rebuilds when nothing changed; failed NAS collections no longer spam the log

- Mock devices no longer appear in the terminal tab list

## v1.4.0 - 2026-09-21

### Added

- Multilingual interface: Simplified Chinese, English and Japanese, switchable at any time in Settings

- First-run onboarding: a three-step guide that selects the interface language, adds a NAS device and checks the connection

- Threshold alerts as system notifications: when CPU, memory or disk usage stays above the configured limit, a desktop notification is shown, and the same alert is not repeated until the reading drops back below the limit

- The AI assistant now answers in the selected interface language

### Fixed

- AI failures are now explained clearly and in the selected interface language: an unreachable service, a missing model or rejected credentials each say what happened and what to do next

## v1.3.0 - 2026-09-18

### Added

- Animated startup splash: hexagon and waveform stroke drawing, wordmark reveal, staggered self-check list, closing breath and fade-out

- The startup splash adapts to both the dark and the light theme

- Startup splash toggle in Settings

- "Quick deploy" placeholder button in the AI assistant header

### Changed

- Orbitron, Inter and JetBrains Mono are now bundled with the app, so the interface no longer depends on system or web fonts

- Redrawn application icons for window, taskbar, tray and store assets

### Fixed

- The startup animation no longer starts too early: the hexagon is still at zero progress when the window appears

- The selected theme is kept after the app is force-killed

- The application config file is no longer written into the project folder

- Taskbar identity now matches the installed shortcut

## v1.2.0 - 2026-09-10

### Added

- Local AI memory: the assistant can remember user preferences and inject them into the system prompt (toggle, storage directory, view/delete/clear in Settings)

### Changed

- Slimmed down the CLI command surface (removed placeholder and legacy commands)

### Fixed

- Application name is shown as DigitalLab in system dialogs
- Saving AI configuration no longer overwrites stored values with empty inputs
- Empty AI replies now show a placeholder instead of an empty bubble
- Memory list no longer requires a second click (config-load race)
- NAS process table header alignment
- Memory deletion now uses a native warning dialog

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

