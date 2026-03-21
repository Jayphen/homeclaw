"""Tests for the marketplace plugin installer."""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from homeclaw.agent.tools import ToolRegistry
from homeclaw.plugins.marketplace.installer import (
    InstallError,
    _verify_checksum,
    install_plugin,
    uninstall_plugin,
)
from homeclaw.plugins.marketplace.models import MarketplacePlugin, MarketplacePluginType
from homeclaw.plugins.registry import PluginRegistry, PluginStatus, PluginType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tarball(name: str, files: dict[str, str]) -> bytes:
    """Create an in-memory .tar.gz with files under a top-level directory."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        for filename, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=f"{name}/{filename}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _sha256(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


MINIMAL_PLUGIN_PY = '''\
"""Minimal test plugin."""
from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.plugins.interface import RoutineDefinition

class Plugin:
    name = "testplugin"
    description = "A test plugin"

    def __init__(self, data_dir=None):
        pass

    def tools(self):
        return []

    async def handle_tool(self, name, args):
        return {"error": "unknown"}

    def routines(self):
        return []
'''

MINIMAL_MANIFEST = json.dumps({
    "name": "testplugin",
    "version": "1.0.0",
    "description": "A test plugin",
    "type": "python",
})

MINIMAL_SKILL_MD = """\
---
name: testskill
description: A test skill
allowed-domains:
  - example.com
---
Just a test skill.
"""


def _make_registry(tmp_path: Path) -> PluginRegistry:
    return PluginRegistry(tool_registry=ToolRegistry())


# ---------------------------------------------------------------------------
# Checksum verification
# ---------------------------------------------------------------------------


def test_verify_checksum_valid():
    data = b"hello world"
    _verify_checksum(data, _sha256(data))


def test_verify_checksum_empty_skips():
    _verify_checksum(b"anything", "")


def test_verify_checksum_mismatch():
    with pytest.raises(InstallError, match="Checksum mismatch"):
        _verify_checksum(b"hello", "sha256:0000")


def test_verify_checksum_unsupported_format():
    with pytest.raises(InstallError, match="Unsupported checksum"):
        _verify_checksum(b"hello", "md5:abc")


# ---------------------------------------------------------------------------
# Python plugin install
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_python_plugin(tmp_path: Path) -> None:
    tarball = _make_tarball("testplugin", {
        "plugin.py": MINIMAL_PLUGIN_PY,
        "manifest.json": MINIMAL_MANIFEST,
    })

    plugin = MarketplacePlugin(
        name="testplugin",
        type=MarketplacePluginType.PYTHON,
        version="1.0.0",
        description="A test plugin",
        download_url="https://example.com/testplugin.tar.gz",
        checksum=_sha256(tarball),
    )

    registry = _make_registry(tmp_path)

    with patch(
        "homeclaw.plugins.marketplace.installer._download",
        new_callable=AsyncMock,
        return_value=tarball,
    ):
        entry = await install_plugin(plugin, tmp_path, registry)

    assert entry.name == "testplugin"
    assert entry.plugin_type == PluginType.PYTHON
    assert entry.status == PluginStatus.ACTIVE

    # Files on disk
    assert (tmp_path / "plugins" / "testplugin" / "plugin.py").is_file()

    # Enabled
    enabled_path = tmp_path / "plugins" / "enabled.json"
    assert enabled_path.exists()
    enabled = json.loads(enabled_path.read_text())
    assert "testplugin" in enabled


@pytest.mark.asyncio
async def test_install_python_plugin_checksum_mismatch(tmp_path: Path) -> None:
    tarball = _make_tarball("testplugin", {"plugin.py": MINIMAL_PLUGIN_PY})

    plugin = MarketplacePlugin(
        name="testplugin",
        type=MarketplacePluginType.PYTHON,
        version="1.0.0",
        description="test",
        download_url="https://example.com/test.tar.gz",
        checksum="sha256:0000bad",
    )

    registry = _make_registry(tmp_path)

    with patch(
        "homeclaw.plugins.marketplace.installer._download",
        new_callable=AsyncMock,
        return_value=tarball,
    ), pytest.raises(InstallError, match="Checksum mismatch"):
        await install_plugin(plugin, tmp_path, registry)


@pytest.mark.asyncio
async def test_install_python_already_exists(tmp_path: Path) -> None:
    dest = tmp_path / "plugins" / "testplugin"
    dest.mkdir(parents=True)

    tarball = _make_tarball("testplugin", {"plugin.py": MINIMAL_PLUGIN_PY})
    plugin = MarketplacePlugin(
        name="testplugin",
        type=MarketplacePluginType.PYTHON,
        version="1.0.0",
        description="test",
        download_url="https://example.com/test.tar.gz",
    )

    registry = _make_registry(tmp_path)

    with patch(
        "homeclaw.plugins.marketplace.installer._download",
        new_callable=AsyncMock,
        return_value=tarball,
    ), pytest.raises(InstallError, match="already installed"):
        await install_plugin(plugin, tmp_path, registry)


@pytest.mark.asyncio
async def test_install_python_missing_plugin_py(tmp_path: Path) -> None:
    tarball = _make_tarball("testplugin", {"README.md": "# hi"})
    plugin = MarketplacePlugin(
        name="testplugin",
        type=MarketplacePluginType.PYTHON,
        version="1.0.0",
        description="test",
        download_url="https://example.com/test.tar.gz",
    )

    registry = _make_registry(tmp_path)

    with patch(
        "homeclaw.plugins.marketplace.installer._download",
        new_callable=AsyncMock,
        return_value=tarball,
    ), pytest.raises(InstallError, match="missing plugin.py"):
        await install_plugin(plugin, tmp_path, registry)


# ---------------------------------------------------------------------------
# Skill plugin install
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_skill_plugin(tmp_path: Path) -> None:
    data = MINIMAL_SKILL_MD.encode()
    plugin = MarketplacePlugin(
        name="testskill",
        type=MarketplacePluginType.SKILL,
        version="0.1.0",
        description="A test skill",
        download_url="https://example.com/testskill.md",
        checksum=_sha256(data),
    )

    registry = _make_registry(tmp_path)

    with patch(
        "homeclaw.plugins.marketplace.installer._download",
        new_callable=AsyncMock,
        return_value=data,
    ):
        entry = await install_plugin(plugin, tmp_path, registry)

    assert entry.name == "testskill"
    assert entry.plugin_type == PluginType.SKILL
    assert (tmp_path / "household" / "skills" / "testskill" / "skill.md").is_file()


@pytest.mark.asyncio
async def test_install_skill_invalid_markdown(tmp_path: Path) -> None:
    data = b"This is not valid skill markdown"
    plugin = MarketplacePlugin(
        name="bad",
        type=MarketplacePluginType.SKILL,
        version="0.1.0",
        description="bad",
        download_url="https://example.com/bad.md",
    )

    registry = _make_registry(tmp_path)

    with patch(
        "homeclaw.plugins.marketplace.installer._download",
        new_callable=AsyncMock,
        return_value=data,
    ), pytest.raises(InstallError, match="Invalid skill markdown"):
        await install_plugin(plugin, tmp_path, registry)


# ---------------------------------------------------------------------------
# MCP sidecar install
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_mcp_plugin(tmp_path: Path) -> None:
    plugin = MarketplacePlugin(
        name="homeassistant",
        type=MarketplacePluginType.MCP,
        version="1.0.0",
        description="Home Assistant integration",
        download_url="ghcr.io/homeclaw/ha-sidecar:1.0.0",
    )

    registry = _make_registry(tmp_path)
    entry = await install_plugin(plugin, tmp_path, registry)

    assert entry.name == "homeassistant"
    assert entry.plugin_type == PluginType.MCP
    assert entry.status == PluginStatus.DISABLED

    compose_path = tmp_path / "plugins" / "mcp" / "homeassistant.yml"
    assert compose_path.exists()
    content = compose_path.read_text()
    assert "ghcr.io/homeclaw/ha-sidecar:1.0.0" in content
    assert "homeassistant:" in content


# ---------------------------------------------------------------------------
# No download_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_install_no_download_url(tmp_path: Path) -> None:
    plugin = MarketplacePlugin(
        name="broken",
        type=MarketplacePluginType.PYTHON,
        version="1.0.0",
        description="no url",
        download_url="",
    )

    registry = _make_registry(tmp_path)
    with pytest.raises(InstallError, match="no download_url"):
        await install_plugin(plugin, tmp_path, registry)


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def test_uninstall_python_plugin(tmp_path: Path) -> None:
    plugins_dir = tmp_path / "plugins"
    plugin_dir = plugins_dir / "testplugin"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text("# plugin")

    # Write enabled.json
    enabled_path = plugins_dir / "enabled.json"
    enabled_path.write_text(json.dumps(["testplugin"]))

    registry = _make_registry(tmp_path)
    removed = uninstall_plugin("testplugin", tmp_path, registry)

    assert removed is True
    assert not plugin_dir.exists()
    enabled = json.loads(enabled_path.read_text())
    assert "testplugin" not in enabled


def test_uninstall_skill_plugin(tmp_path: Path) -> None:
    skill_dir = tmp_path / "household" / "skills" / "testskill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: testskill\ndescription: test\n---\n")

    registry = _make_registry(tmp_path)
    removed = uninstall_plugin("testskill", tmp_path, registry)

    assert removed is True
    assert not skill_dir.exists()


def test_uninstall_mcp_plugin(tmp_path: Path) -> None:
    mcp_dir = tmp_path / "plugins" / "mcp"
    mcp_dir.mkdir(parents=True)
    compose = mcp_dir / "testmcp.yml"
    compose.write_text("services:\n  testmcp:\n    image: foo\n")

    registry = _make_registry(tmp_path)
    removed = uninstall_plugin("testmcp", tmp_path, registry)

    assert removed is True
    assert not compose.exists()


def test_uninstall_not_found(tmp_path: Path) -> None:
    registry = _make_registry(tmp_path)
    assert uninstall_plugin("nonexistent", tmp_path, registry) is False
