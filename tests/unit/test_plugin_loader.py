"""Tests for the Python plugin loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry
from homeclaw.plugins.interface import Plugin
from homeclaw.plugins.loader import (
    PluginLoadError,
    discover_plugins,
    load_all_plugins,
    load_plugin,
)
from homeclaw.plugins.registry import PluginRegistry, PluginStatus, PluginType

# ---------------------------------------------------------------------------
# Helpers — write plugin source files into tmp directories
# ---------------------------------------------------------------------------

VALID_PLUGIN_SRC = """\
from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition


class Plugin:
    name = "fake"
    description = "A fake plugin for testing"

    def tools(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="greet",
                description="Say hello",
                parameters={"type": "object", "properties": {}},
            )
        ]

    async def handle_tool(self, name: str, args: dict) -> dict:
        return {"greeting": "hello"}

    def routines(self) -> list[RoutineDefinition]:
        return []
"""

INVALID_PLUGIN_SRC = '''\
class Plugin:
    """Missing required attributes and methods — fails Protocol check."""
    pass
'''

PLUGIN_WITH_ROUTINES_SRC = """\
from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition


class Plugin:
    name = "cron_test"
    description = "Plugin with routines"

    def tools(self) -> list[ToolDefinition]:
        return []

    async def handle_tool(self, name: str, args: dict) -> dict:
        return {}

    def routines(self) -> list[RoutineDefinition]:
        return [RoutineDefinition(name="daily_check", cron="0 9 * * *", description="Daily check")]
"""

BROKEN_IMPORT_SRC = """\
import this_module_does_not_exist  # noqa: F401
"""


def _write_plugin(plugins_dir: Path, name: str, source: str) -> Path:
    """Write a plugin.py into plugins_dir/name/ and return the directory."""
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.py").write_text(source)
    return plugin_dir


# ---------------------------------------------------------------------------
# discover_plugins
# ---------------------------------------------------------------------------


class TestDiscoverPlugins:
    def test_finds_plugins(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "alpha", VALID_PLUGIN_SRC)
        _write_plugin(tmp_path, "beta", VALID_PLUGIN_SRC)

        found = discover_plugins(tmp_path)
        assert found == ["alpha", "beta"]

    def test_ignores_dirs_without_plugin_py(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "good", VALID_PLUGIN_SRC)
        # Create a directory without plugin.py
        (tmp_path / "bad").mkdir()
        (tmp_path / "bad" / "README.md").write_text("not a plugin")

        found = discover_plugins(tmp_path)
        assert found == ["good"]

    def test_returns_empty_for_nonexistent_dir(self, tmp_path: Path) -> None:
        found = discover_plugins(tmp_path / "does_not_exist")
        assert found == []

    def test_returns_empty_for_empty_dir(self, tmp_path: Path) -> None:
        found = discover_plugins(tmp_path)
        assert found == []


# ---------------------------------------------------------------------------
# load_plugin
# ---------------------------------------------------------------------------


class TestLoadPlugin:
    def test_loads_valid_plugin(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "fake", VALID_PLUGIN_SRC)

        plugin = load_plugin(tmp_path, "fake")
        assert isinstance(plugin, Plugin)
        assert plugin.name == "fake"
        assert plugin.description == "A fake plugin for testing"
        assert len(plugin.tools()) == 1
        assert plugin.tools()[0].name == "greet"

    def test_raises_for_missing_dir(self, tmp_path: Path) -> None:
        with pytest.raises(PluginLoadError, match="Plugin file not found"):
            load_plugin(tmp_path, "nonexistent")

    def test_raises_for_invalid_protocol(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "bad", INVALID_PLUGIN_SRC)

        with pytest.raises(PluginLoadError, match="does not satisfy the Plugin Protocol"):
            load_plugin(tmp_path, "bad")

    def test_raises_for_broken_import(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "broken", BROKEN_IMPORT_SRC)

        with pytest.raises(PluginLoadError, match="Failed to execute plugin module"):
            load_plugin(tmp_path, "broken")

    def test_raises_for_missing_plugin_class(self, tmp_path: Path) -> None:
        # Module loads fine but has no Plugin class
        _write_plugin(tmp_path, "empty", "x = 42\n")

        with pytest.raises(PluginLoadError, match="does not define a 'Plugin' class"):
            load_plugin(tmp_path, "empty")


# ---------------------------------------------------------------------------
# load_all_plugins
# ---------------------------------------------------------------------------


class TestLoadAllPlugins:
    def test_loads_and_registers_all(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "alpha", VALID_PLUGIN_SRC)
        _write_plugin(tmp_path, "cron_test", PLUGIN_WITH_ROUTINES_SRC)

        tool_reg = ToolRegistry()
        registry = PluginRegistry(tool_registry=tool_reg)

        entries = load_all_plugins(tmp_path, registry)

        assert len(entries) == 2
        names = {e.name for e in entries}
        assert "fake" in names  # alpha's Plugin.name is "fake"
        assert "cron_test" in names
        assert registry.plugin_count == 2

    def test_continues_past_failures(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "bad", INVALID_PLUGIN_SRC)
        _write_plugin(tmp_path, "good", VALID_PLUGIN_SRC)

        tool_reg = ToolRegistry()
        registry = PluginRegistry(tool_registry=tool_reg)

        entries = load_all_plugins(tmp_path, registry)

        # Only the good plugin should be registered
        assert len(entries) == 1
        assert entries[0].name == "fake"
        assert entries[0].plugin_type == PluginType.PYTHON
        assert entries[0].status == PluginStatus.ACTIVE

    def test_registers_tools_in_agent_registry(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "tooled", VALID_PLUGIN_SRC)

        tool_reg = ToolRegistry()
        registry = PluginRegistry(tool_registry=tool_reg)

        load_all_plugins(tmp_path, registry)

        # The valid plugin exposes a "greet" tool, namespaced as "fake.greet"
        assert tool_reg.has_tool("fake.greet")

    def test_empty_dir_returns_empty_list(self, tmp_path: Path) -> None:
        tool_reg = ToolRegistry()
        registry = PluginRegistry(tool_registry=tool_reg)

        entries = load_all_plugins(tmp_path, registry)
        assert entries == []
        assert registry.plugin_count == 0

    def test_broken_import_skipped(self, tmp_path: Path) -> None:
        _write_plugin(tmp_path, "broken", BROKEN_IMPORT_SRC)
        _write_plugin(tmp_path, "good", VALID_PLUGIN_SRC)

        tool_reg = ToolRegistry()
        registry = PluginRegistry(tool_registry=tool_reg)

        entries = load_all_plugins(tmp_path, registry)

        assert len(entries) == 1
        assert entries[0].name == "fake"
