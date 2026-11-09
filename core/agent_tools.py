"""Agent 只读工具基础设施（DigitalLab v1.6.0 阶段一，DL-160-01）。

本模块只做四件事：
1. 注册与发现：register_tool / list_tools / get_tool / model_tool_specs；
2. 参数定义与校验：参数使用 JSON Schema 子集（object/array/string/integer/number/boolean），
   支持 required、enum、minimum/maximum、minLength/maxLength、minItems/maxItems、
   items 与 additionalProperties=False（默认拒绝未知参数）；
3. 执行调度：call_tool(name, params) 统一做参数校验、默认值填充、异常兜底、
   结果体积限制，返回结构化结果 {"ok", "tool", "data", "error", "meta"}；
4. 数据范围声明：每个工具声明 data_scope（返回哪些字段）与 read_only，
   所有工具均为只读，不产生任何写入或网络请求。

安全边界（本阶段关键约定）：
- MODEL_EXPOSURE_ENABLED = False：工具一律不暴露给模型；model_tool_specs() 恒返回空列表。
  下一阶段接入模型工具调用循环前，必须先完成数据披露与权限边界设计（见 PRIVACY.md）。
- 工具输出采用白名单字段，不返回 SSH 凭据、认证 Token、NAS 主机地址、进程命令行等敏感内容。
- 工具执行范围受 limit/参数上限约束（见各工具参数定义），并对结果 JSON 体积设硬上限。

依赖原则：只读复用既有模块（core.system_state / core.monitor / core.ai_memory），
不重复采集、不新增存储；不在模块导入期启动任何线程或 IO。
"""

from __future__ import annotations

import copy
import json
import re
import threading
import time

# ── 全局策略开关 ──
# 阶段一明确关闭：模型侧拿到的工具清单必须为空，等数据披露与权限边界设计完成后再打开。
MODEL_EXPOSURE_ENABLED = False

# 单个工具结果的 JSON 体积上限（字节）；超出视为工具实现问题，返回结构化错误而不是截断注入
_MAX_RESULT_BYTES = 64 * 1024
_ALLOWED_TYPES = {"object", "array", "string", "integer", "number", "boolean"}

_TOOLS = {}
_TOOL_LOCK = threading.Lock()


class ToolError(Exception):
    """工具内部抛出的、可安全回传给调用方的结构化错误。"""

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


# ── 参数 schema 规整与校验 ──

def _normalize_schema(schema, path="parameters"):
    """校验并深拷贝工具参数 schema（只接受 JSON Schema 子集）。

    非法 schema 属于开发者错误，注册时立即抛出 ValueError，
    避免把错误定义带到运行时。
    """
    if not isinstance(schema, dict):
        raise ValueError("{0} 必须是对象".format(path))
    out = {}
    stype = schema.get("type")
    if stype is not None:
        if stype not in _ALLOWED_TYPES:
            raise ValueError("{0}.type 不支持: {1}".format(path, stype))
        out["type"] = stype
    if "description" in schema:
        out["description"] = str(schema.get("description") or "")[:300]
    if "default" in schema:
        out["default"] = copy.deepcopy(schema["default"])
    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, (list, tuple)):
            raise ValueError("{0}.enum 必须是数组".format(path))
        out["enum"] = list(enum)
    for key in ("minimum", "maximum"):
        if key in schema:
            val = schema[key]
            if isinstance(val, bool) or not isinstance(val, (int, float)):
                raise ValueError("{0}.{1} 必须是数字".format(path, key))
            out[key] = val
    for key in ("minLength", "maxLength", "minItems", "maxItems"):
        if key in schema:
            val = schema[key]
            if isinstance(val, bool) or not isinstance(val, int) or val < 0:
                raise ValueError("{0}.{1} 必须是非负整数".format(path, key))
            out[key] = val
    if "properties" in schema:
        props = schema["properties"]
        if not isinstance(props, dict):
            raise ValueError("{0}.properties 必须是对象".format(path))
        out["properties"] = {
            str(name): _normalize_schema(sub, "{0}.properties.{1}".format(path, name))
            for name, sub in props.items()
        }
    if "required" in schema:
        required = schema["required"]
        if not isinstance(required, (list, tuple)) or any(not isinstance(x, str) for x in required):
            raise ValueError("{0}.required 必须是字符串数组".format(path))
        out["required"] = list(required)
    if "items" in schema:
        items = schema["items"]
        if isinstance(items, list):
            if len(items) != 1:
                raise ValueError("{0}.items 只支持单元素数组写法".format(path))
            items = items[0]
        out["items"] = _normalize_schema(items, path + ".items")
    if "additionalProperties" in schema:
        out["additionalProperties"] = bool(schema["additionalProperties"])
    elif "properties" in out:
        # 工具参数默认拒绝未知字段：模型/调用方拼错参数必须显式失败，而不是被静默忽略
        out["additionalProperties"] = False
    if out.get("type") == "object" and "properties" not in out:
        out["properties"] = {}
        out.setdefault("additionalProperties", False)
    return out


def _type_ok(value, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _validate_value(value, schema: dict, path: str, errors: list) -> None:
    stype = schema.get("type")
    if stype and not _type_ok(value, stype):
        errors.append("{0} 类型应为 {1}".format(path, stype))
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append("{0} 取值必须是 {1} 之一".format(path, schema["enum"]))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("{0} 不能小于 {1}".format(path, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("{0} 不能大于 {1}".format(path, schema["maximum"]))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("{0} 长度不能小于 {1}".format(path, schema["minLength"]))
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("{0} 长度不能大于 {1}".format(path, schema["maxLength"]))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("{0} 至少需要 {1} 项".format(path, schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("{0} 最多允许 {1} 项".format(path, schema["maxItems"]))
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(value):
                _validate_value(item, items, "{0}[{1}]".format(path, i), errors)
    if isinstance(value, dict):
        props = schema.get("properties") or {}
        additional = schema.get("additionalProperties", False)
        for key in value.keys():
            if key not in props and not additional:
                errors.append("{0} 不支持的参数: {1}".format(path, key))
        for key, sub in props.items():
            if key in value:
                _validate_value(value[key], sub, "{0}.{1}".format(path, key), errors)


def validate_params(schema: dict, params) -> list:
    """按工具参数 schema 校验调用参数，返回错误列表（空列表表示通过）。"""
    errors = []
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return ["params 必须是对象"]
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    for name in required:
        if name not in params:
            errors.append("缺少必填参数: {0}".format(name))
    if not schema.get("additionalProperties", False):
        for key in params.keys():
            if key not in props:
                errors.append("不支持的参数: {0}".format(key))
    for key, sub in props.items():
        if key in params:
            _validate_value(params[key], sub, key, errors)
    return errors


def _apply_defaults(schema: dict, params: dict) -> dict:
    """填充 schema 中声明的默认值（不改动调用方传入的对象）。"""
    out = dict(params or {})
    for key, sub in (schema.get("properties") or {}).items():
        if key not in out and "default" in sub:
            out[key] = copy.deepcopy(sub["default"])
    return out


# ── 注册与发现 ──

_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


def register_tool(name, description, parameters, handler, *, data_scope=None,
                  read_only=True, max_result_bytes=_MAX_RESULT_BYTES) -> dict:
    """注册一个只读工具并返回其元数据（同名重复注册会覆盖，便于测试与迭代）。"""
    if not isinstance(name, str) or not _NAME_RE.match(name):
        raise ValueError("工具名不合法: {0!r}（须为小写字母开头的 snake_case）".format(name))
    if not callable(handler):
        raise ValueError("工具 handler 必须可调用")
    schema = _normalize_schema(parameters or {"type": "object", "properties": {}})
    if schema.get("type") != "object":
        raise ValueError("工具参数 schema 根节点必须是 object")
    spec = {
        "name": name,
        "description": str(description or "")[:500],
        "parameters": schema,
        "data_scope": [str(x) for x in (data_scope or [])],
        "read_only": bool(read_only),
        # 阶段一不向模型暴露；即使将来打开总开关，各工具也需要显式声明 model_visible 才会出现
        "model_visible": False,
        "max_result_bytes": int(max_result_bytes),
        "handler": handler,
    }
    with _TOOL_LOCK:
        _TOOLS[name] = spec
    return _public_spec(spec)


def unregister_tool(name) -> bool:
    with _TOOL_LOCK:
        return _TOOLS.pop(name, None) is not None


def _public_spec(spec: dict) -> dict:
    """对外元数据（剔除 handler，避免调用方拿到内部实现）。"""
    return {
        "name": spec["name"],
        "description": spec["description"],
        "parameters": copy.deepcopy(spec["parameters"]),
        "data_scope": list(spec["data_scope"]),
        "read_only": spec["read_only"],
        "model_visible": spec["model_visible"],
    }


def get_tool(name) -> dict:
    """返回工具的公开元数据（含 handler 的完整 spec 不对外暴露；handler 仅供调度内部使用）。"""
    with _TOOL_LOCK:
        spec = _TOOLS.get(name)
    return _public_spec(spec) if spec else None


def _get_raw(name):
    with _TOOL_LOCK:
        return _TOOLS.get(name)


def list_tools() -> list:
    """按名称排序列出全部工具的公开元数据。"""
    with _TOOL_LOCK:
        specs = list(_TOOLS.values())
    return [_public_spec(spec) for spec in sorted(specs, key=lambda s: s["name"])]


def model_tool_specs() -> list:
    """返回可以暴露给模型的工具定义。

    阶段一恒为空：MODEL_EXPOSURE_ENABLED=False 时不返回任何工具，
    这是"工具不得开放给模型实际调用"这一约束的代码化体现。
    """
    if not MODEL_EXPOSURE_ENABLED:
        return []
    with _TOOL_LOCK:
        specs = list(_TOOLS.values())
    return [
        {"name": spec["name"], "description": spec["description"],
         "parameters": copy.deepcopy(spec["parameters"])}
        for spec in sorted(specs, key=lambda s: s["name"])
        if spec["model_visible"]
    ]


def list_tools_response() -> dict:
    """供 IPC 命令 agent_tools_list 使用的完整响应。"""
    return {
        "ok": True,
        "tools": list_tools(),
        "count": len(list_tools()),
        "model_exposure_enabled": bool(MODEL_EXPOSURE_ENABLED),
    }


# ── 执行调度 ──

def call_tool(name, params=None) -> dict:
    """执行一个已注册工具并返回结构化结果。

    返回：
      成功 {"ok": True, "tool": name, "data": {...}, "meta": {...}}
      失败 {"ok": False, "tool": name, "error": {"code", "params"}, "meta": {...}}
    meta 固定包含 read_only / model_visible / elapsed_ms，成功时含 bytes，
    失败时按需含 data_scope。任何异常都不会向外抛出。
    """
    started = time.perf_counter()
    meta = {"read_only": True, "model_visible": False, "elapsed_ms": 0.0}

    def _finish(payload: dict) -> dict:
        meta["elapsed_ms"] = round((time.perf_counter() - started) * 1000.0, 2)
        payload["meta"] = meta
        return payload

    spec = _get_raw(name) if isinstance(name, str) else None
    if spec is None:
        return _finish({"ok": False, "tool": name,
                        "error": {"code": "tool.err.unknownTool", "params": {"name": str(name)[:64]}}})

    meta["data_scope"] = list(spec["data_scope"])
    errors = validate_params(spec["parameters"], params)
    if errors:
        return _finish({"ok": False, "tool": name,
                        "error": {"code": "tool.err.invalidParams", "params": {"errors": errors}}})
    args = _apply_defaults(spec["parameters"], params or {})
    try:
        data = spec["handler"](args)
    except ToolError as e:
        return _finish({"ok": False, "tool": name,
                        "error": {"code": e.code, "params": dict(e.params)}})
    except Exception as e:  # 任何未预期异常都转成结构化错误，不向上抛
        return _finish({"ok": False, "tool": name,
                        "error": {"code": "tool.err.internal", "params": {"detail": str(e)[:200]}}})
    if data is None:
        data = {}
    try:
        size = len(json.dumps(data, ensure_ascii=False, default=str).encode("utf-8"))
    except Exception:
        return _finish({"ok": False, "tool": name,
                        "error": {"code": "tool.err.internal", "params": {"detail": "结果无法序列化"}}})
    if size > spec["max_result_bytes"]:
        return _finish({"ok": False, "tool": name,
                        "error": {"code": "tool.err.resultTooLarge",
                                  "params": {"bytes": size, "limit": spec["max_result_bytes"]}}})
    meta["bytes"] = size
    return _finish({"ok": True, "tool": name, "data": data})


# ── 六项内置只读工具 ──

def _num(value, default=0.0):
    """兼容 system_state 的 {"value": x, "ts": t} 包装与裸数值。"""
    if isinstance(value, dict):
        value = value.get("value", 0)
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except Exception:
        return default


def _text(value, max_len=80):
    if value is None:
        return ""
    try:
        return str(value).strip()[:max_len]
    except Exception:
        return ""


def _state_snapshot():
    from core.system_state import system_state
    snap = system_state.snapshot()
    return snap if isinstance(snap, dict) else {}


def _h_system_metrics(args):
    mon = _state_snapshot().get("monitor")
    if not isinstance(mon, dict) or not mon:
        raise ToolError("tool.err.noData", source="system_state.monitor",
                        hint="监控采集尚未产生数据")
    return {
        "available": True,
        "cpu_percent": round(_num(mon.get("cpu")), 1),
        "memory_percent": round(_num(mon.get("memory")), 1),
        "disk_percent": round(_num(mon.get("disk")), 1),
        "network_speed_mbps": round(_num(mon.get("network_speed")), 1),
        "updated_at": _text(mon.get("timestamp"), 32),
        "source": "system_state.monitor",
    }


def _h_hardware_info(args):
    hw = _state_snapshot().get("hardware")
    if not isinstance(hw, dict) or not hw:
        raise ToolError("tool.err.noData", source="system_state.hardware",
                        hint="硬件信息尚未采集完成")
    result = {"available": True, "source": "system_state.hardware"}
    cpu = hw.get("cpu") if isinstance(hw.get("cpu"), dict) else None
    if cpu:
        result["cpu"] = {
            "model": _text(cpu.get("model") or cpu.get("short_model"), 80),
            "cores": int(_num(cpu.get("cores"))),
            "threads": int(_num(cpu.get("threads"))),
            "freq_current": _text(cpu.get("freq_current"), 32),
        }
    gpu = hw.get("gpu") if isinstance(hw.get("gpu"), dict) else None
    if gpu:
        result["gpu"] = {
            "name": _text(gpu.get("short_name") or gpu.get("name"), 80),
            "vram_gb": round(_num(gpu.get("vram_gb")), 1),
            "vram_type": _text(gpu.get("vram_type"), 24),
            "utilization": round(_num(gpu.get("utilization")), 1),
        }
    mem = hw.get("memory") if isinstance(hw.get("memory"), dict) else None
    if mem:
        result["memory"] = {
            "total_gb": round(_num(mem.get("total_gb")), 1),
            "type": _text(mem.get("type"), 24),
            "frequency": _text(mem.get("frequency"), 24),
            "available_gb": round(_num(mem.get("available_gb")), 1),
        }
    disk = hw.get("disk") if isinstance(hw.get("disk"), dict) else None
    if disk:
        result["disk"] = {
            "model": _text(disk.get("model"), 60),
            "capacity_gb": round(_num(disk.get("capacity_gb")), 1),
            "type": _text(disk.get("type"), 24),
        }
    system = hw.get("system") if isinstance(hw.get("system"), dict) else None
    if system:
        result["system"] = {
            "os": _text(system.get("os"), 60),
            "edition": _text(system.get("edition"), 60),
        }
    if len(result) == 2:  # 只有 available/source，没有任何可用分区
        raise ToolError("tool.err.noData", source="system_state.hardware")
    return result


def _h_processes(args):
    mon = _state_snapshot().get("monitor")
    procs = mon.get("processes") if isinstance(mon, dict) else None
    if not isinstance(procs, list) or not procs:
        raise ToolError("tool.err.noData", source="system_state.monitor.processes",
                        hint="进程列表尚未采集")
    items = []
    for p in procs:
        if not isinstance(p, dict):
            continue
        items.append({
            "pid": int(_num(p.get("pid"))),
            "name": _text(p.get("name"), 80),
            "cpu_percent": round(_num(p.get("cpu")), 1),
            "memory_percent": round(_num(p.get("memory")), 1),
            "rss_bytes": int(_num(p.get("memory_bytes"))),
        })
    sort_by = args.get("sort_by") or "cpu"
    key = "cpu_percent" if sort_by == "cpu" else "memory_percent"
    # 稳定排序：同值时按 pid 升序，保证相同输入下结果可复现
    items.sort(key=lambda it: (-it[key], it["pid"]))
    limit = int(args.get("limit") or 10)
    return {
        "available": True,
        "sort_by": sort_by,
        "total_available": len(items),
        "returned": len(items[:limit]),
        "processes": items[:limit],
        "source": "system_state.monitor.processes",
    }


def _h_nas_status(args):
    nas = _state_snapshot().get("nas")
    if not isinstance(nas, dict) or not nas:
        raise ToolError("tool.err.noData", source="system_state.nas",
                        hint="尚未配置 NAS 或尚未采集")
    name_filter = _text(args.get("name"), 64)
    include_offline = bool(args.get("include_offline", True))
    devices = []
    for name, dv in nas.items():
        if not isinstance(dv, dict):
            continue
        if name_filter and _text(name, 64) != name_filter:
            continue
        online_raw = dv.get("online")
        online = not (online_raw is False
                      or str(online_raw).strip().lower() in ("false", "0", "offline", "off"))
        if not include_offline and not online:
            continue
        mem = dv.get("memory")
        mem_pct = mem.get("percent") if isinstance(mem, dict) else mem
        dsk = dv.get("disk")
        dsk_pct = dsk.get("percent") if isinstance(dsk, dict) else dsk
        load = dv.get("load") if isinstance(dv.get("load"), dict) else None
        docker = dv.get("docker") if isinstance(dv.get("docker"), dict) else None
        hw = dv.get("hardware") if isinstance(dv.get("hardware"), dict) else None
        device = {
            "name": _text(name, 64),
            "online": bool(online),
            "cpu_percent": round(_num(dv.get("cpu")), 1),
            "memory_percent": round(_num(mem_pct), 1),
            "disk_percent": round(_num(dsk_pct), 1),
            "temperature_c": (round(_num(dv.get("temperature"), None), 1)
                              if dv.get("temperature") is not None else None),
            "uptime": _text(dv.get("uptime"), 40),
            "last_updated": _text(dv.get("last_updated"), 32),
            "last_error": _text(dv.get("last_error"), 120),
            "is_mock": bool(dv.get("is_mock")),
        }
        if load:
            device["load"] = {
                "load_1m": round(_num(load.get("load_1m")), 2),
                "load_5m": round(_num(load.get("load_5m")), 2),
                "load_15m": round(_num(load.get("load_15m")), 2),
            }
        if docker:
            device["docker"] = {
                "total_containers": int(_num(docker.get("total_containers"))),
                "running": int(_num(docker.get("running"))),
            }
        if hw:
            # 白名单：只带运行状态说明需要的规格摘要，绝不带 host / 凭据
            device["hardware"] = {
                "cpu_model": _text(hw.get("cpu_model"), 80),
                "cpu_cores": _text(hw.get("cpu_cores"), 8),
                "memory_total": _text(hw.get("memory_total"), 24),
                "disk_total": _text(hw.get("disk_total"), 24),
                "os": _text(hw.get("os"), 60),
            }
        devices.append(device)
    if name_filter and not devices:
        raise ToolError("tool.err.noData", source="system_state.nas", name=name_filter)
    devices.sort(key=lambda d: d["name"])
    return {
        "available": True,
        "count": len(devices),
        "devices": devices,
        "source": "system_state.nas",
    }


def _h_performance_history(args):
    hours = int(args.get("hours") or 24)
    try:
        from core.monitor import query_history
        result = query_history(hours * 3600)
    except Exception as e:
        raise ToolError("tool.err.noData", source="monitor.query_history", detail=str(e)[:120])
    if not isinstance(result, dict):
        raise ToolError("tool.err.noData", source="monitor.query_history")
    if result.get("error"):
        return {
            "available": False,
            "reason": _text(result.get("error"), 40),
            "count": int(_num(result.get("count"))),
            "hours": hours,
            "source": "monitor.query_history",
        }
    return {
        "available": True,
        "hours": hours,
        "count": int(_num(result.get("count"))),
        "cpu": {
            "avg": round(_num(result.get("cpu_avg")), 1),
            "max": round(_num(result.get("cpu_max")), 1),
        },
        "memory": {
            "avg": round(_num(result.get("memory_avg")), 1),
            "max": round(_num(result.get("memory_max")), 1),
        },
        "disk": {
            "avg": round(_num(result.get("disk_avg")), 1),
            "max": round(_num(result.get("disk_max")), 1),
        },
        "source": "monitor.query_history",
    }


def _h_search_memory(args):
    from core import ai_memory as _aim
    tags = args.get("tags")
    result = _aim.search_memory(
        args.get("query", ""),
        limit=args.get("limit", 5),
        kind=args.get("kind"),
        tags=tags if isinstance(tags, list) else None,
    )
    return {
        "enabled": bool(result.get("enabled")),
        "available": bool(result.get("available")),
        "query": _text(result.get("query"), 200),
        "total_matched": int(result.get("total_matched", 0)),
        "count": int(result.get("count", 0)),
        "results": result.get("results", []),
        "source": "ai_memory.search_memory",
    }


def _register_builtin_tools():
    """注册六项内置只读工具（模块导入时执行一次；重复导入幂等）。"""
    register_tool(
        "get_system_metrics",
        "查询实时系统指标：CPU/内存/磁盘使用率与网络速率。只读，取自已采集的系统状态。",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _h_system_metrics,
        data_scope=["monitor.cpu", "monitor.memory", "monitor.disk", "monitor.network_speed", "monitor.timestamp"],
    )
    register_tool(
        "get_hardware_info",
        "查询硬件信息：CPU/GPU/内存/磁盘/操作系统的型号与规格摘要。只读，复用硬件采集缓存。",
        {"type": "object", "properties": {}, "additionalProperties": False},
        _h_hardware_info,
        data_scope=["hardware.cpu", "hardware.gpu", "hardware.memory", "hardware.disk", "hardware.system"],
    )
    register_tool(
        "get_processes",
        "查询进程列表（按 CPU 或内存排序）。只读，返回 pid/名称/占用率，不含命令行。",
        {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10,
                          "description": "返回条数上限（1-50）"},
                "sort_by": {"type": "string", "enum": ["cpu", "memory"], "default": "cpu",
                            "description": "排序字段"},
            },
            "additionalProperties": False,
        },
        _h_processes,
        data_scope=["monitor.processes.pid", "monitor.processes.name",
                    "monitor.processes.cpu", "monitor.processes.memory"],
    )
    register_tool(
        "get_nas_status",
        "查询 NAS 设备运行状态：在线状态、CPU/内存/磁盘、温度、运行时长、Docker 数量。"
        "只读，不返回主机地址与任何凭据。",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "minLength": 1, "maxLength": 64,
                         "description": "按设备名精确过滤（可选）"},
                "include_offline": {"type": "boolean", "default": True,
                                    "description": "是否包含离线设备"},
            },
            "additionalProperties": False,
        },
        _h_nas_status,
        data_scope=["nas.name", "nas.online", "nas.cpu", "nas.memory", "nas.disk",
                    "nas.temperature", "nas.uptime", "nas.load", "nas.docker",
                    "nas.hardware", "nas.last_error", "nas.last_updated"],
    )
    register_tool(
        "get_performance_history",
        "查询历史性能聚合数据：指定小时数内的 CPU/内存/磁盘平均值与峰值。只读。",
        {
            "type": "object",
            "properties": {
                "hours": {"type": "integer", "minimum": 1, "maximum": 168, "default": 24,
                          "description": "回溯小时数（1-168）"},
            },
            "additionalProperties": False,
        },
        _h_performance_history,
        data_scope=["snapshots.aggregate.cpu", "snapshots.aggregate.memory", "snapshots.aggregate.disk"],
    )
    register_tool(
        "search_memory",
        "检索本地长期记忆：中文/英文关键词匹配内容与结构化元数据（kind/tags/source），"
        "按相关性排序返回。记忆未开启时返回 enabled=false。",
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 200,
                          "description": "检索关键词（中文或英文）"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5,
                          "description": "返回条数上限（1-20）"},
                "kind": {"type": "string", "maxLength": 32, "description": "按类别过滤（可选）"},
                "tags": {"type": "array", "items": {"type": "string", "maxLength": 32},
                         "maxItems": 8, "description": "按标签过滤（任一命中即可，可选）"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        _h_search_memory,
        data_scope=["ai_memory.id", "ai_memory.ts", "ai_memory.content",
                    "ai_memory.kind", "ai_memory.tags", "ai_memory.source"],
    )


_register_builtin_tools()
