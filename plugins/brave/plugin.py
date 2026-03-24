"""Brave Search — web search provider plugin.

Search-only provider using Brave's independent search index.
Set BRAVE_API_KEY in this plugin's .env or as a system environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition, WebProviderDefinition


class _BraveProvider:
    """Web search via Brave Search API."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    async def search(self, query: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Brave search requires BRAVE_API_KEY to be set",
                "query": query,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": 10},
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": self._api_key,
                },
            )
            resp.raise_for_status()

        data = resp.json()
        web_results = data.get("web", {}).get("results", [])
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            }
            for item in web_results
        ]
        return {"query": query, "results": results, "provider": "brave"}


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
    name = "brave"
    description = "Brave Search — fast, independent web search index"

    def __init__(self, data_dir: Path) -> None:
        env = _load_env(data_dir)
        self._api_key = env.get("BRAVE_API_KEY") or os.environ.get("BRAVE_API_KEY")

    def tools(self) -> list[ToolDefinition]:
        return []

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"error": f"Unknown tool: {name}"}

    def routines(self) -> list[RoutineDefinition]:
        return []

    def web_providers(self) -> list[WebProviderDefinition]:
        return [
            WebProviderDefinition(
                name="brave",
                instance=_BraveProvider(api_key=self._api_key),
            ),
        ]
