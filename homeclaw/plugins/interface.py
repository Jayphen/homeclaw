"""Plugin Protocol and routine definitions — structural typing, no inheritance required."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from homeclaw.agent.providers.base import ToolDefinition


class RoutineDefinition(BaseModel):
    name: str  # unique within the plugin, namespaced by registry
    cron: str  # APScheduler cron expression
    description: str


@runtime_checkable
class Plugin(Protocol):
    name: str
    description: str

    def tools(self) -> list[ToolDefinition]: ...
    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...
    def routines(self) -> list[RoutineDefinition]: ...
