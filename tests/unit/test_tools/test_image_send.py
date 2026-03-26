"""Tests for image_send tool — validation, size limits, base64 support."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools


@pytest.fixture
def registry(dev_workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, dev_workspaces)
    return reg


@pytest.fixture
def handler(registry: ToolRegistry):  # noqa: ANN201
    h = registry.get_handler("image_send")
    assert h is not None
    return h


# ── Input validation ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_source_provided(handler) -> None:  # noqa: ANN001
    result = await handler(person="alice")
    assert "error" in result
    assert "required" in result["error"].lower()


@pytest.mark.asyncio
async def test_multiple_sources_rejected(handler) -> None:  # noqa: ANN001
    result = await handler(
        url="https://example.com/img.png",
        file_path="/tmp/img.png",
        person="alice",
    )
    assert "error" in result
    assert "only one" in result["error"].lower()


# ── File path validation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_file_not_found(handler) -> None:  # noqa: ANN001
    result = await handler(file_path="/nonexistent/image.png", person="alice")
    assert "error" in result
    assert "not found" in result["error"].lower()


@pytest.mark.asyncio
async def test_unsupported_file_extension(handler, tmp_path: Path) -> None:  # noqa: ANN001
    txt = tmp_path / "notes.txt"
    txt.write_text("not an image")
    result = await handler(file_path=str(txt), person="alice")
    assert "error" in result
    assert "unsupported" in result["error"].lower()


@pytest.mark.asyncio
async def test_file_too_large(handler, tmp_path: Path) -> None:  # noqa: ANN001
    big = tmp_path / "huge.png"
    big.write_bytes(b"\x00" * (10 * 1024 * 1024 + 1))
    result = await handler(file_path=str(big), person="alice")
    assert "error" in result
    assert "too large" in result["error"].lower()


@pytest.mark.asyncio
async def test_valid_file_path(handler, tmp_path: Path) -> None:  # noqa: ANN001
    img = tmp_path / "photo.jpg"
    img.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
    # No dispatcher → queued
    result = await handler(file_path=str(img), person="alice")
    assert result.get("status") == "queued"


# ── Base64 support ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_raw_base64(handler) -> None:  # noqa: ANN001
    data = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
    result = await handler(base64=data, person="alice")
    assert result.get("status") == "queued"


@pytest.mark.asyncio
async def test_data_uri_base64(handler) -> None:  # noqa: ANN001
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50).decode()
    uri = f"data:image/png;base64,{encoded}"
    result = await handler(base64=uri, person="alice")
    assert result.get("status") == "queued"


@pytest.mark.asyncio
async def test_data_uri_non_image_rejected(handler) -> None:  # noqa: ANN001
    encoded = base64.b64encode(b"hello").decode()
    uri = f"data:text/plain;base64,{encoded}"
    result = await handler(base64=uri, person="alice")
    assert "error" in result
    assert "not an image" in result["error"].lower()


@pytest.mark.asyncio
async def test_invalid_base64_rejected(handler) -> None:  # noqa: ANN001
    result = await handler(base64="not!!!valid===base64", person="alice")
    assert "error" in result
    assert "invalid" in result["error"].lower()


@pytest.mark.asyncio
async def test_base64_bad_magic_bytes_rejected(handler) -> None:  # noqa: ANN001
    data = base64.b64encode(b"not-an-image-format" + b"\x00" * 50).decode()
    result = await handler(base64=data, person="alice")
    assert "error" in result
    assert "not a recognised image" in result["error"].lower()


@pytest.mark.asyncio
async def test_base64_too_large(handler) -> None:  # noqa: ANN001
    data = base64.b64encode(b"\x00" * (10 * 1024 * 1024 + 1)).decode()
    result = await handler(base64=data, person="alice")
    assert "error" in result
    assert "too large" in result["error"].lower()


# ── URL validation ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_url_non_image_content_type_rejected(handler) -> None:  # noqa: ANN001
    """HEAD returns text/html → rejected before download."""
    head_resp = AsyncMock()
    head_resp.headers = {"content-type": "text/html; charset=utf-8"}

    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=head_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await handler(url="https://example.com/page", person="alice")
    assert "error" in result
    assert "not an image" in result["error"].lower()


@pytest.mark.asyncio
async def test_url_too_large_via_content_length(handler) -> None:  # noqa: ANN001
    """HEAD reports content-length over limit → rejected before download."""
    head_resp = AsyncMock()
    head_resp.headers = {
        "content-type": "image/jpeg",
        "content-length": str(11 * 1024 * 1024),
    }

    mock_client = AsyncMock()
    mock_client.head = AsyncMock(return_value=head_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await handler(url="https://example.com/big.jpg", person="alice")
    assert "error" in result
    assert "too large" in result["error"].lower()
