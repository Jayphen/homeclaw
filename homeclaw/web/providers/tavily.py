"""Tavily web search and read provider."""

from __future__ import annotations

from typing import Any


class TavilyProvider:
    """Web search and read via Tavily APIs."""

    def __init__(self, *, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._api_key}"}

    async def search(self, query: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Tavily search requires TAVILY_API_KEY to be set",
                "query": query,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.post(
                "https://api.tavily.com/search",
                json={"query": query},
                headers=self._auth_headers(),
            )
            resp.raise_for_status()

        data = resp.json()
        results = [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("content", ""),
            }
            for item in data.get("results", [])
        ]
        return {"query": query, "results": results, "provider": "tavily"}

    async def read(self, url: str) -> dict[str, Any]:
        import httpx

        if not self._api_key:
            return {
                "error": "Tavily Extract requires TAVILY_API_KEY to be set",
                "url": url,
            }

        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.post(
                "https://api.tavily.com/extract",
                json={"urls": [url]},
                headers=self._auth_headers(),
            )
            resp.raise_for_status()

        data = resp.json()
        results = data.get("results", [])
        if not results:
            return {"error": "Tavily returned no content", "url": url}
        content = results[0].get("raw_content") or results[0].get("text", "")
        return {"url": url, "content": content, "provider": "tavily"}
