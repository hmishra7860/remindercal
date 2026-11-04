"""SSRF protection for user-supplied SMTP hosts and webhook URLs."""
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

from .config import settings


class UnsafeTarget(ValueError):
    pass


def _is_blocked_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip.split("%")[0])
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    )


async def assert_public_host(host: str, port: int | None = None) -> None:
    if settings.allow_private_targets:
        return
    if not host:
        raise UnsafeTarget("Missing host")
    try:
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise UnsafeTarget(f"Cannot resolve host '{host}'") from exc
    for info in infos:
        if _is_blocked_ip(info[4][0]):
            raise UnsafeTarget("Host resolves to a private or reserved network address")


def validate_webhook_url_syntax(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Webhook URL must start with https://")
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local") or host.endswith(".internal"):
        if not settings.allow_private_targets:
            raise ValueError("Webhook URL must point to a public host")
    try:
        if _is_blocked_ip(host) and not settings.allow_private_targets:
            raise ValueError("Webhook URL must point to a public host")
    except ValueError as exc:
        if "Webhook" in str(exc):
            raise
        # not an IP literal - hostname is fine, DNS is checked at send time
    return url
