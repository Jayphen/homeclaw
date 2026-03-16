"""Plugin Protocol and routine definitions — structural typing, no inheritance required."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel


class PluginToolDefinition(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any]


class RoutineDefinition(BaseModel):
    cron: str  # APScheduler cron expression
    description: str


@runtime_checkable
class Plugin(Protocol):
    name: str
    description: str

    def tools(self) -> list[PluginToolDefinition]: ...
    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...
    def routines(self) -> list[RoutineDefinition]: ...
