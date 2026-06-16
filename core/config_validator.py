from __future__ import annotations

import json
import os
import sys
from typing import Optional

_SCHEMA = {
    "lab_root":              {"type": "str",   "default": "",      "desc": "实验室根目录"},
    "tools_dir":             {"type": "str",   "default": "",      "desc": "工具目录"},
    "logs_dir":              {"type": "str",   "default": "",      "desc": "日志目录"},
    "experiments_dir":       {"type": "str",   "default": "",      "desc": "实验目录"},
    "notes_dir":             {"type": "str",   "default": "",      "desc": "笔记目录"},
    "archive_dir":           {"type": "str",   "default": "",      "desc": "存档目录"},
    "interface_dir":         {"type": "str",   "default": "",      "desc": "接口目录"},

    "log_level":             {"type": "str",   "default": "INFO",  "desc": "日志级别",
                              "enum": ["DEBUG", "INFO", "WARN", "ERROR"]},
    "log_max_days":          {"type": "int",   "default": 30,      "desc": "日志保留天数",
                              "min": 1, "max": 365},
    "log_format":            {"type": "str",   "default": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                              "desc": "Python logging 格式字符串"},

    "auto_organize_enabled": {"type": "bool",  "default": False,   "desc": "自动整理开关"},
    "auto_organize_interval":{"type": "int",   "default": 3600,    "desc": "自动整理间隔(秒)",
                              "min": 1, "max": 86400},

    "dashboard_port":        {"type": "int",   "default": 8080,    "desc": "Web 仪表盘端口",
                              "min": 1, "max": 65535},
    "dashboard_host":        {"type": "str",   "default": "127.0.0.1", "desc": "Web 仪表盘监听地址"},

    "monitor_threshold_cpu": {"type": "int",   "default": 80,      "desc": "CPU 告警阈值(%)",
                              "min": 0, "max": 100},
    "monitor_threshold_memory": {"type": "int","default": 85,      "desc": "内存告警阈值(%)",
                              "min": 0, "max": 100},
    "monitor_threshold_disk": {"type": "int",  "default": 90,      "desc": "磁盘告警阈值(%)",
                              "min": 0, "max": 100},
    "monitor_alert_cooldown": {"type": "int",  "default": 300,     "desc": "告警冷却时间(秒)",
                              "min": 1, "max": 86400},
    "monitor_interval":      {"type": "int",   "default": 60,      "desc": "守护采集间隔(秒)",
                              "min": 1, "max": 86400},
    "monitor_db_path":       {"type": "str",   "default": "",      "desc": "监控 SQLite 路径"},
    "monitor_pid_path":      {"type": "str",   "default": "",      "desc": "守护 PID 文件路径"},
    "monitor_log_path":      {"type": "str",   "default": "",      "desc": "守护日志路径"},
}


_DEFAULT_FROM_CONFIG = object()


def _try_coerce(value, target_type: str):
    if target_type == "str":
        if isinstance(value, str):
            return True, value
        if isinstance(value, (bool, type(None))):
            return False, None
        return True, str(value)

    if target_type == "int":
        if isinstance(value, int) and not isinstance(value, bool):
            return True, value
        if isinstance(value, bool):
            return True, int(value)
        if isinstance(value, float):
            return True, int(value)
        if isinstance(value, str):
            try:
                return True, int(value.strip())
            except ValueError:
                return False, None
        return False, None

    if target_type == "bool":
        if isinstance(value, bool):
            return True, value
        if isinstance(value, int):
            return True, bool(value)
        if isinstance(value, str):
            v = value.strip().lower()
            if v in ("true", "1", "yes", "on"):
                return True, True
            if v in ("false", "0", "no", "off", ""):
                return True, False
        return False, None

    return False, None


def _clamp(value, rules: dict):
    lo = rules.get("min")
    hi = rules.get("max")
    original = value
    if lo is not None and value < lo:
        value = lo
    if hi is not None and value > hi:
        value = hi
    return value, value != original


def validate_config(raw_data: dict) -> tuple[dict, list]:
    fixed = {}
    report = []

    for field, rules in _SCHEMA.items():
        ftype = rules["type"]
        default = rules["default"]

        if field not in raw_data:
            fixed[field] = default
            report.append(
                "[缺失] {} = {} (使用默认值)".format(field, _repr_val(default))
            )
            _log_warn("缺少字段 {}, 已填充默认值".format(field))
            continue

        value = raw_data[field]

        ok, converted = _try_coerce(value, ftype)
        if not ok:
            fixed[field] = default
            report.append(
                "[类型] {} = {} → 默认 {} (无法将 {} 转为 {})".format(
                    field, _repr_val(value), _repr_val(default),
                    type(value).__name__, ftype
                )
            )
            _log_warn("字段 {} 类型错误 ({}), 已用默认值替换".format(field, type(value).__name__))
            continue

        if ok and converted != value:
            report.append(
                "[类型] {} = {} → {} (已自动转换)".format(
                    field, _repr_val(value), _repr_val(converted)
                )
            )

        clamped, did_clamp = _clamp(converted, rules)
        if did_clamp:
            report.append(
                "[范围] {} = {} → {} (已截断到 {}-{})".format(
                    field, _repr_val(converted), _repr_val(clamped),
                    rules.get("min", "-∞"), rules.get("max", "∞")
                )
            )
            _log_warn("字段 {} 值超出范围, 已截断".format(field))

        enum_vals = rules.get("enum")
        if ftype == "str" and enum_vals:
            if clamped not in enum_vals:
                fixed[field] = default
                report.append(
                    "[取值] {} = {} → 默认 {} (有效值: {})".format(
                        field, _repr_val(clamped), _repr_val(default),
                        ", ".join(enum_vals)
                    )
                )
                _log_warn("字段 {} 取值非法, 已用默认值替换".format(field))
                continue

        fixed[field] = clamped

    return fixed, report


def _repr_val(v) -> str:
    if isinstance(v, str):
        s = v
        if len(s) > 50:
            s = s[:47] + "..."
        return '"{}"'.format(s)
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _log_warn(msg: str):
    try:
        from core.logger import log_warn
        log_warn(msg)
    except Exception:
        pass


def format_report(report: list) -> str:
    if not report:
        return ""
    lines = []
    lines.append("")
    lines.append("=" * 60)
    lines.append("  Config 校验报告 ({}) 处修正".format(len(report)))
    lines.append("=" * 60)
    for r in report:
        lines.append("  " + r)
    lines.append("=" * 60)
    return "\n".join(lines)


def generate_schema_file(path: str):
    schema = {
        "$schema": "https://json-schema.org/draft-07/schema",
        "title": "Digital Lab 配置规则",
        "description": "自动生成 — 与 core/config_validator.py 中的规则保持同步",
        "type": "object",
        "properties": {},
        "definitions": {},
    }

    for field, rules in _SCHEMA.items():
        prop = {
            "description": rules["desc"],
            "default": rules["default"],
        }

        ftype = rules["type"]
        if ftype == "str":
            prop["type"] = "string"
        elif ftype == "int":
            prop["type"] = "integer"
            if "min" in rules:
                prop["minimum"] = rules["min"]
            if "max" in rules:
                prop["maximum"] = rules["max"]
        elif ftype == "bool":
            prop["type"] = "boolean"

        if "enum" in rules:
            prop["enum"] = rules["enum"]

        schema["properties"][field] = prop

    schema["required"] = []   # all fields have defaults, none required

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)


def run_validator(config_path: str) -> Optional[list]:
    if not os.path.exists(config_path):
        return None

    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            with open(config_path, "r", encoding=enc) as f:
                raw_data = json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue

        fixed_data, report = validate_config(raw_data)

        if report:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(fixed_data, f, indent=2, ensure_ascii=False)

        schema_path = os.path.join(os.path.dirname(config_path) or ".", "config.schema.json")
        generate_schema_file(schema_path)

        return report

    return None
