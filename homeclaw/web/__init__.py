"""Pluggable web search and read providers."""

from homeclaw.web.protocol import BuiltinProvider, WebReadProvider, WebSearchProvider
from homeclaw.web.registry import web_providers

__all__ = [
    "BuiltinProvider",
    "WebReadProvider",
    "WebSearchProvider",
    "web_providers",
]
