"""Firecrawl — web search and read provider plugin.

Search + best-in-class page extraction (handles JS-heavy sites).
Set FIRECRAWL_API_KEY in this plugin's .env or as a system environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition, WebProviderDefinition


class _FirecrawlProvider:
    """Web search and read via Firecrawl API."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def search(self, query: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Firecrawl search requires FIRECRAWL_API_KEY to be set",
                "query": query,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.post(
                "https://api.firecrawl.dev/v2/search",
                json={"query": query, "limit": 10},
                headers=self._headers(),
            )
            resp.raise_for_status()

        data = resp.json()
        web_results = data.get("data", {}).get("web", [])
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            }
            for item in web_results
        ]
        return {"query": query, "results": results, "provider": "firecrawl"}

    async def read(self, url: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Firecrawl read requires FIRECRAWL_API_KEY to be set",
                "url": url,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=60, transport=transport) as client:
            resp = await client.post(
                "https://api.firecrawl.dev/v2/scrape",
                json={"url": url, "formats": ["markdown"]},
                headers=self._headers(),
            )
            resp.raise_for_status()

        data = resp.json()
        content = data.get("data", {}).get("markdown", "")
        if not content:
            return {"error": "Firecrawl returned no content", "url": url}
        return {"url": url, "content": content, "provider": "firecrawl"}


def _load_env(data_dir: Path) -> dict[str, str]:
    """Read .env from the plugin directory, fall back to os.environ."""
    env: dict[str, str] = {}
    env_file = data_dir / ".env"
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


class Plugin:
    name = "firecrawl"
    description = "Firecrawl — search + best-in-class page extraction"

    def __init__(self, data_dir: Path) -> None:
        env = _load_env(data_dir)
        self._api_key = env.get("FIRECRAWL_API_KEY") or os.environ.get("FIRECRAWL_API_KEY")

    def tools(self) -> list[ToolDefinition]:
        return []

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"error": f"Unknown tool: {name}"}

    def routines(self) -> list[RoutineDefinition]:
        return []

    def web_providers(self) -> list[WebProviderDefinition]:
        provider = _FirecrawlProvider(api_key=self._api_key)
        return [
            WebProviderDefinition(name="firecrawl", instance=provider),
        ]
