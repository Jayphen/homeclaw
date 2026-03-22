"""Tests for the unified plugin registry."""

from typing import Any

import pytest

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.agent.tools import ToolRegistry
from homeclaw.plugins.interface import Plugin, RoutineDefinition
from homeclaw.plugins.registry import PluginRegistry, PluginStatus, PluginType


class FakePlugin:
    """A minimal plugin for testing."""

    def __init__(self, name: str = "fake", tool_count: int = 1) -> None:
        self.name = name
        self.description = f"Fake plugin: {name}"
        self._tool_count = tool_count
        self.handle_tool_calls: list[tuple[str, dict[str, Any]]] = []

    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name=f"tool_{i}",
                description=f"Fake tool {i}",
                parameters={"type": "object", "properties": {}},
            )
            for i in range(self._tool_count)
        ]

    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        self.handle_tool_calls.append((name, args))
        return {"handled": name}

    def routines(self) -> list[RoutineDefinition]:
        return []


class FakePluginWithRoutines(FakePlugin):
    def routines(self) -> list[RoutineDefinition]:
        return [RoutineDefinition(name="morning_check", cron="0 8 * * *", description="Morning check")]


def test_fake_plugin_satisfies_protocol() -> None:
    plugin = FakePlugin()
    assert isinstance(plugin, Plugin)


def test_register_and_list() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    plugin = FakePlugin("plants", tool_count=2)
    entry = reg.register(plugin, PluginType.PYTHON)

    assert entry.name == "plants"
    assert entry.plugin_type == PluginType.PYTHON
    assert entry.status == PluginStatus.ACTIVE
    assert len(entry.tool_names) == 2
    assert "plants__tool_0" in entry.tool_names
    assert "plants__tool_1" in entry.tool_names
    assert reg.plugin_count == 1
    assert reg.active_count == 1


def test_tools_exposed_to_agent() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    plugin = FakePlugin("weather", tool_count=1)
    reg.register(plugin, PluginType.PYTHON)

    assert tool_reg.has_tool("weather__tool_0")
    defs = tool_reg.get_definitions()
    names = [d.name for d in defs]
    assert "weather__tool_0" in names


@pytest.mark.asyncio
async def test_tool_handler_dispatches_to_plugin() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    plugin = FakePlugin("test")
    reg.register(plugin, PluginType.PYTHON)

    handler = tool_reg.get_handler("test__tool_0")
    assert handler is not None
    result = await handler()
    assert result == {"handled": "tool_0"}
    assert len(plugin.handle_tool_calls) == 1


def test_unregister() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    plugin = FakePlugin("temp", tool_count=2)
    reg.register(plugin, PluginType.PYTHON)
    assert tool_reg.has_tool("temp__tool_0")

    assert reg.unregister("temp") is True
    assert reg.plugin_count == 0
    assert not tool_reg.has_tool("temp__tool_0")
    assert not tool_reg.has_tool("temp__tool_1")


def test_unregister_nonexistent() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)
    assert reg.unregister("nope") is False


def test_replace_plugin() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    reg.register(FakePlugin("x", tool_count=1), PluginType.PYTHON)
    reg.register(FakePlugin("x", tool_count=3), PluginType.PYTHON)

    assert reg.plugin_count == 1
    entry = reg.get_entry("x")
    assert entry is not None
    assert len(entry.tool_names) == 3


def test_disable_and_enable() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    plugin = FakePlugin("togglable", tool_count=1)
    reg.register(plugin, PluginType.SKILL)

    assert tool_reg.has_tool("togglable__tool_0")

    reg.disable("togglable")
    entry = reg.get_entry("togglable")
    assert entry is not None
    assert entry.status == PluginStatus.DISABLED
    assert not tool_reg.has_tool("togglable__tool_0")

    reg.enable("togglable")
    assert entry.status == PluginStatus.ACTIVE
    assert tool_reg.has_tool("togglable__tool_0")


def test_routines() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    plugin = FakePluginWithRoutines("cron_plugin")
    entry = reg.register(plugin, PluginType.PYTHON)

    assert entry.routine_count == 1
    routines = reg.get_routines("cron_plugin")
    assert len(routines) == 1
    assert routines[0].cron == "0 8 * * *"


def test_all_routines() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    reg.register(FakePlugin("no_routines"), PluginType.PYTHON)
    reg.register(FakePluginWithRoutines("has_routines"), PluginType.PYTHON)

    all_r = reg.all_routines()
    assert "has_routines" in all_r
    assert "no_routines" not in all_r


def test_multiple_plugin_types() -> None:
    tool_reg = ToolRegistry()
    reg = PluginRegistry(tool_registry=tool_reg)

    reg.register(FakePlugin("py_plugin"), PluginType.PYTHON)
    reg.register(FakePlugin("skill_plugin"), PluginType.SKILL)
    reg.register(FakePlugin("mcp_plugin"), PluginType.MCP)

    entries = reg.list_entries()
    types = {e.plugin_type for e in entries}
    assert types == {PluginType.PYTHON, PluginType.SKILL, PluginType.MCP}
    assert reg.plugin_count == 3
