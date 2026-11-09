"""AI 客户端：支持 Ollama 本地模型和 OpenAI 兼容 API（DeepSeek 等）的流式对话。"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import threading
import urllib.parse
import urllib.request
from typing import Iterator, Optional

from core import net_policy


def _err(code: str, **params) -> dict:
    """结构化错误：{"code": ..., "params": {...}}。

    后端不再拼中文文案，文案由前端按 code 查词典渲染（见 locales/*.js 的 ai.err.*）。
    code 与前端词典 key 完全同名，缺 key 时前端会显示 code 本身而不是空白。
    """
    return {"code": code, "params": params}


def _sanitize_detail(value, limit=160) -> str:
    """错误详情脱敏：去掉 URL（含可能的凭据/查询串）与 host，只保留错误类型与摘要。"""
    text = str(value or "")
    text = re.sub(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s'\")]+", "<url>", text)
    text = re.sub(r"(?i)(authorization|bearer|api[_-]?key|password|token)\s*[=:]\s*\S+", r"\1=<redacted>", text)
    text = re.sub(r"[\r\n]+", " ", text).strip()
    return text[:limit]


def _allow_insecure_http(ai_cfg: dict) -> list:
    """HTTP 例外授权清单（仅 ip[:port]，公网与域名永远不允许）。"""
    if not isinstance(ai_cfg, dict):
        return []
    values = ai_cfg.get("allow_insecure_http")
    if isinstance(values, list):
        return [v for v in values if isinstance(v, str)]
    openai_cfg = ai_cfg.get("openai")
    if isinstance(openai_cfg, dict) and isinstance(openai_cfg.get("allow_insecure_http"), list):
        return [v for v in openai_cfg["allow_insecure_http"] if isinstance(v, str)]
    return []


def _ca_bundle(ai_cfg: dict):
    """返回 (规范化路径, 错误码)。

    DL-SEC-06-07 / CA fail-open：未配置 -> ("", "") 表示使用系统信任；
    显式配置但无效/不可读 -> ("", "ai.err.caBundleUnavailable")，调用方
    必须失败关闭，不能静默退回系统信任。
    """
    if not isinstance(ai_cfg, dict):
        return "", ""
    value = None
    explicit = False
    if "ca_bundle" in ai_cfg:
        value = ai_cfg.get("ca_bundle")
        explicit = value is not None and value != ""
    if not explicit:
        openai_cfg = ai_cfg.get("openai")
        if isinstance(openai_cfg, dict) and "ca_bundle" in openai_cfg:
            value = openai_cfg.get("ca_bundle")
            explicit = value is not None and value != ""
    if not explicit:
        return "", ""
    if not isinstance(value, str) or not value.strip():
        return "", "ai.err.caBundleUnavailable"
    try:
        from core import path_policy as _pp
        norm, err = _pp.validate_local_file(value)
        if err:
            return "", "ai.err.caBundleUnavailable"
        return norm, ""
    except Exception:
        return "", "ai.err.caBundleUnavailable"


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """禁用自动重定向：任何 3xx 直接变成 HTTPError，不发出第二次请求。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _resolve_policy(url: str, ai_cfg: dict) -> dict:
    return net_policy.check_endpoint(url, _allow_insecure_http(ai_cfg))


def _build_connection(url: str, policy: dict):
    """把已校验的 loopback 主机名替换为已验证的数值 IP，并返回原始 Host 头。"""
    if not policy.get("pinned"):
        return policy["url"], None
    parsed = urllib.parse.urlsplit(policy["url"])
    host = policy["connect_host"]
    if ":" in host and not host.startswith("["):
        host = "[" + host + "]"
    netloc = host if parsed.port is None else "{0}:{1}".format(host, parsed.port)
    new_url = urllib.parse.urlunsplit(
        (parsed.scheme, netloc, parsed.path or "/", parsed.query, parsed.fragment)
    )
    return new_url, parsed.netloc


def _open_stream(url: str, body: bytes, headers: dict, timeout: int, policy: dict, ca_bundle: str):
    connect_url, host_header = _build_connection(url, policy)
    req_headers = dict(headers or {})
    if host_header:
        req_headers["Host"] = host_header
    auth_value = None
    for key in list(req_headers.keys()):
        if key.lower() == "authorization":
            auth_value = req_headers.pop(key)
            break
    handlers = [
        # loopback 必须绕过系统代理，确保请求直达本机；其余保持默认代理行为
        urllib.request.ProxyHandler({} if policy.get("bypass_proxy") else None),
        _NoRedirectHandler(),
    ]
    if policy.get("scheme") == "https":
        try:
            context = ssl.create_default_context(cafile=ca_bundle or None)
        except Exception as e:
            raise net_policy.EndpointPolicyError("ai.err.caBundleInvalid",
                                                 detail=_sanitize_detail(e))
        handlers.append(urllib.request.HTTPSHandler(context=context))
    opener = urllib.request.build_opener(*handlers)
    request = urllib.request.Request(connect_url, data=body, headers=req_headers, method="POST")
    if auth_value:
        # 双保险：即使将来误引入重定向处理器，Authorization 也不会被转发
        request.add_unredirected_header("Authorization", auth_value)
    return opener.open(request, timeout=timeout)


def _classify_http_error(e) -> Optional[dict]:
    code = getattr(e, "code", None)
    if code in (301, 302, 303, 307, 308):
        return _err("ai.err.redirectBlocked", status=code)
    return None


def _human_error(provider: str, err: Exception) -> dict:
    """将技术异常转换为结构化错误（code + params）。"""
    msg = str(err)
    # ── 连接被拒绝 / 无法连接 ──
    if "ConnectionRefusedError" in msg or "Connection refused" in msg or "WinError 10061" in msg:
        if provider == "ollama":
            return _err("ai.err.ollamaNotRunning")
        return _err("ai.err.cloudUnreachable")
    # ── DNS 解析失败 ──
    if "getaddrinfo" in msg or "Name or service not known" in msg or "No address" in msg:
        if provider == "ollama":
            return _err("ai.err.ollamaBadAddress")
        return _err("ai.err.cloudBadAddress")
    # ── 超时 ──
    if "timeout" in msg.lower() or "timed out" in msg:
        if provider == "ollama":
            return _err("ai.err.ollamaTimeout")
        return _err("ai.err.cloudTimeout")
    # ── SSL / 证书错误 ──
    if "SSL" in msg or "certificate" in msg.lower():
        return _err("ai.err.tlsInvalid")
    # ── 兜底 ──
    if provider == "ollama":
        return _err("ai.err.ollamaRequestFailed", detail=_sanitize_detail(msg))
    return _err("ai.err.cloudRequestFailed", detail=_sanitize_detail(msg))


def _load_ai_config() -> dict:
    """优先从 user_config.json 读取 AI 配置，缺失时回退到 config.json。

    user_config.json 位于 APPDATA 环境变量指向的 DigitalLab 目录，由设置面板保存 AI 配置
    （结构：{"ai": {"provider": ..., "ollama": {...,}, "openai": {...}}}）。
    """
    # BB-C1-01-R1：先统一迁移/校验凭据；迁移失败时不得使用旧明文 AI Key。
    try:
        from core import secret_store as _ss
        if not _ss.ensure_credentials_ready().get("ok"):
            return {}
    except Exception:
        return {}

    # ── 1. 优先 user_config.json ──
    user_path = None
    try:
        from core import config as _cfg
    except Exception:
        _cfg = None
    if _cfg is not None:
        try:
            user_path = _cfg._get_user_config_path()
        except Exception:
            user_path = None
    if not user_path:
        appdata = os.environ.get("APPDATA") or os.environ.get("ProgramData") or ""
        user_path = os.path.join(appdata, "DigitalLab", "user_config.json")
    if user_path and os.path.exists(user_path):
        try:
            with open(user_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            ai = raw.get("ai")
            if isinstance(ai, dict) and ai:
                try:
                    from core import secret_store as _ss
                    openai = ai.get("openai")
                    if isinstance(openai, dict) and isinstance(openai.get("api_key"), str):
                        ok, plain = _ss.get_runtime_secret(openai.get("api_key"))
                        if not ok:
                            openai["api_key"] = ""
                        else:
                            openai["api_key"] = plain
                except Exception:
                    ai = {}
                return ai
        except Exception:
            pass

    # ── 2. 回退 config.json（只保留非敏感字段；旧明文 api_key 不使用）──
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        ai = raw.get("ai", {})
        if isinstance(ai, dict):
            ai = dict(ai)
            openai = ai.get("openai")
            if isinstance(openai, dict):
                openai = dict(openai)
                openai.pop("api_key", None)
                ai["openai"] = openai
        return ai if isinstance(ai, dict) else {}
    except Exception:
        return {}


def chat_stream(
    messages: list[dict],
    provider: str = "ollama",
    on_token=None,
    config_override: Optional[dict] = None,
    lang: str = "zh-CN",
) -> "str | dict":
    """
    流式对话，每收到一个 token 调用 on_token(token_text)。

    lang：界面语言，用于选择流式截断提示的文案；未知值回退中文（旧前端不带该字段）。
    成功返回完整回复文本（str）；失败返回结构化错误 dict（{"code": ..., "params": {...}}），
    文案由前端按 code 渲染，后端不再拼中文。
    """
    ai_cfg = config_override or _load_ai_config()
    if not ai_cfg:
        return _err("ai.err.notConfigured")

    if provider == "ollama":
        return _ollama_stream(messages, ai_cfg.get("ollama", {}), on_token, lang, ai_cfg)
    else:
        return _openai_stream(messages, ai_cfg.get("openai", {}), on_token, lang, ai_cfg)


def _normalize_base(base_url: str, default_scheme: str) -> str:
    """base_url 缺少协议时补默认协议（不改变已有合法 URL）。"""
    text = str(base_url or "").strip()
    if not text:
        return text
    if "://" not in text:
        return default_scheme + "://" + text
    return text


class _StreamLimitError(Exception):
    """BB-C1-03：流式响应超过单行/总量硬上限。"""


_MAX_STREAM_LINE_CHARS = 1024 * 1024
_MAX_STREAM_TOTAL_CHARS = 8 * 1024 * 1024


def _iter_response_lines(resp) -> Iterator[str]:
    """以增量 UTF-8 解码器读取 HTTP 流式响应，逐行产出文本。

    流式响应按 TCP 分块到达，中文等多字节字符可能恰好被块边界切断；
    对每个块直接 decode 会破坏这类字符、产生乱码或替换符。
    这里先按字节块读取并用增量解码器跨块还原完整文本，再按换行
    切出完整行，供 NDJSON / SSE 协议逐行解析。
    """
    import codecs

    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    read_chunk = getattr(resp, "read1", None) or getattr(getattr(resp, "fp", None), "read1", None) or resp.read
    buf = ""
    total = 0
    while True:
        chunk = read_chunk(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > _MAX_STREAM_TOTAL_CHARS:
            raise _StreamLimitError("total")
        buf += decoder.decode(chunk)
        parts = buf.split("\n")
        buf = parts.pop()
        if len(buf) > _MAX_STREAM_LINE_CHARS:
            raise _StreamLimitError("line")
        for line in parts:
            if len(line) > _MAX_STREAM_LINE_CHARS:
                raise _StreamLimitError("line")
            yield line
    tail = decoder.decode(b"", final=True)
    if tail:
        buf += tail
    if len(buf) > _MAX_STREAM_LINE_CHARS:
        raise _StreamLimitError("line")
    if buf:
        yield buf


# ── 失控防护：防止模型陷入无限生成 ──
_MAX_REPLY_CHARS = 4096   # 单次回复字符数上限
_MAX_THINKING_CHARS = 32768  # thinking/reasoning 通道独立总量上限
_REPEAT_MIN_PERIOD = 2    # 重复片段最小周期（字符）
_REPEAT_MAX_PERIOD = 12   # 重复片段最大周期（字符）
_REPEAT_MAX_COUNT = 6     # 同一片段连续重复达到该次数即判定失控
# 流式截断提示：按界面语言选择（lang 随 ai_chat 请求下发，缺省中文；旧前端不带 lang 时走中文）
_STOP_NOTES = {
    "zh-CN": "\n[检测到模型重复输出，已自动停止]",
    "en-US": "\n[Model output was repeating; generation stopped automatically]",
    "ja-JP": "\n[モデルの出力が繰り返しになったため、自動的に停止しました]",
}


def _stop_note(lang: str) -> str:
    return _STOP_NOTES.get(lang, _STOP_NOTES["zh-CN"])


def _should_stop(text: str) -> bool:
    """超过总长上限或检测到周期性重复输出时返回 True，用于截断失控回复。"""
    if len(text) >= _MAX_REPLY_CHARS:
        return True
    for period in range(_REPEAT_MIN_PERIOD, _REPEAT_MAX_PERIOD + 1):
        need = period * _REPEAT_MAX_COUNT
        if len(text) >= need and text[-need:] == text[-period:] * _REPEAT_MAX_COUNT:
            return True
    return False


def _ollama_stream(messages: list[dict], cfg: dict, on_token, lang: str = "zh-CN",
                   ai_cfg=None) -> str:
    """Ollama 流式 API（P0：端点策略 + 禁重定向 + loopback 绑定已验证 IP）。"""
    base_url = _normalize_base(cfg.get("base_url", "http://localhost:11434"), "http")
    model = cfg.get("model", "llama3")

    url = f"{base_url.rstrip('/')}/api/chat"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    })
    headers = {"Content-Type": "application/json"}

    try:
        import urllib.error

        policy = _resolve_policy(url, ai_cfg or {})
        ca_path, ca_error = _ca_bundle(ai_cfg or {})
        if ca_error:
            return _err(ca_error)
        full_text = ""
        thinking_total = 0
        with _open_stream(url, body.encode("utf-8"), headers, 120,
                          policy, ca_path) as resp:
            for line in _iter_response_lines(resp):
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    # 思考过程（如 DeepSeek-R1 通过 Ollama 运行）
                    thinking = msg.get("thinking", "")
                    if thinking:
                        thinking_total += len(thinking)
                        if thinking_total > _MAX_THINKING_CHARS:
                            note = _stop_note(lang)
                            if on_token:
                                on_token(note, "content")
                            break
                        if on_token:
                            on_token(thinking, "thinking")
                    token = msg.get("content", "")
                    if token:
                        full_text += token
                        if on_token:
                            on_token(token, "content")
                        if _should_stop(full_text):
                            note = _stop_note(lang)
                            full_text += note
                            if on_token:
                                on_token(note, "content")
                            break
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

        return full_text

    except _StreamLimitError:
        return _err("ai.err.streamTooLarge")
    except net_policy.EndpointPolicyError as e:
        return _err(e.code, **e.params)
    except urllib.error.HTTPError as e:
        redirected = _classify_http_error(e)
        if redirected is not None:
            return redirected
        if e.code == 404:
            return _err("ai.err.ollamaModelMissing", model=model)
        return _err("ai.err.ollamaHttpError", status=e.code)
    except urllib.error.URLError as e:
        return _human_error("ollama", e.reason)
    except Exception as e:
        return _human_error("ollama", e)


def _openai_stream(messages: list[dict], cfg: dict, on_token, lang: str = "zh-CN",
                   ai_cfg=None) -> str:
    """OpenAI 兼容 API 流式（DeepSeek 等）。P0：端点策略 + 禁重定向 + TLS 校验。"""
    api_key = cfg.get("api_key", "")
    base_url = _normalize_base(cfg.get("base_url", "https://api.deepseek.com"), "https")
    model = cfg.get("model", "deepseek-chat")

    if not api_key:
        return _err("ai.err.cloudNoApiKey")

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    })
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    try:
        import urllib.error

        policy = _resolve_policy(url, ai_cfg or {})
        ca_path, ca_error = _ca_bundle(ai_cfg or {})
        if ca_error:
            return _err(ca_error)
        full_text = ""
        thinking_total = 0
        with _open_stream(url, body.encode("utf-8"), headers, 120,
                          policy, ca_path) as resp:
            for line in _iter_response_lines(resp):
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    # 思考过程（DeepSeek-R1 等推理模型）
                    reasoning = delta.get("reasoning_content", "")
                    if reasoning:
                        thinking_total += len(reasoning)
                        if thinking_total > _MAX_THINKING_CHARS:
                            note = _stop_note(lang)
                            if on_token:
                                on_token(note, "content")
                            break
                        if on_token:
                            on_token(reasoning, "thinking")
                    token = delta.get("content", "")
                    if token:
                        full_text += token
                        if on_token:
                            on_token(token, "content")
                        if _should_stop(full_text):
                            note = _stop_note(lang)
                            full_text += note
                            if on_token:
                                on_token(note, "content")
                            break
                except json.JSONDecodeError:
                    continue

        return full_text

    except _StreamLimitError:
        return _err("ai.err.streamTooLarge")
    except net_policy.EndpointPolicyError as e:
        return _err(e.code, **e.params)
    except urllib.error.HTTPError as e:
        redirected = _classify_http_error(e)
        if redirected is not None:
            return redirected
        if e.code == 401:
            return _err("ai.err.cloudInvalidKey")
        elif e.code == 402:
            return _err("ai.err.cloudNoBalance")
        elif e.code == 403:
            return _err("ai.err.cloudNoPermission")
        elif e.code == 429:
            return _err("ai.err.cloudRateLimited")
        elif e.code == 503:
            return _err("ai.err.cloudUnavailable")
        else:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if "insufficient" in err_body.lower() or "balance" in err_body.lower() or "quota" in err_body.lower():
                return _err("ai.err.cloudNoBalance")
            return _err("ai.err.cloudHttpError", status=e.code)
    except urllib.error.URLError as e:
        return _human_error("openai", e.reason)
    except Exception as e:
        return _human_error("openai", e)