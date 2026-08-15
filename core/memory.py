from __future__ import annotations

import json
import os
import datetime
import threading

from core.system_state import _unpack_val

_lock = threading.Lock()
_last_aggregate_date = None


def _memory_dir():
    from core.config import get_config
    cfg = get_config()
    d = os.path.join(cfg.lab_root, "memory")
    os.makedirs(d, exist_ok=True)
    return d


def _daily_path():
    return os.path.join(_memory_dir(), "daily.jsonl")


def _load_daily() -> list:
    path = _daily_path()
    entries = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return entries


def daily_aggregate() -> dict:
    global _last_aggregate_date
    today = datetime.date.today().isoformat()

    with _lock:
        if _last_aggregate_date == today:
            return {"ok": True, "date": today, "note": "already aggregated"}

        from core.system_state import system_state
        m = system_state.get("monitor", {})

        cpu = _unpack_val(m.get("cpu")) or 0
        memory = _unpack_val(m.get("memory")) or 0
        procs = m.get("processes", []) or []
        top_names = [p.get("name", "") for p in procs[:5]]

        logs = system_state.get("logs", {})
        event_count = logs.get("event_count", 0)

        snap_state = system_state.get("snapshot", {})
        snap_list = snap_state.get("list", [])
        snap_count = len(snap_list)

        active_hours = _guess_active_hours(procs)

        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "date": today,
            "active_hours": active_hours,
            "cpu_avg": round(cpu, 1),
            "memory_avg": round(memory, 1),
            "top_processes": top_names,
            "snapshot_count": snap_count,
            "event_count": event_count,
            "note": "",
        }

        path = _daily_path()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        _last_aggregate_date = today

        from core.logger import log_info
        log_info("daily_aggregate", date=today, cpu=cpu, memory=memory)

        return entry


def _guess_active_hours(procs: list) -> float:
    if not procs:
        return 0
    total = sum(p.get("cpu", 0) or 0 for p in procs)
    return round(min(24, max(1, total / 5)), 1)


def load_timeline(days: int = 7) -> dict:
    entries = _load_daily()
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    filtered = [e for e in entries if e.get("date", "") >= cutoff]
    filtered.sort(key=lambda e: e.get("date", ""))

    days_arr = []
    actives = []
    cpus = []
    mems = []
    events = []

    for e in filtered:
        days_arr.append(e.get("date", ""))
        actives.append(e.get("active_hours", 0))
        cpus.append(e.get("cpu_avg", 0))
        mems.append(e.get("memory_avg", 0))
        events.append(e.get("event_count", 0))

    stats = {}
    if filtered:
        stats = {
            "total_days": len(filtered),
            "avg_active_hours": round(sum(actives) / len(actives), 1),
            "avg_cpu": round(sum(cpus) / len(cpus), 1),
            "avg_memory": round(sum(mems) / len(mems), 1),
            "total_events": sum(events),
        }

    return {
        "timeline": filtered,
        "labels": days_arr,
        "active_hours": actives,
        "cpu_series": cpus,
        "memory_series": mems,
        "stats": stats,
    }


def generate_year_review() -> dict:
    entries = _load_daily()
    year_start = datetime.date(datetime.date.today().year, 1, 1).isoformat()
    year_entries = [e for e in entries if e.get("date", "") >= year_start]

    if not year_entries:
        return {"error": "no data this year"}

    actives = [e.get("active_hours", 0) for e in year_entries]
    cpus = [e.get("cpu_avg", 0) for e in year_entries]
    mems = [e.get("memory_avg", 0) for e in year_entries]

    active_days = len(year_entries)
    avg_active = round(sum(actives) / len(actives), 1) if actives else 0
    avg_cpu = round(sum(cpus) / len(cpus), 1) if cpus else 0
    avg_mem = round(sum(mems) / len(mems), 1) if mems else 0

    top_apps_count = {}
    for e in year_entries:
        for app in e.get("top_processes", []) or []:
            name = app.split(".")[0][:20]
            top_apps_count[name] = top_apps_count.get(name, 0) + 1
    top_apps = sorted(top_apps_count.items(), key=lambda x: -x[1])[:8]

    total_events = sum(e.get("event_count", 0) or 0 for e in year_entries)
    total_snapshots = sum(e.get("snapshot_count", 0) or 0 for e in year_entries)

    return {
        "year": datetime.date.today().year,
        "active_days": active_days,
        "avg_active_hours": avg_active,
        "avg_cpu": avg_cpu,
        "avg_memory": avg_mem,
        "top_apps": [{"name": n, "count": c} for n, c in top_apps],
        "total_events": total_events,
        "total_snapshots": total_snapshots,
        "peak_cpu": max(cpus) if cpus else 0,
        "peak_memory": max(mems) if mems else 0,
        "timeline": year_entries,
    }
