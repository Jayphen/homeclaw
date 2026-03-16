"""Tool registry and shared tool types."""

from typing import Any

from homeclaw.agent.providers.base import ToolDefinition


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, Any] = {}

    def register(self, definition: ToolDefinition, handler: Any) -> None:
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def get_definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_handler(self, name: str) -> Any | None:
        return self._handlers.get(name)

    def has_tool(self, name: str) -> bool:
        return name in self._tools
