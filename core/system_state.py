from __future__ import annotations

import threading
import time

_system_state = {}
_lock = threading.Lock()


def _upsert_with_ts(module: str, key: str, value: float, new_ts: float):
    with _lock:
        ns = _system_state.get(module, {})
        existing = ns.get(key)
        if isinstance(existing, dict) and existing.get("ts", 0) > new_ts:
            return
        ns[key] = {"value": value, "ts": new_ts}
        _system_state[module] = ns


def _unpack_val(data, default=0):
    if isinstance(data, dict) and "value" in data:
        return data["value"]
    return data if data is not None else default


def _unpack_ts(data):
    if isinstance(data, dict) and "ts" in data:
        return data["ts"]
    return 0


class SystemState:

    def __getitem__(self, key: str):
        with _lock:
            if key not in _system_state:
                _system_state[key] = {}
            return _system_state[key]

    def __setitem__(self, key: str, value):
        with _lock:
            _system_state[key] = value

    def get(self, key: str, default=None):
        with _lock:
            return _system_state.get(key, default)

    def update(self, key: str, sub_key: str, value):
        with _lock:
            ns = _system_state.get(key, {})
            ns[sub_key] = value
            _system_state[key] = ns

    def delete(self, key: str, sub_key: str):
        with _lock:
            ns = _system_state.get(key, {})
            ns.pop(sub_key, None)
            _system_state[key] = ns

    def snapshot(self):
        with _lock:
            return dict(_system_state)


system_state = SystemState()
