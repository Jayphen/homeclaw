"""Marketplace data models — typed representations of the remote plugin index."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MarketplacePluginType(str, Enum):
    PYTHON = "python"
    SKILL = "skill"
    MCP = "mcp"


class MarketplacePlugin(BaseModel):
    """A single plugin available in the marketplace."""

    name: str
    type: MarketplacePluginType
    version: str
    description: str
    author: str = ""
    homepage: str = ""
    download_url: str = ""
    checksum: str = ""  # "sha256:<hex>"


class MarketplaceIndex(BaseModel):
    """The full marketplace index as fetched from the remote URL."""

    version: int = 1
    plugins: list[MarketplacePlugin] = []


class CachedIndex(BaseModel):
    """Local cache wrapper with a timestamp for TTL checks."""

    fetched_at: datetime
    index: MarketplaceIndex
