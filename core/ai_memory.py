"""AI 长期记忆存储（后端）。

存储格式：JSONL，每行一个 {"ts": ISO 时间字符串, "content": 文本}。
存储位置：默认 %APPDATA%\\DigitalLab\\memory\\ai_memory.jsonl；
          可由 user_config.json 的 ai.memory.dir 覆盖。
开关字段：user_config.json 的 ai.memory.enabled（默认关闭）。

测试用环境变量覆盖（优先级高于配置文件，仅用于开发与自动化验证）：
  DIGITAL_LAB_AI_MEMORY_ENABLED=1/0
  DIGITAL_LAB_AI_MEMORY_DIR=<目录绝对路径>

所有文件操作均容错：任何异常都不向外抛出，返回安全默认值。
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil

MEMORY_FILE_NAME = "ai_memory.jsonl"
DEFAULT_DIR_NAME = "memory"
MAX_CONTENT_LEN = 500
MAX_PER_REPLY = 3  # 每轮回复最多提取 3 条记忆，超出部分丢弃（标记仍会从正文剥离）

_MARKER_RE = re.compile(r"\[记忆\](.*?)\[/记忆\]", re.S)
_TRUTHY = {"1", "true", "yes", "on"}


def _base_data_dir() -> str:
    try:
        from core.config import BASE_DATA_DIR
        if BASE_DATA_DIR:
            return BASE_DATA_DIR
    except Exception:
        pass
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "DigitalLab")


def _user_config_path() -> str:
    try:
        from core.config import _get_user_config_path
        path = _get_user_config_path()
        if path:
            return path
    except Exception:
        pass
    return os.path.join(_base_data_dir(), "user_config.json")


def _read_user_config() -> dict:
    try:
        with open(_user_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def config_memory() -> dict:
    """读取 user_config.json 的 ai.memory 段；缺失或异常时返回空字典。"""
    cfg = _read_user_config()
    ai = cfg.get("ai")
    mem = ai.get("memory") if isinstance(ai, dict) else None
    return mem if isinstance(mem, dict) else {}


def config_dir() -> str:
    """仅从配置文件读取记忆目录（不含环境变量覆盖）；未配置返回空串。"""
    value = config_memory().get("dir")
    return value.strip() if isinstance(value, str) else ""


def enabled() -> bool:
    """记忆开关：环境变量优先，其次 ai.memory.enabled，默认关闭。"""
    env = os.environ.get("DIGITAL_LAB_AI_MEMORY_ENABLED")
    if isinstance(env, str) and env.strip():
        return env.strip().lower() in _TRUTHY
    value = config_memory().get("enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def memory_dir() -> str:
    """生效的记忆目录：环境变量 > ai.memory.dir > 默认 %APPDATA%\\DigitalLab\\memory。"""
    env = os.environ.get("DIGITAL_LAB_AI_MEMORY_DIR")
    raw = env.strip() if isinstance(env, str) and env.strip() else config_dir()
    if not raw:
        raw = os.path.join(_base_data_dir(), DEFAULT_DIR_NAME)
    try:
        return os.path.abspath(os.path.expanduser(raw))
    except Exception:
        return raw


def memory_file() -> str:
    return os.path.join(memory_dir(), MEMORY_FILE_NAME)


def settings() -> dict:
    """返回 {"enabled": bool, "dir": 生效目录}。"""
    return {"enabled": enabled(), "dir": memory_dir()}


def ensure_dir() -> str:
    path = memory_dir()
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _load_raw() -> list:
    entries = []
    try:
        path = memory_file()
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if not isinstance(obj, dict):
                    continue
                content = obj.get("content")
                if not isinstance(content, str) or not content.strip():
                    continue
                ts = obj.get("ts")
                entries.append({
                    "ts": ts if isinstance(ts, str) else "",
                    "content": content,
                })
    except Exception:
        return entries
    return entries


def list_all() -> list:
    """返回全部记忆条目（跳过坏行与空内容行）。"""
    return _load_raw()


def load_recent(n: int = 10) -> list:
    """返回最近 n 条记忆，按时间从旧到新排序；n 非法或非正数返回空列表。"""
    try:
        count = int(n)
    except Exception:
        return []
    if count <= 0:
        return []
    return _load_raw()[-count:]


def append(content) -> dict:
    """追加一条记忆；内容为空或写入失败时返回 None。"""
    if not isinstance(content, str):
        return None
    text = content.strip()[:MAX_CONTENT_LEN].strip()
    if not text:
        return None
    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "content": text,
    }
    try:
        ensure_dir()
        with open(memory_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return None
    return entry


def _write_all(entries: list) -> bool:
    try:
        ensure_dir()
        with open(memory_file(), "w", encoding="utf-8") as f:
            for item in entries:
                record = {
                    "ts": item.get("ts", "") if isinstance(item, dict) else "",
                    "content": item.get("content", "") if isinstance(item, dict) else "",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def delete(index: int) -> bool:
    """按索引删除一条记忆（索引基于 list_all 的过滤后顺序）；失败返回 False。"""
    try:
        idx = int(index)
    except Exception:
        return False
    entries = _load_raw()
    if idx < 0 or idx >= len(entries):
        return False
    entries.pop(idx)
    return _write_all(entries)


def clear() -> bool:
    """清空记忆文件（保留文件本身）；失败返回 False。"""
    try:
        ensure_dir()
        with open(memory_file(), "w", encoding="utf-8") as f:
            f.write("")
        return True
    except Exception:
        return False


def migrate(old_dir: str, new_dir: str) -> dict:
    """把旧目录的 ai_memory.jsonl 复制到新目录（shutil.copy，不删除旧文件）。

    仅在用户修改 ai.memory.dir 时调用。返回 {"ok", "copied", "message"}。
    """
    result = {"ok": True, "copied": False, "message": ""}
    try:
        if not isinstance(old_dir, str) or not isinstance(new_dir, str) or not old_dir.strip() or not new_dir.strip():
            result["message"] = "目录参数为空，跳过迁移"
            return result
        src = os.path.join(os.path.abspath(os.path.expanduser(old_dir)), MEMORY_FILE_NAME)
        dst_dir = os.path.abspath(os.path.expanduser(new_dir))
        if not os.path.exists(src):
            result["message"] = "旧文件不存在，跳过迁移"
            return result
        if os.path.dirname(src) == dst_dir:
            result["message"] = "新旧目录相同，跳过迁移"
            return result
        os.makedirs(dst_dir, exist_ok=True)
        shutil.copy(src, os.path.join(dst_dir, MEMORY_FILE_NAME))
        result["copied"] = True
        result["message"] = "已复制到 " + dst_dir
    except Exception as e:
        result["ok"] = False
        result["message"] = str(e)
    return result


def extract_markers(text) -> tuple:
    """从回复文本提取 [记忆]...[/记忆] 并剥离标记。

    容错原则：只有成对且内容非空的标记会被提取；格式不合法时保留原文、
    不写入、不抛异常。每轮最多提取 MAX_PER_REPLY 条，超出的丢弃；
    无论是否超出，所有成对标记都会从正文剥离。
    返回 (清洗后的文本, 记忆内容列表)。
    """
    if not isinstance(text, str):
        return ("", [])
    if not text:
        return ("", [])
    found = []
    for match in _MARKER_RE.finditer(text):
        if len(found) >= MAX_PER_REPLY:
            break
        item = (match.group(1) or "").strip()[:MAX_CONTENT_LEN].strip()
        if not item or item in found:
            continue
        found.append(item)
    clean = _MARKER_RE.sub("", text)
    clean = "\n".join(line.rstrip() for line in clean.split("\n"))
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return (clean, found)
