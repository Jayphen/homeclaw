"""Sandboxed HTTP call tool — domain-allowlisted, blocks private IPs."""

from __future__ import annotations

import ipaddress
import json
import logging
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

_SUPPORTED_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH"}
_MAX_RESPONSE_CHARS = 50_000

# Lazy reference to the global config — avoids circular import at module load.
_global_config: Any = None


def set_global_config(config: Any) -> None:
    """Set the global config reference for live setting checks."""
    global _global_config
    _global_config = config


def _check_global_allow_local() -> bool:
    """Check the live global config for skill_allow_local_network."""
    if _global_config is None:
        return False
    return bool(getattr(_global_config, "skill_allow_local_network", False))


class HttpCallConfig(BaseModel):
    allowed_domains: list[str]  # e.g. ["api.openweathermap.org"]
    log_dir: Path | None = None  # where to log requests
    allow_local_network: bool = False  # skip private IP check (for LAN services)


def _is_private_ip(addr: str) -> bool:
    """Return True if *addr* is a private/loopback/reserved IP address."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_reserved
        or ip.is_link_local
        or ip.is_multicast
    )


def _normalize_domain(entry: str) -> str:
    """Extract hostname from an allowed-domains entry.

    Accepts both bare hostnames (``api.example.com``) and full URLs
    (``https://api.example.com/path``).
    """
    if "://" in entry:
        return urlparse(entry).hostname or entry
    return entry


def _check_domain(url: str, allowed_domains: list[str]) -> str:
    """Parse *url* and return the hostname if it's in *allowed_domains*.

    Raises ``ValueError`` if the domain is not allowed.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"Cannot parse hostname from URL: {url}")
    normalized = [_normalize_domain(d) for d in allowed_domains]
    if hostname not in normalized:
        raise ValueError(
            f"Domain '{hostname}' is not in the allowed list: {allowed_domains}"
        )
    return hostname


def _check_private_ip(hostname: str) -> None:
    """Resolve *hostname* and reject if any address is private.

    Raises ``ValueError`` if any resolved address is a private IP.
    """
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"Cannot resolve hostname '{hostname}': {exc}") from exc

    for _family, _type, _proto, _canonname, sockaddr in infos:
        addr = str(sockaddr[0])
        if _is_private_ip(addr):
            raise ValueError(
                f"Hostname '{hostname}' resolves to private address {addr} — blocked"
            )


def _log_request(
    log_dir: Path,
    *,
    url: str,
    method: str,
    status: int | None,
    error: str | None = None,
) -> None:
    """Append a one-line JSON record to ``log_dir/{date}.jsonl``."""
    log_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = log_dir / f"{today}.jsonl"
    record: dict[str, Any] = {
        "url": url,
        "method": method,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if status is not None:
        record["status"] = status
    if error is not None:
        record["error"] = error
    with path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


async def http_call(
    *,
    url: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    config: HttpCallConfig,
) -> dict[str, Any]:
    """Execute a sandboxed HTTP request.

    Returns ``{"status": int, "headers": dict, "body": str}`` on success,
    or ``{"error": str}`` on failure.
    """
    method = method.upper()
    if method not in _SUPPORTED_METHODS:
        return {"error": f"Unsupported HTTP method: {method}"}

    # --- Domain allowlist ---
    try:
        hostname = _check_domain(url, config.allowed_domains)
    except ValueError as exc:
        return {"error": str(exc)}

    # --- Block private IPs (unless local network access is allowed) ---
    allow_local = config.allow_local_network or _check_global_allow_local()
    if not allow_local:
        try:
            _check_private_ip(hostname)
        except ValueError as exc:
            return {"error": str(exc)}

    # --- Make the request ---
    status: int | None = None
    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.request(
                method,
                url,
                headers=headers,
                content=body,
            )
            status = resp.status_code
            resp_headers = dict(resp.headers)
            resp_body = resp.text
            if len(resp_body) > _MAX_RESPONSE_CHARS:
                resp_body = resp_body[:_MAX_RESPONSE_CHARS]

        if config.log_dir:
            _log_request(config.log_dir, url=url, method=method, status=status)

        return {
            "status": status,
            "headers": resp_headers,
            "body": resp_body,
        }
    except Exception as exc:
        logger.exception("http_call failed for %s %s", method, url)
        if config.log_dir:
            _log_request(
                config.log_dir, url=url, method=method, status=status, error=str(exc)
            )
        return {"error": str(exc)}
