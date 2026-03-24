"""Jina AI web search and read provider."""

from __future__ import annotations

import json
from typing import Any


class JinaProvider:
    """Web search and read via Jina AI APIs (s.jina.ai / r.jina.ai)."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _headers(self, accept: str = "text/markdown") -> dict[str, str]:
        headers = {"Accept": accept}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def search(self, query: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Jina search requires JINA_API_KEY to be set",
                "query": query,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                f"https://s.jina.ai/{query}",
                headers=self._headers("application/json"),
            )
            resp.raise_for_status()

        try:
            data = json.loads(resp.text)
        except json.JSONDecodeError:
            data = None

        if isinstance(data, dict) and "data" in data:
            results = [
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "description": item.get("description", ""),
                }
                for item in data["data"]
            ]
            return {"query": query, "results": results, "provider": "jina"}

        # Non-JSON or unexpected shape — return raw, let tool layer truncate
        return {"query": query, "results": resp.text, "provider": "jina"}

    async def read(self, url: str) -> dict[str, Any]:
        import httpx

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                f"https://r.jina.ai/{url}",
                headers=self._headers("text/markdown"),
            )
            resp.raise_for_status()
        return {"url": url, "content": resp.text, "provider": "jina"}
