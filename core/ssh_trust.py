"""SSH 主机身份信任库（DL-SEC-02 / P0，S1）。

设计要点：
- 信任身份 = 规范化的 host:port（不使用设备展示名；host/port 变更即视为新身份）。
- 保存的是服务端主机公钥、算法、SHA256 指纹与信任时间；绝不保存用户凭据或私钥。
- 统一入口 connect_ssh()：先完成 SSH 握手与主机密钥校验（paramiko 在认证之前调用
  MissingHostKeyPolicy），未信任/指纹变化时抛异常，认证凭据不会发出。
- 未知主机只做握手（probe_host_key），用于展示指纹；用户从 NAS 控制台独立核对后
  调用 confirm_trust()，且传入指纹必须与当前握手指纹一致才写入信任库。
- 指纹变化立即拒绝；只有用户重新核验（re_trust）后才替换，旧记录归档供审计。
- 信任库为普通 JSON（不含秘密），原子写入（tmp + os.replace）。

信任文件：%APPDATA%\\DigitalLab\\ssh\\ssh_trust.json
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import threading

TRUST_FILE_NAME = "ssh_trust.json"
TRUST_VERSION = 1
_LOCK = threading.Lock()


class TrustError(Exception):
    """信任校验失败基类（携带结构化信息供上层转成错误码）。"""

    code = "ssh.err.trustFailed"

    def __init__(self, host, port, **params):
        super().__init__(self.code)
        self.host = host
        self.port = port
        self.params = params


class UntrustedHost(TrustError):
    code = "ssh.err.untrustedHost"


class HostKeyChanged(TrustError):
    code = "ssh.err.hostKeyChanged"


class FingerprintMismatch(TrustError):
    code = "ssh.err.fingerprintMismatch"


class TrustErrorUnavailable(TrustError):
    code = "ssh.err.trustStoreUnavailable"


def _base_dir() -> str:
    env = os.environ.get("DIGITAL_LAB_SSH_TRUST_DIR")
    if isinstance(env, str) and env.strip():
        try:
            return os.path.abspath(os.path.expanduser(env.strip()))
        except Exception:
            return env.strip()
    try:
        from core.config import BASE_DATA_DIR
        if BASE_DATA_DIR:
            return os.path.join(BASE_DATA_DIR, "ssh")
    except Exception:
        pass
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(appdata, "DigitalLab", "ssh")


def trust_file() -> str:
    return os.path.join(_base_dir(), TRUST_FILE_NAME)


def canonical_host(host, port) -> str:
    """规范化的信任身份：host:port（IPv6 用 [addr]:port，端口缺省 22）。"""
    name = str(host or "").strip()
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    name = name.lower()
    try:
        port_num = int(port)
    except Exception:
        port_num = 22
    if ":" in name:
        return "[{0}]:{1}".format(name, port_num)
    return "{0}:{1}".format(name, port_num)


def normalize_fingerprint(value) -> str:
    """把指纹规范为 SHA256:<无填充 base64> 形式，便于比较。"""
    text = str(value or "").strip()
    if text.upper().startswith("SHA256:"):
        text = text[7:]
    text = text.strip().rstrip("=")
    return "SHA256:" + text


def _fingerprint(key) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def _empty_store() -> dict:
    return {"version": TRUST_VERSION, "hosts": {}, "archived": []}


def load_trust() -> dict:
    try:
        with open(trust_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("hosts"), dict):
            data.setdefault("version", TRUST_VERSION)
            data.setdefault("archived", [])
            return data
    except Exception:
        pass
    return _empty_store()


def _save_trust(data: dict) -> bool:
    """原子写入信任库；失败返回 False（不影响调用方继续以内存态工作）。"""
    try:
        os.makedirs(os.path.dirname(trust_file()), exist_ok=True)
        tmp = trust_file() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, trust_file())
        return True
    except Exception:
        return False


def get_record(host, port):
    """读取某 host:port 的信任记录；不存在返回 None。"""
    with _LOCK:
        data = load_trust()
    return data["hosts"].get(canonical_host(host, port))


def list_trust() -> list:
    with _LOCK:
        data = load_trust()
    items = []
    for key, rec in data["hosts"].items():
        if isinstance(rec, dict):
            item = dict(rec)
            item["identity"] = key
            items.append(item)
    return sorted(items, key=lambda it: it.get("identity", ""))


def _record_from_key(host, port, key) -> dict:
    return {
        "host": str(host),
        "port": int(port) if str(port).isdigit() else 22,
        "key_type": key.get_name(),
        "fingerprint": _fingerprint(key),
        "public_key_b64": key.get_base64(),
        "added_at": _now(),
        "last_seen": _now(),
    }


def add_trust(host, port, key) -> dict:
    """写入信任记录（覆盖同身份旧记录），返回记录。"""
    record = _record_from_key(host, port, key)
    with _LOCK:
        data = load_trust()
        data["hosts"][canonical_host(host, port)] = record
        _save_trust(data)
    return record


def archive_trust(host, port) -> bool:
    """把当前信任记录移入 archived（供审计），返回是否移出成功。"""
    identity = canonical_host(host, port)
    with _LOCK:
        data = load_trust()
        record = data["hosts"].pop(identity, None)
        if record is None:
            return False
        record["archived_at"] = _now()
        record["identity"] = identity
        data["archived"] = (data.get("archived") or [])[-49:] + [record]
        _save_trust(data)
    return True


def verify_local_key(host, port, key) -> bool:
    """本地校验：host:port 已信任且指纹与 key 一致。"""
    record = get_record(host, port)
    if not record:
        return False
    return normalize_fingerprint(record.get("fingerprint")) == normalize_fingerprint(_fingerprint(key))


class TrustPolicy:
    """paramiko MissingHostKeyPolicy：在认证之前校验主机身份。"""

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def missing_host_key(self, client, hostname, key):
        record = get_record(self.host, self.port)
        current = _fingerprint(key)
        if record is None:
            raise UntrustedHost(self.host, self.port,
                                key_type=key.get_name(), fingerprint=current)
        stored = normalize_fingerprint(record.get("fingerprint"))
        if stored != normalize_fingerprint(current):
            raise HostKeyChanged(self.host, self.port,
                                 old_fingerprint=stored, new_fingerprint=current)
        if record.get("key_type") and record["key_type"] != key.get_name():
            raise HostKeyChanged(self.host, self.port,
                                 old_fingerprint=stored, new_fingerprint=current)
        return


def probe_host_key(host, port, timeout=10) -> dict:
    """只做 SSH 握手（不做任何认证），返回主机公钥信息。"""
    import paramiko
    t = paramiko.Transport((str(host), int(port)))
    try:
        t.start_client(timeout=timeout)
        key = t.get_remote_server_key()
        return {
            "host": str(host),
            "port": int(port),
            "identity": canonical_host(host, port),
            "key_type": key.get_name(),
            "fingerprint": _fingerprint(key),
            "public_key_b64": key.get_base64(),
            "_key": key,
        }
    finally:
        try:
            t.close()
        except Exception:
            pass


def confirm_trust(host, port, expected_fingerprint) -> dict:
    """用户确认首次信任：重新握手取指纹，必须与用户核对值一致才写入。"""
    info = probe_host_key(host, port)
    if normalize_fingerprint(info["fingerprint"]) != normalize_fingerprint(expected_fingerprint):
        raise FingerprintMismatch(host, port,
                                  observed=info["fingerprint"],
                                  expected=normalize_fingerprint(expected_fingerprint))
    return add_trust(host, port, info["_key"])


def re_trust(host, port, expected_fingerprint) -> dict:
    """用户重新核验：归档旧记录后写入新记录（指纹变化时的显式操作）。"""
    info = probe_host_key(host, port)
    if normalize_fingerprint(info["fingerprint"]) != normalize_fingerprint(expected_fingerprint):
        raise FingerprintMismatch(host, port,
                                  observed=info["fingerprint"],
                                  expected=normalize_fingerprint(expected_fingerprint))
    archive_trust(host, port)
    return add_trust(host, port, info["_key"])


def remove_trust(host, port) -> bool:
    with _LOCK:
        data = load_trust()
        removed = data["hosts"].pop(canonical_host(host, port), None)
        if removed is None:
            return False
        _save_trust(data)
    return True


def connect_ssh(host, port, username, password, *, timeout=10,
                banner_timeout=10, auth_timeout=10):
    """统一 SSH 建链入口：先校验主机身份，再认证。

    未信任抛 UntrustedHost、指纹变化抛 HostKeyChanged；这两种情况下 paramiko 尚未
    进入认证阶段，因此用户名/密码不会发送给未信任的主机。
    """
    import paramiko
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(TrustPolicy(host, port))
    client.connect(
        hostname=str(host),
        port=int(port) if str(port).isdigit() else 22,
        username=username,
        password=password,
        timeout=timeout,
        banner_timeout=banner_timeout,
        auth_timeout=auth_timeout,
        allow_agent=False,
        look_for_keys=False,
    )
    return client
