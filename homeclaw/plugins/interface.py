"""Plugin Protocol and routine definitions — structural typing, no inheritance required."""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from homeclaw.agent.providers.base import ToolDefinition


class RoutineDefinition(BaseModel):
    name: str  # unique within the plugin, namespaced by registry
    cron: str  # APScheduler cron expression
    description: str


class WebProviderDefinition(BaseModel):
    """Declares a web search/read provider from a plugin.

    The ``instance`` must satisfy :class:`~homeclaw.web.protocol.WebSearchProvider`
    and/or :class:`~homeclaw.web.protocol.WebReadProvider`.
    """

    name: str  # provider name for config (e.g. "searxng", "brave")
    instance: Any  # the provider object — must implement search() and/or read()

    model_config = {"arbitrary_types_allowed": True}


@runtime_checkable
class Plugin(Protocol):
    name: str
    description: str

    def tools(self) -> list[ToolDefinition]: ...
    async def handle_tool(self, name: str, args: dict[str, Any]) -> dict[str, Any]: ...
    def routines(self) -> list[RoutineDefinition]: ...

    # Optional: plugins may define web_providers() to register custom
    # search/read providers.  Not required — checked with hasattr().
