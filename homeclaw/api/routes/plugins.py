"""Plugins API routes — list installed plugins and browse marketplace."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from homeclaw.api.deps import AdminDep, AuthDep, get_config, get_plugin_registry
from homeclaw.plugins.loader import disable_plugin, enable_plugin, load_plugin
from homeclaw.plugins.marketplace.index import MarketplaceClient
from homeclaw.plugins.marketplace.installer import (
    InstallError,
    install_plugin,
    uninstall_plugin,
)
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


@router.post("/marketplace/install", dependencies=[AdminDep])
async def install_marketplace_plugin(
    name: str,
    enable: bool = True,
) -> dict[str, Any]:
    """Install a plugin from the marketplace by name."""
    config = get_config()
    registry = get_plugin_registry()
    if registry is None:
        raise HTTPException(status_code=503, detail="Plugin system not ready")

    client = MarketplaceClient(
        marketplace_url=config.marketplace_url,
        workspaces=config.workspaces.resolve(),
    )
    if not client.is_configured:
        raise HTTPException(
            status_code=400, detail="Marketplace URL not configured"
        )

    plugin = await client.get_plugin(name)
    if plugin is None:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{name}' not found in marketplace",
        )

    try:
        entry = await install_plugin(
            plugin,
            config.workspaces.resolve(),
            registry,
            enable=enable,
        )
    except InstallError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"status": "installed", "plugin": _entry_to_dict(entry)}


@router.post("/marketplace/uninstall", dependencies=[AdminDep])
async def uninstall_marketplace_plugin(name: str) -> dict[str, Any]:
    """Uninstall a plugin by name."""
    config = get_config()
    registry = get_plugin_registry()
    if registry is None:
        raise HTTPException(status_code=503, detail="Plugin system not ready")

    removed = uninstall_plugin(name, config.workspaces.resolve(), registry)
    if not removed:
        raise HTTPException(
            status_code=404,
            detail=f"Plugin '{name}' not found",
        )

    return {"status": "uninstalled", "name": name}


class PluginInstallRequest(BaseModel):
    url: str
    enable: bool = True
    install_all: bool = False


@router.post("/install", dependencies=[AdminDep])
async def install_plugin_from_url(body: PluginInstallRequest) -> dict[str, Any]:
    """Install a Python plugin from a GitHub repository URL.

    For repos with multiple plugins (no root ``plugin.py``), returns the list
    of available plugins unless ``install_all`` is true.
    """
    import httpx

    from homeclaw.plugins.github import list_repo_plugins
    from homeclaw.plugins.skills.github import parse_github_url

    registry = get_plugin_registry()
    if registry is None:
        raise HTTPException(status_code=503, detail="Plugin system not ready")

    config = get_config()
    plugins_dir = config.workspaces.resolve() / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    original_url = body.url.strip()
    info = parse_github_url(original_url)
    if info is None:
        raise HTTPException(
            status_code=400,
            detail="Only GitHub repository URLs are supported",
        )

    user, repo, branch, subpath = info

    # Check if root plugin.py exists at the target path
    raw_check = (
        f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/"
        f"{(subpath + '/') if subpath else ''}plugin.py"
    )
    has_root_plugin = False
    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.head(raw_check)
            has_root_plugin = resp.status_code == 200
    except httpx.RequestError:
        pass

    if has_root_plugin:
        # Single plugin — derive name from subpath or repo name
        name = subpath.rsplit("/", 1)[-1] if subpath else repo
        result = await _install_single_plugin(
            original_url, name, plugins_dir, registry, enable=body.enable,
        )
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    # Multi-plugin case — discover subdirectories with plugin.py
    available = await list_repo_plugins(original_url)
    if not available:
        raise HTTPException(
            status_code=404,
            detail="No plugin.py files found in this repository",
        )

    if not body.install_all:
        return {
            "status": "multiple_plugins",
            "url": original_url,
            "plugins": available,
            "hint": "Set install_all=true to install all, or use a more specific URL",
        }

    # Install all discovered plugins
    from homeclaw.plugins.skills.github import skill_subpath_url

    results: list[dict[str, Any]] = []
    for plugin_info in available:
        sub_url = skill_subpath_url(original_url, plugin_info["path"])
        name = plugin_info["path"].rsplit("/", 1)[-1]
        result = await _install_single_plugin(
            sub_url, name, plugins_dir, registry, enable=body.enable,
        )
        results.append(result)

    installed = [r for r in results if r.get("status") == "installed"]
    errors = [r for r in results if "error" in r]
    return {
        "status": "installed_multiple",
        "installed": installed,
        "errors": errors,
        "total": len(results),
    }


async def _install_single_plugin(
    url: str,
    name: str,
    plugins_dir: Path,
    registry: Any,
    *,
    enable: bool = True,
) -> dict[str, Any]:
    """Download, load, and register a single plugin from a GitHub URL."""
    import shutil

    from homeclaw.plugins.github import download_plugin_repo, extract_env_hints
    from homeclaw.plugins.loader import PluginLoadError

    plugin_dir = plugins_dir / name
    if plugin_dir.exists():
        return {"error": f"Plugin '{name}' already exists"}

    try:
        plugin_dir.mkdir(parents=True)
        fetched = await download_plugin_repo(url, plugin_dir)

        if not (plugin_dir / "plugin.py").is_file():
            shutil.rmtree(plugin_dir, ignore_errors=True)
            return {"error": f"No plugin.py found for '{name}'"}

        # Hot-load
        plugin = load_plugin(plugins_dir, name)
        entry = registry.register(plugin, PluginType.PYTHON)
        if enable:
            enable_plugin(plugins_dir, registry, name)

        env_hints = extract_env_hints(plugin_dir)

        result: dict[str, Any] = {
            "status": "installed",
            "name": name,
            "description": getattr(plugin, "description", ""),
            "files": fetched,
        }
        if env_hints:
            result["env_hints"] = env_hints
        return result

    except PluginLoadError as exc:
        shutil.rmtree(plugin_dir, ignore_errors=True)
        return {"error": f"Plugin '{name}' downloaded but failed to load: {exc}"}
    except Exception as exc:
        shutil.rmtree(plugin_dir, ignore_errors=True)
        return {"error": f"Failed to install plugin '{name}': {exc}"}


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


@router.post("/{name}/enable", dependencies=[AdminDep])
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


@router.post("/{name}/disable", dependencies=[AdminDep])
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


@router.get("/{name}/env", dependencies=[AdminDep])
async def get_plugin_env(name: str) -> dict[str, Any]:
    """Read a plugin's .env file as key-value pairs."""
    plugin_dir = _plugins_dir() / name
    if not plugin_dir.is_dir():
        raise HTTPException(status_code=404, detail="Plugin not found")

    env_file = plugin_dir / ".env"
    entries: list[dict[str, str]] = []
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            entries.append({"key": key.strip(), "value": value.strip()})

    # Also include env hints so the UI can show placeholders for missing vars
    from homeclaw.plugins.github import extract_env_hints

    hints = extract_env_hints(plugin_dir)

    return {"name": name, "entries": entries, "env_hints": hints}


class PluginEnvUpdate(BaseModel):
    entries: list[dict[str, str]]


@router.put("/{name}/env", dependencies=[AdminDep])
async def update_plugin_env(name: str, body: PluginEnvUpdate) -> dict[str, Any]:
    """Write a plugin's .env file from key-value pairs."""
    plugin_dir = _plugins_dir() / name
    if not plugin_dir.is_dir():
        raise HTTPException(status_code=404, detail="Plugin not found")

    lines: list[str] = []
    for entry in body.entries:
        key = entry.get("key", "").strip()
        value = entry.get("value", "").strip()
        if key:
            lines.append(f"{key}={value}")

    env_file = plugin_dir / ".env"
    env_file.write_text("\n".join(lines) + ("\n" if lines else ""))

    return {"status": "saved", "name": name, "count": len(lines)}
