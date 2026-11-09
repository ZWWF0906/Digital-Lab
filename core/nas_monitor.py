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

from core import ssh_trust
from core.config import get_config
from core.system_state import system_state
from core.logger import log_error, log_info, log_warn

_threads: dict[str, threading.Thread] = {}
_stop_events: dict[str, threading.Event] = {}
_started = False
_last_docker_collect: dict[str, float] = {}
_docker_lock = threading.Lock()

# U01：远端 SSH 输出先经过本文件的 schema 约束，再进入 system_state。
# Renderer 仍必须用 textContent 渲染；这里是第一层边界，不是唯一防线。
_MAX_NAS_DEVICES = 64
_MAX_PROCESSES = 15
_MAX_CONTAINERS = 100


def _clean_text(value, max_len, single_line=True):
    """把远端值转为有界纯文本；只去除控制字符，不把 HTML 当作可信内容。"""
    if value is None:
        return ""
    text = str(value)
    if single_line:
        text = text.replace("\r", " ").replace("\n", " ")
    text = "".join(ch for ch in text if ch == "\t" or ord(ch) >= 32)
    return text[:max_len]


def _safe_last_error(value, fallback="nas.err.collectFailed"):
    """W-07：last_error 只暴露内部稳定错误码，绝不把异常文本/URL/凭据给渲染进程。"""
    text = str(value) if value is not None else ""
    if 1 <= len(text) <= 80 and all(ch.isalnum() or ch in "._:-" for ch in text):
        return text
    return fallback


def _safe_num(value, low, high, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number or number in (float("inf"), float("-inf")):
        return default
    return max(low, min(high, number))


def _safe_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _sanitize_hardware(value):
    if not isinstance(value, dict):
        return {}
    result = {}
    for key, limit in (
        ("cpu_model", 160), ("cpu_cores", 32), ("memory_total", 40),
        ("disk_total", 40), ("disk_model", 160), ("os", 160),
    ):
        if key in value:
            result[key] = _clean_text(value.get(key), limit)
    return result


def _sanitize_nas_entry(value):
    if not isinstance(value, dict):
        return {}
    out = {
        "online": _safe_bool(value.get("online", True)),
        "name": _clean_text(value.get("name", ""), 64),
        "host": _clean_text(value.get("host", ""), 128),
        "ssh_trust": _clean_text(value.get("ssh_trust", ""), 32),
        "fingerprint": _clean_text(value.get("fingerprint", ""), 128),
        "last_error": _clean_text(value.get("last_error", ""), 200),
        "last_updated": _clean_text(value.get("last_updated", ""), 32),
    }
    if "is_mock" in value:
        out["is_mock"] = _safe_bool(value.get("is_mock"))
    if "cpu" in value:
        out["cpu"] = round(_safe_num(value.get("cpu"), 0, 100), 1)
    mem = value.get("memory")
    if isinstance(mem, dict):
        out["memory"] = {
            "percent": round(_safe_num(mem.get("percent"), 0, 100), 1),
            "used_gb": round(_safe_num(mem.get("used_gb"), 0, 1e9), 2),
            "total_gb": round(_safe_num(mem.get("total_gb"), 0, 1e9), 2),
        }
    disk = value.get("disk")
    if isinstance(disk, dict):
        out["disk"] = {
            "percent": round(_safe_num(disk.get("percent"), 0, 100), 1),
            "used_gb": round(_safe_num(disk.get("used_gb"), 0, 1e9), 2),
            "total_gb": round(_safe_num(disk.get("total_gb"), 0, 1e9), 2),
        }
    if "temperature" in value:
        out["temperature"] = round(_safe_num(value.get("temperature"), -50, 200), 1)
    if "uptime" in value:
        out["uptime"] = _clean_text(value.get("uptime"), 120)
    load = value.get("load")
    if isinstance(load, dict):
        out["load"] = {
            "load_1m": round(_safe_num(load.get("load_1m"), 0, 1e6), 2),
            "load_5m": round(_safe_num(load.get("load_5m"), 0, 1e6), 2),
            "load_15m": round(_safe_num(load.get("load_15m"), 0, 1e6), 2),
        }
    out["hardware"] = _sanitize_hardware(value.get("hardware"))
    processes = value.get("processes")
    if isinstance(processes, list):
        out["processes"] = [
            {
                "pid": _clean_text(p.get("pid", ""), 24),
                "name": _clean_text(p.get("name", ""), 128),
                "cpu": round(_safe_num(p.get("cpu"), 0, 100), 1),
                "memory": round(_safe_num(p.get("memory"), 0, 100), 1),
                "command": _clean_text(p.get("command", ""), 256),
            }
            for p in processes[:_MAX_PROCESSES] if isinstance(p, dict)
        ]
    docker = value.get("docker")
    if isinstance(docker, dict):
        containers = docker.get("containers")
        out["docker"] = {
            "containers": [
                {
                    "name": _clean_text(c.get("name", ""), 128),
                    "image": _clean_text(c.get("image", ""), 200),
                    "status": _clean_text(c.get("status", ""), 80),
                }
                for c in (containers if isinstance(containers, list) else [])[:_MAX_CONTAINERS]
                if isinstance(c, dict)
            ],
            "total_containers": int(_safe_num(docker.get("total_containers"), 0, _MAX_CONTAINERS)),
            "running": int(_safe_num(docker.get("running"), 0, _MAX_CONTAINERS)),
            "last_updated": _clean_text(docker.get("last_updated", ""), 32),
        }
    return out


def sanitize_nas_state(value):
    """把 system_state["nas"] 转为有数量/长度上限的安全结构。"""
    if not isinstance(value, dict):
        return {}
    result = {}
    for raw_name, raw_entry in list(value.items())[:_MAX_NAS_DEVICES]:
        clean_name = _clean_text(raw_name, 64)
        if not clean_name or clean_name in result:
            continue
        result[clean_name] = _sanitize_nas_entry(raw_entry)
    return result


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


def _update_nas_trust_state(name, host, trust_state, error_code, fingerprint=""):
    """把 SSH 主机信任状态写入 system_state（保留已采集数据，标记离线）。"""
    existing = system_state.get("nas", {}).get(name, {})
    existing.update({
        "name": name,
        "host": host,
        "online": False,
        "ssh_trust": trust_state,
        "fingerprint": fingerprint or "",
        "last_error": _safe_last_error(error_code),
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
    })
    system_state.update("nas", name, existing)


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

    # 采集失败降噪（1.5.1）：同一指标连续失败只记录首次，恢复时补一条 INFO。
    # 原先每轮每指标都写 WARN，设备离线时 daemon.log 会被刷屏（实测每轮 9 行）。
    _fail_state = {"cpu": False, "memory": False, "disk": False}

    def _note_fail(metric, label, error):
        if _fail_state.get(metric):
            return
        _fail_state[metric] = True
        log_warn(f"NAS [{name}] {label}采集失败", error=str(error))

    def _note_ok(metric, label):
        if _fail_state.get(metric):
            _fail_state[metric] = False
            log_info(f"NAS [{name}] {label}采集恢复正常")

    while not stop_event.is_set():
        client = None
        try:
            # P0（S1）：统一通过信任库建链。paramiko 在认证之前调用主机密钥策略，
            # 未信任/指纹变化时抛异常，用户名与密码不会发送给未信任主机。
            client = ssh_trust.connect_ssh(
                host, port, username, password,
                timeout=10, banner_timeout=10, auth_timeout=10,
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
                _note_ok("cpu", "CPU/进程")
            except Exception as e:
                _note_fail("cpu", "CPU/进程", e)

            # 采集内存
            try:
                _, stdout, _ = client.exec_command("free -m", timeout=10)
                mem_output = stdout.read().decode("utf-8", errors="replace")
                mem = _parse_memory(mem_output)
                if mem:
                    data["memory"] = mem
                _note_ok("memory", "内存")
            except Exception as e:
                _note_fail("memory", "内存", e)

            # 采集磁盘
            try:
                _, stdout, _ = client.exec_command("df -h /", timeout=10)
                disk_output = stdout.read().decode("utf-8", errors="replace")
                disk = _parse_disk(disk_output)
                if disk:
                    data["disk"] = disk
                _note_ok("disk", "磁盘")
            except Exception as e:
                _note_fail("disk", "磁盘", e)

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
                with _docker_lock:
                    last_docker = _last_docker_collect.get(name, 0)
                    should_collect = _now - last_docker >= 30
                    if should_collect:
                        _last_docker_collect[name] = _now
                if should_collect:
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

            system_state.update("nas", name, _sanitize_nas_entry(data))

        except ssh_trust.UntrustedHost as e:
            # 只做握手、未认证：等待用户在 NAS 控制台核对指纹后显式确认
            _update_nas_trust_state(name, host, "untrusted", e.code,
                                    e.params.get("fingerprint", ""))
            log_warn(f"NAS [{name}] SSH 主机未信任", host=host, error=e.code)
        except ssh_trust.HostKeyChanged as e:
            _update_nas_trust_state(name, host, "changed", e.code,
                                    e.params.get("new_fingerprint", ""))
            log_warn(f"NAS [{name}] SSH 主机密钥变化", host=host, error=e.code)
        except Exception as e:
            # W-07：日志与 state 都不直接写入异常全文；稳定码给 UI，类型名供内部排查。
            log_error(f"NAS [{name}] 连接失败", error=type(e).__name__, host=host)

            # 保留上次已知数据，更新离线和错误状态
            existing = system_state.get("nas", {}).get(name, {})
            existing.update({
                "name": name,
                "host": host,
                "online": False,
                "last_error": _safe_last_error("nas.err.collectFailed"),
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
            # 1.5.0：标记 mock 设备。它没有 nas_devices 配置条目，SSH 终端连它必然失败，
            # 前端据此把它排除出可连接的终端标签列表（仪表盘/设备中心仍照常展示）。
            "is_mock": True,
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
            raw_config = {}

    from core import secret_store as _ss
    from core.config import _get_user_config_path
    from core.secret_store import SENSITIVE_KEYS
    if not isinstance(raw_config, dict):
        raw_config = {}
    for _k in SENSITIVE_KEYS:
        raw_config.pop(_k, None)

    # user_config 是凭据的唯一来源；迁移失败时 devices=[]，绝不回退 legacy。
    migration = _ss.ensure_credentials_ready()
    user_config_path = _get_user_config_path()
    user_data = {}
    if os.path.exists(user_config_path):
        try:
            with open(user_config_path, "r", encoding="utf-8") as f:
                user_data = json.load(f)
        except Exception:
            user_data = {}
    if isinstance(user_data, dict):
        for _k, _v in user_data.items():
            if _k not in SENSITIVE_KEYS:
                raw_config[_k] = _v

    devices = []
    if migration.get("ok"):
        raw_devices = user_data.get("nas_devices") if isinstance(user_data, dict) else None
        if isinstance(raw_devices, list):
            for _d in raw_devices:
                if not isinstance(_d, dict):
                    continue
                entry = dict(_d)
                if "password" in entry:
                    ok, plain = _ss.get_runtime_secret(entry.get("password"))
                    if not ok:
                        # 失败关闭：不把未保护/不可解密密码交给 Paramiko。
                        continue
                    entry["password"] = plain
                devices.append(entry)
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