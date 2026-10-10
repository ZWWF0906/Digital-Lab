"""AI 长期记忆存储（后端）。

存储格式：JSONL，每行一个
  {"id": 稳定短哈希, "ts": ISO 时间字符串, "content": 文本,
   "kind": 类别, "tags": [标签], "source": 来源标识}
旧文件只含 ts/content：读取时补默认值（kind="fact"、tags=[]、source=""、
id 由 ts+归一化内容哈希得到），不重写文件。
存储位置：默认 %APPDATA%\\DigitalLab\\memory\\ai_memory.jsonl；
          可由 user_config.json 的 ai.memory.dir 覆盖。
开关字段：user_config.json 的 ai.memory.enabled（默认关闭）。

确定性约束（供 DeepSeek 前缀缓存使用）：load_recent() 只按 ts 做稳定排序，
同一秒内的多条保持文件写入顺序，结果在相同文件下可复现。

测试用环境变量覆盖（优先级高于配置文件，仅用于开发与自动化验证）：
  DIGITAL_LAB_AI_MEMORY_ENABLED=1/0
  DIGITAL_LAB_AI_MEMORY_DIR=<目录绝对路径>

所有文件操作均容错：任何异常都不向外抛出，返回安全默认值。
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import shutil
import unicodedata

MEMORY_FILE_NAME = "ai_memory.jsonl"
DEFAULT_DIR_NAME = "memory"
MAX_CONTENT_LEN = 500
MAX_PER_REPLY = 3  # 每轮回复最多提取 3 条记忆，超出部分丢弃（标记仍会从正文剥离）
MAX_TAGS = 8
DEFAULT_KIND = "fact"
DEFAULT_SOURCE = ""

# 记忆标记：中文 [记忆]...[/记忆] 为默认，英文 <mem>...</mem>；两种都识别、都从正文剥离。
# 用一个组合正则而不是两个：既保留标记在正文中的先后顺序，sub() 也能一次清干净。
# 已写入的记忆条目存的是剥离后的内容，所以标记换代不影响旧记忆的读取。
_MARKER_RE = re.compile(r"\[记忆\](.*?)\[/记忆\]|<mem>(.*?)</mem>", re.S | re.I)
_TRAILING_PUNCT = "。．.，,！!？?；;：:、…~～"
_TRUTHY = {"1", "true", "yes", "on"}


# 去重键专用：零宽与不可见字符（零宽空格/连接符/BOM/词连接符）
_INVISIBLE_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff]")
# 去重键专用：所有 Unicode 空白（含词内空格；NFKC 之后全角空格 U+3000 已折叠为普通空格）
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize(text) -> str:
    """生成去重键（记忆条目的唯一主键），只用于比较，不写回文件。

    处理顺序：NFKC 归一（全角→半角、兼容字符折叠）→ casefold（大小写不敏感）
    → 移除零宽字符 → 移除全部 Unicode 空白（含词内空格）→ 去尾部标点 → 截断长度。

    因此下面四种写法会归一到同一个键 "用户称呼为zwwf0906"：
      '用户称呼为 ZWWF0906' / '用户称呼为ZWWF0906' /
      '用户称呼为 ＺＷＷＦ0906' / '用户称呼为 zwwf0906'
    1.5.0 之前只压缩空白不删除空白，导致"带空格/不带空格"被当成两条（线上已出现该重复）。

    注意：本函数同时参与新条目 id 的生成（entry_id），升级后**新写入**条目的 id 会变化；
    旧条目已落盘的 id 在读取时原样保留，不受影响。
    """
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = t.casefold()
    t = _INVISIBLE_RE.sub("", t)
    t = _WHITESPACE_RE.sub("", t)
    t = t.rstrip(_TRAILING_PUNCT)
    return t[:MAX_CONTENT_LEN]


def entry_id(ts, content) -> str:
    """稳定短哈希（ts + 归一化内容）：同一内容在任何时刻重算结果一致。"""
    raw = "{0}|{1}".format(ts if isinstance(ts, str) else "", normalize(content))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _norm_tags(value) -> list:
    """标签归一化：字符串按逗号/空白切分，去空去重，限长限量，保持输入顺序。"""
    tags = []
    raw = []
    if isinstance(value, str):
        raw = re.split(r"[,，;；\s]+", value)
    elif isinstance(value, (list, tuple)):
        raw = list(value)
    for item in raw:
        tag = normalize(item)[:32]
        if tag and tag not in tags:
            tags.append(tag)
        if len(tags) >= MAX_TAGS:
            break
    return tags


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
                ts = ts if isinstance(ts, str) else ""
                entries.append({
                    "ts": ts,
                    "content": content,
                    # 结构化字段：旧数据缺字段时只在这里补默认值，不回写文件
                    "id": obj.get("id") if isinstance(obj.get("id"), str) and obj.get("id") else entry_id(ts, content),
                    "kind": obj.get("kind") if isinstance(obj.get("kind"), str) and obj.get("kind") else DEFAULT_KIND,
                    "tags": _norm_tags(obj.get("tags")),
                    "source": obj.get("source") if isinstance(obj.get("source"), str) else DEFAULT_SOURCE,
                })
    except Exception:
        return entries
    return entries


def list_all() -> list:
    """返回全部记忆条目（跳过坏行与空内容行），按文件写入顺序。"""
    return _load_raw()


def load_recent(n: int = 10) -> list:
    """返回最近 n 条记忆（按内容归一化去重，同一内容保留最新一条），按时间从旧到新排序。

    排序为稳定排序，只比较 ts：同一秒内的多条保持文件写入顺序，结果可复现。
    """
    try:
        count = int(n)
    except Exception:
        return []
    if count <= 0:
        return []
    ordered = _load_raw()
    ordered.sort(key=lambda item: item.get("ts", ""))
    window = ordered[-count:]
    seen = set()
    picked = []
    for item in reversed(window):
        key = normalize(item.get("content", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        picked.append(item)
    picked.reverse()
    return picked


def append(content, kind=DEFAULT_KIND, tags=None, source=DEFAULT_SOURCE) -> dict:
    """追加一条记忆；内容为空或写入失败时返回 None。

    写入前按归一化内容与库存比对：命中已有内容则跳过不写，返回 {"duplicate": True}；
    实际新增时返回写入的条目，条目带 id / kind / tags / source 四个结构化字段。
    """
    if not isinstance(content, str):
        return None
    text = content.strip()[:MAX_CONTENT_LEN].strip()
    if not text:
        return None
    key = normalize(text)
    if key:
        for item in _load_raw():
            if normalize(item.get("content", "")) == key:
                return {"duplicate": True}
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    entry = {
        "ts": stamp,
        "content": text,
        "id": entry_id(stamp, text),
        "kind": kind if isinstance(kind, str) and kind.strip() else DEFAULT_KIND,
        "tags": _norm_tags(tags),
        "source": source if isinstance(source, str) else DEFAULT_SOURCE,
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
                    "id": item.get("id", "") if isinstance(item, dict) else "",
                    "kind": item.get("kind", DEFAULT_KIND) if isinstance(item, dict) else DEFAULT_KIND,
                    "tags": _norm_tags(item.get("tags")) if isinstance(item, dict) else [],
                    "source": item.get("source", "") if isinstance(item, dict) else "",
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def delete(index_or_id) -> bool:
    """删除一条记忆：传整数按索引（基于 list_all 的顺序），传字符串按 id；失败返回 False。"""
    entries = _load_raw()
    if isinstance(index_or_id, str) and index_or_id.strip() and not index_or_id.strip().isdigit():
        wanted = index_or_id.strip()
        kept = [it for it in entries if it.get("id") != wanted]
        if len(kept) == len(entries):
            return False
        return _write_all(kept)
    try:
        idx = int(index_or_id)
    except Exception:
        return False
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


def dedupe() -> dict:
    """按去重键合并重复条目：同一键保留最早 ts，kind/tags/source 取并集，原子重写文件。

    返回 {"ok", "total", "kept", "removed", "message"}。
    - 无重复时不写文件（幂等，也不改动旧格式条目）；
    - 有重复时先写 .tmp 再 os.replace，中途失败不会损坏记忆文件。
    """
    result = {"ok": True, "total": 0, "kept": 0, "removed": 0, "message": ""}
    try:
        entries = _load_raw()
    except Exception as e:
        result["ok"] = False
        result["message"] = str(e)
        return result
    result["total"] = len(entries)
    if not entries:
        return result

    # ts 升序，同 ts 保持文件顺序 → "最早的那条" 有确定含义
    order = sorted(range(len(entries)), key=lambda i: (entries[i].get("ts", ""), i))
    groups = {}
    for i in order:
        item = entries[i]
        key = normalize(item.get("content", ""))
        if not key:
            continue
        if key not in groups:
            groups[key] = {
                "first": item,
                "kind": item.get("kind") or DEFAULT_KIND,
                "tags": list(item.get("tags") or []),
                "source": item.get("source") or "",
            }
            continue
        g = groups[key]
        for tag in (item.get("tags") or []):
            if tag not in g["tags"]:
                g["tags"].append(tag)
        if g["kind"] == DEFAULT_KIND and item.get("kind"):
            g["kind"] = item["kind"]
        if not g["source"] and item.get("source"):
            g["source"] = item["source"]

    merged = []
    for g in groups.values():
        first = g["first"]
        merged.append({
            "ts": first.get("ts", ""),
            "content": first.get("content", ""),
            "id": first.get("id", ""),
            "kind": g["kind"],
            "tags": g["tags"][:MAX_TAGS],
            "source": g["source"],
        })
    merged.sort(key=lambda it: it.get("ts", ""))

    result["kept"] = len(merged)
    result["removed"] = max(0, len(entries) - len(merged))
    if result["removed"] == 0:
        result["message"] = "no duplicates"
        return result

    tmp_path = memory_file() + ".tmp"
    try:
        ensure_dir()
        with open(tmp_path, "w", encoding="utf-8") as f:
            for it in merged:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
        os.replace(tmp_path, memory_file())
        result["message"] = "deduped"
    except Exception as e:
        result["ok"] = False
        result["message"] = str(e)
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
    return result


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
    """从回复文本提取记忆标记并剥离标记。

    支持的标记：中文 [记忆]...[/记忆]（默认）与英文 <mem>...</mem>，两种等价、可混用。
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
        # 组合正则有两个分组，命中的那个才是内容
        raw = next((g for g in match.groups() if g is not None), "")
        item = (raw or "").strip()[:MAX_CONTENT_LEN].strip()
        if not item or item in found:
            continue
        found.append(item)
    clean = _MARKER_RE.sub("", text)
    clean = "\n".join(line.rstrip() for line in clean.split("\n"))
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    return (clean, found)
