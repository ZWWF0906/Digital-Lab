"""DL-SEC-06-03 / BB-C1-01：Windows 用户范围凭据保护。

Electron safeStorage 的密文只能在 Electron 主进程解开，而 SSH/AI 凭据的实际使用者在
Python 后端。因此这里使用同一 Windows 用户范围的 DPAPI（CryptProtectData /
CryptUnprotectData），由后端负责保护/解保护；不使用明文回退。

存储格式：``dpapi:v1:<base64>``。DPAPI 不可用（非 Windows 或 API 失败）时：
- 新保存凭据失败，调用方必须拒绝写入；
- 既有明文仍可读取，但迁移会报告失败，绝不静默写回明文。
"""
from __future__ import annotations

import base64
import copy
import ctypes
import json
import os
import sys
import tempfile
import threading

PREFIX = "dpapi:v1:"
SENSITIVE_KEYS = ("ai", "auth_token", "nas_devices")
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt32():
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.crypt32
    except Exception:
        return None


def available() -> bool:
    return _crypt32() is not None


def is_protected(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def protect(value):
    """返回带前缀的 DPAPI 密文；失败返回 None。"""
    if not isinstance(value, str) or not value:
        return None
    crypt = _crypt32()
    if crypt is None:
        return None
    raw = value.encode("utf-8")
    buf = ctypes.create_string_buffer(raw)
    blob_in = _DataBlob(len(raw), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    blob_out = _DataBlob()
    try:
        ok = crypt.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None,
            CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
        )
        if not ok:
            return None
        data = ctypes.string_at(blob_out.pbData, blob_out.cbData)
        return PREFIX + base64.b64encode(data).decode("ascii")
    except Exception:
        return None
    finally:
        try:
            if blob_out.pbData:
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        except Exception:
            pass


def unprotect(value):
    """解保护；非密文/失败返回 None。绝不把密文当明文返回。"""
    if not is_protected(value):
        return None
    crypt = _crypt32()
    if crypt is None:
        return None
    try:
        data = base64.b64decode(value[len(PREFIX):], validate=True)
    except Exception:
        return None
    buf = ctypes.create_string_buffer(data)
    blob_in = _DataBlob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    blob_out = _DataBlob()
    try:
        ok = crypt.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None,
            CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(blob_out)
        )
        if not ok:
            return None
        return ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
    except Exception:
        return None
    finally:
        try:
            if blob_out.pbData:
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
        except Exception:
            pass


def get_secret(value):
    """允许读取历史明文；密文解密失败返回空串。"""
    if not isinstance(value, str):
        return ""
    if is_protected(value):
        return unprotect(value) or ""
    return value


def secret_status(value):
    """只返回配置状态/掩码，不返回密文或明文尾部。"""
    return {"configured": bool(value), "mask": "••••" if value else ""}


def _iter_secret_fields(user):
    ai = user.get("ai") if isinstance(user.get("ai"), dict) else None
    if ai:
        openai = ai.get("openai") if isinstance(ai.get("openai"), dict) else None
        if openai and isinstance(openai.get("api_key"), str) and openai.get("api_key"):
            yield openai, "api_key"
    devices = user.get("nas_devices")
    if isinstance(devices, list):
        for dev in devices:
            if isinstance(dev, dict) and isinstance(dev.get("password"), str) and dev.get("password"):
                yield dev, "password"
    if isinstance(user.get("auth_token"), str) and user.get("auth_token"):
        yield user, "auth_token"


def migrate_user_config(path=None) -> dict:
    """把 user_config.json 中的明文凭据迁移为 DPAPI 密文。

    返回 {"ok","migrated","error"}。失败时不写文件；不会产生明文备份。
    """
    result = {"ok": True, "migrated": 0, "error": ""}
    if path is None:
        try:
            from core.config import _get_user_config_path
            path = _get_user_config_path()
        except Exception:
            return {"ok": False, "migrated": 0, "error": "userConfigPathUnavailable"}
    try:
        if not os.path.exists(path):
            return result
        with open(path, "r", encoding="utf-8") as f:
            user = json.load(f)
        if not isinstance(user, dict):
            return result
        for holder, key in list(_iter_secret_fields(user)):
            value = holder.get(key)
            if is_protected(value):
                if unprotect(value) is None:
                    return {"ok": False, "migrated": 0, "error": "secretUnreadable"}
                continue
            token = protect(value)
            if not token:
                return {"ok": False, "migrated": 0, "error": "secretStorageUnavailable"}
            holder[key] = token
            result["migrated"] += 1
        if result["migrated"]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            fd, tmp = tempfile.mkstemp(prefix=".user_config.", suffix=".tmp", dir=os.path.dirname(path))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(user, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except Exception:
                try:
                    os.remove(tmp)
                except Exception:
                    pass
                return {"ok": False, "migrated": 0, "error": "writeFailed"}
        return result
    except Exception:
        return {"ok": False, "migrated": 0, "error": "migrationFailed"}


# DL-SEC-06-06 / BB-C1-01-R1：旧版 config.json 与 user_config.json 的统一迁移入口。
# 设计原则：
# - user_config.json 是敏感字段的唯一权威来源；config.json 只保留非敏感配置。
# - “key 是否存在”决定优先级，而不是“文件是否存在”：user 有该 key（包括空数组）时，
#   旧值不再参与；user 缺少该 key 时才从 legacy 迁移。
# - 加密全部在内存完成后再原子写 user；验证成功后才清理 legacy 的敏感字段。
# - 任一步失败 -> credentials_blocked，运行时不得使用旧明文。
_MIGRATION_LOCK = threading.RLock()
_MIGRATION_RESULT = None


def _config_paths():
    try:
        from core.config import BASE_DATA_DIR, _get_user_config_path, _safe_path
        return _safe_path(BASE_DATA_DIR, "config.json"), _get_user_config_path()
    except Exception:
        base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "DigitalLab")
        return os.path.join(base, "config.json"), os.path.join(base, "user_config.json")


def _read_json_dict(path):
    """返回 (exists, data, error)。只接受 JSON object；缺失不是错误。"""
    if not os.path.exists(path):
        return False, {}, ""
    last = "readFailed"
    for enc in ("utf-8", "utf-8-sig", "gbk", "cp936"):
        try:
            with open(path, "r", encoding=enc) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return True, {}, "notObject"
            return True, data, ""
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            last = type(e).__name__
        except Exception as e:
            last = type(e).__name__
    return True, {}, last


def _atomic_write_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dl_cfg.", suffix=".tmp", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise


def _protect_text(value):
    """返回 (new_value, changed, error)。空值不加密。"""
    if value is None or value == "":
        return value, False, ""
    if not isinstance(value, str):
        return value, False, "notString"
    if is_protected(value):
        if unprotect(value) is None:
            return value, False, "secretUnreadable"
        return value, False, ""
    token = protect(value)
    if not token:
        return value, False, "secretStorageUnavailable"
    return token, True, ""


def _prepare_ai(ai):
    if not isinstance(ai, dict):
        return ai, False, "aiNotObject"
    prepared = copy.deepcopy(ai)
    changed = False
    openai = prepared.get("openai")
    if isinstance(openai, dict) and "api_key" in openai:
        value, did, err = _protect_text(openai.get("api_key"))
        if err:
            return prepared, changed, "ai:" + err
        openai["api_key"] = value
        changed = changed or did
    return prepared, changed, ""


def _prepare_devices(devices):
    if not isinstance(devices, list):
        return devices, False, "nasNotList"
    prepared = []
    changed = False
    for item in devices:
        if not isinstance(item, dict):
            return devices, changed, "nasItemNotObject"
        entry = copy.deepcopy(item)
        if "password" in entry:
            value, did, err = _protect_text(entry.get("password"))
            if err:
                return devices, changed, "nas:" + err
            entry["password"] = value
            changed = changed or did
        prepared.append(entry)
    return prepared, changed, ""


def _prepare_sensitive(user, legacy):
    """把 user 中的权威敏感字段加密；user 缺失的关键字段才从 legacy 复制。"""
    errors = []
    migrated = 0
    changed = False
    for key in SENSITIVE_KEYS:
        if key in user:
            source = user[key]
        elif key in legacy:
            source = copy.deepcopy(legacy[key])
            user[key] = source
            migrated += 1
            changed = True
        else:
            continue
        if key == "ai":
            prepared, did, err = _prepare_ai(source)
        elif key == "auth_token":
            prepared, did, err = _protect_text(source)
        else:
            prepared, did, err = _prepare_devices(source)
        if err:
            errors.append(key + ":" + err)
            continue
        user[key] = prepared
        changed = changed or did
    return errors, migrated, changed


def _assert_user_protected(user):
    """验证 user_config 中所有存在的凭据都是可解密的 DPAPI 密文。"""
    ai = user.get("ai")
    if isinstance(ai, dict):
        openai = ai.get("openai")
        if isinstance(openai, dict) and openai.get("api_key"):
            if not is_protected(openai.get("api_key")) or unprotect(openai.get("api_key")) is None:
                return "ai:notProtected"
    token = user.get("auth_token")
    if token:
        if not is_protected(token) or unprotect(token) is None:
            return "auth_token:notProtected"
    devices = user.get("nas_devices")
    if isinstance(devices, list):
        for item in devices:
            if isinstance(item, dict) and item.get("password"):
                if not is_protected(item.get("password")) or unprotect(item.get("password")) is None:
                    return "nas:notProtected"
    return ""


def _migrate_credentials():
    legacy_path, user_path = _config_paths()
    legacy_exists, legacy, legacy_err = _read_json_dict(legacy_path)
    user_exists, user, user_err = _read_json_dict(user_path)
    if legacy_err:
        return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                "blocked": True, "error": "legacy:" + legacy_err}
    if user_err:
        return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                "blocked": True, "error": "user:" + user_err}

    errors, migrated, changed = _prepare_sensitive(user, legacy)
    if errors:
        return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                "blocked": True, "error": errors[0]}
    # 写入前先在内存验证，避免把不可解密的“半成品”覆盖到用户配置。
    pre_err = _assert_user_protected(user)
    if pre_err:
        return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                "blocked": True, "error": pre_err}

    # 先写用户配置并重新读取验证；失败时保持 legacy 原样，运行时阻断。
    if user_exists or changed or migrated:
        try:
            _atomic_write_json(user_path, user)
        except Exception:
            return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                    "blocked": True, "error": "userWriteFailed"}
        ok_after, verified, verify_err = _read_json_dict(user_path)
        if not ok_after or verify_err:
            return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                    "blocked": True, "error": "userVerifyFailed"}
        v_err = _assert_user_protected(verified)
        if v_err:
            return {"ok": False, "migrated": 0, "legacy_cleaned": False,
                    "blocked": True, "error": v_err}

    # 用户配置已经安全落盘，才清理 legacy 的敏感字段。
    legacy_cleaned = True
    if any(k in legacy for k in SENSITIVE_KEYS):
        clean = {k: v for k, v in legacy.items() if k not in SENSITIVE_KEYS}
        try:
            _atomic_write_json(legacy_path, clean)
        except Exception:
            legacy_cleaned = False
        if legacy_cleaned:
            ok_after, reread, reread_err = _read_json_dict(legacy_path)
            if not ok_after or reread_err or any(k in reread for k in SENSITIVE_KEYS):
                legacy_cleaned = False
    if not legacy_cleaned:
        return {"ok": False, "migrated": migrated, "legacy_cleaned": False,
                "blocked": True, "error": "legacyCleanupFailed"}
    return {"ok": True, "migrated": migrated, "legacy_cleaned": True,
            "blocked": False, "error": ""}


def ensure_credentials_ready(force=False) -> dict:
    """在所有运行时凭据读取之前调用。成功后返回缓存结果。"""
    global _MIGRATION_RESULT
    with _MIGRATION_LOCK:
        if _MIGRATION_RESULT is not None and not force:
            return dict(_MIGRATION_RESULT)
        try:
            result = _migrate_credentials()
        except Exception:
            result = {"ok": False, "migrated": 0, "legacy_cleaned": False,
                      "blocked": True, "error": "migrationException"}
        _MIGRATION_RESULT = result
        return dict(result)


def credentials_blocked() -> bool:
    res = ensure_credentials_ready()
    return not bool(res.get("ok"))


def get_runtime_secret(value):
    """运行时严格读取：只接受 DPAPI 密文；明文视为错误，绝不当密码使用。"""
    if value is None or value == "":
        return True, ""
    if not isinstance(value, str) or not is_protected(value):
        return False, ""
    plain = unprotect(value)
    if plain is None:
        return False, ""
    return True, plain
