"""AI 客户端：支持 Ollama 本地模型和 OpenAI 兼容 API（DeepSeek 等）的流式对话。"""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Iterator, Optional


def _err(code: str, **params) -> dict:
    """结构化错误：{"code": ..., "params": {...}}。

    后端不再拼中文文案，文案由前端按 code 查词典渲染（见 locales/*.js 的 ai.err.*）。
    code 与前端词典 key 完全同名，缺 key 时前端会显示 code 本身而不是空白。
    """
    return {"code": code, "params": params}


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
        return _err("ai.err.ollamaRequestFailed", detail=msg)
    return _err("ai.err.cloudRequestFailed", detail=msg)


def _load_ai_config() -> dict:
    """优先从 user_config.json 读取 AI 配置，缺失时回退到 config.json。

    user_config.json 位于 APPDATA 环境变量指向的 DigitalLab 目录，由设置面板保存 AI 配置
    （结构：{"ai": {"provider": ..., "ollama": {...,}, "openai": {...}}}）。
    """
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
                return ai
        except Exception:
            pass

    # ── 2. 回退 config.json ──
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return raw.get("ai", {})
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
        return _ollama_stream(messages, ai_cfg.get("ollama", {}), on_token, lang)
    else:
        return _openai_stream(messages, ai_cfg.get("openai", {}), on_token, lang)


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
    while True:
        chunk = read_chunk(65536)
        if not chunk:
            break
        buf += decoder.decode(chunk)
        parts = buf.split("\n")
        buf = parts.pop()
        for line in parts:
            yield line
    tail = decoder.decode(b"", final=True)
    if tail:
        buf += tail
    if buf:
        yield buf


# ── 失控防护：防止模型陷入无限生成 ──
_MAX_REPLY_CHARS = 4096   # 单次回复字符数上限
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


def _ollama_stream(messages: list[dict], cfg: dict, on_token, lang: str = "zh-CN") -> str:
    """Ollama 流式 API。"""
    base_url = cfg.get("base_url", "http://localhost:11434")
    model = cfg.get("model", "llama3")

    url = f"{base_url.rstrip('/')}/api/chat"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    })

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        full_text = ""
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in _iter_response_lines(resp):
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    msg = chunk.get("message", {})
                    # 思考过程（如 DeepSeek-R1 通过 Ollama 运行）
                    thinking = msg.get("thinking", "")
                    if thinking and on_token:
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

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _err("ai.err.ollamaModelMissing", model=model)
        return _err("ai.err.ollamaHttpError", status=e.code)
    except urllib.error.URLError as e:
        return _human_error("ollama", e.reason)
    except Exception as e:
        return _human_error("ollama", e)


def _openai_stream(messages: list[dict], cfg: dict, on_token, lang: str = "zh-CN") -> str:
    """OpenAI 兼容 API 流式（DeepSeek 等）。"""
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "https://api.deepseek.com")
    model = cfg.get("model", "deepseek-chat")

    if not api_key:
        return _err("ai.err.cloudNoApiKey")

    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
    })

    try:
        import urllib.request
        import urllib.error

        req = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )

        full_text = ""
        with urllib.request.urlopen(req, timeout=120) as resp:
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
                    if reasoning and on_token:
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

    except urllib.error.HTTPError as e:
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