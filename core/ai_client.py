"""AI 客户端：支持 Ollama 本地模型和 OpenAI 兼容 API（DeepSeek 等）的流式对话。"""

from __future__ import annotations

import json
import os
import sys
import threading
from typing import Iterator, Optional


def _human_error(provider: str, err: Exception) -> str:
    """将技术异常转换为人性化中文提示。"""
    msg = str(err)
    # ── 连接被拒绝 / 无法连接 ──
    if "ConnectionRefusedError" in msg or "Connection refused" in msg or "WinError 10061" in msg:
        if provider == "ollama":
            return "[错误] 本地模型未接入，请确认 Ollama 服务已启动"
        return "[错误] 云端模型未接入，无法连接到 API 服务器"
    # ── DNS 解析失败 ──
    if "getaddrinfo" in msg or "Name or service not known" in msg or "No address" in msg:
        if provider == "ollama":
            return "[错误] 本地模型未接入，无法解析 Ollama 地址，请检查地址配置"
        return "[错误] 云端模型未接入，无法解析 API 地址，请检查地址配置"
    # ── 超时 ──
    if "timeout" in msg.lower() or "timed out" in msg:
        if provider == "ollama":
            return "[错误] 本地模型响应超时，请检查 Ollama 服务是否正常运行"
        return "[错误] 云端模型响应超时，请检查网络连接或稍后重试"
    # ── SSL / 证书错误 ──
    if "SSL" in msg or "certificate" in msg.lower():
        return "[错误] 安全连接失败，API 服务器证书无效"
    # ── 兜底 ──
    if provider == "ollama":
        return f"[错误] 本地模型请求失败（{msg}）"
    return f"[错误] 云端模型请求失败（{msg}）"


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
) -> str:
    """
    流式对话，每收到一个 token 调用 on_token(token_text)。
    返回完整回复文本。
    """
    ai_cfg = config_override or _load_ai_config()
    if not ai_cfg:
        return "[错误] 未配置 AI 参数，请在设置面板中配置"

    if provider == "ollama":
        return _ollama_stream(messages, ai_cfg.get("ollama", {}), on_token)
    else:
        return _openai_stream(messages, ai_cfg.get("openai", {}), on_token)


def _ollama_stream(messages: list[dict], cfg: dict, on_token) -> str:
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
            for line in resp:
                line = line.decode("utf-8", errors="replace").strip()
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
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

        return full_text

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"[错误] 本地模型未接入，模型 '{model}' 未找到，请确认已通过 ollama pull 下载"
        return f"[错误] 本地模型未接入，服务返回异常 (HTTP {e.code})"
    except urllib.error.URLError as e:
        return _human_error("ollama", e.reason)
    except Exception as e:
        return _human_error("ollama", e)


def _openai_stream(messages: list[dict], cfg: dict, on_token) -> str:
    """OpenAI 兼容 API 流式（DeepSeek 等）。"""
    api_key = cfg.get("api_key", "")
    base_url = cfg.get("base_url", "https://api.deepseek.com")
    model = cfg.get("model", "deepseek-chat")

    if not api_key:
        return "[错误] 云端模型未接入，请在设置中填写 API Key"

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
            for line in resp:
                line = line.decode("utf-8", errors="replace").strip()
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
                except json.JSONDecodeError:
                    continue

        return full_text

    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "[错误] 云端模型未接入，API Key 无效或已过期，请检查设置"
        elif e.code == 402:
            return "[错误] 云端模型欠费，请充值后重试"
        elif e.code == 403:
            return "[错误] 云端模型未接入，API Key 无权限访问该模型"
        elif e.code == 429:
            return "[错误] 云端模型请求过于频繁，请稍后重试"
        elif e.code == 503:
            return "[错误] 云端模型服务暂时不可用，请稍后重试"
        else:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            if "insufficient" in err_body.lower() or "balance" in err_body.lower() or "quota" in err_body.lower():
                return "[错误] 云端模型欠费，请充值后重试"
            return f"[错误] 云端模型返回异常 (HTTP {e.code})"
    except urllib.error.URLError as e:
        return _human_error("openai", e.reason)
    except Exception as e:
        return _human_error("openai", e)