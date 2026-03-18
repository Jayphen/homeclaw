"""Marketplace index client — fetch, cache, and query available plugins."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from homeclaw.plugins.marketplace.models import (
    CachedIndex,
    MarketplaceIndex,
    MarketplacePlugin,
    MarketplacePluginType,
)

logger = logging.getLogger(__name__)

# Default cache TTL: 1 hour
DEFAULT_CACHE_TTL_SECONDS = 3600

_CACHE_FILENAME = ".marketplace_cache.json"


class MarketplaceClient:
    """Fetches and caches the remote marketplace plugin index.

    Usage::

        client = MarketplaceClient(
            marketplace_url="https://example.com/index.json",
            workspaces=Path("./workspaces"),
        )
        plugins = await client.list_available()
        plugin = await client.get_plugin("weather")
    """

    def __init__(
        self,
        marketplace_url: str | None,
        workspaces: Path,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
    ) -> None:
        self._url = marketplace_url
        self._cache_path = workspaces / "plugins" / _CACHE_FILENAME
        self._cache_ttl = cache_ttl_seconds
        self._cached: CachedIndex | None = None

    @property
    def is_configured(self) -> bool:
        """Whether a marketplace URL has been set."""
        return bool(self._url)

    async def list_available(
        self,
        plugin_type: MarketplacePluginType | None = None,
        force_refresh: bool = False,
    ) -> list[MarketplacePlugin]:
        """List available plugins, optionally filtered by type.

        Uses the cached index if fresh, otherwise fetches from the remote URL.
        """
        index = await self._get_index(force_refresh=force_refresh)
        plugins = index.plugins
        if plugin_type is not None:
            plugins = [p for p in plugins if p.type == plugin_type]
        return plugins

    async def get_plugin(self, name: str) -> MarketplacePlugin | None:
        """Look up a single plugin by name."""
        index = await self._get_index()
        return next((p for p in index.plugins if p.name == name), None)

    async def refresh(self) -> MarketplaceIndex:
        """Force a fresh fetch from the remote URL and update the cache."""
        return await self._get_index(force_refresh=True)

    async def _get_index(self, force_refresh: bool = False) -> MarketplaceIndex:
        """Return the marketplace index, using cache if fresh."""
        if not force_refresh:
            cached = self._load_cache()
            if cached is not None:
                age = (datetime.now(timezone.utc) - cached.fetched_at).total_seconds()
                if age < self._cache_ttl:
                    return cached.index

        if not self._url:
            logger.debug("No marketplace URL configured — returning empty index")
            return MarketplaceIndex()

        index = await self._fetch_remote()
        self._save_cache(index)
        return index

    async def _fetch_remote(self) -> MarketplaceIndex:
        """Fetch the marketplace index from the remote URL."""
        assert self._url is not None

        try:
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(timeout=15, transport=transport) as client:
                resp = await client.get(self._url)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Marketplace fetch failed: HTTP %s", e.response.status_code)
            # Fall back to cache if available
            return self._load_cache_or_empty()
        except (httpx.RequestError, Exception) as e:
            logger.error("Marketplace fetch failed: %s", e)
            return self._load_cache_or_empty()

        try:
            index = MarketplaceIndex.model_validate(data)
        except Exception:
            logger.exception("Failed to parse marketplace index")
            return self._load_cache_or_empty()

        logger.info(
            "Fetched marketplace index: %d plugins (version %d)",
            len(index.plugins),
            index.version,
        )
        return index

    def _load_cache(self) -> CachedIndex | None:
        """Load the cached index from disk. Returns None if missing or invalid."""
        if self._cached is not None:
            return self._cached
        if not self._cache_path.exists():
            return None
        try:
            data = json.loads(self._cache_path.read_text())
            self._cached = CachedIndex.model_validate(data)
            return self._cached
        except Exception:
            logger.debug("Cache file invalid, ignoring")
            return None

    def _load_cache_or_empty(self) -> MarketplaceIndex:
        """Return cached index if available, otherwise an empty index."""
        cached = self._load_cache()
        if cached is not None:
            logger.info("Using stale cache after fetch failure")
            return cached.index
        return MarketplaceIndex()

    def _save_cache(self, index: MarketplaceIndex) -> None:
        """Write the index to the local cache file."""
        cached = CachedIndex(
            fetched_at=datetime.now(timezone.utc),
            index=index,
        )
        self._cached = cached
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._cache_path.write_text(cached.model_dump_json(indent=2) + "\n")
        except OSError:
            logger.warning("Failed to write marketplace cache")
