from __future__ import annotations

import os
import sys
import json
from dataclasses import dataclass, field, asdict, fields
from typing import Optional

_PY_MIN_VERSION = (3, 7)
_PY_VERSION = sys.version_info[:2]


def _check_python_version():
    if _PY_VERSION < _PY_MIN_VERSION:
        sys.exit(
            "DigitalLab 需要 Python {}.{} 或更高版本，"
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


# 基础数据目录：统一指向 %APPDATA%\DigitalLab，确保所有环境可写
BASE_DATA_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")), "DigitalLab"
)


def _get_user_config_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return _safe_path(base, "DigitalLab")
    base = os.environ.get("XDG_CONFIG_HOME", _safe_path(os.path.expanduser("~"), ".config"))
    return _safe_path(base, "DigitalLab")


def _get_user_config_path():
    return _safe_path(_get_user_config_dir(), "user_config.json")


# 敏感字段：这些字段存储在 AppData 用户目录，不随 soft 文件夹分发
_SENSITIVE_KEYS = {"auth_token", "ai", "nas_devices"}


def _detect_lab_root():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
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
        self.lab_root = _detect_lab_root()
        self.lab_root = _safe_path(self.lab_root)

        # 所有数据路径统一使用 BASE_DATA_DIR（%APPDATA%\DigitalLab）
        self.config_file = _safe_path(BASE_DATA_DIR, "config.json")

        sub_dirs = {
            "tools_dir": "tools",
            "logs_dir": "logs",
            "experiments_dir": "experiments",
            "notes_dir": "notes",
            "archive_dir": "archive",
            "interface_dir": "interface",
        }
        for attr, name in sub_dirs.items():
            setattr(self, attr, _safe_path(BASE_DATA_DIR, name))

        monitor_root = _safe_path(self.logs_dir, "monitor")
        self.monitor_db_path = _safe_path(monitor_root, "monitor.db")
        self.monitor_pid_path = _safe_path(monitor_root, "daemon.pid")
        self.monitor_log_path = _safe_path(monitor_root, "daemon.log")

        # 启动时自动创建目录
        os.makedirs(BASE_DATA_DIR, exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

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
        existing = {}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        data = asdict(self)
        data.pop("config_file", None)
        for k, v in existing.items():
            if k not in data and k not in _SENSITIVE_KEYS:
                data[k] = v
        # 过滤敏感字段，不写入 config.json
        clean = {k: v for k, v in data.items() if k not in _SENSITIVE_KEYS}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, ensure_ascii=False)

        # 敏感字段写入 AppData
        user_data = {}
        user_config_path = _get_user_config_path()
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
            except Exception:
                pass
        full_data = asdict(self)
        for k in _SENSITIVE_KEYS:
            if k in full_data and full_data[k] is not None:
                user_data[k] = full_data[k]
        if user_data:
            os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
            with open(user_config_path, "w", encoding="utf-8") as f:
                json.dump(user_data, f, indent=2, ensure_ascii=False)

    def reload(self):
        """重新从 config.json 和用户配置加载，更新当前实例"""
        if not os.path.exists(self.config_file):
            return
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            # 合并用户敏感配置
            user_config_path = _get_user_config_path()
            if os.path.exists(user_config_path):
                try:
                    with open(user_config_path, "r", encoding="utf-8") as f:
                        user_data = json.load(f)
                    data.update(user_data)
                except Exception:
                    pass
            known = {f.name for f in fields(self)}
            for k, v in data.items():
                if k in known and k != "config_file":
                    setattr(self, k, v)
        except Exception:
            pass

    @classmethod
    def load(cls, config_path: Optional[str] = None) -> Config:
        if config_path is None:
            # 优先从 APPDATA 加载，不存在时回退到项目目录
            appdata_config = _safe_path(BASE_DATA_DIR, "config.json")
            if os.path.exists(appdata_config):
                config_path = appdata_config
            else:
                config_path = _safe_path(_detect_lab_root(), "config.json")

        data = {}
        if os.path.exists(config_path):
            for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
                try:
                    with open(config_path, "r", encoding=enc) as f:
                        data = json.load(f)
                    break
                except (UnicodeDecodeError, json.JSONDecodeError):
                    continue

        # 从 AppData 加载用户敏感配置（API Key、Token 等），覆盖基础配置
        user_config_path = _get_user_config_path()
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                data.update(user_data)
            except Exception:
                pass
        else:
            # 首次迁移：config.json 中仍有敏感字段时，自动迁移到 AppData
            sensitive_in_config = {k: data[k] for k in _SENSITIVE_KEYS if k in data}
            if sensitive_in_config:
                try:
                    os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
                    with open(user_config_path, "w", encoding="utf-8") as f:
                        json.dump(sensitive_in_config, f, indent=2, ensure_ascii=False)
                except Exception:
                    pass

        data["config_file"] = config_path
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        return cls(**data)

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
