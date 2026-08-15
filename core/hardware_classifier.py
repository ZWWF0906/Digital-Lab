from __future__ import annotations

import re
from typing import Optional

# ============================================================
#  CPU 后缀分类表
# ============================================================

INTEL_NOTEBOOK = frozenset({"H", "HX", "HK", "P", "U", "Y", "G", "GX", "V", "EVO"})
INTEL_DESKTOP  = frozenset({"K", "KF", "KS", "F", "T", "S", "X", "XE"})
INTEL_EMBEDDED = frozenset({"E", "TE", "L", "LE", "UE", "HE", "Q", "R"})
INTEL_SERVER   = frozenset({"W", "XP", "D", "M", "GOLD", "SILVER"})

AMD_NOTEBOOK = frozenset({"H", "HS", "HX", "U", "C", "Z", "E"})
AMD_DESKTOP  = frozenset({"X", "XT", "X3D", "G", "GE", "F", "AF"})
AMD_EMBEDDED = frozenset({"P", "EE", "HE", "LE", "V", "I"})
AMD_SERVER   = frozenset({"WX", "P", "F", "V", "PRO"})

# 设备类型：笔记本关键词
NOTEBOOK_KEYWORDS = frozenset({
    "laptop", "notebook", "tx gaming", "tuf gaming f",
    "rog zephyrus", "legion", "omen", "thinkpad", "macbook",
    "zenbook", "vivobook", "probook", "elitebook", "latitude",
    "precision", "xps 13", "xps 15", "xps 17", "surface laptop",
    "surface pro", "surface book", "yoga", "ideapad", "swift",
    "aspire", "predator", "nitro", "katana", "stealth",
    "razer blade", "framework",
})

EMBEDDED_KEYWORDS = frozenset({
    "nuc", "jetson", "raspberry pi", "industrial",
    "beelink", "minisforum", "embedded", "box pc",
})

GPU_LAPTOP_KEYWORDS = frozenset({"laptop", "mobile", "max-q", "m"})


def _extract_cpu_vendor(raw: str) -> Optional[str]:
    if not raw:
        return None
    r = raw.lower()
    if "intel" in r:
        return "intel"
    if "amd" in r or "ryzen" in r:
        return "amd"
    return None


def _extract_cpu_suffix(raw: str, vendor: str) -> Optional[str]:
    """提取 CPU 后缀，如 HX, K, U 等"""
    if not raw:
        return None
    if vendor == "intel":
        m = re.search(r'i[3579]\s*-\s*\d{4,5}(\w{0,4})$', raw)
        if m:
            sfx = m.group(1).upper()
            # 过滤掉纯数字后缀
            if sfx and not sfx.isdigit():
                return sfx
    elif vendor == "amd":
        m = re.search(r'[Rr]yzen\s+\d\s+\d{3,4}(\w{0,4})$', raw)
        if m:
            sfx = m.group(1).upper()
            if sfx and not sfx.isdigit():
                return sfx
    return None


def classify_cpu_suffix(raw: str) -> dict:
    """
    返回 { vendor, suffix, category, friendly_category, tags }
    """
    vendor = _extract_cpu_vendor(raw)
    suffix = _extract_cpu_suffix(raw, vendor) if vendor else None

    result: dict = {
        "vendor": vendor,
        "suffix": suffix,
        "category": "unknown",
        "friendly_category": "通用",
        "tags": [],
    }

    if not vendor or not suffix:
        return result

    _check = suffix.upper()

    if vendor == "intel":
        # 优先匹配最长后缀
        for cset, cat, friendly in [
            (INTEL_NOTEBOOK, "notebook", "笔记本级"),
            (INTEL_DESKTOP, "desktop", "桌面级"),
            (INTEL_EMBEDDED, "embedded", "嵌入式"),
            (INTEL_SERVER, "server", "服务器级"),
        ]:
            if _check in cset:
                result["category"] = cat
                result["friendly_category"] = friendly
                break

        if suffix == "HX":
            result["tags"] = ["HX系列", "游戏本标压"]
            result["friendly_category"] = "笔记本旗舰级"
        elif suffix in ("HK",):
            result["tags"] = [f"{suffix}系列", "可超频本"]
        elif suffix == "H":
            result["tags"] = ["H系列", "游戏本标准压"]
        elif suffix == "P":
            result["tags"] = ["P系列", "全能本"]
        elif suffix == "U":
            result["tags"] = ["U系列", "轻薄本低压"]
        elif suffix == "Y":
            result["tags"] = ["Y系列", "超低功耗"]
        elif suffix in ("G", "GX"):
            result["tags"] = [f"{suffix}系列", "集显增强本"]
        elif suffix == "K":
            result["tags"] = ["K系列", "可超频桌面级"]
        elif suffix == "KF":
            result["tags"] = ["KF系列", "无核显桌面级"]
        elif suffix == "KS":
            result["tags"] = ["KS系列", "特挑桌面级"]
        elif suffix == "F":
            result["tags"] = ["F系列", "无核显桌面级"]
        elif suffix == "T":
            result["tags"] = ["T系列", "低功耗桌面级"]
        elif suffix == "S":
            result["tags"] = ["S系列", "节能桌面级"]
        elif suffix in ("X", "XE"):
            result["tags"] = ["X系列", "极致性能桌面级"]
        elif suffix == "W":
            result["tags"] = ["W系列", "工作站"]
        elif suffix in ("GOLD", "SILVER"):
            result["tags"] = [f"{suffix}系列", "服务器"]
    else:  # amd
        for cset, cat, friendly in [
            (AMD_NOTEBOOK, "notebook", "笔记本级"),
            (AMD_DESKTOP, "desktop", "桌面级"),
            (AMD_EMBEDDED, "embedded", "嵌入式"),
            (AMD_SERVER, "server", "服务器级"),
        ]:
            if _check in cset:
                result["category"] = cat
                result["friendly_category"] = friendly
                break

        if suffix == "HX":
            result["tags"] = ["HX系列", "游戏本旗舰"]
        elif suffix in ("HS", "H"):
            result["tags"] = ["H系列", "游戏本标准压"]
        elif suffix == "U":
            result["tags"] = ["U系列", "轻薄本低压"]
        elif suffix in ("C", "Z", "E"):
            result["tags"] = [f"{suffix}系列", "Zen笔记本"]
        elif suffix == "X":
            result["tags"] = ["X系列", "可超频桌面级"]
        elif suffix == "XT":
            result["tags"] = ["XT系列", "高频桌面级"]
        elif suffix == "X3D":
            result["tags"] = ["X3D系列", "3D V-Cache 游戏旗舰"]
        elif suffix == "G":
            result["tags"] = ["G系列", "APU桌面级"]
        elif suffix == "GE":
            result["tags"] = ["GE系列", "低功耗APU"]
        elif suffix == "F":
            result["tags"] = ["F系列", "无核显桌面级"]
        elif suffix == "AF":
            result["tags"] = ["AF系列", "Refresh桌面级"]
        elif suffix == "WX":
            result["tags"] = ["WX系列", "工作站"]
        elif suffix == "PRO":
            result["tags"] = ["PRO系列", "商用版"]

    return result


# ============================================================
#  设备类型检测
# ============================================================

def detect_device_type(
    system_model: Optional[str] = None,
    manufacturer: Optional[str] = None,
    gpu_name: Optional[str] = None,
    has_battery: Optional[bool] = None,
    form_factor: Optional[str] = None,
) -> dict:
    """
    返回 { type, confidence, methods[] }
    type: "notebook" | "desktop" | "embedded" | "unknown"
    """
    result: dict = {
        "type": "desktop",
        "confidence": 0.5,
        "methods": [],
    }

    model_low = (system_model or "").lower()

    # 1. 检查笔记本关键词
    nb_hit = False
    for kw in NOTEBOOK_KEYWORDS:
        if kw in model_low:
            nb_hit = True
            result["methods"].append(f"型号含笔记本关键词: {kw}")
            break

    if nb_hit:
        result["type"] = "notebook"
        result["confidence"] = 0.8

    # 2. 检查 GPU 名称
    gpu_low = (gpu_name or "").lower()
    for kw in GPU_LAPTOP_KEYWORDS:
        if kw in gpu_low:
            result["methods"].append(f"GPU 含移动关键词: {kw}")
            if result["type"] != "notebook":
                result["type"] = "notebook"
                result["confidence"] = 0.7
            break

    # 3. 检测电池
    if has_battery and result["type"] == "notebook":
        result["confidence"] = 0.95
        result["methods"].append("检测到电池")
    elif has_battery and result["type"] != "notebook":
        result["methods"].append("检测到电池但未命中笔记本关键词")
        # 不强制改类型, 留给冲突检测

    # 4. 检查 Form Factor
    ff_low = (form_factor or "").lower()
    if ff_low in ("notebook", "laptop", "convertible", "detachable"):
        result["type"] = "notebook"
        result["confidence"] = max(result["confidence"], 0.95)
        result["methods"].append(f"Form Factor: {form_factor}")

    # 5. 检查嵌入式关键词
    for kw in EMBEDDED_KEYWORDS:
        if kw in model_low:
            result["type"] = "embedded"
            result["confidence"] = 0.95
            result["methods"].append(f"型号含嵌入式关键词: {kw}")
            break

    # 6. 标准台式机 (无笔记本关键词 + 无电池)
    if not nb_hit and not has_battery and result["type"] != "embedded":
        result["type"] = "desktop"
        result["confidence"] = 0.9
        result["methods"].append("标准主板 (无笔记本特征无电池)")

    result["confidence"] = round(result["confidence"], 2)
    return result


# ============================================================
#  配置校验 (冲突检测)
# ============================================================

def validate_config(
    cpu_suffix_info: Optional[dict] = None,
    gpu_name: Optional[str] = None,
    device_type_info: Optional[dict] = None,
) -> dict:
    """
    返回 { valid, warnings[], suggestions[] }
    """
    warnings = []
    suggestions = []

    if not cpu_suffix_info or not device_type_info:
        return {"valid": True, "warnings": warnings, "suggestions": suggestions}

    cpu_cat = cpu_suffix_info.get("category", "unknown")
    cpu_suffix = cpu_suffix_info.get("suffix", "")
    dev_type = device_type_info.get("type", "unknown")
    gpu_low = (gpu_name or "").lower()

    is_laptop_gpu = any(kw in gpu_low for kw in GPU_LAPTOP_KEYWORDS)
    has_battery = "检测到电池" in device_type_info.get("methods", [])

    # 冲突 1: Laptop GPU + 桌面级 CPU (K/X)
    if is_laptop_gpu and cpu_cat == "desktop":
        warnings.append(f"移动工作站/准系统? — Laptop GPU + 桌面级 CPU后缀 '{cpu_suffix}'")
        suggestions.append("可能为准系统或移动工作站，CPU 后缀优先信任原始数据")

    # 冲突 2: 有电池 + 桌面级 CPU (S/T)
    if has_battery and cpu_cat == "desktop":
        warnings.append(f"一体机/特殊形态? — 有电池 + 桌面级 CPU后缀 '{cpu_suffix}'")
        suggestions.append("可能为一体机或 AIO，建议核对机型")

    # 冲突 3: 无电池 + 笔记本级 CPU (H/HX/U)
    if not has_battery and cpu_cat == "notebook" and dev_type in ("desktop", "unknown"):
        warnings.append(f"ES样品/魔改台式? — 无电池 + 笔记本级 CPU后缀 '{cpu_suffix}'")
        suggestions.append("可能为 ES 工程样品或魔改主板，建议核对 CPU 来源")

    # 冲突 4: 嵌入式 + 高性能 CPU
    if dev_type == "embedded" and cpu_cat in ("notebook", "desktop") and cpu_suffix in (
        "HX", "HK", "H", "K", "KS", "X", "XT", "X3D"
    ):
        warnings.append(f"工业计算平台 — 嵌入式设备 + 高性能 CPU后缀 '{cpu_suffix}'")
        suggestions.append("可能为工业计算平台，非消费级嵌入式设备")

    valid = len(warnings) == 0
    return {
        "valid": valid,
        "warnings": warnings,
        "suggestions": suggestions,
    }


# ============================================================
#  温度告警阈值
# ============================================================

def get_temp_thresholds(device_type: str) -> dict:
    thresholds = {
        "notebook":  {"cpu_warn": 85, "cpu_critical": 95,  "gpu_warn": 83, "gpu_critical": 90},
        "desktop":   {"cpu_warn": 95, "cpu_critical": 105, "gpu_warn": 85, "gpu_critical": 95},
        "embedded":  {"cpu_warn": 75, "cpu_critical": 85,  "gpu_warn": 75, "gpu_critical": 85},
    }
    return thresholds.get(device_type, thresholds["desktop"])


def temp_status(temp: Optional[int], device_type: str, component: str = "cpu") -> str:
    if temp is None:
        return "ok"
    thresholds = get_temp_thresholds(device_type)
    key = f"{component}_critical"
    key_warn = f"{component}_warn"
    if temp >= thresholds.get(key, 105):
        return "critical"
    if temp >= thresholds.get(key_warn, 95):
        return "warn"
    return "ok"


# ============================================================
#  显示卡片配置生成
# ============================================================

def generate_display_config(hw: dict) -> dict:
    """根据硬件数据 + 分类结果生成前端渲染配置"""
    c = hw.get("cpu", {}) or {}
    m = hw.get("memory", {}) or {}
    g = hw.get("gpu", {}) or {}
    d = hw.get("disk", {}) or {}
    s = hw.get("system", {}) or {}
    dev = hw.get("_device_type", {}) or {}
    cpu_cls = hw.get("_cpu_class", {}) or {}
    valid = hw.get("_validation", {}) or {}

    display = {
        "cpu": {},
        "memory": {},
        "gpu": {},
        "disk": {},
        "system": {},
        "warnings": valid.get("warnings", []),
    }

    # ── CPU 卡片 ──
    short = c.get("short_model")
    display["cpu"]["title"] = short or (c.get("model") or "处理器")
    subs = []
    if c.get("cores") and c.get("threads"):
        subs.append(f"{c['cores']}核{c['threads']}线程")
    if c.get("freq_current"):
        subs.append(f"{c['freq_current']}GHz")
    elif c.get("freq_base"):
        subs.append(f"{c['freq_base']}GHz")
    display["cpu"]["subtitle"] = " · ".join(subs) if subs else ""

    cpu_tags = list(cpu_cls.get("tags", []))
    # 温度标签
    temp_s = temp_status(c.get("temperature"), dev.get("type", "desktop"), "cpu")
    if temp_s == "critical":
        cpu_tags.append("⚠ 高温")
    elif temp_s == "warn":
        cpu_tags.append("🌡 温热")
    display["cpu"]["tags"] = cpu_tags

    if cpu_cls.get("category") == "notebook":
        if "HX" in (cpu_cls.get("suffix") or ""):
            display["cpu"]["tag_color"] = "#FF6B6B"
    # 兼容性冲突时特殊标识
    if valid.get("warnings"):
        display["cpu"]["has_warning"] = True

    # ── 内存卡片 ──
    display["memory"]["title"] = f"{m.get('total_gb')} GB" if m.get("total_gb") else ""
    mem_subs = []
    if m.get("type") and m.get("frequency"):
        mem_subs.append(f"{m['type']}-{m['frequency']}")
    elif m.get("type"):
        mem_subs.append(m["type"])
    if m.get("available_gb"):
        mem_subs.append(f"{m['available_gb']}GB 可用")
    if m.get("slots_used") is not None and m.get("slots_total"):
        mem_subs.append(f"{m['slots_used']}/{m['slots_total']} 插槽")
    display["memory"]["subtitle"] = " · ".join(mem_subs) if mem_subs else ""
    if m.get("total_gb") and m.get("available_gb"):
        display["memory"]["bar"] = round((m["total_gb"] - m["available_gb"]) / m["total_gb"] * 100)
    else:
        display["memory"]["bar"] = 0

    mem_tags = []
    if m.get("slots_used") and m.get("slots_total") and m["slots_used"] < m["slots_total"]:
        mem_tags.append("可扩展")
    display["memory"]["tags"] = mem_tags

    # ── GPU 卡片 ──
    gpu_title = g.get("short_name") or g.get("name") or "集成显卡"
    display["gpu"]["title"] = gpu_title
    gpu_subs = []
    if g.get("vram_gb") and g.get("vram_type"):
        gpu_subs.append(f"{g['vram_gb']}GB {g['vram_type']}")
    elif g.get("vram_gb"):
        gpu_subs.append(f"{g['vram_gb']}GB 显存")
    if g.get("temperature"):
        gpu_subs.append(f"{g['temperature']}°C")
    if g.get("utilization") is not None:
        gpu_subs.append(f"{g['utilization']}%")
    display["gpu"]["subtitle"] = " · ".join(gpu_subs) if gpu_subs else ""

    gpu_tags = []
    if g.get("dedicated"):
        gpu_tags.append("独显模式")
        display["gpu"]["glow"] = "var(--accent-teal)"
    if g.get("driver"):
        gpu_tags.append(f"驱动 {g['driver']}")
    if g.get("mode") == "laptop":
        gpu_tags.append("Laptop")
    display["gpu"]["tags"] = gpu_tags

    # GPU 温度状态
    temp_g = temp_status(g.get("temperature"), dev.get("type", "desktop"), "gpu")
    if temp_g == "critical":
        gpu_tags.append("⚠ 高温")
    elif temp_g == "warn":
        gpu_tags.append("🌡 温热")

    # ── 磁盘卡片 ──
    display["disk"]["title"] = f"{d.get('capacity_gb')} GB" if d.get("capacity_gb") else ""
    disk_subs = []
    if d.get("model"):
        disk_subs.append(d["model"][:28])
    if d.get("type"):
        disk_subs.append(d["type"])
    if d.get("interface"):
        disk_subs.append(d["interface"])
    display["disk"]["subtitle"] = " · ".join(disk_subs) if disk_subs else ""

    parts = []
    for p in d.get("partitions", []) or []:
        if p.get("total_gb") and p.get("free_gb") is not None:
            pct = round(p["free_gb"] / p["total_gb"] * 100)
            cls = "bad" if pct < 10 else ("warn" if pct < 20 else "ok")
            parts.append({
                "letter": p.get("letter", ""),
                "free": p["free_gb"],
                "total": p["total_gb"],
                "pct": pct,
                "cls": cls,
                "label": p.get("label"),
            })
    display["disk"]["parts"] = parts

    disk_tags = []
    if len(parts) >= 2:
        disk_tags.append("双盘位")
    display["disk"]["tags"] = disk_tags

    # ── 系统卡片 ──
    os_str = ""
    if s.get("edition"):
        os_raw = s.get("os", "")
        if "windows 11" in os_raw.lower() or "win11" in os_raw.lower():
            os_str = f"Win11 {s['edition']}"
        elif "windows 10" in os_raw.lower() or "win10" in os_raw.lower():
            os_str = f"Win10 {s['edition']}"
        else:
            os_str = f"{os_raw} {s['edition']}"
    else:
        os_raw = s.get("os", "")
        os_str = os_raw.replace("Windows 11 build", "Win11").replace("Windows 10 build", "Win10")
    if not os_str:
        os_str = s.get("os", "")

    display["system"]["title"] = os_str

    sys_subs = []
    if s.get("uptime_seconds"):
        secs = s["uptime_seconds"]
        d = int(secs // 86400)
        h = int(secs % 86400 // 3600)
        m = int(secs % 3600 // 60)
        if d > 0:
            sys_subs.append(f"运行 {d}d {h}h")
        elif h > 0:
            sys_subs.append(f"运行 {h}h {m}m")
        else:
            sys_subs.append(f"运行 {m}m")
    if s.get("python_version"):
        sys_subs.append(f"Python {s['python_version']}")
    display["system"]["subtitle"] = " · ".join(sys_subs) if sys_subs else ""

    sys_tags = []
    if s.get("boot_time"):
        sys_tags.append(s["boot_time"][:10])
    # 显示器信息可在后续扩展
    display["system"]["tags"] = sys_tags

    # 设备类型标识
    display["device_type"] = dev.get("type", "unknown")
    display["device_confidence"] = dev.get("confidence", 0)

    return display