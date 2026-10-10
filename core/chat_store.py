"""AI 对话历史存储（后端）。

存储格式：JSONL，每行一个
  {"id": 稳定短哈希, "ts": ISO 秒级时间, "role": "user"|"assistant",
   "content": 文本, "session_id": 会话标识}

存储位置：默认 %APPDATA%\\DigitalLab\\memory\\chat_history.jsonl；
          可由 user_config.json 的 ai.history.dir 覆盖。
开关字段：user_config.json 的 ai.history.enabled（默认开启）。
保留上限：user_config.json 的 ai.history.limit（默认 200 条，超出后按最旧优先裁剪）。

测试用环境变量覆盖（优先级高于配置文件，仅用于开发与自动化验证）：
  DIGITAL_LAB_CHAT_HISTORY_ENABLED=1/0
  DIGITAL_LAB_CHAT_HISTORY_DIR=<目录绝对路径>

确定性约束（供 DeepSeek 前缀缓存使用）：load() 只按 ts 做稳定排序，
同一秒内的多条保持文件写入顺序，绝不引入随机或哈希排序。
append() 同时负责裁剪，保证同一份文件在相同输入下产出相同结果。

所有文件操作均容错：任何异常都不向外抛出，返回安全默认值。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re

HISTORY_FILE_NAME = "chat_history.jsonl"
DEFAULT_DIR_NAME = "memory"
DEFAULT_SESSION_ID = "default"
DEFAULT_LIMIT = 200
MIN_LIMIT = 20
MAX_LIMIT = 5000
MAX_CONTENT_LEN = 12000
ROLES = ("user", "assistant")
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


def config_history() -> dict:
    """读取 user_config.json 的 ai.history 段；缺失或异常时返回空字典。"""
    cfg = _read_user_config()
    ai = cfg.get("ai")
    hist = ai.get("history") if isinstance(ai, dict) else None
    return hist if isinstance(hist, dict) else {}


def _config_dir() -> str:
    value = config_history().get("dir")
    return value.strip() if isinstance(value, str) else ""


def enabled() -> bool:
    """历史开关：环境变量优先，其次 ai.history.enabled，默认开启。"""
    env = os.environ.get("DIGITAL_LAB_CHAT_HISTORY_ENABLED")
    if isinstance(env, str) and env.strip():
        return env.strip().lower() in _TRUTHY
    value = config_history().get("enabled")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in _TRUTHY
    if isinstance(value, (int, float)):
        return bool(value)
    return True


def limit() -> int:
    """保留上限：环境变量 > ai.history.limit > 默认 200，并夹在 [20, 5000]。"""
    env = os.environ.get("DIGITAL_LAB_CHAT_HISTORY_LIMIT")
    raw = env.strip() if isinstance(env, str) and env.strip() else config_history().get("limit")
    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_LIMIT
    if value < MIN_LIMIT:
        value = MIN_LIMIT
    if value > MAX_LIMIT:
        value = MAX_LIMIT
    return value


def history_dir() -> str:
    """生效目录：环境变量 > ai.history.dir > 默认 %APPDATA%\\DigitalLab\\memory。"""
    env = os.environ.get("DIGITAL_LAB_CHAT_HISTORY_DIR")
    raw = env.strip() if isinstance(env, str) and env.strip() else _config_dir()
    if not raw:
        raw = os.path.join(_base_data_dir(), DEFAULT_DIR_NAME)
    try:
        return os.path.abspath(os.path.expanduser(raw))
    except Exception:
        return raw


def history_file() -> str:
    return os.path.join(history_dir(), HISTORY_FILE_NAME)


def settings() -> dict:
    """返回 {"enabled": bool, "dir": 生效目录, "limit": int}。"""
    return {"enabled": enabled(), "dir": history_dir(), "limit": limit()}


def ensure_dir() -> str:
    path = history_dir()
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:
        pass
    return path


def _norm_session(session_id) -> str:
    value = session_id.strip() if isinstance(session_id, str) else ""
    return value or DEFAULT_SESSION_ID


def _entry_id(ts: str, role: str, content: str) -> str:
    """稳定短哈希：同一条消息在任意时刻重算都得到同一个 id。"""
    raw = "{0}|{1}|{2}".format(ts, role, content)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _clean(text, max_len: int = MAX_CONTENT_LEN) -> str:
    if not isinstance(text, str):
        return ""
    value = text.strip()
    if max_len and len(value) > max_len:
        value = value[:max_len]
    return value


def _load_raw() -> list:
    """按文件顺序读取全部合法条目（坏行与空内容行跳过）。"""
    entries = []
    try:
        path = history_file()
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
                role = obj.get("role")
                content = obj.get("content")
                if role not in ROLES or not isinstance(content, str) or not content.strip():
                    continue
                ts = obj.get("ts")
                ts = ts if isinstance(ts, str) else ""
                entry = {
                    "ts": ts,
                    "role": role,
                    "content": content,
                    "session_id": _norm_session(obj.get("session_id")),
                }
                entry["id"] = obj.get("id") if isinstance(obj.get("id"), str) and obj.get("id") else _entry_id(ts, role, content)
                entries.append(entry)
    except Exception:
        return entries
    return entries


def _write_all(entries: list) -> bool:
    try:
        ensure_dir()
        with open(history_file(), "w", encoding="utf-8") as f:
            for item in entries:
                record = {
                    "id": item.get("id", ""),
                    "ts": item.get("ts", ""),
                    "role": item.get("role", ""),
                    "content": item.get("content", ""),
                    "session_id": _norm_session(item.get("session_id")),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def count(session_id=None) -> int:
    items = _load_raw()
    if session_id:
        target = _norm_session(session_id)
        items = [it for it in items if it.get("session_id") == target]
    return len(items)


def load(limit_n=None, session_id=None) -> list:
    """返回历史条目，按 ts 稳定排序（同秒保持写入顺序）。

    limit_n 为 None 时返回全部；给出时返回最近 N 条（仍为从旧到新）。
    """
    items = _load_raw()
    if session_id:
        target = _norm_session(session_id)
        items = [it for it in items if it.get("session_id") == target]
    # ts 为空的行排在最前，避免时间缺失的旧数据扰乱顺序；稳定排序保证同秒顺序不变
    items.sort(key=lambda it: it.get("ts", ""))
    if limit_n is not None:
        try:
            n = int(limit_n)
        except Exception:
            n = 0
        if n > 0:
            items = items[-n:]
        elif n == 0:
            items = []
    for i, it in enumerate(items):
        it["index"] = i
    return items


def prune(max_entries=None, session_id=None) -> int:
    """把（指定会话的）条目裁剪到上限，返回删除条数。"""
    cap = max_entries if max_entries is not None else limit()
    items = _load_raw()
    if session_id:
        target = _norm_session(session_id)
        scoped = [it for it in items if it.get("session_id") == target]
    else:
        scoped = items
    overflow = len(scoped) - cap
    if overflow <= 0:
        return 0
    doomed = set()
    for it in scoped[:overflow]:
        doomed.add((it.get("ts", ""), it.get("role", ""), it.get("content", "")))
    kept = [it for it in items if (it.get("ts", ""), it.get("role", ""), it.get("content", "")) not in doomed]
    return overflow if _write_all(kept) else 0


def append(role, content, session_id=None, ts=None) -> dict:
    """追加一条消息；角色非法、内容为空或写入失败时返回 None。

    写入后按 ai.history.limit 裁剪最旧条目。
    """
    if role not in ROLES:
        return None
    text = _clean(content)
    if not text:
        return None
    stamp = ts if isinstance(ts, str) and ts.strip() else datetime.datetime.now().isoformat(timespec="seconds")
    entry = {
        "ts": stamp,
        "role": role,
        "content": text,
        "session_id": _norm_session(session_id),
    }
    entry["id"] = _entry_id(entry["ts"], entry["role"], entry["content"])
    try:
        ensure_dir()
        with open(history_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        return None
    try:
        prune()
    except Exception:
        pass
    return entry


def delete(index_or_id) -> bool:
    """按 index（load 顺序下标）或 id 删除一条；失败返回 False。"""
    items = _load_raw()
    ordered = load(None)
    target_key = None
    if isinstance(index_or_id, str) and index_or_id.strip() and not index_or_id.strip().isdigit():
        wanted = index_or_id.strip()
        if not any(it.get("id") == wanted for it in items):
            return False
        kept = [it for it in items if it.get("id") != wanted]
        return _write_all(kept)
    try:
        idx = int(index_or_id)
    except Exception:
        return False
    if idx < 0 or idx >= len(ordered):
        return False
    picked = ordered[idx]
    target_key = (picked.get("ts", ""), picked.get("role", ""), picked.get("content", ""))
    kept = []
    removed = False
    for it in items:
        key = (it.get("ts", ""), it.get("role", ""), it.get("content", ""))
        if not removed and key == target_key:
            removed = True
            continue
        kept.append(it)
    return _write_all(kept) if removed else False


def clear(session_id=None) -> bool:
    """清空历史；给出 session_id 时只清该会话。失败返回 False。"""
    try:
        if session_id:
            target = _norm_session(session_id)
            kept = [it for it in _load_raw() if it.get("session_id") != target]
            return _write_all(kept)
        ensure_dir()
        with open(history_file(), "w", encoding="utf-8") as f:
            f.write("")
        return True
    except Exception:
        return False


def sessions() -> list:
    """返回出现过的会话标识（按文件顺序去重）。"""
    seen = []
    for it in _load_raw():
        sid = it.get("session_id", DEFAULT_SESSION_ID)
        if sid not in seen:
            seen.append(sid)
    return seen


def extract_markers(text) -> tuple:
    """占位：历史模块不解析记忆标记，保留函数名以便调用方统一 import 时不出错。"""
    return (text if isinstance(text, str) else "", [])


# 供 main.py 做确定性排序时复用：把内容里的连续空白压平，只用于比较，不写回。
def normalize(text) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()
