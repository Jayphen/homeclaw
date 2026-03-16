"""Unified plugin registry — manages Python, skill, and MCP plugins."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.agent.tools import ToolRegistry
from homeclaw.plugins.interface import Plugin, RoutineDefinition

logger = logging.getLogger(__name__)


class PluginType(Enum):
    PYTHON = "python"
    SKILL = "skill"
    MCP = "mcp"


class PluginStatus(Enum):
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginEntry:
    """Metadata for a registered plugin."""

    name: str
    plugin_type: PluginType
    status: PluginStatus = PluginStatus.ACTIVE
    description: str = ""
    tool_names: list[str] = field(default_factory=list)
    routine_count: int = 0
    error: str | None = None


class PluginRegistry:
    """Unified registry for all plugin types.

    Manages plugin lifecycle and bridges plugin tools into the agent's
    ToolRegistry. Each plugin is identified by its name (must be unique).

    Usage:
        registry = PluginRegistry(tool_registry=agent_tool_registry)
        registry.register(my_plugin, PluginType.PYTHON)
        registry.unregister("my_plugin")
    """

    def __init__(self, tool_registry: ToolRegistry) -> None:
        self._tool_registry = tool_registry
        self._plugins: dict[str, Plugin] = {}
        self._entries: dict[str, PluginEntry] = {}

    def register(self, plugin: Plugin, plugin_type: PluginType) -> PluginEntry:
        """Register a plugin and expose its tools to the agent loop."""
        name = plugin.name

        if name in self._plugins:
            logger.warning("Plugin '%s' already registered — replacing", name)
            self.unregister(name)

        entry = PluginEntry(
            name=name,
            plugin_type=plugin_type,
            description=plugin.description,
        )

        # Register tools
        try:
            tools = plugin.tools()
            for tool_def in tools:
                # Namespace tool names to avoid collisions: plugin_name.tool_name
                namespaced = f"{name}.{tool_def.name}"
                namespaced_def = ToolDefinition(
                    name=namespaced,
                    description=f"[{name}] {tool_def.description}",
                    parameters=tool_def.parameters,
                )

                async def _handler(
                    _plugin: Plugin = plugin,
                    _tool_name: str = tool_def.name,
                    **kwargs: Any,
                ) -> dict[str, Any]:
                    return await _plugin.handle_tool(_tool_name, kwargs)

                self._tool_registry.register(namespaced_def, _handler)
                entry.tool_names.append(namespaced)
        except Exception as e:
            entry.status = PluginStatus.ERROR
            entry.error = str(e)
            logger.exception("Failed to register tools for plugin '%s'", name)

        # Count routines
        try:
            entry.routine_count = len(plugin.routines())
        except Exception:
            logger.exception("Failed to get routines for plugin '%s'", name)

        self._plugins[name] = plugin
        self._entries[name] = entry

        logger.info(
            "Registered plugin '%s' (%s): %d tools, %d routines",
            name,
            plugin_type.value,
            len(entry.tool_names),
            entry.routine_count,
        )
        return entry

    def unregister(self, name: str) -> bool:
        """Remove a plugin and its tools from the registry."""
        entry = self._entries.get(name)
        if entry is None:
            return False

        # Remove tools from the agent's tool registry
        for tool_name in entry.tool_names:
            self._tool_registry.remove(tool_name)

        del self._plugins[name]
        del self._entries[name]
        logger.info("Unregistered plugin '%s'", name)
        return True

    def get(self, name: str) -> Plugin | None:
        return self._plugins.get(name)

    def get_entry(self, name: str) -> PluginEntry | None:
        return self._entries.get(name)

    def list_entries(self) -> list[PluginEntry]:
        return list(self._entries.values())

    def get_routines(self, name: str) -> list[RoutineDefinition]:
        """Get routine definitions for a specific plugin."""
        plugin = self._plugins.get(name)
        if plugin is None:
            return []
        try:
            return plugin.routines()
        except Exception:
            logger.exception("Failed to get routines for plugin '%s'", name)
            return []

    def all_routines(self) -> dict[str, list[RoutineDefinition]]:
        """Get all routines from all active plugins, keyed by plugin name."""
        result: dict[str, list[RoutineDefinition]] = {}
        for name, entry in self._entries.items():
            if entry.status != PluginStatus.ACTIVE:
                continue
            routines = self.get_routines(name)
            if routines:
                result[name] = routines
        return result

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    @property
    def active_count(self) -> int:
        return sum(
            1 for e in self._entries.values() if e.status == PluginStatus.ACTIVE
        )

    def disable(self, name: str) -> bool:
        """Disable a plugin without removing it."""
        entry = self._entries.get(name)
        if entry is None:
            return False
        entry.status = PluginStatus.DISABLED
        # Remove tools while disabled
        for tool_name in entry.tool_names:
            self._tool_registry.remove(tool_name)
        logger.info("Disabled plugin '%s'", name)
        return True

    def enable(self, name: str) -> bool:
        """Re-enable a disabled plugin."""
        entry = self._entries.get(name)
        plugin = self._plugins.get(name)
        if entry is None or plugin is None:
            return False
        if entry.status != PluginStatus.DISABLED:
            return False

        # Re-register tools
        try:
            tools = plugin.tools()
            entry.tool_names.clear()
            for tool_def in tools:
                namespaced = f"{name}.{tool_def.name}"
                namespaced_def = ToolDefinition(
                    name=namespaced,
                    description=f"[{name}] {tool_def.description}",
                    parameters=tool_def.parameters,
                )

                async def _handler(
                    _plugin: Plugin = plugin,
                    _tool_name: str = tool_def.name,
                    **kwargs: Any,
                ) -> dict[str, Any]:
                    return await _plugin.handle_tool(_tool_name, kwargs)

                self._tool_registry.register(namespaced_def, _handler)
                entry.tool_names.append(namespaced)
            entry.status = PluginStatus.ACTIVE
            entry.error = None
        except Exception as e:
            entry.status = PluginStatus.ERROR
            entry.error = str(e)
            return False

        logger.info("Enabled plugin '%s'", name)
        return True
