"""Tests for web provider plugins (brave, exa, searxng, firecrawl)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from homeclaw.web.protocol import WebReadProvider, WebSearchProvider

# ---------------------------------------------------------------------------
# Load plugin modules from plugins/ directory
# ---------------------------------------------------------------------------

_PLUGINS_ROOT = Path(__file__).resolve().parents[2] / "plugins"


def _import_plugin(name: str) -> Any:
    """Import a plugin module from plugins/{name}/plugin.py."""
    mod_name = f"_test_plugin_{name}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    plugin_file = _PLUGINS_ROOT / name / "plugin.py"
    spec = importlib.util.spec_from_file_location(mod_name, plugin_file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod


brave_mod = _import_plugin("brave")
exa_mod = _import_plugin("exa")
searxng_mod = _import_plugin("searxng")
firecrawl_mod = _import_plugin("firecrawl")

BraveProvider = brave_mod._BraveProvider
ExaProvider = exa_mod._ExaProvider
SearxngProvider = searxng_mod._SearxngProvider
FirecrawlProvider = firecrawl_mod._FirecrawlProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(data: dict[str, Any], status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=data,
        request=httpx.Request("GET", "https://example.com"),
    )


# ---------------------------------------------------------------------------
# Brave
# ---------------------------------------------------------------------------


class TestBraveProvider:
    @pytest.mark.asyncio
    async def test_search_no_key(self) -> None:
        p = BraveProvider()
        result = await p.search("test")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        p = BraveProvider(api_key="test-key")
        mock_data = {
            "web": {
                "results": [
                    {"title": "Result 1", "url": "https://a.com", "description": "Desc 1"},
                    {"title": "Result 2", "url": "https://b.com", "description": "Desc 2"},
                ]
            }
        }
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.search("test query")

        assert result["provider"] == "brave"
        assert result["query"] == "test query"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Result 1"


# ---------------------------------------------------------------------------
# Exa
# ---------------------------------------------------------------------------


class TestExaProvider:
    @pytest.mark.asyncio
    async def test_search_no_key(self) -> None:
        p = ExaProvider()
        result = await p.search("test")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_read_no_key(self) -> None:
        p = ExaProvider()
        result = await p.read("https://example.com")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        p = ExaProvider(api_key="test-key")
        mock_data = {
            "results": [
                {"title": "Exa Result", "url": "https://c.com", "publishedDate": "2025-01-01"},
            ]
        }
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.search("test query")

        assert result["provider"] == "exa"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Exa Result"

    @pytest.mark.asyncio
    async def test_read_success(self) -> None:
        p = ExaProvider(api_key="test-key")
        mock_data = {"results": [{"text": "Page content here", "url": "https://c.com"}]}
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.read("https://c.com")

        assert result["provider"] == "exa"
        assert result["content"] == "Page content here"

    @pytest.mark.asyncio
    async def test_read_empty(self) -> None:
        p = ExaProvider(api_key="test-key")
        mock_data = {"results": []}
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.read("https://empty.com")

        assert "error" in result


# ---------------------------------------------------------------------------
# SearXNG
# ---------------------------------------------------------------------------


class TestSearxngProvider:
    @pytest.mark.asyncio
    async def test_search_no_url(self) -> None:
        p = SearxngProvider()
        result = await p.search("test")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        p = SearxngProvider(base_url="http://searxng:8080")
        mock_data = {
            "results": [
                {"title": "SearX Hit", "url": "https://d.com", "content": "A snippet"},
                *[{"title": f"R{i}", "url": f"https://d{i}.com", "content": ""} for i in range(15)],
            ]
        }
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.search("test query")

        assert result["provider"] == "searxng"
        assert len(result["results"]) == 10  # capped at 10
        assert result["results"][0]["description"] == "A snippet"

    @pytest.mark.asyncio
    async def test_trailing_slash_stripped(self) -> None:
        p = SearxngProvider(base_url="http://searxng:8080/")
        assert p._base_url == "http://searxng:8080"


# ---------------------------------------------------------------------------
# Firecrawl
# ---------------------------------------------------------------------------


class TestFirecrawlProvider:
    @pytest.mark.asyncio
    async def test_search_no_key(self) -> None:
        p = FirecrawlProvider()
        result = await p.search("test")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_read_no_key(self) -> None:
        p = FirecrawlProvider()
        result = await p.read("https://example.com")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_search_success(self) -> None:
        p = FirecrawlProvider(api_key="fc-test")
        mock_data = {
            "success": True,
            "data": {
                "web": [
                    {"title": "FC Result", "url": "https://e.com", "description": "Fire desc"},
                ]
            },
        }
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.search("test query")

        assert result["provider"] == "firecrawl"
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "FC Result"

    @pytest.mark.asyncio
    async def test_read_success(self) -> None:
        p = FirecrawlProvider(api_key="fc-test")
        mock_data = {
            "success": True,
            "data": {"markdown": "# Page Title\n\nContent here."},
        }
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.read("https://e.com")

        assert result["provider"] == "firecrawl"
        assert "# Page Title" in result["content"]

    @pytest.mark.asyncio
    async def test_read_empty(self) -> None:
        p = FirecrawlProvider(api_key="fc-test")
        mock_data = {"success": True, "data": {"markdown": ""}}
        mock_resp = _mock_response(mock_data)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await p.read("https://empty.com")

        assert "error" in result


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_brave_is_search_provider() -> None:
    assert isinstance(BraveProvider(), WebSearchProvider)


def test_exa_is_search_and_read_provider() -> None:
    p = ExaProvider()
    assert isinstance(p, WebSearchProvider)
    assert isinstance(p, WebReadProvider)


def test_searxng_is_search_provider() -> None:
    assert isinstance(SearxngProvider(), WebSearchProvider)


def test_firecrawl_is_search_and_read_provider() -> None:
    p = FirecrawlProvider()
    assert isinstance(p, WebSearchProvider)
    assert isinstance(p, WebReadProvider)


# ---------------------------------------------------------------------------
# Plugin integration — web_providers() returns correct definitions
# ---------------------------------------------------------------------------


def test_brave_plugin_web_providers() -> None:
    plugin = brave_mod.Plugin(data_dir=_PLUGINS_ROOT / "brave")
    defs = plugin.web_providers()
    assert len(defs) == 1
    assert defs[0].name == "brave"
    assert isinstance(defs[0].instance, WebSearchProvider)


def test_exa_plugin_web_providers() -> None:
    plugin = exa_mod.Plugin(data_dir=_PLUGINS_ROOT / "exa")
    defs = plugin.web_providers()
    assert len(defs) == 1
    assert defs[0].name == "exa"
    assert isinstance(defs[0].instance, WebSearchProvider)
    assert isinstance(defs[0].instance, WebReadProvider)


def test_searxng_plugin_web_providers() -> None:
    plugin = searxng_mod.Plugin(data_dir=_PLUGINS_ROOT / "searxng")
    defs = plugin.web_providers()
    assert len(defs) == 1
    assert defs[0].name == "searxng"
    assert isinstance(defs[0].instance, WebSearchProvider)


def test_firecrawl_plugin_web_providers() -> None:
    plugin = firecrawl_mod.Plugin(data_dir=_PLUGINS_ROOT / "firecrawl")
    defs = plugin.web_providers()
    assert len(defs) == 1
    assert defs[0].name == "firecrawl"
    assert isinstance(defs[0].instance, WebSearchProvider)
    assert isinstance(defs[0].instance, WebReadProvider)
