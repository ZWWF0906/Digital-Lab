"""AI 网络端点安全策略（DL-SEC-02 / P0，S6）。

默认规则：
- loopback（127.0.0.0/8、::1、localhost）HTTP 允许；localhost 必须先解析并确认
  全部解析结果是回环地址，随后用已确认的数值 IP 建立连接（不再次依赖 DNS），
  且绕过系统 HTTP 代理。
- 远程 HTTPS 允许，必须保留默认 TLS 证书校验（本模块不提供关闭校验的开关）。
- 私有网段 / Tailscale 的 HTTP：默认拒绝；只有用户精确授权 ip[:port] 后才允许，
  连接直接使用该 IP 字面量（无 DNS，因此无 TOCTOU）。
- 域名形式的 HTTP：拒绝（DNS 解析与连接之间存在时间差）。
- 公网 IP 的 HTTP：永久拒绝，不提供任何授权例外。
- link-local（169.254.0.0/16、fe80::/10）与云元数据地址不允许作为 HTTP 例外目标。

对外只暴露 check_endpoint() / resolve_loopback() / is_public_ip() 等纯函数，
不发起网络请求。
"""

from __future__ import annotations

import ipaddress
import socket
import urllib.parse

LOOPBACK_NETS = [ipaddress.ip_network("127.0.0.0/8"), ipaddress.ip_network("::1/128")]
PRIVATE_NETS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("fc00::/7"),
]
LINK_LOCAL_NETS = [
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("fe80::/10"),
]
TAILSCALE_NETS = [
    ipaddress.ip_network("100.64.0.0/10"),          # CGNAT / Tailscale
    ipaddress.ip_network("fd7a:115c:a1e0::/48"),    # Tailscale ULA
]
METADATA_IPS = {
    "169.254.169.254",
    "fd00:ec2::254",
    "100.100.100.200",
}
FORBIDDEN_HTTP_CATEGORIES = {"public", "linklocal", "metadata", "domain"}


class EndpointPolicyError(Exception):
    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params


def _ip_or_none(text):
    try:
        return ipaddress.ip_address(text)
    except Exception:
        return None


def classify_ip(ip) -> str:
    addr = _ip_or_none(ip) if not isinstance(ip, (ipaddress.IPv4Address, ipaddress.IPv6Address)) else ip
    if addr is None:
        return "invalid"
    if str(addr) in METADATA_IPS:
        return "metadata"
    for net in LOOPBACK_NETS:
        if addr.version == net.version and addr in net:
            return "loopback"
    for net in LINK_LOCAL_NETS:
        if addr.version == net.version and addr in net:
            return "linklocal"
    for net in TAILSCALE_NETS:
        if addr.version == net.version and addr in net:
            return "tailscale"
    for net in PRIVATE_NETS:
        if addr.version == net.version and addr in net:
            return "private"
    return "public"


def is_public_ip(ip) -> bool:
    return classify_ip(ip) == "public"


def resolve_loopback(host, timeout=3.0) -> str:
    """解析 host 并确认全部结果都是回环地址，返回可用于连接的数值 IP。

    只要出现任一非回环地址就拒绝（防止 hosts 文件/DNS 把 localhost 指到外部）。
    """
    name = str(host or "").strip()
    if not name:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="emptyHost")
    literal = _ip_or_none(name.strip("[]"))
    if literal is not None:
        if classify_ip(literal) != "loopback":
            raise EndpointPolicyError("ai.err.insecureEndpoint", category=classify_ip(literal))
        return str(literal)
    try:
        infos = socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)
    except Exception as e:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="dnsFailed", detail=str(e)[:80])
    if not infos:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="dnsEmpty")
    ips = []
    for info in infos:
        ip = info[4][0]
        ips.append(ip)
        if classify_ip(ip) != "loopback":
            raise EndpointPolicyError("ai.err.insecureEndpoint", category=classify_ip(ip), host=name)
    if not ips:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="dnsEmpty")
    return ips[0]


def _normalize_allow_entry(entry) -> str:
    text = str(entry or "").strip().lower()
    if text.startswith("[") and "]" in text:
        host, _, rest = text[1:].partition("]")
        port = rest.lstrip(":")
        return "[{0}]:{1}".format(host, port or "80")
    if ":" in text:
        return text
    return text + ":80"


def check_endpoint(url, allow_insecure_http=None) -> dict:
    """校验 AI 端点，返回连接计划；不合法时抛 EndpointPolicyError。

    返回：
      {"url", "scheme", "host", "port", "category", "connect_host", "pinned", "bypass_proxy"}
    """
    if not isinstance(url, str) or not url.strip():
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="emptyUrl")
    raw = url.strip()
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="parseFailed")
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="unsupportedScheme", scheme=scheme)
    if parsed.username or parsed.password:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="userinfoNotAllowed")
    host = (parsed.hostname or "").strip()
    if not host:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="hostMissing")
    default_port = 443 if scheme == "https" else 80
    try:
        port = int(parsed.port) if parsed.port else default_port
    except Exception:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="badPort")
    if port < 1 or port > 65535:
        raise EndpointPolicyError("ai.err.invalidEndpoint", reason="badPort")

    literal = _ip_or_none(host)
    if literal is not None:
        category = classify_ip(literal)
        connect_host = str(literal)
        pinned = True
    else:
        lowered = host.lower()
        if lowered in ("localhost", "localhost.localdomain"):
            category = "loopback"
            connect_host = resolve_loopback(host)
            pinned = True
        else:
            category = "domain"
            connect_host = host
            pinned = False

    if scheme == "https":
        # HTTPS 一律保留默认 TLS 校验；不把主机名改写成 IP，避免破坏证书主机名校验
        return {
            "url": raw, "scheme": scheme, "host": host, "port": port,
            "category": category, "connect_host": host,
            "pinned": False, "bypass_proxy": category == "loopback",
        }

    # ── HTTP 分支 ──
    if category == "loopback":
        return {
            "url": raw, "scheme": "http", "host": host, "port": port,
            "category": "loopback", "connect_host": connect_host,
            "pinned": True, "bypass_proxy": True,
        }
    if category in ("linklocal", "metadata"):
        raise EndpointPolicyError("ai.err.insecureEndpoint", category=category,
                                  reason="linkLocalOrMetadataNotAllowed")
    if category == "public":
        raise EndpointPolicyError("ai.err.insecureEndpoint", category="public",
                                  reason="publicHttpNotAllowed")
    if category == "domain":
        raise EndpointPolicyError("ai.err.insecureEndpoint", category="domain",
                                  reason="domainHttpNotAllowed")
    # private / tailscale：必须精确到 ip[:port] 的授权
    allow = {_normalize_allow_entry(x) for x in (allow_insecure_http or []) if isinstance(x, str)}
    identity = "{0}:{1}".format(host.lower(), port)
    if identity not in allow:
        raise EndpointPolicyError("ai.err.insecureEndpoint", category=category,
                                  host=host, port=port, reason="notAuthorized")
    return {
        "url": raw, "scheme": "http", "host": host, "port": port,
        "category": category, "connect_host": connect_host,
        "pinned": True, "bypass_proxy": True,
    }


def normalize_allow_entry(entry) -> str:
    return _normalize_allow_entry(entry)
