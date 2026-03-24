"""Exa AI — web search and read provider plugin.

Neural search + content extraction via Exa AI APIs.
Set EXA_API_KEY in this plugin's .env or as a system environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition, WebProviderDefinition


class _ExaProvider:
    """Web search and read via Exa AI APIs."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def search(self, query: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Exa search requires EXA_API_KEY to be set",
                "query": query,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.post(
                "https://api.exa.ai/search",
                json={"query": query, "numResults": 10, "type": "auto"},
                headers=self._headers(),
            )
            resp.raise_for_status()

        data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("publishedDate", ""),
            }
            for item in data.get("results", [])
        ]
        return {"query": query, "results": results, "provider": "exa"}

    async def read(self, url: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Exa read requires EXA_API_KEY to be set",
                "url": url,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.post(
                "https://api.exa.ai/contents",
                json={"urls": [url], "text": True},
                headers=self._headers(),
            )
            resp.raise_for_status()

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return {"error": "Exa returned no content", "url": url}
        content = results[0].get("text", "")
        return {"url": url, "content": content, "provider": "exa"}


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
    name = "exa"
    description = "Exa AI — neural search and content extraction"

    def __init__(self, data_dir: Path) -> None:
        env = _load_env(data_dir)
        self._api_key = env.get("EXA_API_KEY") or os.environ.get("EXA_API_KEY")

    def tools(self) -> list[ToolDefinition]:
        return []

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"error": f"Unknown tool: {name}"}

    def routines(self) -> list[RoutineDefinition]:
        return []

    def web_providers(self) -> list[WebProviderDefinition]:
        provider = _ExaProvider(api_key=self._api_key)
        return [
            WebProviderDefinition(name="exa", instance=provider),
        ]
