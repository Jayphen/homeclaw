"""Python plugin loader — discovers and loads plugins from the workspace."""

from __future__ import annotations

import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

from homeclaw.plugins.interface import Plugin as PluginProtocol
from homeclaw.plugins.registry import PluginEntry, PluginRegistry, PluginType

logger = logging.getLogger(__name__)

_ENABLED_FILE = "enabled.json"


def _read_enabled(plugins_dir: Path) -> set[str]:
    """Read the set of explicitly enabled plugin names."""
    path = plugins_dir / _ENABLED_FILE
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return set(data)
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read %s — treating all plugins as disabled", path)
    return set()


def _write_enabled(plugins_dir: Path, enabled: set[str]) -> None:
    """Persist the set of enabled plugin names."""
    path = plugins_dir / _ENABLED_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(enabled), indent=2) + "\n")


class PluginLoadError(Exception):
    """Raised when a plugin cannot be loaded or does not satisfy the Protocol."""


def discover_plugins(plugins_dir: Path) -> list[str]:
    """Find all subdirectories of *plugins_dir* that contain a ``plugin.py`` file.

    Returns a sorted list of plugin names (the subdirectory names).
    """
    if not plugins_dir.is_dir():
        logger.debug("Plugin directory does not exist: %s", plugins_dir)
        return []

    names: list[str] = []
    for child in sorted(plugins_dir.iterdir()):
        if child.is_dir() and (child / "plugin.py").is_file():
            names.append(child.name)
    return names


def load_plugin(plugins_dir: Path, name: str) -> PluginProtocol:
    """Load and instantiate a single Python plugin by name.

    The plugin file is expected at ``plugins_dir / name / plugin.py`` and must
    contain a class called ``Plugin`` that satisfies the :class:`Plugin` Protocol.

    Raises:
        PluginLoadError: If the file is missing, the module cannot be loaded,
            the ``Plugin`` class is absent, or the instance fails the Protocol check.
    """
    plugin_file = plugins_dir / name / "plugin.py"
    if not plugin_file.is_file():
        raise PluginLoadError(f"Plugin file not found: {plugin_file}")

    module_name = f"homeclaw.plugins.ext.{name}"

    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"Cannot create module spec for {plugin_file}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"Failed to execute plugin module '{name}': {exc}") from exc

    plugin_cls: Any = getattr(module, "Plugin", None)
    if plugin_cls is None:
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"Plugin module '{name}' does not define a 'Plugin' class")

    data_dir = plugins_dir / name
    try:
        instance = plugin_cls(data_dir=data_dir)
    except TypeError:
        # Plugin doesn't accept data_dir — instantiate without it
        try:
            instance = plugin_cls()
        except Exception as exc:
            sys.modules.pop(module_name, None)
            raise PluginLoadError(
                f"Failed to instantiate Plugin class from '{name}': {exc}"
            ) from exc
    except Exception as exc:
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"Failed to instantiate Plugin class from '{name}': {exc}") from exc

    if not isinstance(instance, PluginProtocol):
        sys.modules.pop(module_name, None)
        raise PluginLoadError(f"Plugin '{name}' does not satisfy the Plugin Protocol")

    logger.info("Loaded plugin '%s' from %s", name, plugin_file)
    return instance  # type: ignore[return-value]


def load_all_plugins(
    plugins_dir: Path,
    registry: PluginRegistry,
) -> list[PluginEntry]:
    """Discover, load, and register all Python plugins found in *plugins_dir*.

    Plugins are disabled by default. Only plugins listed in ``enabled.json``
    have their tools exposed to the agent. Errors for individual plugins are
    logged but do not prevent other plugins from loading.
    """
    names = discover_plugins(plugins_dir)
    enabled = _read_enabled(plugins_dir)
    entries: list[PluginEntry] = []

    for name in names:
        try:
            plugin = load_plugin(plugins_dir, name)
        except PluginLoadError:
            logger.exception("Skipping plugin '%s' — failed to load", name)
            continue

        try:
            entry = registry.register(plugin, PluginType.PYTHON)
            if entry.name not in enabled:
                registry.disable(entry.name)
            entries.append(entry)
        except Exception:
            logger.exception("Skipping plugin '%s' — failed to register", name)

    active = sum(1 for e in entries if e.status.value == "active")
    logger.info(
        "Plugin loading complete: %d discovered, %d active, %d disabled",
        len(entries), active, len(entries) - active,
    )
    return entries


def enable_plugin(plugins_dir: Path, registry: PluginRegistry, name: str) -> bool:
    """Enable a plugin and persist the change."""
    if not registry.enable(name):
        return False
    enabled = _read_enabled(plugins_dir)
    enabled.add(name)
    _write_enabled(plugins_dir, enabled)
    return True


def disable_plugin(plugins_dir: Path, registry: PluginRegistry, name: str) -> bool:
    """Disable a plugin and persist the change."""
    if not registry.disable(name):
        return False
    enabled = _read_enabled(plugins_dir)
    enabled.discard(name)
    _write_enabled(plugins_dir, enabled)
    return True
