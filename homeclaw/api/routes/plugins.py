"""Plugins API routes — list installed plugins and browse marketplace."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from homeclaw.api.deps import AuthDep, get_config, get_plugin_registry
from homeclaw.plugins.loader import disable_plugin, enable_plugin
from homeclaw.plugins.marketplace.index import MarketplaceClient
from homeclaw.plugins.marketplace.models import MarketplacePluginType
from homeclaw.plugins.registry import PluginStatus, PluginType

router = APIRouter(prefix="/api/plugins", tags=["plugins"])

_VALID_TYPES = ", ".join(t.value for t in PluginType)
_VALID_STATUSES = ", ".join(s.value for s in PluginStatus)


def _entry_to_dict(entry: Any) -> dict[str, Any]:
    """Serialize a PluginEntry to a JSON-safe dict."""
    return {
        "name": entry.name,
        "type": entry.plugin_type.value,
        "status": entry.status.value,
        "description": entry.description,
        "tools": entry.tool_names,
        "routine_count": entry.routine_count,
        "error": entry.error,
    }


def _plugins_dir() -> Any:
    return get_config().workspaces.resolve() / "plugins"


@router.get("", dependencies=[AuthDep])
async def list_plugins(
    plugin_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List all installed plugins with optional type/status filters."""
    registry = get_plugin_registry()
    if registry is None:
        return {"plugins": []}

    entries = registry.list_entries()

    if plugin_type is not None:
        try:
            pt = PluginType(plugin_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plugin_type: {plugin_type}. "
                f"Must be one of: {_VALID_TYPES}",
            ) from e
        entries = [e for e in entries if e.plugin_type == pt]

    if status is not None:
        try:
            ps = PluginStatus(status)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. "
                f"Must be one of: {_VALID_STATUSES}",
            ) from e
        entries = [e for e in entries if e.status == ps]

    return {"plugins": [_entry_to_dict(e) for e in entries]}


# NOTE: static paths must come before /{name} to avoid being captured
@router.get("/marketplace/browse", dependencies=[AuthDep])
async def browse_marketplace(
    plugin_type: str | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """Browse available plugins from the marketplace."""
    config = get_config()
    client = MarketplaceClient(
        marketplace_url=config.marketplace_url,
        workspaces=config.workspaces.resolve(),
    )

    if not client.is_configured:
        return {"plugins": [], "configured": False}

    type_filter: MarketplacePluginType | None = None
    if plugin_type is not None:
        try:
            type_filter = MarketplacePluginType(plugin_type)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid plugin_type: {plugin_type}",
            ) from e

    plugins = await client.list_available(
        plugin_type=type_filter, force_refresh=refresh,
    )
    return {
        "plugins": [p.model_dump() for p in plugins],
        "configured": True,
    }


@router.get("/{name}", dependencies=[AuthDep])
async def get_plugin(name: str) -> dict[str, Any]:
    """Get details for a single installed plugin."""
    registry = get_plugin_registry()
    if registry is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    entry = registry.get_entry(name)
    if entry is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    return {"plugin": _entry_to_dict(entry)}


@router.post("/{name}/enable", dependencies=[AuthDep])
async def enable_plugin_route(name: str) -> dict[str, Any]:
    """Enable a disabled plugin, exposing its tools to the agent."""
    registry = get_plugin_registry()
    if registry is None or registry.get_entry(name) is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    if not enable_plugin(_plugins_dir(), registry, name):
        entry = registry.get_entry(name)
        if entry and entry.status == PluginStatus.ACTIVE:
            return {"status": "already_active", "plugin": _entry_to_dict(entry)}
        raise HTTPException(status_code=400, detail="Could not enable plugin")

    entry = registry.get_entry(name)
    return {"status": "enabled", "plugin": _entry_to_dict(entry)}


@router.post("/{name}/disable", dependencies=[AuthDep])
async def disable_plugin_route(name: str) -> dict[str, Any]:
    """Disable an active plugin, removing its tools from the agent."""
    registry = get_plugin_registry()
    if registry is None or registry.get_entry(name) is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    if not disable_plugin(_plugins_dir(), registry, name):
        entry = registry.get_entry(name)
        if entry and entry.status == PluginStatus.DISABLED:
            return {"status": "already_disabled", "plugin": _entry_to_dict(entry)}
        raise HTTPException(status_code=400, detail="Could not disable plugin")

    entry = registry.get_entry(name)
    return {"status": "disabled", "plugin": _entry_to_dict(entry)}
