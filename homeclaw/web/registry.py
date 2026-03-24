"""Global registry for web search and read providers."""

from __future__ import annotations

import logging
from typing import Any

from homeclaw.web.protocol import WebReadProvider, WebSearchProvider

logger = logging.getLogger(__name__)


class WebProviderRegistry:
    """Registry of named web search and read providers.

    Built-in providers are registered at import time via
    :func:`homeclaw.web.providers.register_builtins`.  Plugins and
    custom code can register additional providers at any time.
    """

    def __init__(self) -> None:
        self._search: dict[str, WebSearchProvider] = {}
        self._read: dict[str, WebReadProvider] = {}

    # -- registration --

    def register_search(self, name: str, provider: WebSearchProvider) -> None:
        self._search[name] = provider
        logger.info("Registered web search provider: %s", name)

    def register_read(self, name: str, provider: WebReadProvider) -> None:
        self._read[name] = provider
        logger.info("Registered web read provider: %s", name)

    def register(
        self,
        name: str,
        *,
        search: WebSearchProvider | None = None,
        read: WebReadProvider | None = None,
    ) -> None:
        """Register a provider for search, read, or both."""
        if search is not None:
            self.register_search(name, search)
        if read is not None:
            self.register_read(name, read)

    # -- lookup --

    def get_search(self, name: str) -> WebSearchProvider | None:
        return self._search.get(name)

    def get_read(self, name: str) -> WebReadProvider | None:
        return self._read.get(name)

    def search_providers(self) -> list[str]:
        """Return names of all registered search providers."""
        return list(self._search)

    def read_providers(self) -> list[str]:
        """Return names of all registered read providers."""
        return list(self._read)

    # -- high-level dispatch with fallback --

    async def search(
        self, query: str, primary: str, fallback: str | None = None,
    ) -> dict[str, Any]:
        """Run a search with automatic fallback on failure."""
        import httpx

        provider = self.get_search(primary)
        if provider is None:
            return {"error": f"Unknown search provider: {primary}", "query": query}

        try:
            result = await provider.search(query)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            fb = self._try_search_fallback(fallback, primary)
            if code in {402, 429} and fb:
                try:
                    return await fb.search(query)
                except (httpx.HTTPStatusError, httpx.RequestError):
                    pass
            result = {"error": f"HTTP {code}", "query": query}
        except httpx.RequestError as e:
            result = {"error": str(e), "query": query}

        # Soft-error fallback (e.g. missing API key)
        if "error" in result:
            fb = self._try_search_fallback(fallback, primary)
            if fb:
                try:
                    return await fb.search(query)
                except (httpx.HTTPStatusError, httpx.RequestError):
                    pass

        return result

    async def read(
        self,
        url: str,
        primary: str,
        fallback: str | None = None,
        content_looks_bad: Any = None,
    ) -> dict[str, Any]:
        """Fetch a URL with automatic fallback on failure or bad content."""
        import httpx

        provider = self.get_read(primary)
        if provider is None:
            return {"error": f"Unknown read provider: {primary}", "url": url}

        try:
            result = await provider.read(url)
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            result = {"error": str(e), "url": url}

        content = result.get("content", "")
        fb = self._try_read_fallback(fallback, primary)
        if fb and ("error" in result or (content_looks_bad and content_looks_bad(content))):
            try:
                result = await fb.read(url)
            except (httpx.HTTPStatusError, httpx.RequestError):
                pass  # keep primary result

        return result

    # -- helpers --

    def _try_search_fallback(
        self, fallback: str | None, primary: str,
    ) -> WebSearchProvider | None:
        if fallback and fallback != primary:
            return self._search.get(fallback)
        return None

    def _try_read_fallback(
        self, fallback: str | None, primary: str,
    ) -> WebReadProvider | None:
        if fallback and fallback != primary:
            return self._read.get(fallback)
        return None


# Global singleton — providers register here at import time.
web_providers = WebProviderRegistry()
