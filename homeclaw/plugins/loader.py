"""Python plugin loader — discovers and loads plugins from the workspace."""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any

from homeclaw.plugins.interface import Plugin as PluginProtocol
from homeclaw.plugins.registry import PluginEntry, PluginRegistry, PluginType

logger = logging.getLogger(__name__)


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

    Errors for individual plugins are logged but do not prevent other plugins
    from loading. Returns the list of :class:`PluginEntry` objects for
    successfully registered plugins.
    """
    names = discover_plugins(plugins_dir)
    entries: list[PluginEntry] = []

    for name in names:
        try:
            plugin = load_plugin(plugins_dir, name)
        except PluginLoadError:
            logger.exception("Skipping plugin '%s' — failed to load", name)
            continue

        try:
            entry = registry.register(plugin, PluginType.PYTHON)
            entries.append(entry)
        except Exception:
            logger.exception("Skipping plugin '%s' — failed to register", name)

    logger.info("Plugin loading complete: %d/%d plugins loaded", len(entries), len(names))
    return entries
