from __future__ import annotations

import os
import re
import sys
import json
import time
import platform
import subprocess
import datetime
from typing import Optional

HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

_CACHE_FILE = None
_CACHE_TTL = 86400


def _get_cache_path() -> str:
    global _CACHE_FILE
    if _CACHE_FILE:
        return _CACHE_FILE
    from core.config import get_config
    cfg = get_config()
    cache_dir = os.path.join(cfg.logs_dir, "cache")
    os.makedirs(cache_dir, exist_ok=True)
    _CACHE_FILE = os.path.join(cache_dir, "hardware.json")
    return _CACHE_FILE


def _load_cache() -> Optional[dict]:
    path = _get_cache_path()
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - data.get("_ts", 0) > _CACHE_TTL:
            return None
        data.pop("_ts", None)
        return data
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def _save_cache(data: dict):
    cached = dict(data)
    cached["_ts"] = time.time()
    try:
        with open(_get_cache_path(), "w", encoding="utf-8") as f:
            json.dump(cached, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


def _run(cmd: list[str], timeout: int = 5) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
        return r.stdout.strip()
    except Exception:
        return ""


def _run_ps(script: str, timeout: int = 8) -> str:
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True, text=False, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        raw = r.stdout
        for enc in ("utf-8", "gbk", "cp936", "latin-1"):
            try:
                return raw.decode(enc).strip()
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="replace").strip()
    except Exception:
        return ""


def _run_nvidia_smi() -> Optional[dict]:
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,temperature.gpu,"
                "utilization.gpu,driver_version", "--format=csv,noheader,nounits"],
               timeout=8)
    if not out:
        return None
    parts = [p.strip() for p in out.split(",")]
    if len(parts) < 5:
        return None
    name = parts[0]
    vram = _parse_number(parts[1])
    temp = _parse_number(parts[2])
    util = _parse_number(parts[3])
    driver = parts[4]
    if not name:
        return None
    return {
        "name": name, "vram_gb": round(vram / 1024) if vram else None,
        "temperature": int(temp) if temp else None,
        "utilization": int(util) if util else None,
        "driver": driver or None,
    }


def _parse_number(text: str) -> Optional[float]:
    m = re.search(r'([\d.]+)', str(text))
    return float(m.group(1)) if m else None


def _clean_cpu_name(raw: str) -> Optional[str]:
    if not raw or len(raw) < 5:
        return None
    s = raw.strip()
    noise = [
        r'\bGenui?neIntel\b', r'\bAuthenticAMD\b', r'\bx86[-\s]?Family\b',
        r'(?i)\bCPU\s*@?\s*[\d.]+\s*GHz\b', r'(?i)\bprocessor\b',
        r'\(R\)', r'\(TM\)', r'\u00AE', r'\u2122',
        r'with\s+Radeon\s*(TM)?\s*Graphics', r'Radeon\s*(TM)?',
        r'64-base\s+processor', r'Core\(TM\)',
    ]
    for n in noise:
        s = re.sub(n, '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    s = re.sub(r'[,\-\s]+$', '', s)
    arch_only = re.match(r'^(AMD64|x86_64|ARM64|armv[0-9]+[a-z]?|aarch64)$', s)
    if arch_only:
        return None
    if len(s) < 4 or 'Family' in s or 'Model' in s or 'Stepping' in s:
        return None
    return s


def _extract_short_model(full: str) -> Optional[str]:
    if not full:
        return None
    m = re.search(r'(i[3579]\s*-\s*\d{4,5}\w{0,2})', full)
    if m:
        return m.group(1).replace(' ', '')
    m = re.search(r'(Ryzen\s*\d\s*\d{3,4}\w{0,2})', full, re.IGNORECASE)
    if m:
        return re.sub(r'\s+', ' ', m.group(1).strip())
    words = full.split()
    if len(words) >= 2:
        return words[-1] if len(words[-1]) >= 4 else words[-2] + ' ' + words[-1]
    return full


def get_cpu_info() -> dict:
    result = {
        "model": None, "short_model": None,
        "cores": None, "threads": None,
        "freq_base": None, "freq_current": None,
        "temperature": None, "architecture": platform.machine(),
    }
    confidence = "low"

    model = None

    try:
        import cpuinfo
        info = cpuinfo.get_cpu_info()
        brand = info.get("brand_raw") or info.get("brand", "")
        if brand and brand != "Unknown":
            model = brand
            confidence = "high"
    except (ImportError, Exception):
        pass

    if not model and sys.platform == "win32":
        out = _run_ps("Get-CimInstance Win32_Processor | Select-Object -ExpandProperty Name")
        if out:
            model = out.strip()
            confidence = "high"
    elif not model and sys.platform == "darwin":
        out = _run(["system_profiler", "SPHardwareDataType"])
        m = re.search(r'Processor Name:\s*(.+)', out)
        if m:
            model = m.group(1).strip()
            confidence = "high"
    elif not model and sys.platform == "linux":
        out = _run(["lscpu"])
        m = re.search(r'Model name:\s*(.+)', out)
        if m:
            model = m.group(1).strip()
            confidence = "high"
        if not model:
            out = _run(["cat", "/proc/cpuinfo"])
            m = re.search(r'model name\s*:\s*(.+)', out)
            if m:
                model = m.group(1).strip()
                confidence = "high"

    if not model:
        model = platform.processor()
        if model and model not in ("", "Unknown", "x86_64", "AMD64", "ARM64", "armv7l", "aarch64"):
            confidence = "medium"

    model = _clean_cpu_name(model) if model else None

    if model and len(model) > 80:
        model = model[:80]

    result["model"] = model
    result["short_model"] = _extract_short_model(model) if model else None

    if HAS_PSUTIL:
        try:
            result["cores"] = psutil.cpu_count(logical=False)
            result["threads"] = psutil.cpu_count(logical=True)
            freq = psutil.cpu_freq()
            if freq:
                if freq.max and freq.max > 0:
                    result["freq_base"] = round(freq.max / 1000, 1)
                if freq.current and freq.current > 0:
                    result["freq_current"] = round(freq.current / 1000, 1)
            confidence = max(confidence, "medium")
        except Exception:
            pass

    if not result["temperature"] and HAS_PSUTIL:
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in temps.items():
                    for e in entries:
                        if e.current and e.current > 0 and e.current < 120:
                            result["temperature"] = round(e.current)
                            break
                    if result["temperature"]:
                        break
        except Exception:
            pass

    if not result["cores"]:
        try:
            logical = os.cpu_count()
            if logical:
                result["cores"] = logical
                result["threads"] = logical
                confidence = max(confidence, "medium")
        except Exception:
            pass

    result["_confidence"] = confidence
    return result


def get_memory_info() -> dict:
    result = {
        "total_gb": None, "available_gb": None,
        "type": None, "frequency": None,
        "slots_used": None, "slots_total": None,
    }
    confidence = "low"

    if HAS_PSUTIL:
        try:
            mem = psutil.virtual_memory()
            result["total_gb"] = int(round(mem.total / (1024 ** 3)))
            result["available_gb"] = round(mem.available / (1024 ** 3), 1)
            confidence = "medium"
        except Exception:
            pass

    if sys.platform == "win32":
        out = _run_ps("Get-CimInstance Win32_PhysicalMemory | "
                      "Select-Object Speed,SMBIOSMemoryType | Format-Table -HideTableHeaders")
        if out:
            speeds = []
            for line in out.splitlines():
                m = re.search(r'(\d{3,4})', line)
                if m:
                    speeds.append(int(m.group(1)))
            if speeds:
                result["frequency"] = max(speeds)
                if result["frequency"] >= 4800:
                    result["type"] = "DDR5"
                elif result["frequency"] >= 2133:
                    result["type"] = "DDR4"
                else:
                    result["type"] = "DDR3"
                confidence = "high"
            result["slots_used"] = len(speeds) if speeds else None

        out2 = _run_ps("(Get-CimInstance Win32_PhysicalMemoryArray | "
                       "Select-Object -ExpandProperty MemoryDevices)")
        m = re.search(r'(\d+)', out2)
        if m:
            result["slots_total"] = int(m.group(1))

    elif sys.platform == "linux":
        out = _run(["sudo", "dmidecode", "-t", "memory"])
        if out:
            m = re.search(r'Type:\s*(DDR\d?)', out)
            if m:
                result["type"] = m.group(1)
            m = re.search(r'Speed:\s*(\d+)', out)
            if m:
                result["frequency"] = int(m.group(1))
            confidence = "high"
        if not result["total_gb"]:
            out = _run(["free", "-h"])
            m = re.search(r'Mem:\s*([\d.]+)Gi', out)
            if m:
                result["total_gb"] = float(m.group(1))

    result["_confidence"] = confidence
    return result


def get_gpu_info() -> Optional[dict]:
    result = {
        "name": None, "short_name": None, "vram_gb": None, "driver": None,
        "temperature": None, "utilization": None,
        "dedicated": False, "mode": None,
    }
    confidence = "low"

    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        result["name"] = pynvml.nvmlDeviceGetName(handle)
        result["dedicated"] = True
        try:
            result["vram_gb"] = round(pynvml.nvmlDeviceGetMemoryInfo(handle).total / (1024 ** 3), 1)
        except Exception:
            pass
        try:
            result["temperature"] = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        except Exception:
            pass
        try:
            result["utilization"] = pynvml.nvmlDeviceGetUtilizationRates(handle).gpu
        except Exception:
            pass
        try:
            ver = pynvml.nvmlSystemGetDriverVersion()
            result["driver"] = str(ver)
        except Exception:
            pass
        confidence = "high"
        pynvml.nvmlShutdown()
        result["_confidence"] = confidence
        return _enrich_gpu(result)
    except (ImportError, Exception):
        pass

    smi = _run_nvidia_smi()
    if smi:
        result["name"] = smi["name"]
        result["dedicated"] = True
        result["vram_gb"] = smi.get("vram_gb")
        result["temperature"] = smi.get("temperature")
        result["utilization"] = smi.get("utilization")
        result["driver"] = smi.get("driver")
        result["_confidence"] = "high"
        return _enrich_gpu(result)

    try:
        import pyamdgpuinfo
        devices = pyamdgpuinfo.get_gpus()
        if devices:
            d = devices[0]
            result["name"] = d.name
            result["dedicated"] = True
            try:
                result["vram_gb"] = round(d.vram_size / (1024 ** 3), 1)
            except Exception:
                pass
            try:
                result["temperature"] = d.query_temperature()
            except Exception:
                pass
            try:
                result["utilization"] = d.query_load()
            except Exception:
                pass
            confidence = "high"
            result["_confidence"] = confidence
            return _enrich_gpu(result)
    except (ImportError, Exception):
        pass

    if sys.platform == "win32":
        out = _run_ps("Get-CimInstance Win32_VideoController | "
                      "Select-Object Name,AdapterRAM,DriverVersion | Format-Table -HideTableHeaders")
        if out:
            candidates = []
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                parts = line.rsplit(None, 3) if line else [line]
                name_part = parts[0] if parts else line
                if not name_part or name_part.lower() in (
                    "microsoft basic display adapter", "microsoft basic render driver"):
                    continue
                is_igpu = bool(re.search(r'(?i)\bIntel\b', name_part))
                ram_val = None
                for p in parts[1:]:
                    n = _parse_number(p)
                    if n:
                        ram_val = n
                        break
                candidates.append((name_part, ram_val, is_igpu))

            dgpu = [(n, r) for n, r, ig in candidates if not ig]
            if dgpu:
                name, ram = dgpu[0]
                result["name"] = name
                result["dedicated"] = True
                if ram:
                    result["vram_gb"] = round(ram / (1024 ** 3))
                result["_confidence"] = "high"
                return _enrich_gpu(result)

    return None


def _enrich_gpu(result: dict) -> dict:
    name = result.get("name") or ""
    # Extract short name: RTX 5060, RTX 4070 Ti, RX 7900 XT, Arc A770
    m = re.search(r'(RTX\s*\d{3,4}\s*(Ti|SUPER)?)', name, re.IGNORECASE)
    if not m:
        m = re.search(r'(GTX\s*\d{3,4}\s*Ti?)', name, re.IGNORECASE)
    if not m:
        m = re.search(r'(RX\s*\d{3,4}\s*XT?)', name, re.IGNORECASE)
    if not m:
        m = re.search(r'(Arc\s*A?\d{3})', name, re.IGNORECASE)
    if m:
        result["short_name"] = re.sub(r'\s+', ' ', m.group(1).strip())
    else:
        words = name.split()
        if len(words) >= 3:
            result["short_name"] = words[-2] + ' ' + words[-1] if len(words[-1]) >= 2 else words[-3]
        else:
            result["short_name"] = words[-1]

    # Detect vRAM type
    if "Laptop" in name:
        result["mode"] = "laptop"
    if "Laptop" in name or "Mobile" in name:
        pass

    if result.get("vram_gb") and result["vram_gb"] >= 8:
        vram_type = "GDDR6" if result["name"] and "30" not in result["name"][-8:] else "GDDR6X"
        result["vram_type"] = "GDDR6"
    elif result.get("vram_gb") and result["vram_gb"] >= 4:
        result["vram_type"] = "GDDR6"

    return result


def get_disk_info() -> dict:
    result = {
        "model": None, "capacity_gb": None, "type": None,
        "health": None, "interface": None,
        "partitions": [],
    }
    confidence = "low"
    total_cap = 0

    if sys.platform == "win32":
        out = _run_ps("Get-CimInstance Win32_DiskDrive | "
                      "Select-Object Model,Size,MediaType,InterfaceType | Format-List")
        if out:
            for line in out.splitlines():
                line = line.strip()
                if line.lower().startswith("model") and ":" in line:
                    model_val = line.split(":", 1)[-1].strip()
                    if model_val and len(model_val) > 3:
                        result["model"] = model_val
                elif line.lower().startswith("size") and ":" in line:
                    size_val = line.split(":", 1)[-1].strip()
                    size = _parse_number(size_val)
                    if size and size > 10 ** 8:
                        cap = int(round(size / (1024 ** 3)))
                        total_cap += cap
                elif line.lower().startswith("mediatype") and ":" in line:
                    mt = line.split(":", 1)[-1].strip()
                    if "ssd" in mt.lower() or "nvme" in mt.lower():
                        result["type"] = "SSD"
                    elif "fixed" in mt.lower():
                        result["type"] = "HDD"
                elif line.lower().startswith("interfacetype") and ":" in line:
                    iface = line.split(":", 1)[-1].strip()
                    if iface and iface != "SCSI":
                        result["interface"] = iface

        if result["model"] and "nvme" in result["model"].lower():
            result["type"] = "NVMe SSD"
            result["interface"] = "PCIe"

        part_out = _run_ps("Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | "
                           "Select-Object DeviceID,Size,FreeSpace,VolumeName | Format-List")
        if part_out:
            current_part = {}
            for line in part_out.splitlines():
                line = line.strip()
                if not line:
                    if current_part.get("letter"):
                        result["partitions"].append(current_part)
                    current_part = {}
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "deviceid":
                        current_part["letter"] = val.rstrip(":")
                    elif key == "size":
                        n = _parse_number(val)
                        if n:
                            current_part["total_gb"] = int(round(n / (1024 ** 3)))
                            total_cap = max(total_cap, current_part["total_gb"])
                    elif key == "freespace":
                        n = _parse_number(val)
                        if n:
                            current_part["free_gb"] = int(round(n / (1024 ** 3)))
                    elif key == "volumename":
                        current_part["label"] = val if val else None
            if current_part.get("letter"):
                result["partitions"].append(current_part)

        result["capacity_gb"] = total_cap if total_cap > 0 else None
        if result["model"]:
            confidence = "high"

    elif sys.platform == "linux":
        out = _run(["lsblk", "-d", "-o", "NAME,SIZE,ROTA,MODEL,TYPE"])
        m = re.search(r'(\S+)\s+([\d.]+G)', out)
        if m:
            result["capacity_gb"] = round(float(m.group(2).replace("G", "")))
        m = re.search(r'ROTA\s*\n\S+\s+\S+\s+(\d)', out)
        if m:
            result["type"] = "HDD" if m.group(1) == "1" else "SSD"
        m = re.search(r'(\S+)\s+\S+\s+\d\s+(.+)', out)
        if m:
            result["model"] = m.group(2).strip()

    elif sys.platform == "darwin":
        out = _run(["diskutil", "info", "disk0"])
        m = re.search(r'Device / Media Name:\s*(.+)', out)
        if m:
            result["model"] = m.group(1).strip()
        m = re.search(r'Disk Size:\s*([\d.]+)\s*([GM]B)', out)
        if m:
            gb = float(m.group(1))
            if "MB" in m.group(2):
                gb /= 1024
            result["capacity_gb"] = round(gb)

    if not result["capacity_gb"] and HAS_PSUTIL:
        try:
            usage = psutil.disk_usage("/")
            result["capacity_gb"] = int(round(usage.total / (1024 ** 3)))
        except Exception:
            pass

    result["_confidence"] = confidence
    return result


def get_system_info() -> dict:
    result = {
        "os": None, "edition": None, "uptime_seconds": None,
        "python_version": None, "boot_time": None,
        "system_model": None, "manufacturer": None,
        "form_factor": None, "has_battery": None,
    }

    result["python_version"] = "{}.{}.{}".format(
        sys.version_info.major, sys.version_info.minor, sys.version_info.micro
    )

    if sys.platform == "win32":
        try:
            wv = sys.getwindowsversion()
            build = wv.build
            if build >= 22000:
                name = "Windows 11"
            else:
                name = "Windows 10"
            result["os"] = "{} build {}".format(name, build)
        except Exception:
            result["os"] = "Windows"

        ed = _run_ps("(Get-CimInstance Win32_OperatingSystem).Caption")
        if ed:
            if "Pro" in ed or "Professional" in ed:
                result["edition"] = "Professional"
            elif "Home" in ed:
                result["edition"] = "Home"
            elif "Enterprise" in ed:
                result["edition"] = "Enterprise"

        cs = _run_ps("Get-CimInstance Win32_ComputerSystem | Select-Object Model,Manufacturer | Format-List")
        if cs:
            for line in cs.splitlines():
                line = line.strip()
                if line.lower().startswith("model") and ":" in line:
                    result["system_model"] = line.split(":", 1)[-1].strip()
                elif line.lower().startswith("manufacturer") and ":" in line:
                    result["manufacturer"] = line.split(":", 1)[-1].strip()

        sf = _run_ps("Get-CimInstance Win32_SystemEnclosure | Select-Object -ExpandProperty ChassisTypes")
        if sf:
            ct = _parse_number(sf)
            if ct is not None:
                form_map = {
                    8: "Laptop", 9: "Laptop", 10: "Notebook", 11: "Notebook",
                    12: "Notebook", 14: "Notebook", 18: "Notebook",
                    21: "Notebook", 31: "Convertible", 32: "Detachable",
                    3: "Desktop", 4: "Desktop", 5: "Desktop", 6: "Desktop",
                    7: "Desktop", 13: "Desktop", 15: "Desktop", 16: "Desktop",
                }
                result["form_factor"] = form_map.get(int(ct), None)

        bat_out = _run_ps("Get-CimInstance Win32_Battery | Select-Object -ExpandProperty Name")
        result["has_battery"] = bool(bat_out and len(bat_out) > 3)

    elif sys.platform == "darwin":
        out = _run(["sw_vers", "-productVersion"])
        if out:
            result["os"] = "macOS {}".format(out)
        out = _run(["system_profiler", "SPHardwareDataType"])
        m = re.search(r'Model Name:\s*(.+)', out)
        if m:
            result["system_model"] = m.group(1).strip()
        m = re.search(r'Model Identifier:\s*(.+)', out)
        if m and not result["system_model"]:
            result["system_model"] = m.group(1).strip()
        out2 = _run(["system_profiler", "SPPowerDataType"])
        result["has_battery"] = "Battery" in out2 or "Charge" in out2
    elif sys.platform == "linux":
        out = _run(["lsb_release", "-ds"])
        if out:
            result["os"] = out.strip('"').strip()
        if not result["os"]:
            out = _run(["cat", "/etc/os-release"])
            m = re.search(r'PRETTY_NAME="?(.+?)"?$', out, re.MULTILINE)
            if m:
                result["os"] = m.group(1)
        out = _run(["cat", "/sys/class/dmi/id/product_name"])
        if out:
            result["system_model"] = out.strip()
        out = _run(["cat", "/sys/class/dmi/id/sys_vendor"])
        if out:
            result["manufacturer"] = out.strip()
        bat_path = "/sys/class/power_supply/BAT0"
        result["has_battery"] = os.path.exists(bat_path)

    if not result["os"]:
        result["os"] = "{} {}".format(platform.system(), platform.release())

    if HAS_PSUTIL:
        try:
            boot = datetime.datetime.fromtimestamp(psutil.boot_time())
            result["uptime_seconds"] = int(time.time() - psutil.boot_time())
            result["boot_time"] = boot.isoformat()
        except Exception:
            pass

    return result


def get_display_info() -> dict:
    result = {"displays": [], "total_resolution": ""}
    if sys.platform == "win32":
        monitor_names = {}
        try:
            mon_out = _run_ps(
                "Get-CimInstance WmiMonitorID -Namespace root/wmi | "
                "ForEach-Object { "
                "  $n=($_.UserFriendlyName|ForEach-Object{[char]$_})-join'';"
                "  if($n.Length -lt 2){$n=($_.ProductCodeID|ForEach-Object{[char]$_})-join''};"
                "  $m=($_.ManufacturerName|ForEach-Object{[char]$_})-join'';"
                "  [PSCustomObject]@{UserFriendlyName=$n;Manufacturer=$m;InstanceName=$_.InstanceName} "
                "} | ConvertTo-Json"
            )
            if mon_out:
                try:
                    mon_raw = json.loads(mon_out)
                except json.JSONDecodeError:
                    mon_raw = None
                if isinstance(mon_raw, dict):
                    mon_raw = [mon_raw]
                if mon_raw:
                    for i, m in enumerate(mon_raw):
                        name = (m.get("UserFriendlyName") or "").strip()
                        manufacturer = (m.get("Manufacturer") or "").strip()
                        if name:
                            display_name = name
                            if manufacturer:
                                display_name = manufacturer + " " + name
                        elif manufacturer:
                            display_name = manufacturer
                        else:
                            display_name = "Monitor " + str(i + 1)
                        monitor_names[i] = display_name
        except Exception:
            pass

        out = _run_ps(
            "Get-CimInstance Win32_VideoController | "
            "Where-Object {$_.CurrentHorizontalResolution -gt 0} | "
            "Select-Object CurrentHorizontalResolution,CurrentVerticalResolution,"
            "CurrentRefreshRate | ConvertTo-Json"
        )
        if out:
            try:
                displays_raw = json.loads(out)
            except json.JSONDecodeError:
                return result
            if isinstance(displays_raw, dict):
                displays_raw = [displays_raw]
            resolutions = []
            for i, d in enumerate(displays_raw):
                width = d.get("CurrentHorizontalResolution")
                height = d.get("CurrentVerticalResolution")
                refresh = d.get("CurrentRefreshRate")
                name = monitor_names.get(i, "Display " + str(i + 1))
                disp = {
                    "name": name,
                    "width": width,
                    "height": height,
                    "refresh_rate": refresh,
                }
                result["displays"].append(disp)
                if width and height:
                    resolutions.append("{}x{}".format(width, height))
            if resolutions:
                if len(resolutions) == 1:
                    result["total_resolution"] = resolutions[0]
                else:
                    result["total_resolution"] = "{} (primary) + {}".format(
                        resolutions[0], " + ".join(resolutions[1:])
                    )
        return result
    result["total_resolution"] = "Unknown"
    return result


def get_network_info() -> dict:
    result = {"adapters": []}
    if sys.platform == "win32":
        out = _run_ps(
            "Get-CimInstance Win32_NetworkAdapter | "
            "Where-Object {$_.NetEnabled -eq $true -and $_.PhysicalAdapter -eq $true} | "
            "Select-Object Name,AdapterType,Speed,Manufacturer,PNPDeviceID,GUID | ConvertTo-Json"
        )
        if out:
            try:
                adapters_raw = json.loads(out)
            except json.JSONDecodeError:
                return result
            if isinstance(adapters_raw, dict):
                adapters_raw = [adapters_raw]
            wireless = []
            wired = []
            other = []
            virtual_keywords = [
                "virtual", "hyper-v", "vpn", "vmware", "virtualbox", "tap-",
                "teredo", "isatap", "6to4", "miniport", "wan miniport",
                "bluetooth", "veth", "radmin", "zerotier", "tailscale",
            ]
            for a in adapters_raw:
                name = (a.get("Name") or "").strip()
                pnp_id = (a.get("PNPDeviceID") or "").lower()
                guid = (a.get("GUID") or "").lower()
                is_virtual = False
                for kw in virtual_keywords:
                    if kw in name.lower() or kw in pnp_id:
                        is_virtual = True
                        break
                if is_virtual:
                    continue
                speed = a.get("Speed")
                speed_mbps = None
                if speed and speed > 0:
                    speed_mbps = int(speed / (1000 * 1000))
                adapter_type = (a.get("AdapterType") or "").strip()
                is_wireless = any(t in adapter_type.lower() for t in (
                    "wireless", "802.11", "wi-fi", "wifi"
                ))
                if is_wireless:
                    adapter_type = "Wi-Fi"
                else:
                    is_wireless = any(kw in name.lower() for kw in (
                        "wi-fi", "wireless", "802.11", "wlan", "intel(r) wi-fi"
                    ))
                    if is_wireless:
                        adapter_type = "Wi-Fi"
                name_clean = name
                for suffix in (
                    "- VirtualBox Host-Only Ethernet Adapter",
                    "- WAN Miniport",
                ):
                    idx = name_clean.find(suffix)
                    if idx >= 0:
                        name_clean = name_clean[:idx].strip()
                adapter = {
                    "name": name_clean,
                    "type": adapter_type,
                    "speed_mbps": speed_mbps,
                    "manufacturer": (a.get("Manufacturer") or "").strip(),
                }
                if is_wireless:
                    wireless.append(adapter)
                elif "ethernet" in adapter_type.lower() or "802.3" in adapter_type.lower():
                    wired.append(adapter)
                else:
                    other.append(adapter)
            result["adapters"] = wireless + wired + other
        return result
    if HAS_PSUTIL:
        try:
            addrs = psutil.net_if_addrs()
            stats = psutil.net_if_stats()
            for name, stat in stats.items():
                if stat.isup:
                    adapter = {
                        "name": name,
                        "type": "Ethernet",
                        "speed_mbps": stat.speed if stat.speed and stat.speed > 0 else None,
                        "manufacturer": None,
                    }
                    result["adapters"].append(adapter)
        except Exception:
            pass
    return result


def collect_all(use_cache: bool = True) -> dict:
    if use_cache:
        cached = _load_cache()
        if cached:
            return cached

    cpu = get_cpu_info()
    memory = get_memory_info()
    gpu = get_gpu_info()
    disk = get_disk_info()
    system = get_system_info()

    data = {
        "cpu": cpu,
        "memory": memory,
        "gpu": gpu,
        "disk": disk,
        "system": system,
        "display": get_display_info(),
        "network": get_network_info(),
    }

    try:
        from core.hardware_classifier import (
            classify_cpu_suffix,
            detect_device_type,
            validate_config,
            generate_display_config,
        )

        cpu_raw = cpu.get("model") or ""
        cpu_class = classify_cpu_suffix(cpu_raw)
        data["_cpu_class"] = cpu_class

        device_type = detect_device_type(
            system_model=system.get("system_model"),
            manufacturer=system.get("manufacturer"),
            gpu_name=gpu.get("name") if gpu else None,
            has_battery=system.get("has_battery"),
            form_factor=system.get("form_factor"),
        )
        data["_device_type"] = device_type

        validation = validate_config(
            cpu_suffix_info=cpu_class,
            gpu_name=gpu.get("name") if gpu else None,
            device_type_info=device_type,
        )
        data["_validation"] = validation

        display = generate_display_config(data)
        data["_display"] = display

    except ImportError:
        pass

    _save_cache(data)
    return data


def invalidate_cache():
    path = _get_cache_path()
    try:
        os.remove(path)
    except OSError:
        pass
