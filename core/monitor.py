from __future__ import annotations

import os
import sys
import time
import datetime
import sqlite3
import threading
import functools

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _log_collect_error(func_name: str, exc: Exception):
    from core.logger import log_error
    log_error("采集失败: {}".format(func_name), error=str(exc))


def _safe_collect(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            _log_collect_error(func.__name__, exc)
            return None
    return wrapper


def _bytes_to_human(n: float) -> str:
    if n < 0:
        n = 0
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(n) < 1024.0:
            return "{:.1f} {}".format(n, unit)
        n /= 1024.0
    return "{:.1f} EB".format(n)


def _percent_bar(pct: float, width: int = 20) -> str:
    filled = int(round(pct / 100.0 * width))
    if filled > width:
        filled = width
    if filled < 0:
        filled = 0
    empty = width - filled
    if pct >= 90:
        ch = "#"
    elif pct >= 70:
        ch = "="
    else:
        ch = "-"
    return "[{}{}] {:5.1f}%".format(ch * filled, " " * empty, pct)


@_safe_collect
def get_cpu_info() -> dict:
    if not HAS_PSUTIL:
        return {"error": "psutil 未安装"}

    freq = psutil.cpu_freq()
    return {
        "model": _cpu_name(),
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
        "freq_current": freq.current if freq else 0,
        "freq_min": freq.min if freq and freq.min else 0,
        "freq_max": freq.max if freq and freq.max else 0,
        "usage_percent": psutil.cpu_percent(interval=0.3),
        "usage_per_core": psutil.cpu_percent(interval=0.1, percpu=True),
        "times": psutil.cpu_times(),
    }


def _cpu_name() -> str:
    try:
        import subprocess
        out = subprocess.check_output(
            'powershell -Command "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name"',
            shell=True, stderr=subprocess.DEVNULL
        ).decode("utf-8", errors="replace").strip()
        if out:
            return out
    except Exception:
        pass

    try:
        import platform
        name = platform.processor()
        if name and name != "Intel64 Family 6 Model 0 Stepping 0, GenuineIntel":
            return name
    except Exception:
        pass

    return "Unknown CPU"


@_safe_collect
def get_memory_info() -> dict:
    if not HAS_PSUTIL:
        return {"error": "psutil 未安装"}

    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total": mem.total,
        "available": mem.available,
        "used": mem.used,
        "free": mem.free,
        "percent": mem.percent,
        "swap_total": swap.total,
        "swap_used": swap.used,
        "swap_free": swap.free,
        "swap_percent": swap.percent,
    }


def get_disk_info() -> list:
    if not HAS_PSUTIL:
        return []

    result = []
    for p in psutil.disk_partitions():
        try:
            usage = psutil.disk_usage(p.mountpoint)
            result.append({
                "device": p.device,
                "mount": p.mountpoint,
                "fstype": p.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": usage.percent,
            })
        except (PermissionError, OSError):
            continue
    return result


def get_disk_io() -> dict:
    if not HAS_PSUTIL:
        return {}

    try:
        io_counters = psutil.disk_io_counters(perdisk=False)
        if io_counters:
            return {
                "read_bytes": io_counters.read_bytes,
                "write_bytes": io_counters.write_bytes,
                "read_count": io_counters.read_count,
                "write_count": io_counters.write_count,
            }
    except Exception:
        pass
    return {}


def get_network_info() -> list:
    if not HAS_PSUTIL:
        return []

    result = []
    for name, stats in psutil.net_io_counters(pernic=True).items():
        result.append({
            "name": name,
            "sent_bytes": stats.bytes_sent,
            "recv_bytes": stats.bytes_recv,
            "sent_packets": stats.packets_sent,
            "recv_packets": stats.packets_recv,
        })
    return result


@_safe_collect
def get_top_processes(limit: int = 10, sort_by: str = "cpu") -> list:
    if not HAS_PSUTIL:
        return []

    process_list = []
    for p in psutil.process_iter(["pid", "name", "memory_percent", "memory_info"]):
        try:
            if p.pid == 0:
                continue
            p.cpu_percent()
            process_list.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.2)

    num_cores = psutil.cpu_count() or 1
    procs = []
    for p in process_list:
        try:
            info = p.as_dict(attrs=["pid", "name", "memory_percent", "memory_info"])
            cpu = p.cpu_percent() / num_cores
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "",
                "cpu": round(cpu, 1) if cpu else 0.0,
                "memory": info["memory_percent"] or 0.0,
                "memory_bytes": info["memory_info"].rss if info["memory_info"] else 0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    key = "cpu" if sort_by == "cpu" else "memory"
    procs.sort(key=lambda x: x[key], reverse=True)
    return procs[:limit]


def get_system_info() -> dict:
    if not HAS_PSUTIL:
        return {"error": "psutil 未安装"}

    boot_time = psutil.boot_time()
    now = time.time()
    uptime_seconds = int(now - boot_time)
    return {
        "boot_time": datetime.datetime.fromtimestamp(boot_time).strftime("%Y-%m-%d %H:%M:%S"),
        "uptime": _format_uptime(uptime_seconds),
    }


def get_sensors() -> dict:
    if not HAS_PSUTIL:
        return {}

    result = {}
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            result["temperatures"] = {}
            for name, entries in temps.items():
                result["temperatures"][name] = [
                    {"label": e.label or "", "current": e.current, "high": e.high, "critical": e.critical}
                    for e in entries
                ]
    except Exception:
        pass

    try:
        battery = psutil.sensors_battery()
        if battery:
            result["battery"] = {
                "percent": battery.percent,
                "plugged": battery.power_plugged,
                "remaining": _format_uptime(battery.secsleft) if battery.secsleft != psutil.POWER_TIME_UNLIMITED else None,
            }
    except Exception:
        pass

    try:
        fans = psutil.sensors_fans()
        if fans:
            result["fans"] = {}
            for name, entries in fans.items():
                result["fans"][name] = [{"label": e.label or "", "current": e.current} for e in entries]
    except Exception:
        pass

    return result


def _format_uptime(seconds: int) -> str:
    if seconds < 0:
        return "未知"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append("{} 天".format(days))
    if hours:
        parts.append("{} 小时".format(hours))
    if mins:
        parts.append("{} 分钟".format(mins))
    if not parts:
        return "{} 秒".format(secs)
    return " ".join(parts)


def format_report() -> str:
    lines = []
    any_data = False

    lines.append("=" * 60)
    lines.append("  Digital Lab - 系统监控报告")
    lines.append("  生成时间: {}".format(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    lines.append("=" * 60)

    # ---- 系统信息 ----
    sys_info = get_system_info()
    if sys_info and "uptime" in sys_info:
        any_data = True
        lines.append("")
        lines.append("--- 系统信息 ---")
        lines.append("  开机时间: {}".format(sys_info["boot_time"]))
        lines.append("  运行时长: {}".format(sys_info["uptime"]))

    # ---- CPU ----
    cpu = get_cpu_info()
    if cpu is not None and "error" not in cpu:
        any_data = True
        lines.append("")
        lines.append("--- CPU ---")
        lines.append("  型号: {}".format(cpu["model"]))
        lines.append("  核心: {} 物理 / {} 逻辑".format(cpu["physical_cores"], cpu["logical_cores"]))
        lines.append("  频率: {:.0f} MHz (最低 {:.0f} / 最高 {:.0f})".format(
            cpu["freq_current"], cpu["freq_min"], cpu["freq_max"]
        ))
        lines.append("  CPU 使用率: {}".format(_percent_bar(cpu["usage_percent"])))
        if cpu["usage_per_core"]:
            core_str = " ".join("{:5.1f}%".format(c) for c in cpu["usage_per_core"])
            lines.append("  各核心: {}".format(core_str))

    # ---- 内存 ----
    mem = get_memory_info()
    if mem is not None and "error" not in mem:
        any_data = True
        lines.append("")
        lines.append("--- 内存 ---")
        lines.append("  物理内存: {} / {}  {}".format(
            _bytes_to_human(mem["used"]),
            _bytes_to_human(mem["total"]),
            _percent_bar(mem["percent"]),
        ))
        lines.append("  可用内存: {}".format(_bytes_to_human(mem["available"])))
        if mem["swap_total"] > 0:
            lines.append("  交换内存: {} / {}  {}".format(
                _bytes_to_human(mem["swap_used"]),
                _bytes_to_human(mem["swap_total"]),
                _percent_bar(mem["swap_percent"]),
            ))

    # ---- 磁盘 ----
    disks = get_disk_info()
    if disks:
        any_data = True
        lines.append("")
        lines.append("--- 磁盘 ---")
        for d in disks:
            lines.append("  {:10s} {:5s}  {} / {}  {}".format(
                d["mount"], d["fstype"],
                _bytes_to_human(d["used"]),
                _bytes_to_human(d["total"]),
                _percent_bar(d["percent"]),
            ))

    # ---- 磁盘 I/O ----
    io = get_disk_io()
    if io:
        lines.append("")
        lines.append("  磁盘读写总量:")
        lines.append("    读取: {} ({} 次)".format(_bytes_to_human(io["read_bytes"]), io["read_count"]))
        lines.append("    写入: {} ({} 次)".format(_bytes_to_human(io["write_bytes"]), io["write_count"]))

    # ---- 网络 ----
    nets = get_network_info()
    if nets:
        lines.append("")
        lines.append("--- 网络 ---")
        for nic in nets:
            lines.append("  {}:".format(nic["name"]))
            lines.append("    发送: {} ({} 包)".format(
                _bytes_to_human(nic["sent_bytes"]), nic["sent_packets"]
            ))
            lines.append("    接收: {} ({} 包)".format(
                _bytes_to_human(nic["recv_bytes"]), nic["recv_packets"]
            ))

    # ---- 传感器 ----
    sensors = get_sensors()
    if sensors:
        if "temperatures" in sensors:
            lines.append("")
            lines.append("--- 温度 ---")
            for name, entries in sensors["temperatures"].items():
                for e in entries:
                    label = " [{}]".format(e["label"]) if e["label"] else ""
                    h = " / 高温: {:.0f}C".format(e["high"]) if e["high"] else ""
                    c = " / 临界: {:.0f}C".format(e["critical"]) if e["critical"] else ""
                    lines.append("  {}{}: {:.1f}C{}{}".format(name, label, e["current"], h, c))
        if "battery" in sensors:
            b = sensors["battery"]
            status = "充电中" if b["plugged"] else "放电中"
            lines.append("")
            lines.append("--- 电池 ---")
            lines.append("  电量: {}%  [{}]".format(b["percent"], status))
            if b["remaining"]:
                lines.append("  剩余: {}".format(b["remaining"]))
        if "fans" in sensors:
            lines.append("")
            lines.append("--- 风扇 ---")
            for name, entries in sensors["fans"].items():
                for e in entries:
                    label = " [{}]".format(e["label"]) if e["label"] else ""
                    lines.append("  {}{}: {} RPM".format(name, label, e["current"]))

    # ---- 进程 Top 10 ----
    procs = get_top_processes(10, "cpu")
    if procs:
        lines.append("")
        lines.append("--- CPU 占用 Top 10 ---")
        lines.append("  {:6s}  {:25s}  {:8s}  {}".format("PID", "进程名", "CPU%", "内存%"))
        for p in procs:
            name = p["name"]
            if len(name) > 25:
                name = name[:22] + "..."
            lines.append("  {:6d}  {:25s}  {:6.1f}%  {:6.1f}%".format(
                p["pid"], name, p["cpu"], p["memory"]
            ))

    mem_procs = get_top_processes(10, "memory")
    if mem_procs:
        lines.append("")
        lines.append("--- 内存占用 Top 10 ---")
        lines.append("  {:6s}  {:25s}  {:8s}  {}".format("PID", "进程名", "内存%", "物理内存"))
        for p in mem_procs:
            name = p["name"]
            if len(name) > 25:
                name = name[:22] + "..."
            lines.append("  {:6d}  {:25s}  {:6.1f}%  {}".format(
                p["pid"], name, p["memory"], _bytes_to_human(p["memory_bytes"])
            ))

    if not any_data:
        lines.append("")
        lines.append("  [!] 系统信息采集暂时不可用，请稍后重试。")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


# ============================================================
#  SQLite 存储
# ============================================================

_db_lock = threading.Lock()
_last_alert_time = {}
_alert_test_mode = False
_pending_snapshots = []
_pending_lock = threading.Lock()


def enable_alert_test():
    global _alert_test_mode
    _alert_test_mode = True


def _get_db_path():
    from core.config import get_config
    cfg = get_config()
    os.makedirs(os.path.dirname(cfg.monitor_db_path), exist_ok=True)
    return cfg.monitor_db_path


def init_db():
    db_path = _get_db_path()
    with _db_lock:
        for attempt in range(3):
            try:
                conn = sqlite3.connect(db_path, timeout=5)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT    NOT NULL,
                        cpu       REAL    NOT NULL,
                        memory    REAL    NOT NULL,
                        disk      REAL    NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_snapshots_ts
                    ON snapshots(timestamp)
                """)
                conn.commit()
                conn.close()
                return True
            except sqlite3.OperationalError:
                if attempt < 2:
                    time.sleep(1)
                else:
                    from core.logger import log_error
                    log_error("SQLite 初始化失败", path=db_path, attempt=attempt + 1)
                    return False
    return False


def _write_snapshot_to_db(db_path: str, entries: list):
    conn = sqlite3.connect(db_path, timeout=5)
    conn.executemany(
        "INSERT INTO snapshots (timestamp, cpu, memory, disk) VALUES (?, ?, ?, ?)",
        entries,
    )
    conn.commit()
    conn.close()


def insert_snapshot(cpu: float, memory: float, disk: float):
    ts = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    db_path = _get_db_path()

    _flush_pending(db_path)

    entry = (ts, cpu, memory, disk)

    with _db_lock:
        for attempt in range(3):
            try:
                _write_snapshot_to_db(db_path, [entry])
                return
            except sqlite3.OperationalError:
                if attempt < 2:
                    time.sleep(1)
                else:
                    from core.logger import log_error
                    log_error("SQLite 写入失败 (3次重试耗尽), 已缓存到内存队列")

    with _pending_lock:
        _pending_snapshots.append(entry)


def _flush_pending(db_path: str):
    global _pending_snapshots
    with _pending_lock:
        if not _pending_snapshots:
            return
        batch = list(_pending_snapshots)
        _pending_snapshots.clear()

    with _db_lock:
        try:
            _write_snapshot_to_db(db_path, batch)
            from core.logger import log_info
            log_info("内存队列写入成功", count=len(batch))
        except sqlite3.OperationalError:
            with _pending_lock:
                _pending_snapshots[:0] = batch
            from core.logger import log_error
            log_error("内存队列恢复写入失败", count=len(batch))


def query_history(seconds_ago: int) -> dict:
    cutoff = (datetime.datetime.now() - datetime.timedelta(seconds=seconds_ago)).strftime("%Y-%m-%dT%H:%M:%S")
    db_path = _get_db_path()
    with _db_lock:
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cur = conn.execute(
                "SELECT AVG(cpu), MAX(cpu), AVG(memory), MAX(memory), AVG(disk), MAX(disk), COUNT(*) "
                "FROM snapshots WHERE timestamp >= ?",
                (cutoff,),
            )
            row = cur.fetchone()
            conn.close()
            count = row[6] if row else 0
            if count < 10:
                return {"error": "insufficient", "count": count}
            return {
                "cpu_avg": round(row[0], 1) if row[0] else 0,
                "cpu_max": round(row[1], 1) if row[1] else 0,
                "memory_avg": round(row[2], 1) if row[2] else 0,
                "memory_max": round(row[3], 1) if row[3] else 0,
                "disk_avg": round(row[4], 1) if row[4] else 0,
                "disk_max": round(row[5], 1) if row[5] else 0,
                "count": count,
            }
        except sqlite3.OperationalError:
            return {"error": "db_error", "count": 0}


def get_daemon_stats() -> dict:
    db_path = _get_db_path()
    with _db_lock:
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cur = conn.execute("SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM snapshots")
            row = cur.fetchone()
            conn.close()
            return {
                "total": row[0] if row else 0,
                "first": row[1] if row and row[1] else "",
                "last": row[2] if row and row[2] else "",
            }
        except sqlite3.OperationalError:
            return {"total": 0, "first": "", "last": ""}


# ============================================================
#  阈值告警
# ============================================================

def _color_text(text: str, color: str) -> str:
    codes = {
        "red": "\033[91m",
        "yellow": "\033[93m",
        "green": "\033[92m",
        "cyan": "\033[96m",
        "bold": "\033[1m",
        "reset": "\033[0m",
    }
    return "{}{}{}".format(codes.get(color, ""), text, codes["reset"])


def _get_max_disk_percent() -> float:
    disks = get_disk_info()
    if not disks:
        return 0.0
    return max(d["percent"] for d in disks)


def check_alerts(cpu: float, memory: float, disk: float, thresholds: dict, cooldown: int) -> list:
    global _last_alert_time, _alert_test_mode

    alerts = []
    now = time.time()

    checks = [
        ("CPU", cpu, thresholds.get("cpu", 80), "cpu"),
        ("内存", memory, thresholds.get("memory", 85), "memory"),
        ("磁盘", disk, thresholds.get("disk", 90), "disk"),
    ]

    for name, value, limit, key in checks:
        if _alert_test_mode or value >= limit:
            last = _last_alert_time.get(key, 0)
            if _alert_test_mode or (now - last >= cooldown):
                level = "red" if value >= limit else "yellow"
                tag = "[紧急]" if value >= limit else "[警告]"
                alerts.append((name, value, limit, tag, level))
                _last_alert_time[key] = now

                from core.logger import log_alert
                log_alert(name, value, limit, test=_alert_test_mode)
            else:
                from core.logger import log_info
                log_info("{} 超标(冷却中)".format(name), current=value, threshold=limit)

    return alerts


def format_alerts(alerts: list) -> str:
    if not alerts:
        return ""
    lines = []
    lines.append("")
    lines.append("=" * 56)
    for name, value, limit, tag, level in alerts:
        color = "red" if level == "red" else "yellow"
        lines.append(
            _color_text(
                "  {}  {}: {:.1f}%  (阈值: {}%)".format(tag, name, value, limit),
                color,
            )
        )
    lines.append("=" * 56)
    return "\n".join(lines)


def format_compare(current_cpu: float, current_mem: float, current_disk: float,
                   history: dict, period_label: str) -> str:
    if "error" in history:
        if history["error"] == "insufficient":
            return _color_text(
                "\n[!] 历史数据不足 ({} 条)，建议先运行守护模式累积数据。\n"
                "    dlab monitor --daemon --interval 60".format(history["count"]),
                "yellow",
            )
        return _color_text("\n[!] 读取历史数据失败，请检查数据库状态。", "red")

    def trend(cur, avg):
        diff = cur - avg
        if diff > 5:
            return _color_text("↑ +{:.1f}%".format(diff), "red")
        elif diff > 1:
            return _color_text("↑ +{:.1f}%".format(diff), "yellow")
        elif diff < -5:
            return _color_text("↓ {:.1f}%".format(diff), "green")
        elif diff < -1:
            return _color_text("↓ {:.1f}%".format(diff), "cyan")
        else:
            return "→ {:.1f}%".format(diff)

    lines = []
    lines.append("")
    lines.append("=" * 56)
    lines.append("  历史对比: 当前  vs  {} ({} 条数据)".format(period_label, history["count"]))
    lines.append("=" * 56)
    lines.append("  {:6s}  {:10s}  {:10s}  {:10s}  {}".format(
        "指标", "当前值", "对比均值", "对比峰值", "变化趋势"
    ))
    lines.append("-" * 56)

    rows = [
        ("CPU",   "{:.1f}%".format(current_cpu),  history["cpu_avg"], history["cpu_max"]),
        ("内存",  "{:.1f}%".format(current_mem),  history["memory_avg"], history["memory_max"]),
        ("磁盘",  "{:.1f}%".format(current_disk), history["disk_avg"], history["disk_max"]),
    ]
    for name, cur_str, avg, mx in rows:
        lines.append("  {:6s}  {:10s}  {:8.1f}%      {:8.1f}%     {}".format(
            name, cur_str, avg, mx, trend(float(cur_str.rstrip("%")), avg)
        ))
    lines.append("=" * 56)
    return "\n".join(lines)


def collect_and_store():
    cpu_raw = get_cpu_info()
    mem_raw = get_memory_info()
    disk_pct = _get_max_disk_percent()

    cpu_val = 0
    mem_val = 0
    disk_val = disk_pct or 0

    if cpu_raw and cpu_raw.get("usage_percent") is not None:
        cpu_val = cpu_raw["usage_percent"]
    if mem_raw and mem_raw.get("percent") is not None:
        mem_val = mem_raw["percent"]

    if cpu_raw is None and mem_raw is None:
        return None, None, None

    init_db()
    insert_snapshot(cpu_val, mem_val, disk_val)

    return cpu_val, mem_val, disk_val


def format_live(clr: bool = False) -> str:
    lines = []

    now = datetime.datetime.now().strftime("%H:%M:%S")
    cpu = get_cpu_info()
    mem = get_memory_info()

    lines.append("  Digital Lab 实时监控  |  {}  |  Ctrl+C 退出".format(now))
    lines.append("-" * 60)

    if cpu is not None and "error" not in cpu:
        lines.append("  CPU: {}  |  {}核 / {:.0f}MHz  |  {}".format(
            cpu["model"][:35] if len(cpu["model"]) > 35 else cpu["model"],
            cpu["logical_cores"],
            cpu["freq_current"],
            _percent_bar(cpu["usage_percent"]),
        ))
    else:
        lines.append("  CPU: --- 采集失败 ---")

    if mem is not None and "error" not in mem:
        lines.append("  内存: {} / {}  {}".format(
            _bytes_to_human(mem["used"]),
            _bytes_to_human(mem["total"]),
            _percent_bar(mem["percent"]),
        ))
    else:
        lines.append("  内存: --- 采集失败 ---")

    disks = get_disk_info()
    disk_strs = []
    if disks:
        for d in disks[:4]:
            disk_strs.append("{} {} / {} {}".format(
                d["mount"], _bytes_to_human(d["used"]), _bytes_to_human(d["total"]), _percent_bar(d["percent"])
            ))
    if disk_strs:
        lines.append("  磁盘: {}".format("  |  ".join(disk_strs)))
    else:
        lines.append("  磁盘: --- 采集失败 ---")

    lines.append("-" * 60)
    lines.append("  {:6s}  {:22s}  {:12s}  {}".format("PID", "进程名", "CPU%", "内存%"))
    procs = get_top_processes(15, "cpu")
    if procs:
        for p in procs:
            name = p["name"]
            if len(name) > 22:
                name = name[:19] + "..."
            lines.append("  {:6d}  {:22s}  {:8.1f}%  {:8.1f}%".format(
                p["pid"], name, p["cpu"], p["memory"]
            ))
    else:
        lines.append("  --- 进程信息暂时不可用 ---")

    return "\n".join(lines)
