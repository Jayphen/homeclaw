"""Tests for the marketplace index client."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeclaw.plugins.marketplace.index import MarketplaceClient
from homeclaw.plugins.marketplace.models import (
    CachedIndex,
    MarketplaceIndex,
    MarketplacePlugin,
    MarketplacePluginType,
)

SAMPLE_INDEX = {
    "version": 1,
    "plugins": [
        {
            "name": "weather",
            "type": "skill",
            "version": "0.1.0",
            "description": "Get current weather and forecasts",
            "author": "homeclaw",
            "download_url": "https://example.com/weather.md",
            "checksum": "sha256:abc123",
        },
        {
            "name": "budget",
            "type": "python",
            "version": "0.2.0",
            "description": "Track household expenses",
            "author": "community",
            "download_url": "https://example.com/budget.tar.gz",
        },
        {
            "name": "homeassistant",
            "type": "mcp",
            "version": "1.0.0",
            "description": "Home Assistant integration",
            "author": "homeclaw",
            "download_url": "ghcr.io/homeclaw/ha-sidecar:1.0.0",
        },
    ],
}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_marketplace_plugin_parses():
    p = MarketplacePlugin.model_validate(SAMPLE_INDEX["plugins"][0])
    assert p.name == "weather"
    assert p.type == MarketplacePluginType.SKILL
    assert p.version == "0.1.0"


def test_marketplace_index_parses():
    idx = MarketplaceIndex.model_validate(SAMPLE_INDEX)
    assert idx.version == 1
    assert len(idx.plugins) == 3


def test_marketplace_index_empty():
    idx = MarketplaceIndex()
    assert idx.plugins == []


# ---------------------------------------------------------------------------
# Client — no URL configured
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_not_configured(tmp_path: Path) -> None:
    client = MarketplaceClient(marketplace_url=None, workspaces=tmp_path)
    assert not client.is_configured
    plugins = await client.list_available()
    assert plugins == []


# ---------------------------------------------------------------------------
# Client — fetching
# ---------------------------------------------------------------------------


def _patch_httpx(data: dict):
    """Patch MarketplaceClient._fetch_remote to return a parsed index from *data*."""
    index = MarketplaceIndex.model_validate(data)

    async def _fake_fetch(self):
        return index

    return patch.object(MarketplaceClient, "_fetch_remote", _fake_fetch)


class _FakeAsyncClient:
    """A fake httpx.AsyncClient that raises on .get()."""

    def __init__(self, error: Exception) -> None:
        self._error = error

    async def get(self, url: str) -> None:
        raise self._error

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        pass


def _patch_httpx_error(error: Exception):
    """Patch httpx to fail so _fetch_remote falls back to cache."""
    fake = _FakeAsyncClient(error)
    return patch("homeclaw.plugins.marketplace.index.httpx.AsyncClient", return_value=fake)


@pytest.mark.asyncio
async def test_client_fetches_remote(tmp_path: Path) -> None:
    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )
    assert client.is_configured

    with _patch_httpx(SAMPLE_INDEX):
            plugins = await client.list_available()

    assert len(plugins) == 3
    assert plugins[0].name == "weather"


@pytest.mark.asyncio
async def test_client_filters_by_type(tmp_path: Path) -> None:
    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx(SAMPLE_INDEX):
            skills = await client.list_available(plugin_type=MarketplacePluginType.SKILL)

    assert len(skills) == 1
    assert skills[0].name == "weather"


@pytest.mark.asyncio
async def test_client_get_plugin(tmp_path: Path) -> None:
    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx(SAMPLE_INDEX):
            plugin = await client.get_plugin("budget")

    assert plugin is not None
    assert plugin.type == MarketplacePluginType.PYTHON


@pytest.mark.asyncio
async def test_client_get_plugin_not_found(tmp_path: Path) -> None:
    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx(SAMPLE_INDEX):
            plugin = await client.get_plugin("nonexistent")

    assert plugin is None


# ---------------------------------------------------------------------------
# Client — caching
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_caches_to_disk(tmp_path: Path) -> None:
    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx(SAMPLE_INDEX):
            await client.list_available()

    cache_path = tmp_path / "plugins" / ".marketplace_cache.json"
    assert cache_path.exists()

    cached = json.loads(cache_path.read_text())
    assert cached["index"]["version"] == 1
    assert len(cached["index"]["plugins"]) == 3


@pytest.mark.asyncio
async def test_client_uses_fresh_cache(tmp_path: Path) -> None:
    """If cache is fresh, no HTTP call is made."""
    # Pre-seed cache
    cache_path = tmp_path / "plugins" / ".marketplace_cache.json"
    cache_path.parent.mkdir(parents=True)
    cached = CachedIndex(
        fetched_at=datetime.now(timezone.utc),
        index=MarketplaceIndex.model_validate(SAMPLE_INDEX),
    )
    cache_path.write_text(cached.model_dump_json(indent=2))

    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    # Should NOT make any HTTP call
    plugins = await client.list_available()
    assert len(plugins) == 3


@pytest.mark.asyncio
async def test_client_refetches_stale_cache(tmp_path: Path) -> None:
    """If cache is stale, a new fetch is made."""
    # Pre-seed stale cache (2 hours old)
    cache_path = tmp_path / "plugins" / ".marketplace_cache.json"
    cache_path.parent.mkdir(parents=True)
    cached = CachedIndex(
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=2),
        index=MarketplaceIndex(version=1, plugins=[]),
    )
    cache_path.write_text(cached.model_dump_json(indent=2))

    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx(SAMPLE_INDEX):
            plugins = await client.list_available()

    # Got fresh data from the "fetch", not the empty stale cache
    assert len(plugins) == 3


@pytest.mark.asyncio
async def test_client_force_refresh_ignores_cache(tmp_path: Path) -> None:
    # Pre-seed fresh cache with empty index
    cache_path = tmp_path / "plugins" / ".marketplace_cache.json"
    cache_path.parent.mkdir(parents=True)
    cached = CachedIndex(
        fetched_at=datetime.now(timezone.utc),
        index=MarketplaceIndex(version=1, plugins=[]),
    )
    cache_path.write_text(cached.model_dump_json(indent=2))

    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx(SAMPLE_INDEX):
            plugins = await client.list_available(force_refresh=True)

    assert len(plugins) == 3


# ---------------------------------------------------------------------------
# Client — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_client_falls_back_to_cache_on_fetch_error(tmp_path: Path) -> None:
    """If remote fetch fails, return stale cache."""
    cache_path = tmp_path / "plugins" / ".marketplace_cache.json"
    cache_path.parent.mkdir(parents=True)
    cached = CachedIndex(
        fetched_at=datetime.now(timezone.utc) - timedelta(hours=2),
        index=MarketplaceIndex.model_validate(SAMPLE_INDEX),
    )
    cache_path.write_text(cached.model_dump_json(indent=2))

    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx_error(Exception("network error")):
        plugins = await client.list_available()

    # Falls back to stale cache
    assert len(plugins) == 3


@pytest.mark.asyncio
async def test_client_returns_empty_on_error_without_cache(tmp_path: Path) -> None:
    """If fetch fails and no cache exists, return empty."""
    client = MarketplaceClient(
        marketplace_url="https://example.com/index.json",
        workspaces=tmp_path,
    )

    with _patch_httpx_error(Exception("network error")):
        plugins = await client.list_available()

    assert plugins == []
