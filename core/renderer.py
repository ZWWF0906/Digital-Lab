from __future__ import annotations

from core.system_state import _unpack_val, _unpack_ts


def _unpacked_monitor(state: dict) -> dict:
    raw = state.get("monitor", {})
    out = {}
    for k, v in raw.items():
        if isinstance(v, dict) and "value" in v:
            out[k] = v["value"]
        else:
            out[k] = v
    return out


def _read_monitor(state: dict) -> dict:
    return _unpacked_monitor(state)


def _read_hardware(state: dict) -> dict:
    return state.get("hardware", {})


def _read_snapshot(state: dict) -> dict:
    return state.get("snapshot", {})


def _read_logs(state: dict) -> dict:
    return state.get("logs", {})


def _read_status(state: dict) -> dict:
    return state.get("status", {})


# ══════════════════════════════════════════════════════
#  render_cli — 终端格式化输出
# ══════════════════════════════════════════════════════

def render_cli(state: dict) -> str:
    m = _read_monitor(state)
    if not m or m.get("cpu") is None:
        return "[无数据] system_state[\"monitor\"] 为空。\n启动守护进程: dl monitor --daemon"

    lines = []
    lines.append("")
    lines.append("=" * 56)
    lines.append("  DigitalLab — system_state 实时状态")
    lines.append("-" * 56)
    lines.append("  CPU:     {:.1f}%".format(m.get("cpu", 0)))
    lines.append("  Memory:  {:.1f}%".format(m.get("memory", 0)))
    lines.append("  Disk:    {:.1f}%".format(m.get("disk", 0)))
    lines.append("  Time:    {}".format(m.get("timestamp", "-")))

    alert = m.get("alert", {})
    if alert.get("last_time"):
        keys = list(alert["last_time"].keys())
        lines.append("  Alerts:  {} (keys: {})".format(len(keys), ", ".join(keys)))

    processes = m.get("processes")
    if processes:
        lines.append("")
        lines.append("--- 进程 Top {} ---".format(len(processes)))
        lines.append("  {:<8s} {:>30s}  {:>6s}  {:>6s}".format("PID", "Name", "CPU%", "Mem%"))
        for p in processes[:10]:
            lines.append("  {:<8s} {:>30s}  {:>5.1f}%  {:>5.1f}%".format(
                str(p.get("pid", "")),
                (p.get("name", "") or "")[:30],
                p.get("cpu", 0),
                p.get("memory", 0)))
    lines.append("=" * 56)
    return "\n".join(lines)


def _format_value(value, fallback="not detected"):
    """Unified fallback: never return '-' or empty string for missing data."""
    if value is None:
        return fallback
    s = str(value).strip()
    if not s or s == "-":
        return fallback
    return s


def _uptime_str(seconds):
    """Convert uptime seconds to human-readable string."""
    if not seconds or seconds < 0:
        return None
    d, h = divmod(seconds, 86400)
    h, m = divmod(h, 3600)
    m, s = divmod(m, 60)
    parts = []
    if d > 0:
        parts.append("{}d".format(d))
    if h > 0:
        parts.append("{}h".format(h))
    if m > 0:
        parts.append("{}m".format(m))
    return " ".join(parts) if parts else "{}s".format(s)


def _summarize_hw(key, d):
    """Build a human-readable summary string for each hardware category."""
    if not d:
        return "not detected"

    if key == "cpu":
        return _format_value(d.get("short_model") or d.get("model"),
                             "unknown processor")

    if key == "memory":
        total = d.get("total_gb")
        mem_type = d.get("type")
        freq = d.get("frequency")
        parts = []
        if total:
            parts.append("{} GB".format(total))
        if mem_type and freq:
            parts.append("{}-{}".format(mem_type, freq))
        elif mem_type:
            parts.append(mem_type)
        elif freq:
            parts.append("{} MHz".format(freq))
        if not parts:
            return "unknown (missing source)"
        return " ".join(parts)

    if key == "gpu":
        return _format_value(d.get("short_name") or d.get("name"),
                             "unknown graphics")

    if key == "disk":
        parts = []
        cap = d.get("capacity_gb")
        if cap:
            parts.append("{} GB".format(cap))
        dtype = d.get("type")
        if dtype:
            parts.append(dtype)
        model = d.get("model")
        if model:
            parts.append(model[:30])
        if not parts:
            return "unknown storage"
        return " ".join(parts)

    if key == "system":
        os_name = d.get("os") or ""
        edition = d.get("edition")
        if edition:
            os_name = "{} {}".format(os_name, edition)
        uptime = _uptime_str(d.get("uptime_seconds"))
        if uptime:
            os_name = "{} (up {})".format(os_name, uptime)
        return _format_value(os_name, "unknown OS")

    if key == "display":
        res = d.get("total_resolution")
        if res:
            return res
        n = len(d.get("displays", []))
        if n > 0:
            return "{} display(s)".format(n)
        return "unknown display"

    if key == "network":
        adapters = d.get("adapters", [])
        if not adapters:
            return "unknown network"
        names = [a.get("name", "?") for a in adapters[:2]]
        extra = " +{} more".format(len(adapters) - 2) if len(adapters) > 2 else ""
        return ", ".join(names) + extra

    return "not detected"


def render_cli_hardware(state: dict) -> str:
    hw = _read_hardware(state)
    if not hw or not hw.get("cpu"):
        return "[无数据] 硬件信息未采集。运行: dl hardware refresh"

    lines = ["", "=" * 56, "  DigitalLab — 硬件信息", "-" * 56]
    for key in ("cpu", "memory", "gpu", "disk", "system", "display", "network"):
        d = hw.get(key) or {}
        name = _summarize_hw(key, d)
        lines.append("  {}: {}".format(key.upper(), name[:70]))
    lines.append("=" * 56)
    return "\n".join(lines)


def render_cli_snapshot(state: dict) -> str:
    sn = _read_snapshot(state)
    lst = sn.get("list", [])
    last = sn.get("last", {})
    lines = ["", "=" * 56, "  DigitalLab — 快照状态", "-" * 56]
    lines.append("  快照总数: {}".format(len(lst)))
    if last:
        per = last.get("performance", {})
        lines.append("  最新: {}  |  CPU {:.1f}%  |  Memory {:.1f}%".format(
            last.get("id", "-"),
            per.get("cpu", {}).get("current", 0),
            per.get("memory", {}).get("current", 0)))
    lines.append("=" * 56)
    return "\n".join(lines)


def render_cli_logs(state: dict) -> str:
    logs = _read_logs(state)
    lines = ["", "=" * 56, "  DigitalLab — 日志状态", "-" * 56]
    lines.append("  事件总数: {}".format(logs.get("event_count", 0)))
    last = logs.get("last", {})
    if last:
        lines.append("  最近: [{}] {} @ {}".format(
            last.get("level", "-"), last.get("message", "-"), last.get("timestamp", "-")))
    lines.append("=" * 56)
    return "\n".join(lines)


def render_cli_status(state: dict) -> str:
    st = _read_status(state)
    lines = ["", "=" * 56, "  DigitalLab — 系统状态", "-" * 56]
    lines.append("  Python: {}".format(st.get("python_version", "-")))
    lines.append("  System: {}".format(st.get("platform", "-")))
    dirs = st.get("dirs", [])
    for d in dirs:
        name = d.get("name", "")
        ok = d.get("ok", False)
        tag = "[OK]" if ok else "[MISSING]"
        lines.append("  {:15s} {}".format(name, tag))
    lines.append("=" * 56)
    return "\n".join(lines)


# ══════════════════════════════════════════════════════
#  render_web — API JSON 响应
# ══════════════════════════════════════════════════════

def render_web_current(state: dict) -> dict:
    m = _read_monitor(state)
    return {
        "cpu": round(m.get("cpu", 0), 1),
        "memory": round(m.get("memory", 0), 1),
        "disk": round(m.get("disk", 0), 1),
    }


def render_web_hardware(state: dict) -> dict:
    hw = _read_hardware(state)
    if not hw or not hw.get("cpu"):
        return {"error": "hardware not collected"}
    data = {k: hw.get(k) for k in ("cpu", "memory", "gpu", "disk", "system", "display", "network") if hw.get(k)}
    for k in list(data.keys()):
        if isinstance(data[k], dict):
            data[k].pop("_confidence", None)
    if hw.get("_display"):
        data["_display"] = hw["_display"]
    return data


def render_web_processes(state: dict) -> list:
    m = _read_monitor(state)
    processes = m.get("processes", [])
    result = []
    for p in processes:
        result.append({
            "pid": p.get("pid", 0),
            "name": p.get("name", ""),
            "cpu": round(p.get("cpu", 0), 1),
            "memory": round(p.get("memory", 0), 1),
            "rss": p.get("rss", 0),
        })
    return result


def render_web_alerts(state: dict) -> list:
    m = _read_monitor(state)
    raw = m.get("alerts_history", [])
    result = []
    for a in raw:
        result.append({
            "timestamp": a.get("time", ""),
            "message": a.get("metric", ""),
            "data": {
                "current": a.get("value", 0),
                "threshold": a.get("threshold", 0),
            },
        })
    return result


def render_web_status(state: dict) -> dict:
    st = _read_status(state)
    dirs = st.get("dirs", [])
    dir_strs = []
    for d in dirs:
        tag = "[OK]" if d.get("ok") else "[MISSING]"
        dir_strs.append("  {}  {}".format(d.get("name", ""), tag))
    return {
        "python": st.get("python_version", ""),
        "platform": st.get("platform", ""),
        "dirs": dir_strs,
        "config": st.get("config_summary", ""),
    }


# ══════════════════════════════════════════════════════
#  render_report — HTML 报告数据
# ══════════════════════════════════════════════════════

def render_report_current(state: dict) -> dict:
    m = _read_monitor(state)
    return {
        "cpu": round(m.get("cpu", 0), 1),
        "memory": round(m.get("memory", 0), 1),
        "disk": round(m.get("disk", 0), 1),
        "timestamp": m.get("timestamp", ""),
    }


def render_report_snapshot(state: dict, snap_id: str = "") -> dict:
    sn = _read_snapshot(state)
    snap = sn.get("last", {})
    if snap_id and sn.get("cache", {}).get(snap_id):
        snap = sn["cache"][snap_id]
    if not snap:
        return {"error": "no snapshot", "id": snap_id}
    perf = snap.get("performance", {})
    cpu = perf.get("cpu", {})
    mem = perf.get("memory", {})
    disk = perf.get("disk", {})
    return {
        "id": snap.get("id", ""),
        "timestamp": snap.get("timestamp", ""),
        "note": snap.get("note", ""),
        "system": snap.get("system", {}),
        "performance": {
            "cpu": {"current": cpu.get("current", 0), "avg": cpu.get("avg", 0), "peak": cpu.get("peak", 0)},
            "memory": {"current": mem.get("current", 0), "avg": mem.get("avg", 0), "peak": mem.get("peak", 0)},
            "disk": {"current": disk.get("current", 0), "avg": disk.get("avg", 0), "peak": disk.get("peak", 0)},
        },
        "services": snap.get("services", []),
    }
