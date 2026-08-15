from __future__ import annotations

import threading

_stop = threading.Event()
_thread_fast = None
_thread_slow = None
_lock = threading.Lock()


def start_collector(interval: float = 3.0):
    global _thread_fast, _thread_slow
    with _lock:
        if _thread_fast is not None and _thread_fast.is_alive():
            return
        _stop.clear()
        _thread_fast = threading.Thread(target=_run_fast, daemon=True)
        _thread_fast.start()
        _thread_slow = threading.Thread(target=_run_slow, daemon=True)
        _thread_slow.start()


def stop_collector():
    _stop.set()
    global _thread_fast, _thread_slow
    for t in (_thread_fast, _thread_slow):
        if t is not None:
            t.join(timeout=5)
    _thread_fast = None
    _thread_slow = None


def is_running():
    return (_thread_fast is not None and _thread_fast.is_alive())


def _run_fast():
    from core.monitor import collect_and_store, check_alerts, init_db
    from core.config import get_config
    from core.logger import log_error

    init_db()
    cfg = get_config()

    try:
        collect_and_store()
    except Exception as e:
        log_error("collector fast init", error=str(e))

    while not _stop.wait(1.0):
        try:
            cpu, mem, disk = collect_and_store()
            if cpu is not None:
                thresholds = cfg.get_thresholds()
                check_alerts(cpu, mem, disk, thresholds, cfg.monitor_alert_cooldown)
        except Exception as e:
            log_error("collector fast tick", error=str(e))


def _run_slow():
    from core.logger import log_error
    from core.config import get_config

    cfg = get_config()

    try:
        from core.hardware import collect_all
        collect_all(use_cache=True)
    except Exception as e:
        log_error("collector slow hardware", error=str(e))

    _tick = 0
    while not _stop.wait(3.0):
        try:
            from core.memory import daily_aggregate
            daily_aggregate()
        except Exception:
            pass

        _tick += 1
        # Refresh volatile hardware every 30s (10 ticks × 3s)
        if _tick % 10 == 0:
            try:
                from core.hardware import refresh_hardware_live
                refresh_hardware_live()
            except Exception as e:
                log_error("collector slow refresh_hardware_live", error=str(e))
