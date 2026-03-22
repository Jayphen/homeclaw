"""Tests for the plugins API routes."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.agent.tools import ToolRegistry
from homeclaw.api.app import app
from homeclaw.api.deps import set_config, set_plugin_registry
from homeclaw.config import HomeclawConfig
from homeclaw.plugins.interface import RoutineDefinition
from homeclaw.plugins.registry import PluginRegistry, PluginType


class FakePlugin:
    def __init__(self, name: str = "plants") -> None:
        self.name = name
        self.description = f"Test plugin: {name}"

    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters={"type": "object", "properties": {}},
            )
        ]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True}

    def routines(self) -> list[RoutineDefinition]:
        return []


@pytest.fixture()
def _setup(tmp_path: Any) -> Any:
    """Set up config and plugin registry for API tests."""
    config = HomeclawConfig(web_password="", member_passwords={}, workspaces_path=str(tmp_path))
    set_config(config)

    tool_reg = ToolRegistry()
    registry = PluginRegistry(tool_registry=tool_reg)
    registry.register(FakePlugin("plants"), PluginType.PYTHON)
    registry.register(FakePlugin("weather"), PluginType.SKILL)
    set_plugin_registry(registry)
    yield
    set_plugin_registry(None)


@pytest.fixture()
def client(_setup: Any) -> TestClient:
    return TestClient(app)


def test_list_plugins(client: TestClient) -> None:
    resp = client.get("/api/plugins")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["plugins"]) == 2
    names = {p["name"] for p in data["plugins"]}
    assert names == {"plants", "weather"}


def test_list_plugins_filter_type(client: TestClient) -> None:
    resp = client.get("/api/plugins", params={"plugin_type": "python"})
    assert resp.status_code == 200
    plugins = resp.json()["plugins"]
    assert len(plugins) == 1
    assert plugins[0]["name"] == "plants"
    assert plugins[0]["type"] == "python"


def test_list_plugins_filter_invalid_type(client: TestClient) -> None:
    resp = client.get("/api/plugins", params={"plugin_type": "bogus"})
    assert resp.status_code == 400


def test_get_plugin(client: TestClient) -> None:
    resp = client.get("/api/plugins/plants")
    assert resp.status_code == 200
    plugin = resp.json()["plugin"]
    assert plugin["name"] == "plants"
    assert plugin["type"] == "python"
    assert plugin["status"] == "active"
    assert len(plugin["tools"]) == 1


def test_get_plugin_not_found(client: TestClient) -> None:
    resp = client.get("/api/plugins/nonexistent")
    assert resp.status_code == 404


def test_list_plugins_no_registry(tmp_path: Any) -> None:
    """When no registry is set, returns empty list."""
    config = HomeclawConfig(web_password="", member_passwords={}, workspaces_path=str(tmp_path))
    set_config(config)
    set_plugin_registry(None)
    c = TestClient(app)
    resp = c.get("/api/plugins")
    assert resp.status_code == 200
    assert resp.json()["plugins"] == []


def test_disable_plugin(client: TestClient) -> None:
    resp = client.post("/api/plugins/plants/disable")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "disabled"
    assert data["plugin"]["status"] == "disabled"


def test_enable_plugin(client: TestClient) -> None:
    # First disable, then re-enable
    client.post("/api/plugins/plants/disable")
    resp = client.post("/api/plugins/plants/enable")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "enabled"
    assert data["plugin"]["status"] == "active"


def test_disable_nonexistent(client: TestClient) -> None:
    resp = client.post("/api/plugins/nonexistent/disable")
    assert resp.status_code == 404


def test_marketplace_not_configured(client: TestClient) -> None:
    resp = client.get("/api/plugins/marketplace/browse")
    assert resp.status_code == 200
    data = resp.json()
    assert data["configured"] is False
    assert data["plugins"] == []
