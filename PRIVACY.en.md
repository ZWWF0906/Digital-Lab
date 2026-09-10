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
