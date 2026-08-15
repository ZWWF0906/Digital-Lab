from __future__ import annotations

import threading
import time


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers = []

    def subscribe(self, callback):
        with self._lock:
            self._subscribers.append(callback)

    def emit(self, module, key, value):
        with self._lock:
            subs = list(self._subscribers)
        ts = time.time()
        event = {"module": module, "key": key, "value": value, "ts": ts}
        for cb in subs:
            try:
                cb(event)
            except Exception:
                pass

    def emit_batch(self, module, updates):
        ts = time.time()
        with self._lock:
            subs = list(self._subscribers)
        for key, value in updates.items():
            event = {"module": module, "key": key, "value": value, "ts": ts}
            for cb in subs:
                try:
                    cb(event)
                except Exception:
                    pass


_bus = EventBus()


def subscribe(callback):
    _bus.subscribe(callback)


def emit_state_update(module, key, value):
    _bus.emit(module, key, value)


def emit_batch(module, updates):
    _bus.emit_batch(module, updates)
