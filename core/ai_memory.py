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

本地检索（v1.6.0 阶段一）：search_memory() 用纯本地关键词 + 结构化元数据做相关性排序，
不引入向量数据库或任何外部依赖；derive_metadata() 为写入条目推导 kind/tags。

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
import threading
import unicodedata

MEMORY_FILE_NAME = "ai_memory.jsonl"
DEFAULT_DIR_NAME = "memory"
MAX_CONTENT_LEN = 500
MAX_PER_REPLY = 3  # 每轮回复最多提取 3 条记忆，超出部分丢弃（标记仍会从正文剥离）
MAX_TAGS = 8
DEFAULT_KIND = "fact"
# 同一后端进程内的读-比较-写回必须串行；写回使用 temp + os.replace，避免中途失败留下半文件。
_MEMORY_LOCK = threading.RLock()


def _memory_locked(fn):
    def wrapper(*args, **kwargs):
        with _MEMORY_LOCK:
            return fn(*args, **kwargs)
    return wrapper
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
    """生效的记忆目录：环境变量 > ai.memory.dir > 默认 %APPDATA%\\DigitalLab\\memory。

    W-02：配置目录若未通过本地路径策略（UNC/设备命名空间/路径穿越/symlink 等），
    回退到应用管理默认目录；不把不可信路径继续用于读写。
    """
    env = os.environ.get("DIGITAL_LAB_AI_MEMORY_DIR")
    raw = env.strip() if isinstance(env, str) and env.strip() else config_dir()
    if raw:
        try:
            from core import path_policy as _pp
            _norm, _err = _pp.validate_local_dir(raw)
            if not _err:
                raw = _norm
            else:
                raw = ""
        except Exception:
            raw = ""
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


# ── 本地检索（v1.6.0 阶段一）：纯本地关键词 + 结构化元数据相关性排序，不引入向量库 ──
_SEARCH_DEFAULT_LIMIT = 5
_SEARCH_MAX_LIMIT = 20
# 相关性下限：只命中一个 CJK 单字（1.0 分）视为噪声不返回；
# 两个单字命中（2.0）或一个词元/结构化字段命中才进入结果集，避免长查询被常见字淹没。
_SEARCH_MIN_SCORE = 2.0
_LATIN_RE = re.compile(r"[a-z0-9]+")
_CJK_RANGES = ((0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF))

# kind 启发式规则：命中即取第一个匹配的类别；未命中为 fact。
_KIND_RULES = (
    ("preference", ("喜欢", "偏好", "习惯", "称呼", "叫我", "希望", "想要", "讨厌", "风格", "主题")),
    ("device", ("设备", "电脑", "笔记本", "主机", "手机", "平板", "nas", "路由器",
                "显示器", "显卡", "内存", "硬盘", "型号", "cpu", "gpu")),
)
# tags 启发式规则：命中关键词就打标签，供检索时的结构化过滤使用。
_TAG_RULES = (
    ("称呼", ("称呼", "叫我", "名字", "昵称")),
    ("主题", ("主题", "深色", "浅色", "夜间", "配色")),
    ("设备", ("电脑", "笔记本", "主机", "显卡", "内存", "硬盘", "显示器", "设备")),
    ("nas", ("nas", "群晖", "威联通", "存储")),
    ("语言", ("语言", "中文", "英文", "日语")),
    ("偏好", ("喜欢", "偏好", "习惯", "讨厌")),
)


def _is_cjk(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _CJK_RANGES)


def _search_tokens(text) -> list:
    """检索分词：拉丁字母/数字整词 + CJK 单字 + CJK 连续片段内的二字组合（去重保序）。

    二字词元只在连续 CJK 片段内生成，避免"深色 主题"这类空格分隔的查询
    拼出"色主"这种跨词边界的假词元。
    """
    if not isinstance(text, str):
        return []
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = _INVISIBLE_RE.sub("", normalized)
    tokens = []
    for token in _LATIN_RE.findall(normalized):
        if token not in tokens:
            tokens.append(token)
    # 按连续 CJK 片段切分，片段内生成单字与二字词元
    runs = []
    current = []
    for ch in normalized:
        if _is_cjk(ch):
            current.append(ch)
        elif current:
            runs.append("".join(current))
            current = []
    if current:
        runs.append("".join(current))
    for run in runs:
        for ch in run:
            if ch not in tokens:
                tokens.append(ch)
        for i in range(len(run) - 1):
            bigram = run[i] + run[i + 1]
            if bigram not in tokens:
                tokens.append(bigram)
    return tokens


def derive_metadata(content) -> dict:
    """从记忆内容保守推导 kind / tags（本地启发式，不覆盖调用方的显式取值）。

    v1.5.0 起条目已有 kind/tags/source 字段，但对话提取路径一直写默认值，字段形同虚设。
    本函数让"关键词命中才打标"，既能给检索提供结构化过滤维度，也不会制造假标签。
    返回 {"kind": str, "tags": [str]}。
    """
    if not isinstance(content, str):
        return {"kind": DEFAULT_KIND, "tags": []}
    text = unicodedata.normalize("NFKC", content).casefold()
    kind = DEFAULT_KIND
    for candidate, keywords in _KIND_RULES:
        if any(keyword in text for keyword in keywords):
            kind = candidate
            break
    tags = []
    for tag, keywords in _TAG_RULES:
        if any(keyword in text for keyword in keywords) and tag not in tags:
            tags.append(tag)
    return {"kind": kind, "tags": tags[:MAX_TAGS]}


def search_memory(query, limit=_SEARCH_DEFAULT_LIMIT, kind=None, tags=None) -> dict:
    """本地长期记忆检索：中文/英文关键词 + 结构化元数据，返回结构化结果。

    相关性排序（完全确定性，同一份文件结果可复现）：
      1) 归一化后的完整子串命中内容 +100；
      2) 检索词元（拉丁整词 / CJK 单字 / CJK 二字）每命中一个 +1，二字词元 +2；
      3) 结构化加分：kind 命中 +8，tag 命中每个 +12，source 命中 +4；
      4) 排序键：score 降序 → ts 降序 → id 升序。

    记忆未开启时返回 enabled=False、空结果，且不读取记忆文件；
    旧版仅 ts/content 的条目由 _load_raw 补齐 id/kind/tags/source 后参与检索，完全兼容。
    返回 {"enabled", "available", "query", "total_matched", "count", "results"}。
    """
    result = {
        "enabled": enabled(),
        "available": False,
        "query": query.strip() if isinstance(query, str) else "",
        "total_matched": 0,
        "count": 0,
        "results": [],
    }
    if not result["query"]:
        return result
    if not result["enabled"]:
        return result
    try:
        result["available"] = os.path.exists(memory_file())
    except Exception:
        result["available"] = False
    try:
        count = int(limit)
    except Exception:
        count = _SEARCH_DEFAULT_LIMIT
    count = max(1, min(count, _SEARCH_MAX_LIMIT))

    query_key = normalize(result["query"])
    tokens = _search_tokens(result["query"])
    kind_filter = normalize(kind) if isinstance(kind, str) and kind.strip() else ""
    tag_filters = []
    if isinstance(tags, (list, tuple)):
        for tag in tags:
            normalized_tag = normalize(tag)
            if normalized_tag and normalized_tag not in tag_filters:
                tag_filters.append(normalized_tag)

    scored = []
    for item in _load_raw():
        content = item.get("content", "")
        content_key = normalize(content)
        if not content_key:
            continue
        if kind_filter and normalize(item.get("kind", "")) != kind_filter:
            continue
        item_tags = [normalize(tag) for tag in (item.get("tags") or [])]
        if tag_filters and not any(flt in item_tags for flt in tag_filters):
            continue
        score = 0.0
        matched = []
        if query_key and query_key in content_key:
            score += 100.0
            matched.append("content")
        for token in tokens:
            if token in content_key:
                score += 2.0 if len(token) > 1 else 1.0
                matched.append(token)
        item_kind = normalize(item.get("kind", ""))
        if item_kind and query_key and (item_kind in query_key or query_key in item_kind):
            score += 8.0
            matched.append("kind")
        for tag in item_tags:
            if tag and query_key and (tag in query_key or query_key in tag):
                score += 12.0
                matched.append("tag")
        item_source = normalize(item.get("source", ""))
        if item_source and query_key and (item_source in query_key or query_key in item_source):
            score += 4.0
            matched.append("source")
        if score <= 0:
            continue
        if score < _SEARCH_MIN_SCORE:
            # 仅一个 CJK 单字命中属于噪声，不进入结果集
            continue
        scored.append({
            "id": item.get("id", ""),
            "ts": item.get("ts", ""),
            "content": content[:MAX_CONTENT_LEN],
            "kind": item.get("kind", DEFAULT_KIND),
            "tags": list(item.get("tags") or []),
            "source": item.get("source", DEFAULT_SOURCE),
            "score": round(score, 3),
            "matched_fields": sorted(set(matched)),
        })

    # 稳定排序三级收敛：id 升序 → ts 降序 → score 降序
    scored.sort(key=lambda it: it["id"])
    scored.sort(key=lambda it: it["ts"], reverse=True)
    scored.sort(key=lambda it: it["score"], reverse=True)
    result["total_matched"] = len(scored)
    result["results"] = scored[:count]
    result["count"] = len(result["results"])
    return result


def append(content, kind=DEFAULT_KIND, tags=None, source=DEFAULT_SOURCE) -> dict:
    """追加一条记忆；内容为空或写入失败时返回 None。

    写入前按归一化内容与库存比对：命中已有内容则跳过不写，返回 {"duplicate": True}；
    实际新增时返回写入的条目，条目带 id / kind / tags / source 四个结构化字段。
    读-比较-追加在同一进程锁内完成。
    """
    if not isinstance(content, str):
        return None
    text = content.strip()[:MAX_CONTENT_LEN].strip()
    if not text:
        return None
    key = normalize(text)
    with _MEMORY_LOCK:
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


def _entry_digest(item) -> str:
    raw = str((item or {}).get("ts", "")) + "\0" + str((item or {}).get("content", ""))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _write_all(entries: list) -> bool:
    """原子重写记忆文件：先写 .tmp，再 os.replace；失败不覆盖原文件。"""
    tmp_path = memory_file() + ".tmp"
    try:
        ensure_dir()
        with _MEMORY_LOCK:
            with open(tmp_path, "w", encoding="utf-8") as f:
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
            os.replace(tmp_path, memory_file())
        return True
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        return False


def delete(index_or_id, expected_sha256=None) -> bool:
    """删除一条记忆：传整数按索引（基于 list_all 的顺序），传字符串按 id；失败返回 False。

    expected_sha256 非空时，目标读取、摘要比较、pop 与原子写回在同一进程锁内完成；
    目标已变化则不做任何写回。索引只用于定位，实际删除仍由锁内重新读取的条目决定。
    """
    with _MEMORY_LOCK:
        entries = _load_raw()
        if isinstance(index_or_id, str) and index_or_id.strip() and not index_or_id.strip().isdigit():
            wanted = index_or_id.strip()
            matches = [it for it in entries if it.get("id") == wanted]
            if not matches:
                return False
            target = matches[0]
            if expected_sha256 is not None and _entry_digest(target) != str(expected_sha256).lower():
                return False
            kept = [it for it in entries if it.get("id") != wanted]
            return _write_all(kept)
        try:
            idx = int(index_or_id)
        except Exception:
            return False
        if idx < 0 or idx >= len(entries):
            return False
        target = entries[idx]
        if expected_sha256 is not None and _entry_digest(target) != str(expected_sha256).lower():
            return False
        entries.pop(idx)
        return _write_all(entries)


def clear() -> bool:
    """清空记忆文件（保留文件本身），使用同一原子写回；失败返回 False。"""
    with _MEMORY_LOCK:
        return _write_all([])


@_memory_locked
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
    """把旧目录的 ai_memory.jsonl 复制到新目录，不删除旧文件。

    W-02-R1：迁移源和目标都必须通过当前本地路径策略；旧配置不能成为 UNC/
    设备命名空间/路径穿越/symlink 的访问通道。迁移使用同目录临时文件后再
    替换，目标已存在时绝不覆盖。返回稳定 code，不返回原始异常或完整路径。
    """
    result = {"ok": True, "copied": False, "skipped": "", "message": ""}
    try:
        if not isinstance(old_dir, str) or not isinstance(new_dir, str) or not old_dir.strip() or not new_dir.strip():
            result["message"] = "目录参数为空，跳过迁移"
            result["skipped"] = "empty"
            return result

        from core import path_policy as _pp
        old_norm, old_err = _pp.validate_local_dir(old_dir)
        new_norm, new_err = _pp.validate_local_dir(new_dir)
        if old_err:
            # 旧路径不合法时不触碰它；允许用户改到新的受管目录。
            result["skipped"] = "unsafeSource"
            result["message"] = "旧目录未通过路径安全校验，跳过迁移"
            return result
        if new_err:
            result["ok"] = False
            result["skipped"] = "unsafeTarget"
            result["message"] = "目标目录未通过路径安全校验"
            return result
        if os.path.normcase(old_norm) == os.path.normcase(new_norm):
            result["skipped"] = "sameDir"
            result["message"] = "新旧目录相同，跳过迁移"
            return result

        src_file = os.path.join(old_norm, MEMORY_FILE_NAME)
        dst_file = os.path.join(new_norm, MEMORY_FILE_NAME)
        if not os.path.exists(src_file):
            result["skipped"] = "noSource"
            result["message"] = "旧文件不存在，跳过迁移"
            return result
        # 目录已验证；这里额外拒绝文件级 symlink/junction。
        try:
            if os.path.islink(src_file) or os.path.normcase(os.path.realpath(src_file)) != os.path.normcase(os.path.abspath(src_file)):
                result["skipped"] = "unsafeSourceFile"
                result["message"] = "旧记忆文件不是可信普通文件，跳过迁移"
                return result
        except Exception:
            result["skipped"] = "unsafeSourceFile"
            result["message"] = "旧记忆文件校验失败，跳过迁移"
            return result

        os.makedirs(new_norm, exist_ok=True)
        if os.path.exists(dst_file):
            result["skipped"] = "targetExists"
            result["message"] = "目标已有记忆文件，保留目标内容，不覆盖"
            return result

        tmp_file = os.path.join(new_norm, "." + MEMORY_FILE_NAME + ".migrate.tmp")
        try:
            shutil.copyfile(src_file, tmp_file)
            # 再次检查目标；不希望并发/外部变化被覆盖。
            if os.path.exists(dst_file):
                result["skipped"] = "targetExists"
                result["message"] = "目标已有记忆文件，保留目标内容，不覆盖"
                try:
                    os.remove(tmp_file)
                except Exception:
                    pass
                return result
            os.replace(tmp_file, dst_file)
            result["copied"] = True
            result["message"] = "已复制到新目录"
        except Exception:
            result["ok"] = False
            result["message"] = "记忆文件复制失败，原文件保留"
            try:
                if os.path.exists(tmp_file):
                    os.remove(tmp_file)
            except Exception:
                pass
    except Exception:
        result["ok"] = False
        result["message"] = "记忆迁移失败，原文件保留"
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
