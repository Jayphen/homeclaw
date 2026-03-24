"""Provider protocols and built-in provider enum for web search/read."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class BuiltinProvider(StrEnum):
    """Known built-in provider names.

    Use these when referencing built-in providers in code for type safety
    and autocomplete.  The registry accepts any ``str`` name, so custom
    providers are not limited to this enum.
    """

    JINA = "jina"
    TAVILY = "tavily"
    BRAVE = "brave"
    EXA = "exa"
    SEARXNG = "searxng"
    FIRECRAWL = "firecrawl"


@runtime_checkable
class WebSearchProvider(Protocol):
    """Protocol for web search providers."""

    async def search(self, query: str) -> dict[str, Any]:
        """Search the web and return structured results.

        Returns a dict with at least ``query`` and ``results`` keys.
        On error, include an ``error`` key instead.  Always include
        ``provider`` with the provider name.
        """
        ...


@runtime_checkable
class WebReadProvider(Protocol):
    """Protocol for web read (page fetch) providers."""

    async def read(self, url: str) -> dict[str, Any]:
        """Fetch a URL and return its content.

        Returns a dict with at least ``url`` and ``content`` keys.
        On error, include an ``error`` key instead.  Always include
        ``provider`` with the provider name.
        """
        ...
