from __future__ import annotations

import json
import os
import threading
import datetime
from typing import Optional


class JsonLogger:
    _instance: Optional[JsonLogger] = None
    _lock = threading.Lock()

    def __init__(self, log_path: str):
        self._path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    @classmethod
    def get(cls, log_path: Optional[str] = None) -> JsonLogger:
        if cls._instance is None:
            if log_path is None:
                from core.config import get_config
                log_path = get_config().monitor_log_path
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(log_path)
        return cls._instance

    @classmethod
    def reset(cls):
        with cls._lock:
            cls._instance = None

    def _write(self, level: str, message: str, **extra):
        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "level": level,
            "message": message,
        }
        if extra:
            entry["data"] = extra
        with self._lock:
            try:
                with open(self._path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def info(self, message: str, **extra):
        self._write("INFO", message, **extra)

    def warn(self, message: str, **extra):
        self._write("WARN", message, **extra)

    def error(self, message: str, **extra):
        self._write("ERROR", message, **extra)

    def alert(self, metric: str, current: float, threshold: float, **extra):
        self._write("ALERT", "{} 超过阈值".format(metric), current=current, threshold=threshold, **extra)


def log_info(message: str, **extra):
    JsonLogger.get().info(message, **extra)


def log_warn(message: str, **extra):
    JsonLogger.get().warn(message, **extra)


def log_error(message: str, **extra):
    JsonLogger.get().error(message, **extra)


def log_alert(metric: str, current: float, threshold: float, **extra):
    JsonLogger.get().alert(metric, current, threshold, **extra)
