from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass, field, asdict
from typing import Optional

_PY_MIN_VERSION = (3, 7)
_PY_VERSION = sys.version_info[:2]


def _check_python_version():
    if _PY_VERSION < _PY_MIN_VERSION:
        sys.exit(
            "Digital Lab 需要 Python {}.{} 或更高版本，"
            "当前版本: {}.{}".format(*_PY_MIN_VERSION, *_PY_VERSION)
        )


def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        encoded_args = []
        for a in args:
            if isinstance(a, str):
                encoded_args.append(
                    a.encode(sys.stdout.encoding or "utf-8", errors="replace")
                    .decode(sys.stdout.encoding or "utf-8", errors="replace")
                )
            else:
                encoded_args.append(a)
        print(*encoded_args, **kwargs)


def _safe_path(*parts):
    joined = os.path.join(*parts)
    return os.path.normpath(joined)


def _detect_lab_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Config:

    lab_root: str = ""

    tools_dir: str = ""
    logs_dir: str = ""
    experiments_dir: str = ""
    notes_dir: str = ""
    archive_dir: str = ""
    interface_dir: str = ""

    log_level: str = "INFO"
    log_max_days: int = 30
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    auto_organize_enabled: bool = False
    auto_organize_interval: int = 3600

    dashboard_port: int = 8080
    dashboard_host: str = "127.0.0.1"

    monitor_threshold_cpu: int = 80
    monitor_threshold_memory: int = 85
    monitor_threshold_disk: int = 90
    monitor_alert_cooldown: int = 300
    monitor_interval: int = 60
    monitor_db_path: str = ""
    monitor_pid_path: str = ""
    monitor_log_path: str = ""

    config_file: str = ""

    def __post_init__(self):
        if not self.lab_root:
            self.lab_root = _detect_lab_root()
        self.lab_root = _safe_path(self.lab_root)

        if not self.config_file:
            self.config_file = _safe_path(self.lab_root, "config.json")

        sub_dirs = {
            "tools_dir": "tools",
            "logs_dir": "logs",
            "experiments_dir": "experiments",
            "notes_dir": "notes",
            "archive_dir": "archive",
            "interface_dir": "interface",
        }
        for attr, name in sub_dirs.items():
            if not getattr(self, attr):
                setattr(self, attr, _safe_path(self.lab_root, name))

        monitor_root = _safe_path(self.logs_dir, "monitor")
        if not self.monitor_db_path:
            self.monitor_db_path = _safe_path(monitor_root, "monitor.db")
        if not self.monitor_pid_path:
            self.monitor_pid_path = _safe_path(monitor_root, "daemon.pid")
        if not self.monitor_log_path:
            self.monitor_log_path = _safe_path(monitor_root, "daemon.log")

    def ensure_dirs(self):
        for d in [
            self.tools_dir, self.logs_dir, self.experiments_dir,
            self.notes_dir, self.archive_dir, self.interface_dir,
        ]:
            os.makedirs(d, exist_ok=True)
        os.makedirs(os.path.dirname(self.monitor_db_path), exist_ok=True)

    def get_thresholds(self) -> dict:
        return {
            "cpu": self.monitor_threshold_cpu,
            "memory": self.monitor_threshold_memory,
            "disk": self.monitor_threshold_disk,
        }

    def save(self):
        data = asdict(self)
        data.pop("config_file", None)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> Config:
        if config_path is None:
            config_path = _safe_path(_detect_lab_root(), "config.json")
        if os.path.exists(config_path):
            for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
                try:
                    with open(config_path, "r", encoding=enc) as f:
                        data = json.load(f)
                    data["config_file"] = config_path
                    return cls(**data)
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue
        return cls(config_file=config_path)

    @property
    def python_version(self) -> str:
        return "{}.{}.{}".format(*sys.version_info[:3])

    @property
    def platform_info(self) -> str:
        if sys.platform == "win32":
            try:
                build = sys.getwindowsversion().build
                name = "Windows 11" if build >= 22000 else "Windows 10"
                return "{} build {}".format(name, build)
            except Exception:
                return "Windows (未知版本)"
        return "{} {}".format(sys.platform, os.name)


_default_config: Optional[Config] = None


def get_config() -> Config:
    global _default_config
    if _default_config is None:
        _check_python_version()
        _default_config = Config.load()
    return _default_config
