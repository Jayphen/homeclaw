"""Tests for the sandboxed http_call tool."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from homeclaw.plugins.skills.http_call import HttpCallConfig, http_call


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(
    allowed: list[str] | None = None,
    log_dir: Path | None = None,
) -> HttpCallConfig:
    return HttpCallConfig(
        allowed_domains=allowed or ["api.example.com"],
        log_dir=log_dir,
    )


def _fake_getaddrinfo_public(
    host: str, port: Any, *args: Any, **kwargs: Any
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Return a public IP for any lookup."""
    return [(2, 1, 6, "", ("93.184.216.34", 0))]


def _fake_getaddrinfo_private(
    host: str, port: Any, *args: Any, **kwargs: Any
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Return a private IP (192.168.x)."""
    return [(2, 1, 6, "", ("192.168.1.1", 0))]


def _fake_getaddrinfo_loopback(
    host: str, port: Any, *args: Any, **kwargs: Any
) -> list[tuple[int, int, int, str, tuple[str, int]]]:
    """Return a loopback IP."""
    return [(2, 1, 6, "", ("127.0.0.1", 0))]


def _fake_getaddrinfo_ipv6_private(
    host: str, port: Any, *args: Any, **kwargs: Any
) -> list[tuple[int, int, int, str, tuple[str, int, int, int]]]:
    """Return a private IPv6 address."""
    return [(10, 1, 6, "", ("::1", 0, 0, 0))]


def _mock_response(status: int = 200, text: str = '{"ok": true}') -> httpx.Response:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.headers = {"content-type": "application/json"}
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Domain allowlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_allowed_domain_passes() -> None:
    """A request to an allowed domain should succeed (mocked)."""
    cfg = _config(allowed=["api.example.com"])
    mock_resp = _mock_response()

    with (
        patch("socket.getaddrinfo", _fake_getaddrinfo_public),
        patch("httpx.AsyncClient") as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.request = AsyncMock(return_value=mock_resp)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await http_call(url="https://api.example.com/data", config=cfg)

    assert "error" not in result
    assert result["status"] == 200


@pytest.mark.asyncio
async def test_disallowed_domain_rejected() -> None:
    """A request to a domain NOT in the allowlist should be rejected."""
    cfg = _config(allowed=["api.example.com"])
    result = await http_call(url="https://evil.com/hack", config=cfg)

    assert "error" in result
    assert "evil.com" in result["error"]


# ---------------------------------------------------------------------------
# Internal IP blocking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_private_ip_blocked() -> None:
    """Hostnames resolving to private IPs (192.168.x) should be blocked."""
    cfg = _config(allowed=["api.example.com"])

    with patch("socket.getaddrinfo", _fake_getaddrinfo_private):
        result = await http_call(url="https://api.example.com/data", config=cfg)

    assert "error" in result
    assert "private" in result["error"].lower() or "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_loopback_ip_blocked() -> None:
    """Hostnames resolving to 127.0.0.1 should be blocked."""
    cfg = _config(allowed=["api.example.com"])

    with patch("socket.getaddrinfo", _fake_getaddrinfo_loopback):
        result = await http_call(url="https://api.example.com/data", config=cfg)

    assert "error" in result
    assert "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_ipv6_loopback_blocked() -> None:
    """Hostnames resolving to ::1 should be blocked."""
    cfg = _config(allowed=["api.example.com"])

    with patch("socket.getaddrinfo", _fake_getaddrinfo_ipv6_private):
        result = await http_call(url="https://api.example.com/data", config=cfg)

    assert "error" in result
    assert "blocked" in result["error"].lower()


# ---------------------------------------------------------------------------
# Successful HTTP call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_successful_get() -> None:
    """A normal GET request should return status, headers, and body."""
    cfg = _config(allowed=["api.example.com"])
    mock_resp = _mock_response(200, '{"weather": "sunny"}')

    with (
        patch("socket.getaddrinfo", _fake_getaddrinfo_public),
        patch("httpx.AsyncClient") as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.request = AsyncMock(return_value=mock_resp)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await http_call(url="https://api.example.com/weather", config=cfg)

    assert result["status"] == 200
    assert result["body"] == '{"weather": "sunny"}'
    assert "headers" in result


@pytest.mark.asyncio
async def test_post_with_body() -> None:
    """POST requests should forward the body."""
    cfg = _config(allowed=["api.example.com"])
    mock_resp = _mock_response(201, '{"id": 1}')

    with (
        patch("socket.getaddrinfo", _fake_getaddrinfo_public),
        patch("httpx.AsyncClient") as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.request = AsyncMock(return_value=mock_resp)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await http_call(
            url="https://api.example.com/items",
            method="POST",
            body='{"name": "test"}',
            config=cfg,
        )

    assert result["status"] == 201
    # Verify request was called with the body
    client_instance.request.assert_called_once()
    call_kwargs = client_instance.request.call_args
    assert call_kwargs.kwargs.get("content") == '{"name": "test"}'


@pytest.mark.asyncio
async def test_unsupported_method_rejected() -> None:
    """Unsupported HTTP methods should be rejected."""
    cfg = _config(allowed=["api.example.com"])
    result = await http_call(url="https://api.example.com/data", method="TRACE", config=cfg)
    assert "error" in result
    assert "Unsupported" in result["error"]


# ---------------------------------------------------------------------------
# Response truncation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_truncation() -> None:
    """Responses longer than 50,000 chars should be truncated."""
    cfg = _config(allowed=["api.example.com"])
    long_body = "x" * 60_000
    mock_resp = _mock_response(200, long_body)

    with (
        patch("socket.getaddrinfo", _fake_getaddrinfo_public),
        patch("httpx.AsyncClient") as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.request = AsyncMock(return_value=mock_resp)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await http_call(url="https://api.example.com/big", config=cfg)

    assert result["status"] == 200
    assert len(result["body"]) == 50_000


# ---------------------------------------------------------------------------
# Request logging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_request_logging(tmp_path: Path) -> None:
    """Requests should be logged to log_dir/{date}.jsonl when log_dir is set."""
    cfg = _config(allowed=["api.example.com"], log_dir=tmp_path / "logs")
    mock_resp = _mock_response(200, '{"ok": true}')

    with (
        patch("socket.getaddrinfo", _fake_getaddrinfo_public),
        patch("httpx.AsyncClient") as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.request = AsyncMock(return_value=mock_resp)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await http_call(
            url="https://api.example.com/data",
            config=cfg,
        )

    assert result["status"] == 200

    # Find the log file
    log_dir = tmp_path / "logs"
    assert log_dir.is_dir()
    log_files = list(log_dir.glob("*.jsonl"))
    assert len(log_files) == 1

    records = [json.loads(line) for line in log_files[0].read_text().splitlines()]
    assert len(records) == 1
    assert records[0]["url"] == "https://api.example.com/data"
    assert records[0]["method"] == "GET"
    assert records[0]["status"] == 200
    assert "timestamp" in records[0]


@pytest.mark.asyncio
async def test_no_logging_when_log_dir_not_set() -> None:
    """When log_dir is None, no logging files should be created."""
    cfg = _config(allowed=["api.example.com"], log_dir=None)
    mock_resp = _mock_response(200, "ok")

    with (
        patch("socket.getaddrinfo", _fake_getaddrinfo_public),
        patch("httpx.AsyncClient") as MockClient,
    ):
        client_instance = AsyncMock()
        client_instance.request = AsyncMock(return_value=mock_resp)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        result = await http_call(url="https://api.example.com/data", config=cfg)

    assert result["status"] == 200
