from __future__ import annotations

import argparse
import io
import sys
import os
import time
import types

_project_root = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

_PY_MIN = (3, 7)


def _setup_windows_console():
    if sys.platform != "win32":
        return

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    else:
        if sys.stdout.encoding.lower() in ("", "none", "ansi_x3.4-1968"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace"
            )
 # 强制 stdin 也为 UTF-8，防止 Electron 传入的中文被错误解码
    if hasattr(sys.stdin, "reconfigure"):
        try:
            sys.stdin.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    else:
        if sys.stdin.encoding.lower() in ("", "none", "ansi_x3.4-1968"):
            sys.stdin = io.TextIOWrapper(
                sys.stdin.buffer, encoding="utf-8", errors="replace"
            )            


def _safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", "utf-8") or "utf-8"
        safe_args = []
        for a in args:
            if isinstance(a, str):
                a = a.encode(enc, errors="replace").decode(enc, errors="replace")
            safe_args.append(a)
        print(*safe_args, **kwargs)


def _safe_input(prompt=""):
    try:
        if prompt:
            _safe_print(prompt, end="", flush=True)
        return sys.stdin.readline().strip()
    except (EOFError, KeyboardInterrupt):
        return ""


def _check_python():
    vi = sys.version_info[:2]
    if vi < _PY_MIN:
        sys.exit(
            "DigitalLab 需要 Python {}.{} 或更高版本，"
            "当前版本: {}.{}".format(*_PY_MIN, *vi)
        )


def _get_python_info():
    return "Python {}.{}.{} ({})".format(
        sys.version_info.major,
        sys.version_info.minor,
        sys.version_info.micro,
        sys.executable,
    )


def _get_system_info():
    if sys.platform == "win32":
        try:
            wv = sys.getwindowsversion()
            build = wv.build
            if build >= 22000:
                name = "Windows 11"
            else:
                name = "Windows 10"
            return "{} build {}".format(name, build)
        except Exception:
            return "Windows (未知版本)"
    return "{} {}".format(sys.platform, os.name)


def _cli_header():
    _safe_print("")
    _safe_print("=" * 56)
    _safe_print("    DigitalLab — 个人数字实验室")
    _safe_print("    {}  |  {}".format(_get_python_info(), _get_system_info()))
    _safe_print("-" * 56)
    _safe_print("    © 2026 ZWWF0906")
    _safe_print("=" * 56)


def _pause():
    _safe_print("")
    _safe_input("按回车键返回菜单...")
    _safe_print("")


# ============================================================
#  命令实现
# ============================================================

def cmd_init(_args=None):
    from core.config import get_config

    config = get_config()
    config.ensure_dirs()
    config.save()
    _safe_print("[OK] DigitalLab 已初始化")
    _safe_print("     根目录: {}".format(config.lab_root))
    _safe_print("     工具目录: {}".format(config.tools_dir))
    _safe_print("     日志目录: {}".format(config.logs_dir))
    _safe_print("     实验目录: {}".format(config.experiments_dir))
    _safe_print("     笔记目录: {}".format(config.notes_dir))
    _safe_print("     存档目录: {}".format(config.archive_dir))
    _safe_print("     接口目录: {}".format(config.interface_dir))


def cmd_status(_args=None):
    from core.config import get_config

    config = get_config()
    _safe_print("=== DigitalLab 系统状态 ===")
    _safe_print("")
    _safe_print("系统信息:")
    _safe_print("  {}".format(_get_python_info()))
    _safe_print("  {}".format(_get_system_info()))
    _safe_print("  控制台编码: {}".format(
        getattr(sys.stdout, "encoding", "unknown") or "unknown"
    ))
    _safe_print("")
    _safe_print("实验室:")
    _safe_print("  根目录: {}".format(config.lab_root))

    dirs = [
        ("tools",        config.tools_dir),
        ("logs",         config.logs_dir),
        ("experiments",  config.experiments_dir),
        ("notes",        config.notes_dir),
        ("archive",      config.archive_dir),
        ("interface",    config.interface_dir),
    ]
    for name, path in dirs:
        ok = os.path.isdir(path)
        tag = "[OK]" if ok else "[缺失]"
        _safe_print("  {:15s} {}  {}".format(name, tag, path))

    cf = config.config_file
    if os.path.exists(cf):
        _safe_print("")
        _safe_print("配置文件: {} [OK]".format(cf))
    else:
        _safe_print("")
        _safe_print("配置文件: {} [缺失]".format(cf))

    _safe_print("")
    _safe_print("运行设置:")
    _safe_print("  日志级别: {}".format(config.log_level))
    _safe_print("  自动整理: {}".format(
        "开启" if config.auto_organize_enabled else "关闭"
    ))
    _safe_print("  仪表盘: {}:{}".format(
        config.dashboard_host, config.dashboard_port
    ))
    _safe_print("  监控阈值: CPU>{}% / 内存>{}% / 磁盘>{}%".format(
        config.monitor_threshold_cpu,
        config.monitor_threshold_memory,
        config.monitor_threshold_disk,
    ))


def cmd_config(_args=None):
    from core.config import Config

    config = Config.load()
    config.ensure_dirs()
    config.save()
    _safe_print("[OK] 默认配置已保存到 {}".format(config.config_file))


def cmd_monitor(args=None):
    from core.config import get_config
    from core.monitor import (
        HAS_PSUTIL, format_report, format_live,
        init_db, collect_and_store, check_alerts, format_alerts,
        query_history, format_compare, enable_alert_test,
    )

    if not HAS_PSUTIL:
        _safe_print("[ERROR] 系统监控需要 psutil 库，请运行: pip install psutil")
        return

    cfg = get_config()

    daemon = getattr(args, "daemon", False)
    do_stop = getattr(args, "stop", False)
    do_daemon_status = getattr(args, "daemon_status", False)
    alert_test = getattr(args, "alert_test", False)
    compare = getattr(args, "compare", None)
    live = getattr(args, "live", False)
    interval = getattr(args, "interval", 2.0)

    if do_stop:
        from core.daemon import stop_daemon
        _safe_print(stop_daemon(cfg.monitor_pid_path))
        return

    if do_daemon_status:
        from core.daemon import daemon_status
        st = daemon_status(cfg.monitor_pid_path)
        if st["running"]:
            _safe_print("")
            _safe_print("=== 守护进程状态 ===")
            _safe_print("  PID:      {}".format(st["pid"]))
            _safe_print("  运行时长: {}".format(st["runtime"]))
            _safe_print("  采集次数: {}".format(st["collections"]))
            _safe_print("  首次采集: {}".format(st["first_snapshot"] or "无"))
            _safe_print("  最近采集: {}".format(st["last_snapshot"] or "无"))
            _safe_print("")
        else:
            _safe_print("[!] 守护进程未运行 ({})".format(st["reason"]))
        return

    if daemon:
        from core.daemon import start_daemon
        intv = int(interval) if interval > 1 else cfg.monitor_interval
        script = os.path.join(os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__)), "main.py")
        _safe_print(start_daemon(cfg.monitor_pid_path, script, intv))
        return

    if alert_test:
        enable_alert_test()
        init_db()
        cpu, mem, disk = collect_and_store()
        thresholds = cfg.get_thresholds()
        cooldown = cfg.monitor_alert_cooldown
        alerts = check_alerts(cpu, mem, disk, thresholds, cooldown)
        _safe_print("")
        _safe_print("=== 告警测试 ===")
        _safe_print("  当前值: CPU {:.1f}% / 内存 {:.1f}% / 磁盘 {:.1f}%".format(cpu, mem, disk))
        _safe_print("  阈值:   CPU {}% / 内存 {}% / 磁盘 {}%".format(
            thresholds["cpu"], thresholds["memory"], thresholds["disk"]
        ))
        _safe_print(format_alerts(alerts))
        return

    init_db()
    cpu, mem, disk = collect_and_store()
    thresholds = cfg.get_thresholds()
    cooldown = cfg.monitor_alert_cooldown

    compare_text = ""
    if compare:
        period_seconds = {"7d": 604800, "24h": 86400, "1h": 3600, "30m": 1800}
        secs = period_seconds.get(compare, 86400)
        label = {"7d": "7 天前", "24h": "24 小时前", "1h": "1 小时前", "30m": "30 分钟前"}.get(compare, compare)
        history = query_history(secs)
        compare_text = format_compare(cpu, mem, disk, history, label)

    if live:
        _safe_print("正在启动实时监控 (Ctrl+C 退出)...")
        _safe_print("")
        try:
            import time
            while True:
                sys.stdout.write("\033[2J\033[H")
                sys.stdout.flush()
                _safe_print(format_live())
                sys.stdout.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            _safe_print("")
            _safe_print("监控已停止。")
    else:
        if compare_text:
            _safe_print(compare_text)
            _safe_print("")
        else:
            alerts = check_alerts(cpu, mem, disk, thresholds, cooldown)
            _safe_print(format_alerts(alerts))

        _safe_print(format_report())


def cmd_report(args=None):
    from core.reporter import generate_report, format_terminal_summary, HAS_MPL

    if not HAS_MPL:
        _safe_print("[WARN] matplotlib 未安装，将生成纯文本报告（无图表）。")
        _safe_print("       安装: pip install matplotlib")

    source = getattr(args, "source", "monitor")
    if source != "monitor":
        _safe_print("[!] 当前仅支持 --source monitor")
        return

    days = getattr(args, "days", None)
    hours = getattr(args, "hours", None)
    if hours is not None:
        seconds = int(hours) * 3600
    elif days is not None:
        seconds = int(days) * 86400
    else:
        seconds = 86400

    result = generate_report(seconds)
    _safe_print(format_terminal_summary(result))


def cmd_launcher(args=None):
    from core.launcher import show_menu, launch, add_shortcut, remove_shortcut

    name = getattr(args, "name", None)
    path = getattr(args, "path", None)
    remove = getattr(args, "remove", None)
    add = getattr(args, "add", None)

    if remove:
        _safe_print(remove_shortcut(remove))
        return
    if add and path:
        _safe_print(add_shortcut(add, path))
        return
    if add:
        _safe_print("[!] --add 需要同时指定 --path")
        return

    menu_text = show_menu()
    _safe_print(menu_text)

    if "暂无" in menu_text:
        _pause()
        return

    try:
        choice = _safe_input("请输入序号启动 (0 返回) > ").strip()
        idx = int(choice)
        if idx == 0:
            return
        _safe_print(launch(idx))
    except ValueError:
        _safe_print("[!] 请输入数字序号")

    _pause()



def cmd_snapshot(args=None):
    from core.snapshot import create_snapshot, list_snapshots, compare_snapshots
    from core.snapshot import delete_snapshot, report_snapshot

    if args is None or (hasattr(args, 'subcommand') and args.subcommand is None):
        args = types.SimpleNamespace(subcommand="create", note="", snap_id1=None, snap_id2=None)

    sub = args.subcommand if hasattr(args, 'subcommand') else "create"

    if sub == "list":
        snaps = list_snapshots()
        if not snaps:
            _safe_print("")
            _safe_print("  暂无快照。使用 'dlab snapshot' 创建第一个快照。")
            return
        _safe_print("")
        _cli_header()
        _safe_print("  {:<24s}  {:<20s}  {:<30s}  {:>8s} {:>8s} {:>8s}".format(
            "ID", "时间", "备注", "CPU%", "内存%", "磁盘%"))
        _safe_print("  " + "-" * 100)
        for s in snaps:
            ts = s["timestamp"][:16].replace("T", " ")
            note = s.get("note", "")[:28]
            perf = s.get("performance", {})
            cpu = perf.get("cpu", {}).get("current", "-")
            mem = perf.get("memory", {}).get("current", "-")
            disk = perf.get("disk", {}).get("current", "-")
            _safe_print("  {:<24s}  {:<20s}  {:<30s}  {:>7.1f}% {:>7.1f}% {:>7.1f}%".format(
                s["id"], ts, note, cpu if isinstance(cpu, (int, float)) else 0,
                mem if isinstance(mem, (int, float)) else 0,
                disk if isinstance(disk, (int, float)) else 0))
        _safe_print("")
        _safe_print("  [命令] dlab snapshot compare <id1> <id2>  -- 对比快照")
        _safe_print("  [命令] dlab snapshot delete <id>             -- 删除快照")
        _safe_print("  [命令] dlab snapshot report <id>             -- 生成 HTML 报告")

    elif sub == "delete":
        sid = args.snap_id1 or ""
        if not sid:
            _safe_print("[!] 用法: dlab snapshot delete <snap-id>")
            return
        if delete_snapshot(sid):
            _safe_print("[OK] 已删除: {}".format(sid))
        else:
            _safe_print("[!] 未找到快照: {}".format(sid))

    elif sub == "report":
        sid = args.snap_id1 or ""
        if not sid:
            _safe_print("[!] 用法: dlab snapshot report <snap-id>")
            return
        path = report_snapshot(sid)
        if path:
            _safe_print("[OK] 报告已生成: {}".format(path))
        else:
            _safe_print("[!] 未找到快照: {}".format(sid))

    elif sub == "compare":
        a = args.snap_id1 or ""
        b = args.snap_id2 or ""
        if not a or not b:
            _safe_print("[!] 用法: dlab snapshot compare <id1> <id2>")
            return
        diff = compare_snapshots(a, b)
        if diff.get("error"):
            _safe_print("[!] {}".format(diff["error"]))
            return
        _safe_print("")
        _cli_header()
        _safe_print("  对比: {}  vs  {}".format(diff["id1"], diff["id2"]))
        _safe_print("  {}  →  {}".format(diff["ts1"][:19], diff["ts2"][:19]))
        _safe_print("")
        _safe_print("  {:>8s}  {:>10s}  {:>10s}  {}".format("指标", diff["id1"][:10], diff["id2"][:10], "变化"))
        _safe_print("  " + "-" * 56)
        for label in ["CPU", "内存", "磁盘"]:
            d = diff[label]
            for sub_label in ["current", "avg", "peak"]:
                v1, v2, arrow = d[sub_label]
                _safe_print("  {:<6s}{:<4s}  {:>6.1f}%    {:>6.1f}%    {}".format(
                    label, sub_label, v1, v2, arrow))
        if diff.get("service_changes"):
            _safe_print("")
            _safe_print("  --- 服务变更 ---")
            for sv in diff["service_changes"]:
                arrow = "→ Running" if sv["after"] == "Running" else "→ Stopped"
                _safe_print("  {} : {} {}".format(sv["name"], sv["before"], arrow))
        else:
            _safe_print("")
            _safe_print("  服务状态: 无变化")
        if diff.get("config_changes"):
            _safe_print("")
            _safe_print("  --- 配置变更 ---")
            for c in diff["config_changes"]:
                _safe_print("  {}".format(c))
        _safe_print("")

    else:
        _safe_print("")
        note = args.note if hasattr(args, 'note') else ""
        if not note:
            note = _safe_input("  备注 (可选, 直接回车跳过): ").strip()
        snap = create_snapshot(note)
        _safe_print("")
        _safe_print("[OK] 快照已创建: {}".format(snap["id"]))
        perf = snap["performance"]
        _safe_print("  CPU  {:.1f}%  |  内存 {:.1f}%  |  磁盘 {:.1f}%".format(
            perf["cpu"]["current"], perf["memory"]["current"], perf["disk"]["current"]))
        _safe_print("  数据点: {}".format(perf["cpu"].get("data_points", 0)))


def cmd_json_mode():
    """JSON 行协议模式：通过 stdin/stdout 与 Electron 主进程通信。"""
    import json
    import threading
    import os as _os

    # 初始化
    from core.config import get_config
    from core.collector import start_collector
    from core.system_state import system_state

    cfg = get_config()
    start_collector()

    # 启动 NAS 远程监控
    from core.nas_monitor import start_nas_monitor, stop_nas_monitor
    import atexit
    start_nas_monitor()
    atexit.register(stop_nas_monitor)

    # ── stdout 锁：防止主循环状态推送与命令响应交织导致 JSON 解析失败 ──
    _stdout_lock = threading.Lock()

    def _safe_print(*args, **kwargs):
        """线程安全的 stdout 输出"""
        with _stdout_lock:
            print(*args, **kwargs)

    # 缓存最新硬件数据
    _latest_hardware = None
    _latest_processes = []

    def _format_state():
        nonlocal _latest_hardware, _latest_processes
        snap = system_state.snapshot()
        monitor = snap.get("monitor", {})
        hw = snap.get("hardware", {})

        # 硬件数据只在首次或变化时更新
        if hw and hw != _latest_hardware:
            _latest_hardware = hw

        procs = monitor.get("processes", [])
        if procs:
            _latest_processes = procs[:15]

        cpu_raw = monitor.get("cpu", 0)
        memory_raw = monitor.get("memory", 0)
        disk_raw = monitor.get("disk", 0)
        # system_state 存储格式为 {"value": x, "ts": t}，需要解包
        cpu = cpu_raw.get("value", 0) if isinstance(cpu_raw, dict) else cpu_raw
        memory = memory_raw.get("value", 0) if isinstance(memory_raw, dict) else memory_raw
        disk = disk_raw.get("value", 0) if isinstance(disk_raw, dict) else disk_raw

        payload = {
            "monitor": {
                "cpu": round(cpu, 1) if isinstance(cpu, (int, float)) else 0,
                "memory": round(memory, 1) if isinstance(memory, (int, float)) else 0,
                "disk": round(disk, 1) if isinstance(disk, (int, float)) else 0,
                "network_speed": monitor.get("network_speed", 0) if isinstance(monitor.get("network_speed"), (int, float)) else 0,
                "processes": [
                    {
                        "pid": p.get("pid", 0),
                        "name": p.get("name", ""),
                        "cpu": round(p.get("cpu", 0), 1),
                        "memory": round(p.get("memory", 0), 1),
                        "rss": p.get("memory_bytes", 0),
                    }
                    for p in _latest_processes
                ],
            },
            "hardware": _format_hardware(_latest_hardware),
            "nas": snap.get("nas", {}),
        }
        return payload

    def _format_hardware(hw):
        if not hw:
            return None
        result = {}
        cpu = hw.get("cpu")
        if cpu:
            result["cpu"] = {
                "model": cpu.get("model", "") or cpu.get("short_model", ""),
                "cores": cpu.get("cores", 0),
                "threads": cpu.get("threads", 0),
                "freq_current": cpu.get("freq_current", ""),
            }
        gpu = hw.get("gpu")
        if gpu:
            result["gpu"] = {
                "name": gpu.get("short_name", "") or gpu.get("name", ""),
                "vram_gb": gpu.get("vram_gb", 0),
                "vram_type": gpu.get("vram_type", ""),
                "utilization": gpu.get("utilization", 0),
            }
        mem = hw.get("memory")
        if mem:
            result["memory"] = {
                "total_gb": mem.get("total_gb", 0),
                "type": mem.get("type", ""),
                "frequency": mem.get("frequency", ""),
                "available_gb": mem.get("available_gb", 0),
            }
        disk = hw.get("disk")
        if disk:
            result["disk"] = {
                "model": disk.get("model", ""),
                "capacity_gb": disk.get("capacity_gb", 0),
                "type": disk.get("type", ""),
            }
        sys_info = hw.get("system")
        if sys_info:
            result["system"] = {
                "os": sys_info.get("os", ""),
                "edition": sys_info.get("edition", ""),
            }
        return result if result else None

    # ── 终端会话管理 ──
    _terminal_sessions = {}
    _terminal_lock = threading.Lock()

    def _send_terminal_output(session_id, data):
        """向 stdout 推送终端输出"""
        msg = json.dumps({"session_id": session_id, "data": data}, ensure_ascii=False)
        _safe_print(msg, flush=True)

    def _handle_terminal_input(session_id, data):
        """前端输入 → SSH stdin，单向转发，后端不做任何回显。"""
        with _terminal_lock:
            sess = _terminal_sessions.get(session_id)
        if not sess or not sess.get("channel"):
            return
        try:
            sess["channel"].sendall(data.encode("utf-8"))
        except Exception:
            pass

    def _handle_terminal_resize(session_id, cols, rows):
        """真实调用 resize_pty，保持远端 shell 与前端 xterm 格尺寸一致。"""
        with _terminal_lock:
            sess = _terminal_sessions.get(session_id)
        if not sess or not sess.get("channel"):
            return
        try:
            sess["channel"].resize_pty(width=int(cols or 80), height=int(rows or 24))
        except Exception:
            pass

    def _handle_terminal_close(session_id):
        with _terminal_lock:
            sess = _terminal_sessions.pop(session_id, None)
        if not sess:
            return
        if sess.get("channel"):
            try:
                sess["channel"].close()
            except Exception:
                pass
        if sess.get("client"):
            try:
                sess["client"].close()
            except Exception:
                pass

    def _handle_ssh_terminal_init(host, port, cols, rows):
        """host 参数实际是设备名称（name），按名称匹配配置后取 IP 连接。

        标准 paramiko 会话建立（参考 webssh / paramiko-shell 成熟写法）：
        - PTY 尺寸采用前端建立会话时提供的真实 cols/rows，不硬编码
        - SSH stdout 原样转发到前端，不附加任何字符
        - SSH stderr 单独排空，不混入终端输出
        """
        import uuid
        sid = str(uuid.uuid4())[:8]
        try:
            import paramiko
            # 从 config.json + user_config.json 读取 NAS 设备凭据
            nas_devices = _get_nas_devices()
            # 按设备名称匹配（name），不是 host IP
            device = next((d for d in nas_devices if d.get("name") == host), None)
            if not device:
                return {"error": "\u672a\u627e\u5230\u8bbe\u5907\u914d\u7f6e: {}".format(host)}
            username = device.get("username", "")
            password = device.get("password", "")
            if not username:
                return {"error": "\u8bbe\u5907\u672a\u914d\u7f6e\u7528\u6237\u540d: {}".format(host)}

            # 使用设备配置中的实际 IP 和端口进行 SSH 连接
            ssh_host = device.get("host", host)
            ssh_port = int(device.get("port", 22)) if device.get("port") else 22

            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=ssh_host,
                port=ssh_port,
                username=username,
                password=password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )

            # 会话建立即使用前端真实尺寸，消除连接后再 resize 的首屏错位窗口期
            channel = client.invoke_shell(
                term="xterm-256color",
                width=int(cols or 80),
                height=int(rows or 24),
            )
            channel.settimeout(None)  # 阻塞读，替代忙轮询
            try:
                client.get_transport().set_keepalive(30)
            except Exception:
                pass

            with _terminal_lock:
                _terminal_sessions[sid] = {
                    "type": "ssh",
                    "proc": None,
                    "host": host,
                    "client": client,
                    "channel": channel,
                }

            def _stdout_reader():
                """远端 SSH stdout → 前端，按块原样转发，不附加任何字符。"""
                try:
                    while not channel.closed:
                        chunk = channel.recv(65536)
                        if not chunk:
                            break
                        _send_terminal_output(sid, chunk.decode("utf-8", errors="replace"))
                except Exception:
                    pass
                finally:
                    _handle_terminal_close(sid)

            def _stderr_drainer():
                """排空远端 SSH stderr（仅丢弃），防止 stderr 缓冲积压阻塞通道。"""
                try:
                    while not channel.closed:
                        if not channel.recv_stderr(4096):
                            break
                except Exception:
                    pass

            threading.Thread(target=_stdout_reader, daemon=True).start()
            threading.Thread(target=_stderr_drainer, daemon=True).start()
            return {"session_id": sid}
        except Exception as e:
            return {"error": str(e)}

    # ── 构建 AI 系统上下文：将实时系统状态格式化为文本，注入 AI 对话 ──

    # 控制字符表：0x00-0x1F 与 0x7F-0x9F 一律替换为空格，杜绝 NUL/控制字符进入模型上下文
    _CTRL_TABLE = dict.fromkeys(list(range(0x00, 0x20)) + list(range(0x7F, 0xA0)), 0x20)

    def _clean_text(v, max_len=80):
        """字段安全清洗：过滤 None、str 转换、去控制字符与代理区字符、限长。"""
        if v is None:
            return ""
        s = str(v)
        s = s.translate(_CTRL_TABLE)
        if any(0xD800 <= ord(c) <= 0xDFFF for c in s):
            s = s.encode("utf-8", errors="replace").decode("utf-8", errors="replace")
        s = s.replace("\ufffd", "")
        s = " ".join(s.split())
        return s[:max_len] if max_len and len(s) > max_len else s

    def _num(v, default=0.0):
        """数值安全转换：dict(含 value) / int / float / 数字字符串均可，其余返回默认值。"""
        vv = v.get("value", 0) if isinstance(v, dict) else v
        if isinstance(vv, bool):
            return default
        if isinstance(vv, (int, float)):
            return float(vv)
        try:
            return float(str(vv).replace("%", "").strip())
        except Exception:
            return default

    _AI_MAX_HISTORY = 16  # 发送给模型的历史消息条数上限，防止长对话上下文膨胀或脏数据回灌
    _AI_MEMORY_LIMIT = 10  # 注入 system 提示的长期记忆条数上限
    # 输出格式约束：原前端 system 消息会被本侧剔除，格式要求统一由 Python 侧下发
    _AI_FORMAT_RULES = (
        "输出格式要求：只使用纯文本，不要使用 Markdown 或 HTML，不要使用反引号与星号加粗；"
        "如需列举，使用纯文本编号或缩进；代码或命令用引号包裹；数学公式用纯文本表达。"
    )
    # 记忆指令：仅在 ai.memory.enabled 开启时追加到 system 提示末尾
    _AI_MEMORY_INSTRUCTION = (
        "记忆标记：如果用户表达了值得长期记住的偏好或设定（如称呼、设备名、使用习惯），"
        "在回复最后另起一行写 [记忆]xx[/记忆]，xx 换成你要记的具体信息，"
        "例如 [记忆]用户喜欢深色主题[/记忆]。没有则不要写这个标记。"
    )

    def _system_context() -> str:
        from core.system_state import system_state

        snap = {}
        try:
            s = system_state.snapshot()
            if isinstance(s, dict):
                snap = s
        except Exception:
            pass

        lines = []
        mon = snap.get("monitor", {}) or {}
        lines.append("CPU使用率: {:.1f}%".format(_num(mon.get("cpu"))))
        lines.append("内存使用率: {:.1f}%".format(_num(mon.get("memory"))))
        lines.append("磁盘使用率: {:.1f}%".format(_num(mon.get("disk"))))

        hw = snap.get("hardware", {}) or {}
        cpu_m = _clean_text((hw.get("cpu") or {}).get("model"), 60)
        gpu_m = _clean_text((hw.get("gpu") or {}).get("name"), 60)
        mem_gb = _num((hw.get("memory") or {}).get("total_gb"))
        hw_bits = []
        if cpu_m:
            hw_bits.append(cpu_m)
        if gpu_m:
            hw_bits.append(gpu_m)
        if mem_gb > 0:
            hw_bits.append("{}GB 内存".format(int(mem_gb)))
        if hw_bits:
            lines.append("硬件: " + ", ".join(hw_bits))

        nas = snap.get("nas", {}) or {}
        if isinstance(nas, dict):
            nas_bits = []
            for name, dv in list(nas.items())[:4]:
                if not isinstance(dv, dict):
                    continue
                clean_name = _clean_text(name, 40)
                if not clean_name:
                    continue
                online_raw = dv.get("online")
                online = not (online_raw is False
                              or str(online_raw).strip().lower() in ("false", "0", "offline", "off"))
                bit = "{}（{}".format(clean_name, "在线" if online else "离线")
                if online:
                    nm = dv.get("memory")
                    npct = nm.get("percent") if isinstance(nm, dict) else nm
                    nd = dv.get("disk")
                    dpct = nd.get("percent") if isinstance(nd, dict) else nd
                    bit += ", CPU {:.1f}%".format(_num(dv.get("cpu")))
                    bit += ", 内存 {:.1f}%".format(_num(npct))
                    bit += ", 磁盘 {:.1f}%".format(_num(dpct))
                    temp = _num(dv.get("temperature"), None)
                    if temp is not None:
                        bit += ", 温度{:.1f}°C".format(temp)
                nas_bits.append(bit + "）")
            if nas_bits:
                lines.append("NAS设备: " + "；".join(nas_bits))

        header = ("你是 DigitalLab 的 AI 助手，必须始终使用中文回答用户问题。\n"
                  "你可以访问以下实时系统状态：")
        # 记忆开关：仅开启时追加记忆指令（关闭时不追加）
        try:
            from core import ai_memory as _aim
            _memory_on = bool(_aim.settings().get("enabled"))
        except Exception:
            _memory_on = False
        suffix = "\n" + _AI_FORMAT_RULES
        if _memory_on:
            suffix += "\n" + _AI_MEMORY_INSTRUCTION
        if not lines:
            return ("你是 DigitalLab 的 AI 助手，必须始终使用中文回答用户问题。\n"
                    "当前系统状态数据不可用。如果用户询问电脑、设备、NAS、性能等相关信息，"
                    "请明确告诉用户暂时无法获取系统数据，不要编造数据。") + suffix
        body = "\n".join(lines)
        if len(body) > 1000:
            body = body[:1000]
        trailer = ("\n当用户询问电脑、设备、NAS、性能等相关问题时，直接引用以上数据回答。\n"
                   "如果系统状态数据不可用，明确告诉用户暂时无法获取，不要编造数据。")
        return header + "\n" + body + trailer + suffix

    # ── AI 流式对话 ──
    def _handle_ai_chat(messages, provider, request_id):
        """在独立线程中执行 AI 流式对话，通过 stdout 推送 token。"""
        def _run():
            from core.ai_client import chat_stream
            def _push_token(token, token_type="content"):
                msg = json.dumps({
                    "type": "ai_token",
                    "data": {"token": token, "kind": token_type},
                    "requestId": request_id,
                }, ensure_ascii=False)
                _safe_print(msg, flush=True)
            try:
                system_ctx = _system_context()
                base_msgs = messages if isinstance(messages, list) else []
                # 历史消息清洗：只保留合法角色；字符串内容做同样的安全清理，避免脏字符回灌模型
                clean_msgs = []
                for m in base_msgs:
                    if not isinstance(m, dict):
                        continue
                    role = str(m.get("role", "")).strip()
                    if role not in ("system", "user", "assistant", "tool"):
                        continue
                    content = m.get("content")
                    if isinstance(content, str):
                        content = _clean_text(content, 4000)
                    clean_msgs.append({"role": role, "content": content})
                # 统一剔除前端遗留的 role=system 消息（系统提示改由 Python 侧下发）
                clean_msgs = [m for m in clean_msgs if m.get("role") != "system"]
                # 仅保留最近若干条历史，防止长对话上下文膨胀或脏数据回灌
                if len(clean_msgs) > _AI_MAX_HISTORY:
                    clean_msgs = clean_msgs[-_AI_MAX_HISTORY:]
                prefix_msgs = []
                if system_ctx:
                    prefix_msgs.append({"role": "system", "content": system_ctx})
                # 记忆开关开启时注入最近若干条长期记忆（独立 system 消息，不占用系统状态预算）
                try:
                    from core import ai_memory as _aim
                    if _aim.settings().get("enabled"):
                        _recent_mem = _aim.load_recent(_AI_MEMORY_LIMIT)
                        _mem_lines = []
                        for _item in _recent_mem:
                            _c = _clean_text(_item.get("content", ""), 200)
                            if _c:
                                _mem_lines.append("- " + _c)
                        if _mem_lines:
                            prefix_msgs.append({
                                "role": "system",
                                "content": "以下是用户此前确认需要长期记住的偏好（越靠后越新）：\n" + "\n".join(_mem_lines),
                            })
                except Exception:
                    pass
                chat_msgs = prefix_msgs + clean_msgs
                result = chat_stream(chat_msgs, provider, on_token=_push_token)
                # 解析并剥离 [记忆]...[/记忆]：无论开关如何都剥离标记，仅在开关开启时写入
                reply_text = result
                memory_saved = []
                try:
                    from core import ai_memory as _aim
                    _found = []
                    if not str(result).startswith("[错误]"):
                        reply_text, _found = _aim.extract_markers(result)
                    if _found and _aim.settings().get("enabled"):
                        for _item in _found:
                            _r = _aim.append(_item)
                            # 库存已有相同内容（归一化比较）时跳过，不写入也不提示“已记住”
                            if _r and not _r.get("duplicate"):
                                memory_saved.append(_item)
                except Exception:
                    memory_saved = []
                # 发送完成信号
                done_msg = json.dumps({
                    "type": "ai_done",
                    "text": reply_text,
                    "memory": memory_saved,
                    "requestId": request_id,
                }, ensure_ascii=False)
                _safe_print(done_msg, flush=True)
            except Exception as e:
                err_msg = json.dumps({
                    "type": "ai_done",
                    "text": f"[错误] {e}",
                    "memory": [],
                    "requestId": request_id,
                }, ensure_ascii=False)
                _safe_print(err_msg, flush=True)
        threading.Thread(target=_run, daemon=True).start()

    # ── 配置管理 ──
    def _get_config_data():
        import json, os
        from dataclasses import asdict
        from core.config import _get_user_config_path, _SENSITIVE_KEYS
        config_path = cfg.config_file
        raw = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception:
                pass
        # 合并用户敏感配置（nas_devices、ai、auth_token 等）
        user_config_path = _get_user_config_path()
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                raw.update(user_data)
            except Exception:
                pass
        # 过滤掉 IPC 协议字段（防止 config.json 被污染后循环传染）
        raw = {k: v for k, v in raw.items()
               if k not in ("__cmd_response__", "requestId")}
        defaults = asdict(cfg)
        defaults.pop("config_file", None)
        for k, v in defaults.items():
            if k not in raw or not raw[k]:
                raw[k] = v
        return raw

    def _save_config_data(new_config):
        import json, os
        from core.config import _get_user_config_path, _SENSITIVE_KEYS, BASE_DATA_DIR
        # 记忆目录变更时迁移旧文件（shutil.copy，不删旧文件；失败不影响保存）
        try:
            _new_ai = new_config.get("ai") if isinstance(new_config, dict) else None
            _new_mem = _new_ai.get("memory") if isinstance(_new_ai, dict) else None
            _new_dir = _new_mem.get("dir") if isinstance(_new_mem, dict) else None
            if isinstance(_new_dir, str) and _new_dir.strip():
                from core import ai_memory as _aim
                _old_dir = _aim.config_dir()
                if _old_dir and os.path.abspath(_old_dir) != os.path.abspath(_new_dir.strip()):
                    _aim.migrate(_old_dir, _new_dir.strip())
        except Exception:
            pass
        config_path = cfg.config_file
        # 安全校验：确保写入路径在 APPDATA\DigitalLab 下，绝不写入安装目录（MSIX 只读）
        _appdata_root = os.path.abspath(BASE_DATA_DIR)
        if not os.path.abspath(config_path).startswith(_appdata_root):
            config_path = os.path.join(BASE_DATA_DIR, "config.json")
        # 过滤掉 IPC 协议字段和路径字段（路径由运行时自动检测，不写入配置文件）
        _skip_keys = {
            "__cmd_response__", "requestId",
            "lab_root", "tools_dir", "logs_dir", "experiments_dir",
            "notes_dir", "archive_dir", "interface_dir",
            "monitor_db_path", "monitor_pid_path", "monitor_log_path",
            "config_file",
        }
        clean = {k: v for k, v in new_config.items() if k not in _skip_keys}
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            # 非敏感字段写入 config.json
            public = {k: v for k, v in clean.items() if k not in _SENSITIVE_KEYS}
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(public, f, indent=2, ensure_ascii=False)
            # 敏感字段（API Key、Token 等）写入 AppData
            sensitive = {k: v for k, v in clean.items() if k in _SENSITIVE_KEYS}
            if sensitive:
                user_config_path = _get_user_config_path()
                # 安全校验：user_config_path 也必须在 APPDATA 下
                if not os.path.abspath(user_config_path).startswith(_appdata_root):
                    user_config_path = os.path.join(BASE_DATA_DIR, "user_config.json")
                user_data = {}
                if os.path.exists(user_config_path):
                    try:
                        with open(user_config_path, "r", encoding="utf-8") as f:
                            user_data = json.load(f)
                    except Exception:
                        pass
                user_data.update(sensitive)
                os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
                with open(user_config_path, "w", encoding="utf-8") as f:
                    json.dump(user_data, f, indent=2, ensure_ascii=False)
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def _test_nas_connection(device):
        import paramiko
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=device.get("host", ""),
                port=device.get("port", 22),
                username=device.get("username", ""),
                password=device.get("password", ""),
                timeout=5,
                banner_timeout=5,
                auth_timeout=5,
            )
            client.close()
            return {"ok": True, "message": "\u8fde\u63a5\u6210\u529f"}
        except Exception as e:
            return {"ok": False, "message": str(e)}

    def _get_nas_devices():
        import json, os
        from core.config import _get_user_config_path
        config_path = cfg.config_file
        devices = []
        # 先从 config.json 读取基础设备列表
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                devices = raw.get("nas_devices", [])
            except Exception:
                pass
        # 用户敏感配置（AppData）中的设备列表覆盖
        user_config_path = _get_user_config_path()
        if os.path.exists(user_config_path):
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    user_data = json.load(f)
                if "nas_devices" in user_data:
                    devices = user_data["nas_devices"]
            except Exception:
                pass
        return devices

    def _handle_command(cmd):
        request_id = cmd.get("requestId")
        ctype = cmd.get("cmd", "")
        resp = None

        try:
            if ctype == "get_hardware":
                payload = _format_state()
                resp = {"hardware": payload.get("hardware")}
            elif ctype == "get_processes":
                payload = _format_state()
                resp = {"processes": payload["monitor"].get("processes", [])}
            elif ctype == "get_history":
                hours = cmd.get("hours", 24)
                resp = _get_history(hours)
            elif ctype == "ai_message":
                # 兼容旧接口：返回占位回复
                text = cmd.get("text", "")
                resp = {"type": "ai_response", "text": "AI \u529f\u80fd\u5df2\u91cd\u6784\uff0c\u8bf7\u4f7f\u7528\u65b0\u7684\u6d41\u5f0f\u5bf9\u8bdd\u63a5\u53e3"}
            elif ctype == "ai_chat":
                # 流式 AI 对话：在独立线程中处理，通过 stdout 推送 token
                messages = cmd.get("messages", [])
                provider = cmd.get("provider", "ollama")
                req_id = cmd.get("requestId", "")
                _handle_ai_chat(messages, provider, req_id)
                resp = {"ok": True, "streaming": True}
            elif ctype == "get_ai_memory":
                from core import ai_memory as _aim
                _st = _aim.settings()
                _items = _aim.list_all()
                resp = {
                    "enabled": bool(_st.get("enabled")),
                    "dir": _st.get("dir", ""),
                    "count": len(_items),
                    "items": [
                        {"index": _i, "ts": _it.get("ts", ""), "content": _it.get("content", "")}
                        for _i, _it in enumerate(_items)
                    ],
                }
            elif ctype == "delete_ai_memory":
                from core import ai_memory as _aim
                try:
                    _idx = int(cmd.get("index"))
                except Exception:
                    _idx = -1
                resp = {"ok": _aim.delete(_idx)}
            elif ctype == "clear_ai_memory":
                from core import ai_memory as _aim
                resp = {"ok": _aim.clear()}
            elif ctype == "ping":
                resp = {"pong": True}
            elif ctype == "get_config":
                resp = _get_config_data()
            elif ctype == "save_config":
                resp = _save_config_data(cmd.get("config", {}))
            elif ctype == "test_nas_connection":
                resp = _test_nas_connection(cmd.get("device", {}))
            elif ctype == "reload_config":
                # 重载配置：逐步独立 try-except，单步失败不阻塞后续
                reload_errors = []
                # 1. 停止所有 NAS 监控线程
                try:
                    stop_nas_monitor()
                except Exception as _e:
                    reload_errors.append("stop_nas: " + str(_e))
                # 2. 清理已删除设备的残留状态
                try:
                    devices = _get_nas_devices()
                    device_names = {d.get("name", "") for d in devices if d.get("name")}
                    nas_state = system_state.get("nas", {})
                    for name in list(nas_state.keys()):
                        if name not in device_names:
                            system_state.delete("nas", name)
                except Exception as _e:
                    reload_errors.append("cleanup: " + str(_e))
                # 3. 重新加载配置
                try:
                    cfg.reload()
                except Exception as _e:
                    reload_errors.append("reload: " + str(_e))
                # 4. 重启 NAS 监控
                try:
                    start_nas_monitor()
                except Exception as _e:
                    reload_errors.append("start_nas: " + str(_e))

                if reload_errors:
                    resp = {"ok": True, "message": "\u914d\u7f6e\u5df2\u91cd\u8f7d\uff08\u90e8\u5206\u9519\u8bef\uff09", "warnings": reload_errors}
                else:
                    resp = {"ok": True, "message": "\u914d\u7f6e\u5df2\u91cd\u8f7d"}
            elif ctype == "get_nas_devices":
                resp = {"devices": _get_nas_devices()}
            elif ctype == "terminal_input":
                _handle_terminal_input(cmd.get("session_id"), cmd.get("data", ""))
                resp = {"ok": True}
            elif ctype == "terminal_resize":
                _handle_terminal_resize(cmd.get("session_id"), cmd.get("cols", 80), cmd.get("rows", 24))
                resp = {"ok": True}
            elif ctype == "terminal_close":
                _handle_terminal_close(cmd.get("session_id"))
                resp = {"ok": True}
            elif ctype == "ssh_terminal_init":
                resp = _handle_ssh_terminal_init(
                    cmd.get("host", ""), cmd.get("port", 22),
                    cmd.get("cols", 80), cmd.get("rows", 24),
                )
            else:
                resp = {"error": "unknown command"}
        except Exception as _e:
            # 顶层兜底：任何未捕获异常都返回 error 响应，绝不抛出
            resp = {"error": "handler error: " + str(_e)}

        if resp is None:
            resp = {"error": "handler returned None"}
        resp["__cmd_response__"] = True
        if request_id:
            resp["requestId"] = request_id
        return json.dumps(resp, ensure_ascii=False)

    def _get_history(hours):
        from core.monitor import query_history
        try:
            history = query_history(hours * 3600)
            if not history:
                return {"error": "no data"}
            if "error" in history:
                return {"error": history["error"], "count": history.get("count", 0)}
            return {
                "cpu_avg": history.get("cpu_avg", 0),
                "cpu_max": history.get("cpu_max", 0),
                "memory_avg": history.get("memory_avg", 0),
                "memory_max": history.get("memory_max", 0),
                "disk_avg": history.get("disk_avg", 0),
                "disk_max": history.get("disk_max", 0),
                "count": history.get("count", 0),
            }
        except Exception as e:
            return {"error": str(e)}

    def _stdin_reader():
        for line in sys.stdin:
            try:
                line = line.strip()
                if not line:
                    continue
                try:
                    cmd = json.loads(line)
                except json.JSONDecodeError:
                    _safe_print(json.dumps({"error": "invalid JSON"}), flush=True)
                    continue
                resp = _handle_command(cmd)
                _safe_print(resp, flush=True)
            except Exception as _e:
                # 任何异常都不能杀死 stdin 读取线程，否则后续命令全部无响应
                try:
                    err_resp = json.dumps({
                        "error": "command processing error: " + str(_e),
                        "__cmd_response__": True,
                    }, ensure_ascii=False)
                    _safe_print(err_resp, flush=True)
                except Exception:
                    pass

    # 启动 stdin 监听线程
    stdin_thread = threading.Thread(target=_stdin_reader, daemon=True)
    stdin_thread.start()

    # 主循环：每秒推送状态
    running = True
    while running:
        try:
            payload = _format_state()
            _safe_print(json.dumps(payload, ensure_ascii=False), flush=True)
            time.sleep(1)
        except (BrokenPipeError, IOError):
            running = False
        except KeyboardInterrupt:
            running = False
        except Exception:
            time.sleep(1)


def cmd_system_state(args=None):
    from core.system_state import system_state
    from core.renderer import (
        render_cli, render_cli_hardware, render_cli_snapshot, render_cli_logs,
    )

    sub = getattr(args, "subcommand", None)
    snap = system_state.snapshot()

    if sub == "monitor":
        _safe_print(render_cli(snap))

    elif sub == "hardware":
        _safe_print(render_cli_hardware(snap))

    elif sub == "snapshot":
        _safe_print(render_cli_snapshot(snap))

    elif sub == "logs":
        _safe_print(render_cli_logs(snap))

    else:
        _safe_print("")
        _safe_print("=" * 56)
        _safe_print("  system_state (全部命名空间)")
        _safe_print("-" * 56)
        for ns_name in sorted(snap.keys()):
            ns = snap[ns_name]
            if isinstance(ns, dict):
                top_keys = list(ns.keys())[:6]
                _safe_print("  [{}]  {} keys: {}".format(
                    ns_name, len(ns), ", ".join(str(k) for k in top_keys)))
            else:
                _safe_print("  [{}]  type={}".format(ns_name, type(ns).__name__))
        _safe_print("=" * 56)
        _safe_print("")
        _safe_print("  子命令: dl state monitor | hardware | snapshot | logs")
        _safe_print("")


def cmd_hardware_refresh(args=None):
    from core.hardware import collect_all, invalidate_cache
    from core.system_state import system_state
    _safe_print("正在采集硬件信息...")
    invalidate_cache()
    data = collect_all(use_cache=False)
    _safe_print("[OK] 硬件信息已更新到 system_state[\"hardware\"]")
    cpu = data.get("cpu") or {}
    mem = data.get("memory") or {}
    _safe_print("  CPU: {}".format(cpu.get("model", "-")[:60]))
    _safe_print("  Memory: {:.1f} GB".format(mem.get("total_gb", 0)))
    _safe_print("  类型: {}".format(data.get("_device_type", "-")))


# ============================================================
#  交互式终端（State-Driven Command Prompt）
# ============================================================

_STATE_PROMPT = """  DigitalLab > 输入命令 (help / state / monitor / snapshot / hardware / init / ...)
"""


def _state_repl():
    import json

    _cli_header()
    _safe_print("")
    _safe_print("  State-Driven Command System — 输入 help 查看命令")
    _safe_print("  state = 查看系统状态 | monitor = 查看监控 | snapshot = 快照管理")
    _safe_print("-" * 56)

    while True:
        choice = _safe_input(_STATE_PROMPT).strip().lower()
        if not choice:
            continue
        if choice in ("0", "q", "quit", "exit"):
            break

        _safe_print("")

        # ── state queries (READ from system_state) ──
        if choice == "state" or choice == "system":
            cmd_system_state()

        elif choice == "state monitor" or choice == "monitor":
            from core.system_state import system_state
            from core.renderer import render_cli
            _safe_print(render_cli(system_state.snapshot()))

        elif choice == "state hardware" or choice == "hardware":
            cmd_system_state(types.SimpleNamespace(subcommand="hardware"))

        elif choice == "state snapshot" or choice.startswith("snapshot"):
            parts = choice.split()
            if len(parts) >= 2 and parts[1] == "list":
                cmd_system_state(types.SimpleNamespace(subcommand="snapshot"))
                cmd_snapshot(types.SimpleNamespace(subcommand="list", note="", snap_id1=None, snap_id2=None))
            elif len(parts) >= 2 and parts[1] == "create":
                cmd_snapshot()
            else:
                cmd_system_state(types.SimpleNamespace(subcommand="snapshot"))

        elif choice == "state logs" or choice == "logs":
            cmd_system_state(types.SimpleNamespace(subcommand="logs"))

        # ── write operations ──
        elif choice == "init":
            cmd_init()

        elif choice == "config":
            cmd_config()

        elif choice == "status":
            from core.system_state import system_state
            from core.renderer import render_cli_status
            _safe_print(render_cli_status(system_state.snapshot()))

        elif choice == "report":
            cmd_report()

        elif choice == "launcher":
            cmd_launcher()

        elif choice == "hardware refresh":
            cmd_hardware_refresh()

        elif choice in ("?", "help", "h"):
            _safe_print("=== 可用命令 ===")
            _safe_print("  state             查看 system_state 全貌")
            _safe_print("  monitor           查看实时监控状态")
            _safe_print("  hardware          查看硬件信息")
            _safe_print("  hardware refresh  重新采集硬件信息")
            _safe_print("  snapshot list     查看快照列表")
            _safe_print("  snapshot create   创建新快照")
            _safe_print("  logs              查看日志计数")
            _safe_print("  init              初始化目录结构")
            _safe_print("  status            系统状态")
            _safe_print("  config            刷新配置文件")
            _safe_print("  report            生成分析报告")
            _safe_print("  q / quit          退出")

        else:
            _safe_print("[!] 未知命令: {}。输入 help 查看可用命令。".format(choice))

        _safe_print("")

    _safe_print("")
    _safe_print("感谢使用 DigitalLab，再见！")
    _safe_print("")


# ============================================================
#  命令行入口
# ============================================================

def _cli_mode():
    parser = argparse.ArgumentParser(
        prog="dlab",
        description="DigitalLab - 个人数字实验室 (工具 + 实验 + AI助手)",
    )
    parser.add_argument("--json-mode", action="store_true", help="JSON 行协议模式 (stdin/stdout)")
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    subparsers.add_parser("init", help="初始化目录结构")
    subparsers.add_parser("status", help="显示系统状态")
    subparsers.add_parser("config", help="生成默认配置文件")

    # state / system 查询
    p_state = subparsers.add_parser("state", help="查看 system_state（全局状态中心）")
    state_subs = p_state.add_subparsers(dest="subcommand")
    state_subs.add_parser("monitor", help="查看 monitor 命名空间")
    state_subs.add_parser("hardware", help="查看 hardware 命名空间")
    state_subs.add_parser("snapshot", help="查看 snapshot 命名空间")
    state_subs.add_parser("logs", help="查看 logs 命名空间")

    p_hw = subparsers.add_parser("hardware", help="硬件信息")
    hw_subs = p_hw.add_subparsers(dest="subcommand")
    hw_subs.add_parser("info", help="显示已缓存硬件信息")
    hw_subs.add_parser("refresh", help="强制刷新硬件信息")

    p_monitor = subparsers.add_parser("monitor", help="查看系统监控")
    p_monitor.add_argument("--live", "-l", action="store_true", help="实时刷新模式")
    p_monitor.add_argument("--interval", "-n", type=float, default=2.0, help="刷新/采集间隔(秒)")
    p_monitor.add_argument("--alert-test", action="store_true", help="强制触发告警测试")
    p_monitor.add_argument("--daemon", action="store_true", help="启动后台守护模式")
    p_monitor.add_argument("--stop", action="store_true", help="停止守护进程")
    p_monitor.add_argument("--daemon-status", action="store_true", help="查看守护进程状态")
    p_monitor.add_argument("--compare", choices=["7d", "24h", "1h", "30m"], help="历史对比")

    p_launch = subparsers.add_parser("launcher", help="启动快捷面板")
    p_launch.add_argument("--add", type=str, default=None, metavar="NAME", help="添加快捷方式")
    p_launch.add_argument("--path", type=str, default=None, metavar="PATH", help="程序路径 (配合 --add)")
    p_launch.add_argument("--remove", type=str, default=None, metavar="NAME", help="删除快捷方式")

    p_report = subparsers.add_parser("report", help="生成分析报告")
    p_report.add_argument("--source", default="monitor", choices=["monitor"], help="数据源")
    p_report.add_argument("--days", type=int, default=None, help="读取最近 N 天数据")
    p_report.add_argument("--hours", type=int, default=None, help="读取最近 N 小时数据")

    # snapshot with subcommands
    p_snap = subparsers.add_parser("snapshot", help="系统快照管理")
    snap_subs = p_snap.add_subparsers(dest="subcommand")
    snap_subs.add_parser("list", help="列出所有快照")
    p_snap_del = snap_subs.add_parser("delete", help="删除快照")
    p_snap_del.add_argument("snap_id1", nargs="?", help="快照 ID")
    p_snap_rep = snap_subs.add_parser("report", help="生成快照报告")
    p_snap_rep.add_argument("snap_id1", nargs="?", help="快照 ID")
    p_snap_cmp = snap_subs.add_parser("compare", help="对比两个快照")
    p_snap_cmp.add_argument("snap_id1", nargs="?", help="快照 1 ID")
    p_snap_cmp.add_argument("snap_id2", nargs="?", help="快照 2 ID")
    p_snap_create = snap_subs.add_parser("create", help="创建新快照")
    p_snap_create.add_argument("--note", "-n", default="", help="备注说明")

    args = parser.parse_args()

    if args.json_mode:
        cmd_json_mode()
        return

    _CLI_COMMANDS = {
        "init": cmd_init,
        "status": cmd_status,
        "config": cmd_config,
        "monitor": cmd_monitor,
        "report": cmd_report,
        "launcher": cmd_launcher,
        "snapshot": cmd_snapshot,
        "state": cmd_system_state,
        "hardware": lambda a: (
            cmd_hardware_refresh(a) if getattr(a, "subcommand", None) == "refresh"
            else cmd_system_state(types.SimpleNamespace(subcommand="hardware"))
        ),
    }

    if args.command in _CLI_COMMANDS:
        _CLI_COMMANDS[args.command](args)
    else:
        parser.print_help()


def main():
    _setup_windows_console()
    _check_python()

    if os.environ.get("DLAB_DAEMON") != "1":
        lab_root = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
        config_path = os.path.join(lab_root, "config.json")
        from core.config_validator import run_validator, format_report
        report = run_validator(config_path)
        if report:
            _safe_print(format_report(report))
        from core.system_state import system_state
        from core.config import get_config
        cfg = get_config()
        dirs_status = []
        for name in ("tools", "logs", "experiments", "notes", "archive", "interface"):
            d = getattr(cfg, name + "_dir", "")
            dirs_status.append({"name": name, "ok": os.path.isdir(d) if d else False, "path": d or ""})
        system_state["status"] = {
            "python_version": _get_python_info(),
            "platform": _get_system_info(),
            "dirs": dirs_status,
        }

    if os.environ.get("DLAB_DAEMON") == "1":
        pidfile = os.environ.get("DLAB_DAEMON_PIDFILE", "")
        interval = int(os.environ.get("DLAB_DAEMON_INTERVAL", "60"))
        from core.daemon import run_daemon_loop
        run_daemon_loop(pidfile, interval)
        return

    from core.collector import start_collector
    start_collector()

    # 启动 NAS 远程监控
    from core.nas_monitor import start_nas_monitor
    start_nas_monitor()

    if len(sys.argv) > 1:
        _cli_mode()
    else:
        try:
            _state_repl()
        except KeyboardInterrupt:
            _safe_print("")
            _safe_print("已中断。")
            _safe_print("")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _safe_print("")
        _safe_print("已中断。")
        sys.exit(0)
    except Exception as e:
        _safe_print("[ERROR] {}".format(e))
        sys.exit(1)
