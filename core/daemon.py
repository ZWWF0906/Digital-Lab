from __future__ import annotations

import os
import sys
import time
import signal
import subprocess
from typing import Optional


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def daemon_status(pid_path: str) -> dict:
    if not os.path.exists(pid_path):
        return {"running": False, "reason": "PID 文件不存在"}

    try:
        with open(pid_path, "r") as f:
            lines = f.read().strip().splitlines()
        pid = int(lines[0])
        start_ts = lines[1] if len(lines) > 1 else ""
    except (ValueError, IndexError):
        return {"running": False, "reason": "PID 文件损坏"}

    if not _is_pid_alive(pid):
        os.remove(pid_path)
        return {"running": False, "reason": "PID {} 进程已死亡，已清理 PID 文件".format(pid)}

    runtime = ""
    if start_ts:
        try:
            elapsed = int(time.time()) - int(start_ts)
            days, rem = divmod(elapsed, 86400)
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
                parts.append("{} 秒".format(secs))
            runtime = " ".join(parts)
        except Exception:
            runtime = "未知"

    from core.monitor import get_daemon_stats
    stats = get_daemon_stats()

    return {
        "running": True,
        "pid": pid,
        "runtime": runtime,
        "started_at": start_ts,
        "collections": stats.get("total", 0),
        "first_snapshot": stats.get("first", ""),
        "last_snapshot": stats.get("last", ""),
    }


def start_daemon(pid_path: str, script_path: str, interval: int) -> str:
    status = daemon_status(pid_path)
    if status["running"]:
        return "[!] 守护进程已在运行 (PID: {})".format(status["pid"])

    os.makedirs(os.path.dirname(pid_path), exist_ok=True)

    env = os.environ.copy()
    env["DLAB_DAEMON"] = "1"
    env["DLAB_DAEMON_INTERVAL"] = str(interval)
    env["DLAB_DAEMON_PIDFILE"] = pid_path

    if sys.platform == "win32":
        flags = 0x00000008
        if hasattr(subprocess, "CREATE_NO_WINDOW"):
            flags = subprocess.CREATE_NO_WINDOW
        elif hasattr(subprocess, "DETACHED_PROCESS"):
            flags = subprocess.DETACHED_PROCESS
        proc = subprocess.Popen(
            [sys.executable, script_path],
            creationflags=flags,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            [sys.executable, script_path],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None,
        )

    time.sleep(0.5)
    if not _is_pid_alive(proc.pid):
        return "[!] 守护进程启动后立即退出，请检查日志。"

    with open(pid_path, "w") as f:
        f.write("{}\n{}".format(proc.pid, int(time.time())))

    from core.logger import log_info
    log_info("守护进程已启动", pid=proc.pid)

    return "[OK] 守护进程已启动 (PID: {}, 间隔: {}s)".format(proc.pid, interval)


def stop_daemon(pid_path: str) -> str:
    if not os.path.exists(pid_path):
        return "[!] 守护进程未运行 (PID 文件不存在)"

    try:
        with open(pid_path, "r") as f:
            pid_str = f.read().strip().splitlines()[0]
        pid = int(pid_str)
    except (ValueError, IndexError):
        os.remove(pid_path)
        return "[!] PID 文件损坏，已清理"

    if not _is_pid_alive(pid):
        os.remove(pid_path)
        return "[OK] PID 文件存在但进程已死亡，已清理"

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not _is_pid_alive(pid):
                break
            time.sleep(0.2)
    except (OSError, ProcessLookupError):
        pass

    if _is_pid_alive(pid):
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                os.kill(pid, signal.SIGKILL)
            time.sleep(0.3)
        except (OSError, ProcessLookupError):
            pass

    if os.path.exists(pid_path):
        os.remove(pid_path)

    from core.logger import log_info
    log_info("守护进程已停止", pid=pid)

    return "[OK] 守护进程已停止 (PID: {})".format(pid)


def run_daemon_loop(pid_path: str, interval: int):
    with open(pid_path, "w") as f:
        f.write("{}\n{}".format(os.getpid(), int(time.time())))

    from core.monitor import init_db, collect_and_store, check_alerts, format_alerts, enable_alert_test
    from core.config import get_config
    from core.logger import log_info, log_error, JsonLogger

    cfg = get_config()
    JsonLogger.get(cfg.monitor_log_path)

    thresholds = cfg.get_thresholds()
    cooldown = cfg.monitor_alert_cooldown

    if not init_db():
        log_error("守护进程启动失败: 无法初始化数据库")
        sys.exit(1)

    log_info("守护进程开始运行", pid=os.getpid(), interval=interval)

    count = 0
    while True:
        try:
            cpu, mem, disk = collect_and_store()
            count += 1

            if cpu is None and mem is None and disk is None:
                log_error("全部指标采集失败, 跳过告警检查")
            elif cpu is not None or mem is not None or disk is not None:
                alerts = check_alerts(cpu or 0, mem or 0, disk or 0, thresholds, cooldown)
                if alerts:
                    alert_str = ", ".join(
                        "{}:{:.0f}%".format(a[0], a[1]) for a in alerts
                    )
                    log_info("采集 #{}: {}".format(count, alert_str))

            time.sleep(interval)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_error("守护进程采集异常", error=str(e))
            time.sleep(interval)

    if os.path.exists(pid_path):
        os.remove(pid_path)
    log_info("守护进程已退出", total_collections=count)
