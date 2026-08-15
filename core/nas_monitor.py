"""
NAS 远程监控采集模块
通过 SSH 连接局域网内的 NAS 设备，采集 CPU、内存、磁盘、温度、运行时间等指标。
采集线程独立运行，数据写入 system_state["nas"]。
"""
from __future__ import annotations

import threading
import time
import re
import json
import os
from typing import Optional

import paramiko

from core.config import get_config
from core.system_state import system_state
from core.logger import log_error, log_info, log_warn

_threads: dict[str, threading.Thread] = {}
_stop_events: dict[str, threading.Event] = {}
_started = False
_last_docker_collect: dict[str, float] = {}


def _parse_cpu(top_output: str) -> Optional[float]:
    """解析 top -bn1 输出中的 CPU 使用率"""
    # 格式: %Cpu(s):  5.2 us,  2.1 sy,  0.0 ni, 92.0 id,  0.5 wa,  0.0 hi,  0.2 si,  0.0 st
    # 或: Cpu(s): 12.5%us, 3.2%sy, ...
    # 计算 100 - idle
    idle_match = re.search(r'(\d+\.?\d*)\s*id', top_output)
    if idle_match:
        return round(100.0 - float(idle_match.group(1)), 1)

    # 备选: 匹配百分号格式
    pct_match = re.search(r'(\d+\.?\d*)\s*%?\s*id', top_output)
    if pct_match:
        return round(100.0 - float(pct_match.group(1)), 1)

    return None


def _parse_memory(free_output: str) -> Optional[dict]:
    """解析 free -m 输出，返回 {used_gb, total_gb, percent}"""
    # 格式:
    #               total        used        free      shared  buff/cache   available
    # Mem:          15976        3142        8192         123        4642       12456
    lines = free_output.strip().split('\n')
    for line in lines:
        if line.startswith('Mem:') or line.startswith('内存'):
            parts = line.split()
            # 找到数字列
            nums = [p for p in parts if re.match(r'^\d+$', p)]
            if len(nums) >= 2:
                total_mb = float(nums[0])
                used_mb = float(nums[1])
                total_gb = round(total_mb / 1024, 1)
                used_gb = round(used_mb / 1024, 1)
                percent = round(used_mb / total_mb * 100, 1) if total_mb > 0 else 0
                return {"used_gb": used_gb, "total_gb": total_gb, "percent": percent}
    return None


def _parse_disk(df_output: str) -> Optional[dict]:
    """解析 df -h / 输出，返回 {used_gb, total_gb, percent}"""
    lines = df_output.strip().split('\n')
    for line in lines[1:]:  # 跳过标题行
        parts = line.split()
        if len(parts) >= 5:
            # 格式: Filesystem  Size  Used  Avail  Use%  Mounted on
            try:
                total_str = parts[1]  # e.g. "1.8T" or "500G"
                used_str = parts[2]
                pct_str = parts[4].rstrip('%')
                total_gb = _size_to_gb(total_str)
                used_gb = _size_to_gb(used_str)
                percent = float(pct_str)
                return {"used_gb": used_gb, "total_gb": total_gb, "percent": percent}
            except (ValueError, IndexError):
                continue
    return None


def _size_to_gb(size_str: str) -> float:
    """将 df 输出的大小字符串转换为 GB"""
    size_str = size_str.upper().strip()
    multipliers = {"T": 1024, "G": 1, "M": 1 / 1024, "K": 1 / 1048576}
    for unit, mult in multipliers.items():
        if size_str.endswith(unit):
            try:
                return round(float(size_str[:-1]) * mult, 1)
            except ValueError:
                pass
    try:
        return round(float(size_str), 1)
    except ValueError:
        return 0


def _parse_temp(sensors_output: str) -> Optional[float]:
    """解析 sensors 或 /sys/class/thermal 输出，提取最高温度"""
    # 格式1: temp1: +45.0°C 或 CPU: 55.0°C (lm-sensors)
    temps = re.findall(r'\+?(\d+\.?\d*)\s*°?C', sensors_output)
    if temps:
        return max(float(t) for t in temps)
    # 格式2: /sys/class/thermal/thermal_zone*/temp (毫度, 如 45000 = 45.0°C)
    millideg = re.findall(r'\b(\d{4,6})\b', sensors_output)
    if millideg:
        vals = [float(v) / 1000 for v in millideg if 1000 < float(v) < 200000]
        if vals:
            return round(max(vals), 1)
    return None


def _parse_uptime(uptime_output: str) -> Optional[str]:
    """解析 uptime 输出"""
    # 格式: 14:30:15 up 12 days,  3:45,  2 users,  load average: 0.15, 0.10, 0.05
    match = re.search(r'up\s+(.+?),\s+\d+\s+user', uptime_output)
    if match:
        return match.group(1).strip()
    return uptime_output.strip()


def _parse_load(uptime_output: str) -> Optional[dict]:
    """解析 uptime 输出中的 load average"""
    match = re.search(r'load average:\s+([\d.]+),\s+([\d.]+),\s+([\d.]+)', uptime_output)
    if match:
        return {
            "load_1m": float(match.group(1)),
            "load_5m": float(match.group(2)),
            "load_15m": float(match.group(3)),
        }
    return None


def _parse_processes(top_output: str) -> list[dict]:
    """解析 top -bn1 输出中的进程列表，返回 TOP15"""
    processes = []
    lines = top_output.strip().split('\n')
    # 找到 PID USER ... COMMAND 标题行
    start_idx = None
    for i, line in enumerate(lines):
        if 'PID' in line and 'COMMAND' in line:
            start_idx = i + 1
            break
    if start_idx is None:
        return []
    # 解析前 15 个进程
    count = 0
    for line in lines[start_idx:]:
        parts = re.findall(r'\S+', line.strip())
        if len(parts) < 11:
            continue
        try:
            pid = parts[0]
            cpu = float(parts[8])
            mem = float(parts[9])
            cmd = ' '.join(parts[11:])
            name = cmd.split()[0] if cmd else "unknown"
            # 截取进程名（去掉路径）
            if '/' in name:
                name = name.rsplit('/', 1)[-1]
            processes.append({
                "pid": pid,
                "name": name,
                "cpu": cpu,
                "memory": mem,
                "command": cmd,
            })
            count += 1
            if count >= 15:
                break
        except (ValueError, IndexError):
            continue
    return processes


def _parse_docker_ps(ps_output: str) -> Optional[list[dict]]:
    """解析 docker ps -a --format '{{json .}}' 输出"""
    if not ps_output or ps_output.strip() in ('', '[]'):
        return []
    containers = []
    for line in ps_output.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            containers.append({
                "name": obj.get("Names", ""),
                "image": obj.get("Image", ""),
                "status": obj.get("Status", ""),
            })
        except json.JSONDecodeError:
            continue
    return containers


def _exec_ssh(client, cmd: str) -> str:
    """执行 SSH 命令，返回 strip() 后的字符串，失败返回空字符串"""
    try:
        _, stdout, stderr = client.exec_command(cmd, timeout=5)
        output = stdout.read().decode("utf-8", errors="replace").strip()
        if not output:
            output = stderr.read().decode("utf-8", errors="replace").strip()
        return output
    except Exception:
        return ""


def _collect_nas(device: dict, stop_event: threading.Event):
    """单台 NAS 设备的采集线程"""
    name = device.get("name", "unknown")
    host = device.get("host", "")
    port = device.get("port", 22)
    username = device.get("username", "")
    password = device.get("password", "")
    interval = device.get("interval", 15)
    # 确保最小间隔 5 秒
    if interval < 5:
        interval = 5

    log_info(f"NAS [{name}] 采集线程已启动", host=host, interval=interval)

    while not stop_event.is_set():
        client = None
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10,
            )

            data = {"online": True, "name": name, "host": host}

            # 首次连接成功后采集硬件规格信息（仅一次）
            existing_data = system_state.get("nas", {}).get(name, {})
            if not existing_data.get("hardware"):
                data["hardware"] = {
                    "cpu_model": _exec_ssh(client, "cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d: -f2 | sed -e 's/^ *//'"),
                    "cpu_cores": _exec_ssh(client, "nproc"),
                    "memory_total": _exec_ssh(client, "free -h | grep Mem | awk '{print $2}'"),
                    "disk_total": _exec_ssh(client, "df -h / | tail -1 | awk '{print $2}'"),
                    "disk_model": _exec_ssh(client, "lsblk -d -o name,model,size 2>/dev/null | grep -v NAME | head -1 | awk '{print $2, $3}' | sed -e 's/^ *//'"),
                    "os": _exec_ssh(client, "cat /etc/os-release 2>/dev/null | grep PRETTY_NAME | cut -d= -f2 | tr -d '\"'") or _exec_ssh(client, "uname -a"),
                }
            else:
                data["hardware"] = existing_data["hardware"]

            # 采集 CPU + 进程 TOP15（一次 top -bn1 调用）
            try:
                _, stdout, _ = client.exec_command("top -bn1", timeout=10)
                top_output = stdout.read().decode("utf-8", errors="replace")
                cpu = _parse_cpu(top_output)
                if cpu is not None:
                    data["cpu"] = cpu
                processes = _parse_processes(top_output)
                if processes:
                    data["processes"] = processes
            except Exception as e:
                log_warn(f"NAS [{name}] CPU/进程采集失败", error=str(e))

            # 采集内存
            try:
                _, stdout, _ = client.exec_command("free -m", timeout=10)
                mem_output = stdout.read().decode("utf-8", errors="replace")
                mem = _parse_memory(mem_output)
                if mem:
                    data["memory"] = mem
            except Exception as e:
                log_warn(f"NAS [{name}] 内存采集失败", error=str(e))

            # 采集磁盘
            try:
                _, stdout, _ = client.exec_command("df -h /", timeout=10)
                disk_output = stdout.read().decode("utf-8", errors="replace")
                disk = _parse_disk(disk_output)
                if disk:
                    data["disk"] = disk
            except Exception as e:
                log_warn(f"NAS [{name}] 磁盘采集失败", error=str(e))

            # 采集温度
            try:
                _, stdout, _ = client.exec_command(
                    "sensors 2>/dev/null || cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null",
                    timeout=10,
                )
                temp_output = stdout.read().decode("utf-8", errors="replace")
                if temp_output.strip():
                    temp = _parse_temp(temp_output)
                    if temp is not None:
                        data["temperature"] = temp
            except Exception:
                pass  # 温度采集非必须，静默跳过

            # 采集 uptime 和 load
            try:
                _, stdout, _ = client.exec_command("uptime", timeout=10)
                uptime_output = stdout.read().decode("utf-8", errors="replace")
                if uptime_output.strip():
                    uptime = _parse_uptime(uptime_output)
                    if uptime:
                        data["uptime"] = uptime
                    load_info = _parse_load(uptime_output)
                    if load_info:
                        data["load"] = load_info
            except Exception:
                pass

            # 采集 Docker 容器状态（低频，30 秒一次）
            try:
                _now = time.time()
                if _now - _last_docker_collect.get(name, 0) >= 30:
                    _last_docker_collect[name] = _now
                    _, stdout, _ = client.exec_command(
                        "docker ps -a --format '{{json .}}' 2>/dev/null || echo '[]'",
                        timeout=10,
                    )
                    docker_output = stdout.read().decode("utf-8", errors="replace")
                    containers = _parse_docker_ps(docker_output)
                    if containers is not None:
                        running = sum(1 for c in containers if c.get("status", "").lower().startswith("up"))
                        data["docker"] = {
                            "containers": containers,
                            "total_containers": len(containers),
                            "running": running,
                            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        }
            except Exception:
                pass  # Docker 不存在或采集失败，静默跳过，保留旧数据

            data["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            data["last_error"] = None

            system_state.update("nas", name, data)

        except Exception as e:
            error_msg = str(e)
            log_error(f"NAS [{name}] 连接失败", error=error_msg, host=host)

            # 保留上次已知数据，更新离线和错误状态
            existing = system_state.get("nas", {}).get(name, {})
            existing.update({
                "name": name,
                "host": host,
                "online": False,
                "last_error": error_msg,
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            })
            system_state.update("nas", name, existing)

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

        # 等待下一次采集（分段等待以响应停止信号）
        wait_remaining = interval
        while wait_remaining > 0 and not stop_event.is_set():
            time.sleep(min(1, wait_remaining))
            wait_remaining -= 1

    log_info(f"NAS [{name}] 采集线程已停止")


def _collect_mock_nas(stop_event: threading.Event):
    """Mock NAS 数据生成器，用于开发测试。
    模拟真实 NAS 的数据结构，通过 system_state.update("nas", ...) 注入。
    """
    import random

    name = "Mock-NAS"
    host = "127.0.0.1"
    interval = 15

    log_info(f"NAS [{name}] Mock 模式已启动", interval=interval)

    _process_templates = [
        {"name": "smbd", "cmd": "/usr/sbin/smbd --foreground --no-process-group"},
        {"name": "nginx", "cmd": "nginx: worker process"},
        {"name": "mysqld", "cmd": "/usr/sbin/mysqld --basedir=/usr"},
        {"name": "python3", "cmd": "python3 /app/server.py"},
        {"name": "dockerd", "cmd": "dockerd --log-level=info"},
        {"name": "sshd", "cmd": "sshd: /usr/sbin/sshd -D"},
        {"name": "cron", "cmd": "/usr/sbin/cron -f"},
        {"name": "containerd", "cmd": "containerd --config /etc/containerd/config.toml"},
    ]

    _docker_templates = [
        {"name": "portainer", "image": "portainer/portainer-ce:latest", "status": "Up 3 days"},
        {"name": "nginx-proxy", "image": "nginx:alpine", "status": "Up 3 days"},
        {"name": "filebrowser", "image": "filebrowser/filebrowser:latest", "status": "Up 3 days"},
        {"name": "mysql", "image": "mysql:8.0", "status": "Up 3 days"},
        {"name": "redis", "image": "redis:alpine", "status": "Exited (0) 2 days ago"},
    ]

    _pid_base = 1000

    while not stop_event.is_set():
        total_mem_gb = 16.0
        used_mem_gb = round(random.uniform(2.5, 9.0), 1)
        total_disk_gb = 2000.0
        used_disk_gb = round(random.uniform(300, 900), 1)

        data = {
            "name": name,
            "host": host,
            "online": True,
            "hardware": {
                "cpu_model": "Intel Celeron J4125 @ 2.0GHz",
                "cpu_cores": "4",
                "memory_total": "16Gi",
                "disk_total": "2.0T",
                "disk_model": "WD Red",
                "os": "OpenMediaVault 6 (Debian 11)",
            },
            "cpu": round(random.uniform(5, 45), 1),
            "memory": {
                "used_gb": used_mem_gb,
                "total_gb": total_mem_gb,
                "percent": round(used_mem_gb / total_mem_gb * 100, 1),
            },
            "disk": {
                "used_gb": used_disk_gb,
                "total_gb": total_disk_gb,
                "percent": round(used_disk_gb / total_disk_gb * 100, 1),
            },
            "temperature": round(random.uniform(38, 62), 1),
            "uptime": "{} days, {:02d}:{:02d}".format(
                random.randint(1, 30), random.randint(0, 23), random.randint(0, 59)
            ),
            "load": {
                "load_1m": round(random.uniform(0.1, 2.5), 2),
                "load_5m": round(random.uniform(0.1, 2.0), 2),
                "load_15m": round(random.uniform(0.1, 1.5), 2),
            },
            "processes": [
                {
                    "pid": str(_pid_base + i * 100 + random.randint(0, 99)),
                    "name": t["name"],
                    "cpu": round(random.uniform(0.1, 8.0), 1),
                    "memory": round(random.uniform(0.3, 5.0), 1),
                    "command": t["cmd"],
                }
                for i, t in enumerate(_process_templates)
            ],
            "docker": {
                "containers": _docker_templates,
                "total_containers": len(_docker_templates),
                "running": sum(1 for c in _docker_templates if c["status"].lower().startswith("up")),
                "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            },
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_error": None,
        }
        system_state.update("nas", name, data)

        wait_remaining = interval
        while wait_remaining > 0 and not stop_event.is_set():
            time.sleep(min(1, wait_remaining))
            wait_remaining -= 1

    log_info(f"NAS [{name}] Mock 模式已停止")


def start_nas_monitor():
    """启动所有启用的 NAS 设备采集线程（含 Mock 模式）"""
    global _started, _threads, _stop_events

    if _started:
        return

    config = get_config()
    config_path = config.config_file
    raw_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                raw_config = json.load(f)
        except Exception:
            pass

    devices = raw_config.get("nas_devices", [])
    mock_enabled = raw_config.get("nas_mock_enabled", False)

    # ── Mock 模式：无真实设备时提供测试数据 ──
    if mock_enabled:
        stop_event = threading.Event()
        thread = threading.Thread(
            target=_collect_mock_nas,
            args=(stop_event,),
            daemon=True,
            name="nas-mock",
        )
        _threads["Mock-NAS"] = thread
        _stop_events["Mock-NAS"] = stop_event
        thread.start()
        _started = True
        log_info("NAS Mock 模式已启用（模拟数据）")
        if not devices:
            return

    if not devices:
        return

    enabled_count = 0
    for device in devices:
        if device.get("enabled") is False:
            continue
        name = device.get("name", "")
        if not name or not device.get("host"):
            log_warn("NAS 设备配置不完整，跳过", name=name, host=device.get("host"))
            continue

        stop_event = threading.Event()
        thread = threading.Thread(
            target=_collect_nas,
            args=(device, stop_event),
            daemon=True,
            name=f"nas-{name}",
        )
        _threads[name] = thread
        _stop_events[name] = stop_event
        thread.start()
        enabled_count += 1

    _started = True
    if enabled_count > 0:
        log_info(f"NAS 监控已启动，共 {enabled_count} 台设备")


def stop_nas_monitor():
    """停止所有 NAS 采集线程"""
    global _started, _threads, _stop_events

    if not _started:
        return

    for name, event in _stop_events.items():
        event.set()

    for name, thread in _threads.items():
        thread.join(timeout=3)

    _threads.clear()
    _stop_events.clear()
    _started = False
    log_info("NAS 监控已停止")