from __future__ import annotations

import os
import sys
import json
import subprocess


def _get_path():
    from core.config import get_config
    return os.path.join(get_config().lab_root, "launchers.json")


def _load() -> list:
    path = _get_path()
    if not os.path.exists(path):
        return []
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            with open(path, "r", encoding=enc) as f:
                data = json.load(f)
            return data.get("shortcuts", [])
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return []


def _save(shortcuts: list):
    path = _get_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"shortcuts": shortcuts}, f, indent=2, ensure_ascii=False)


def add_shortcut(name: str, exe_path: str, args: str = "") -> str:
    shortcuts = _load()
    for s in shortcuts:
        if s["name"].lower() == name.lower():
            return "[!] 快捷方式 '{}' 已存在".format(name)
    shortcuts.append({"name": name, "path": exe_path, "args": args})
    _save(shortcuts)
    return "[OK] 已添加: {} → {}".format(name, exe_path)


def remove_shortcut(name: str) -> str:
    shortcuts = _load()
    for i, s in enumerate(shortcuts):
        if s["name"].lower() == name.lower():
            shortcuts.pop(i)
            _save(shortcuts)
            return "[OK] 已删除: {}".format(name)
    return "[!] 未找到快捷方式: {}".format(name)


def list_shortcuts() -> list:
    return _load()


def launch(index: int) -> str:
    shortcuts = _load()
    if index < 1 or index > len(shortcuts):
        return "[!] 无效的序号 (1-{})".format(len(shortcuts))
    s = shortcuts[index - 1]
    parts = [s["path"]]
    if s.get("args"):
        parts.append(s["args"])
    try:
        subprocess.Popen(parts, shell=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return "[OK] 已启动: {}".format(s["name"])
    except FileNotFoundError:
        return "[!] 找不到程序: {}".format(s["path"])
    except Exception as e:
        return "[!] 启动失败: {}".format(e)


def show_menu() -> str:
    shortcuts = _load()
    if not shortcuts:
        return "\n  暂无快捷方式。\n  添加: dlab launcher --add 名称 路径\n"

    lines = []
    lines.append("")
    lines.append("-" * 56)
    lines.append("  {:4s}  {:20s}  {}".format("序号", "名称", "路径"))
    lines.append("-" * 56)
    for i, s in enumerate(shortcuts, 1):
        path_display = s["path"]
        if len(path_display) > 28:
            path_display = "..." + path_display[-25:]
        lines.append("  [{:2d}]  {:20s}  {}".format(i, s["name"], path_display))
    lines.append("-" * 56)
    return "\n".join(lines)
