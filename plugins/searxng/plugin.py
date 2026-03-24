"""SearXNG — self-hosted web search provider plugin.

Search-only provider using a self-hosted SearXNG instance.
Set SEARXNG_BASE_URL in this plugin's .env or as a system environment variable
(e.g. http://searxng:8080). The SearXNG instance must have JSON format enabled
in its settings.yml (search: formats: [json]).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition, WebProviderDefinition


class _SearxngProvider:
    """Web search via a self-hosted SearXNG instance."""

    def __init__(self, *, base_url: str | None = None) -> None:
        self._base_url = (base_url or "").rstrip("/")

    async def search(self, query: str) -> dict[str, Any]:
        import httpx

        if not self._base_url:
            return {
                "error": "SearXNG requires SEARXNG_BASE_URL to be set (e.g. http://searxng:8080)",
                "query": query,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                f"{self._base_url}/search",
                params={"q": query, "format": "json", "categories": "general"},
            )
            resp.raise_for_status()

        data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("content", ""),
            }
            for item in data.get("results", [])[:10]
        ]
        return {"query": query, "results": results, "provider": "searxng"}


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
    name = "searxng"
    description = "SearXNG — free, self-hosted meta-search (no API key needed)"

    def __init__(self, data_dir: Path) -> None:
        env = _load_env(data_dir)
        self._base_url = env.get("SEARXNG_BASE_URL") or os.environ.get("SEARXNG_BASE_URL")

    def tools(self) -> list[ToolDefinition]:
        return []

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"error": f"Unknown tool: {name}"}

    def routines(self) -> list[RoutineDefinition]:
        return []

    def web_providers(self) -> list[WebProviderDefinition]:
        return [
            WebProviderDefinition(
                name="searxng",
                instance=_SearxngProvider(base_url=self._base_url),
            ),
        ]
