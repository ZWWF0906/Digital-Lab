import json
import os
import time
import datetime
import subprocess

from core.config import get_config
from core.logger import log_info

SNAP_DIR = ""
_ANSI = True


def _ensure_dir():
    global SNAP_DIR
    if not SNAP_DIR:
        cfg = get_config()
        SNAP_DIR = os.path.join(cfg.lab_root, "snapshots")
    os.makedirs(SNAP_DIR, exist_ok=True)
    return SNAP_DIR


# ══════════════════════════════════════════════════════
#  Collect
# ══════════════════════════════════════════════════════
def create_snapshot(note: str = "") -> dict:
    """Capture system state and save to snap-XXX.json"""
    ts = datetime.datetime.now()
    sid = "snap-" + ts.strftime("%Y%m%d_%H%M%S")

    import psutil
    from core.config import get_config as _cfg
    cfg = _cfg()

    # ── system info ──
    sys_info = {
        "platform": cfg.platform_info,
        "python": cfg.python_version,
        "boot_time": datetime.datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": _fmt_uptime(int(time.time() - psutil.boot_time())),
        "cpu_model": _cpu_model(),
        "cores": psutil.cpu_count(logical=False),
        "total_memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "total_disk_gb": 0,
    }
    try:
        sys_info["total_disk_gb"] = round(psutil.disk_usage("C:").total / (1024**3), 1)
    except Exception:
        pass

    # ── services ──
    svcs = _collect_services()

    # ── current values ──
    cur_cpu = psutil.cpu_percent(interval=0.2)
    cur_mem = psutil.virtual_memory().percent
    try:
        cur_disk = psutil.disk_usage("C:").percent
    except Exception:
        cur_disk = 0

    # ── performance summary (last 1h) ──
    perf = _perf_summary(3600, cur_cpu, cur_mem, cur_disk)

    # ── config snapshot ──
    cfg_data = {
        "thresholds": {"cpu": getattr(cfg, "cpu_threshold", 80),
                       "memory": getattr(cfg, "memory_threshold", 85),
                       "disk": getattr(cfg, "disk_threshold", 90)},
        "monitor_interval": getattr(cfg, "monitor_interval", 60),
    }

    snap = {
        "id": sid,
        "timestamp": ts.isoformat(),
        "note": note,
        "system": sys_info,
        "config": cfg_data,
        "services": svcs,
        "performance": perf,
    }

    _ensure_dir()
    path = os.path.join(SNAP_DIR, sid + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snap, f, indent=2, ensure_ascii=False)
    log_info("snapshot_created", id=sid, note=note)
    return snap


# ══════════════════════════════════════════════════════
#  List
# ══════════════════════════════════════════════════════
def list_snapshots() -> list:
    """Return all snapshots sorted newest-first"""
    _ensure_dir()
    snaps = []
    for name in sorted(os.listdir(SNAP_DIR), reverse=True):
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(SNAP_DIR, name), encoding="utf-8") as f:
                s = json.load(f)
            snaps.append(s)
        except (json.JSONDecodeError, KeyError):
            continue
    return snaps


# ══════════════════════════════════════════════════════
#  Compare
# ══════════════════════════════════════════════════════
def compare_snapshots(id1: str, id2: str) -> dict:
    """Return structured diff between two snapshots"""
    a = _load(id1)
    b = _load(id2)
    if not a or not b:
        return {"error": "snapshot not found"}

    result = {
        "id1": id1, "id2": id2,
        "ts1": a["timestamp"], "ts2": b["timestamp"],
        "note1": a.get("note", ""), "note2": b.get("note", ""),
    }

    # performance diff
    for key, label in [("cpu", "CPU"), ("memory", "内存"), ("disk", "磁盘")]:
        ap = a["performance"][key]
        bp = b["performance"][key]
        result[label] = {
            "current": (ap["current"], bp["current"], _delta(ap["current"], bp["current"])),
            "avg": (ap["avg"], bp["avg"], _delta(ap["avg"], bp["avg"])),
            "peak": (ap["peak"], bp["peak"], _delta(ap["peak"], bp["peak"])),
        }

    # service diff
    sa = {s["name"]: s["status"] for s in a.get("services", [])}
    sb = {s["name"]: s["status"] for s in b.get("services", [])}
    all_svc = sorted(set(sa) | set(sb))
    svc_diff = []
    for name in all_svc:
        st_a = sa.get(name, "-")
        st_b = sb.get(name, "-")
        if st_a != st_b:
            svc_diff.append({"name": name, "before": st_a, "after": st_b})
    result["service_changes"] = svc_diff
    result["service_count"] = (len(sa), len(sb))

    # config diff
    ca = a.get("config", {})
    cb = b.get("config", {})
    cfg_diff = []
    for k in set(ca) | set(cb):
        va, vb = ca.get(k), cb.get(k)
        if va != vb:
            if isinstance(va, dict):
                for sub in set(va) | set(vb):
                    if va.get(sub) != vb.get(sub):
                        cfg_diff.append("{}.{}: {} → {}".format(k, sub, va.get(sub, "-"), vb.get(sub, "-")))
            else:
                cfg_diff.append("{}: {} → {}".format(k, va, vb))
    result["config_changes"] = cfg_diff

    result["sys_uptime"] = (a["system"]["uptime"], b["system"]["uptime"])
    return result


# ══════════════════════════════════════════════════════
#  Delete
# ══════════════════════════════════════════════════════
def delete_snapshot(snap_id: str) -> bool:
    _ensure_dir()
    path = os.path.join(SNAP_DIR, snap_id + ".json")
    if os.path.exists(path):
        os.remove(path)
        log_info("snapshot_deleted", id=snap_id)
        return True
    return False


# ══════════════════════════════════════════════════════
#  Report (HTML)
# ══════════════════════════════════════════════════════
def report_snapshot(snap_id: str) -> str:
    snap = _load(snap_id)
    if not snap:
        return ""
    perf = snap["performance"]
    svcs = snap.get("services", [])
    sys_info = snap["system"]
    running = [s for s in svcs if s["status"] == "Running"]
    stopped = [s for s in svcs if s["status"] == "Stopped"]

    rows = ""
    for key, label in [("cpu", "CPU"), ("memory", "内存"), ("disk", "磁盘")]:
        p = perf[key]
        rows += "<tr><td>{}</td><td>{:.1f}%</td><td>{:.1f}%</td><td>{:.1f}%</td><td>{}</td></tr>".format(
            label, p["current"], p["avg"], p["peak"], p.get("data_points", 0))

    svc_html = ""
    for s in svcs:
        color = "#73daca" if s["status"] == "Running" else "#f7768e"
        svc_html += '<span style="display:inline-block;background:#161822;padding:3px 8px;margin:2px;border-radius:4px;font-size:11px;color:{}">{}</span>'.format(
            color, s["name"])

    html = ("<!DOCTYPE html><html lang=zh><head><meta charset=utf-8><title>{title}</title>"
    "<style>*{{margin:0;padding:0;box-sizing:border-box}}body{{background:#0f1119;color:#c8ccd4;"
    "font-family:\"Microsoft YaHei UI\",sans-serif;padding:32px 40px}}h1{{font-size:22px;color:#7aa2f7}}"
    ".meta{{font-size:12px;color:#6b7080;margin-bottom:24px}}"
    ".card{{background:#161822;border:1px solid #222639;border-radius:8px;padding:18px 22px;margin-bottom:16px}}"
    ".card h2{{font-size:14px;color:#7aa2f7;margin-bottom:12px}}"
    "table{{width:100%;border-collapse:collapse;font-size:13px}}"
    "th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #222639}}th{{color:#6b7080}}"
    ".row{{display:flex;gap:12px;flex-wrap:wrap}}"
    ".item{{flex:1;min-width:140px;background:#161822;border:1px solid #222639;border-radius:6px;padding:12px 16px}}"
    ".item .num{{font-size:20px;font-weight:bold}}.item .lbl{{font-size:11px;color:#6b7080}}"
    ".note{{background:#1a1b26;border-left:3px solid #f7768e;padding:10px 16px;font-size:12px;margin-top:12px;border-radius:0 6px 6px 0}}"
    "</style></head><body>"
    "<h1>{title}</h1><div class=meta>{ts}  {note}</div>"
    "<div class=card><h2>系统信息</h2><div class=row>"
    "<div class=item><div class=lbl>系统</div><div class=num style=font-size:13px;color:#c8ccd4>{platform}</div></div>"
    "<div class=item><div class=lbl>CPU</div><div class=num style=font-size:13px;color:#c8ccd4>{cpu_model}</div></div>"
    "<div class=item><div class=lbl>核心数</div><div class=num style=color:#7aa2f7>{cores}</div></div>"
    "<div class=item><div class=lbl>内存总量</div><div class=num style=color:#73daca>{mem_gb} GB</div></div>"
    "<div class=item><div class=lbl>磁盘总量</div><div class=num style=color:#7dcfff>{disk_gb} GB</div></div>"
    "<div class=item><div class=lbl>开机时间</div><div class=num style=font-size:13px;color:#e0af68>{boot}</div></div>"
    "<div class=item><div class=lbl>运行时长</div><div class=num style=font-size:16px>{uptime}</div></div>"
    "</div></div>"
    "<div class=card><h2>性能摘要 (最近 1 小时)</h2><table>{rows}</table></div>"
    "<div class=card><h2>服务状态 ({running}/{total})</h2>"
    "<span style=font-size:11px;color:#73daca>运行中: {running}</span>"
    "<span style=font-size:11px;color:#f7768e;margin-left:12px>已停止: {stopped}</span>"
    "<div style=margin-top:8px>{svcs}</div></div></body></html>").format(
        title="快照报告 - {}".format(snap_id),
        ts=snap["timestamp"][:19].replace("T", " "),
        note='<div class=note>{}</div>'.format(snap.get("note", "")) if snap.get("note") else "",
        platform=sys_info["platform"], cpu_model=sys_info.get("cpu_model", ""),
        cores=sys_info["cores"], mem_gb=sys_info["total_memory_gb"],
        disk_gb=sys_info["total_disk_gb"], boot=sys_info["boot_time"],
        uptime=sys_info["uptime"], rows=rows, svcs=svc_html,
        running=len(running), stopped=len(stopped), total=len(svcs))

    cfg = get_config()
    out_dir = os.path.join(cfg.lab_root, "reports")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "{}.html".format(snap_id))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


# ══════════════════════════════════════════════════════
#  CLI formatters
# ══════════════════════════════════════════════════════
def _fmt_uptime(sec):
    d, r = divmod(sec, 86400)
    h, r = divmod(r, 3600)
    m, _ = divmod(r, 60)
    if d:
        return "{}d {}h {}m".format(d, h, m)
    return "{}h {}m".format(h, m)


def _cpu_model():
    try:
        import psutil
        info = psutil.cpu_info()
        return info.get("brand_raw", "") if info else ""
    except Exception:
        return ""


def _collect_services():
    targets = [
        "SysMain", "WSearch", "defragsvc", "Spooler", "wuauserv",
        "BITS", "DiagTrack", "PcaSvc", "FontCache", "Themes",
        "EventSystem", "Audiosrv", "WinDefend", "MpsSvc", "UsoSvc",
        "WaaSMedicSvc", "DoSvc", "MapsBroker", "lfsvc", "XblAuthManager",
    ]
    result = []
    for name in targets:
        try:
            out = subprocess.check_output(
                ["sc", "query", name],
                stderr=subprocess.DEVNULL, timeout=3,
                encoding="utf-8", errors="replace"
            )
            status = "Running" if "RUNNING" in out else "Stopped"
        except Exception:
            status = "-"
        result.append({"name": name, "status": status})
    return result


def _perf_summary(seconds, cur_cpu, cur_mem, cur_disk):
    from core.monitor import query_history
    hist = query_history(seconds)
    defaults = {
        "current": 0, "avg": 0, "peak": 0, "data_points": 0
    }
    if hist.get("error"):
        return {
            "cpu": {**defaults, "current": round(cur_cpu, 1)},
            "memory": {**defaults, "current": round(cur_mem, 1)},
            "disk": {**defaults, "current": round(cur_disk, 1)},
            "note": "insufficient" if hist.get("count", 0) < 10 else hist["error"],
        }
    return {
        "cpu": {"current": round(cur_cpu, 1), "avg": hist["cpu_avg"], "peak": hist["cpu_max"], "data_points": hist["count"]},
        "memory": {"current": round(cur_mem, 1), "avg": hist["memory_avg"], "peak": hist["memory_max"], "data_points": hist["count"]},
        "disk": {"current": round(cur_disk, 1), "avg": hist["disk_avg"], "peak": hist["disk_max"], "data_points": hist["count"]},
    }


def _delta(a, b):
    d = b - a
    if abs(d) < 0.3:
        return "\u2192   0"
    arrow = "\u2191" if d > 0 else "\u2193"
    return "{} {:.1f}".format(arrow, abs(d))


def _load(sid):
    _ensure_dir()
    path = os.path.join(SNAP_DIR, sid + ".json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)
