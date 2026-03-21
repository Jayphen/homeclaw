"""Marketplace plugin installer — download, verify, and register plugins."""

from __future__ import annotations

import hashlib
import logging
import shutil
import tarfile
import tempfile
from pathlib import Path

import httpx

from homeclaw.plugins.loader import (
    PluginLoadError,
    _read_enabled,
    _write_enabled,
    load_plugin,
)
from homeclaw.plugins.marketplace.models import MarketplacePlugin, MarketplacePluginType
from homeclaw.plugins.registry import PluginEntry, PluginRegistry, PluginType
from homeclaw.plugins.skills.loader import (
    load_skill,
    skill_md_to_definition,
)

logger = logging.getLogger(__name__)


class InstallError(Exception):
    """Raised when a plugin installation fails."""


def _verify_checksum(data: bytes, expected: str) -> None:
    """Verify ``sha256:<hex>`` checksum. Raises InstallError on mismatch."""
    if not expected:
        return
    if not expected.startswith("sha256:"):
        raise InstallError(f"Unsupported checksum format: {expected}")
    expected_hex = expected.removeprefix("sha256:")
    actual_hex = hashlib.sha256(data).hexdigest()
    if actual_hex != expected_hex:
        raise InstallError(
            f"Checksum mismatch: expected {expected_hex[:16]}…, "
            f"got {actual_hex[:16]}…"
        )


async def _download(url: str) -> bytes:
    """Download a URL and return the raw bytes."""
    transport = httpx.AsyncHTTPTransport(retries=2)
    async with httpx.AsyncClient(timeout=60, transport=transport) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def install_plugin(
    plugin: MarketplacePlugin,
    workspaces: Path,
    registry: PluginRegistry,
    *,
    enable: bool = True,
) -> PluginEntry:
    """Install a marketplace plugin by type, verify checksum, and register it.

    Args:
        plugin: The marketplace plugin descriptor.
        workspaces: Path to the workspaces directory.
        registry: The live plugin registry to register into.
        enable: Whether to enable the plugin after install (default True).

    Returns:
        The PluginEntry for the newly installed plugin.

    Raises:
        InstallError: If download, verification, or registration fails.
    """
    if not plugin.download_url:
        raise InstallError(f"Plugin '{plugin.name}' has no download_url")

    if plugin.type == MarketplacePluginType.PYTHON:
        return await _install_python(plugin, workspaces, registry, enable=enable)
    if plugin.type == MarketplacePluginType.SKILL:
        return await _install_skill(plugin, workspaces, registry)
    if plugin.type == MarketplacePluginType.MCP:
        return await _install_mcp(plugin, workspaces)

    raise InstallError(f"Unknown plugin type: {plugin.type}")


# ---------------------------------------------------------------------------
# Python plugins
# ---------------------------------------------------------------------------


async def _install_python(
    plugin: MarketplacePlugin,
    workspaces: Path,
    registry: PluginRegistry,
    *,
    enable: bool = True,
) -> PluginEntry:
    """Download and extract a Python plugin tarball.

    Expected tarball layout::

        plugin_name/
            plugin.py
            manifest.json
            ...
    """
    data = await _download(plugin.download_url)
    _verify_checksum(data, plugin.checksum)

    plugins_dir = workspaces / "plugins"
    dest = plugins_dir / plugin.name

    if dest.exists():
        raise InstallError(
            f"Plugin '{plugin.name}' already installed at {dest}. "
            "Uninstall first."
        )

    # Extract to a temp dir, then move into place
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp).resolve()
        tar_path = tmp_path / "plugin.tar.gz"
        tar_path.write_bytes(data)

        try:
            with tarfile.open(tar_path, "r:gz") as tf:
                # Security: reject paths that escape the extraction dir
                for member in tf.getmembers():
                    resolved = (tmp_path / member.name).resolve()
                    if not resolved.is_relative_to(tmp_path):
                        raise InstallError(
                            f"Tarball contains unsafe path: {member.name}"
                        )
                tf.extractall(tmp_path, filter="data")
        except tarfile.TarError as e:
            raise InstallError(f"Failed to extract tarball: {e}") from e

        # Find the extracted directory (should be plugin.name/ or a single top-level dir)
        extracted = tmp_path / plugin.name
        if not extracted.is_dir():
            # Try single top-level directory
            children = [c for c in tmp_path.iterdir() if c.is_dir()]
            if len(children) == 1:
                extracted = children[0]
            else:
                raise InstallError(
                    "Tarball must contain a single directory with plugin.py"
                )

        if not (extracted / "plugin.py").is_file():
            raise InstallError("Tarball missing plugin.py")

        shutil.move(str(extracted), str(dest))

    # Load and register
    try:
        loaded = load_plugin(plugins_dir, plugin.name)
    except PluginLoadError as e:
        # Clean up on failure
        shutil.rmtree(dest, ignore_errors=True)
        raise InstallError(f"Plugin failed to load after install: {e}") from e

    entry = registry.register(loaded, PluginType.PYTHON)

    if enable:
        enabled = _read_enabled(plugins_dir)
        enabled.add(plugin.name)
        _write_enabled(plugins_dir, enabled)
    else:
        registry.disable(plugin.name)

    logger.info("Installed Python plugin '%s' v%s", plugin.name, plugin.version)
    return entry


# ---------------------------------------------------------------------------
# Skill plugins
# ---------------------------------------------------------------------------


async def _install_skill(
    plugin: MarketplacePlugin,
    workspaces: Path,
    registry: PluginRegistry,
) -> PluginEntry:
    """Download a skill markdown file and register it."""
    data = await _download(plugin.download_url)
    _verify_checksum(data, plugin.checksum)

    content = data.decode("utf-8")

    # Validate before writing to disk
    try:
        skill_md_to_definition(content)
    except ValueError as e:
        raise InstallError(f"Invalid skill markdown: {e}") from e

    skills_dir = workspaces / "household" / "skills" / plugin.name
    if skills_dir.exists():
        raise InstallError(
            f"Skill '{plugin.name}' already installed at {skills_dir}. "
            "Uninstall first."
        )

    skills_dir.mkdir(parents=True, exist_ok=True)
    (skills_dir / "SKILL.md").write_text(content)

    skill_plugin = load_skill(skills_dir, "household")
    entry = registry.register(skill_plugin, PluginType.SKILL)

    logger.info("Installed skill plugin '%s' v%s", plugin.name, plugin.version)
    return entry


# ---------------------------------------------------------------------------
# MCP sidecar plugins
# ---------------------------------------------------------------------------


async def _install_mcp(
    plugin: MarketplacePlugin,
    workspaces: Path,
) -> PluginEntry:
    """Generate a docker-compose fragment for an MCP sidecar.

    MCP plugins are Docker images — we don't pull or start them here,
    just write the compose config so the user can bring them up.
    """
    mcp_dir = workspaces / "plugins" / "mcp"
    mcp_dir.mkdir(parents=True, exist_ok=True)

    compose_path = mcp_dir / f"{plugin.name}.yml"
    if compose_path.exists():
        raise InstallError(
            f"MCP plugin '{plugin.name}' already installed. Uninstall first."
        )

    # download_url is the Docker image reference for MCP plugins
    image = plugin.download_url
    compose = (
        f"# MCP sidecar: {plugin.name} v{plugin.version}\n"
        f"# {plugin.description}\n"
        f"services:\n"
        f"  {plugin.name}:\n"
        f"    image: {image}\n"
        f"    restart: unless-stopped\n"
        f"    labels:\n"
        f'      homeclaw.plugin: "{plugin.name}"\n'
        f'      homeclaw.plugin.type: "mcp"\n'
    )
    compose_path.write_text(compose)

    logger.info(
        "Installed MCP sidecar config for '%s' (image: %s)",
        plugin.name, image,
    )

    # Return a synthetic entry — MCP plugins aren't registered in the
    # PluginRegistry until the container is running and connected.
    from homeclaw.plugins.registry import PluginStatus

    return PluginEntry(
        name=plugin.name,
        plugin_type=PluginType.MCP,
        status=PluginStatus.DISABLED,
        description=plugin.description,
    )


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def uninstall_plugin(
    name: str,
    workspaces: Path,
    registry: PluginRegistry,
) -> bool:
    """Remove an installed plugin from disk and the registry.

    Returns True if something was removed.
    """
    removed = False

    # Unregister from runtime
    if registry.get_entry(name) is not None:
        registry.unregister(name)
        removed = True

    # Remove from enabled.json
    plugins_dir = workspaces / "plugins"
    enabled = _read_enabled(plugins_dir)
    if name in enabled:
        enabled.discard(name)
        _write_enabled(plugins_dir, enabled)

    # Remove Python plugin dir
    python_dir = plugins_dir / name
    if python_dir.is_dir():
        shutil.rmtree(python_dir)
        removed = True
        logger.info("Removed Python plugin directory: %s", python_dir)

    # Remove skill dir
    skill_dir = workspaces / "household" / "skills" / name
    if skill_dir.is_dir():
        shutil.rmtree(skill_dir)
        removed = True
        logger.info("Removed skill directory: %s", skill_dir)

    # Remove MCP compose file
    mcp_path = plugins_dir / "mcp" / f"{name}.yml"
    if mcp_path.is_file():
        mcp_path.unlink()
        removed = True
        logger.info("Removed MCP compose file: %s", mcp_path)

    if removed:
        logger.info("Uninstalled plugin '%s'", name)
    else:
        logger.warning("Plugin '%s' not found for uninstall", name)

    return removed
