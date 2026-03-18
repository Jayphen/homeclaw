"""Tests for skill_remove and skill_migrate built-in tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
from homeclaw.plugins.registry import PluginRegistry, PluginType
from homeclaw.plugins.skills.loader import load_skill

SKILL_MD = """\
# Skill: {name}

Description: A test skill

## Allowed Domains
- api.example.com

## Tools

## Instructions
Test instructions.
"""


def make_skill(workspaces: Path, owner: str, name: str) -> Path:
    skill_dir = workspaces / owner / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill.md").write_text(SKILL_MD.format(name=name))
    (skill_dir / "notes.md").write_text(f"# {name} notes\n\n- Some data\n")
    return skill_dir


@pytest.fixture
def workspaces(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def plugin_reg(workspaces: Path) -> PluginRegistry:
    tool_reg = ToolRegistry()
    return PluginRegistry(tool_registry=tool_reg)


@pytest.fixture
def registry(workspaces: Path, plugin_reg: PluginRegistry) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, workspaces, plugin_registry=plugin_reg)
    return reg


# ---------------------------------------------------------------------------
# skill_remove
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_remove_archives_household_skill(
    registry: ToolRegistry, workspaces: Path, plugin_reg: PluginRegistry
) -> None:
    skill_dir = make_skill(workspaces, "household", "weather")
    plugin_reg.register(load_skill(skill_dir, "household"), PluginType.SKILL)

    result = await registry.get_handler("skill_remove")(  # type: ignore[misc]
        person="alice", name="weather", owner="household"
    )

    assert result["status"] == "archived"
    assert result["name"] == "weather"
    assert result["unregistered"] is True

    # Original dir gone
    assert not skill_dir.exists()

    # Archive exists with data intact
    archive_path = Path(result["archive_path"])
    assert archive_path.exists()
    assert (archive_path / "skill.md").exists()
    assert (archive_path / "notes.md").exists()

    # No longer in registry
    assert plugin_reg.get("weather") is None


@pytest.mark.asyncio
async def test_skill_remove_archives_private_skill(
    registry: ToolRegistry, workspaces: Path
) -> None:
    skill_dir = make_skill(workspaces, "alice", "my_secret")

    result = await registry.get_handler("skill_remove")(  # type: ignore[misc]
        person="alice", name="my_secret", owner="alice"
    )

    assert result["status"] == "archived"
    archive_path = Path(result["archive_path"])
    assert archive_path.parent == workspaces / "alice" / "skills" / ".archive"
    assert archive_path.name.startswith("my_secret_")


@pytest.mark.asyncio
async def test_skill_remove_archive_name_includes_timestamp(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "household", "weather")
    result = await registry.get_handler("skill_remove")(  # type: ignore[misc]
        person="alice", name="weather", owner="household"
    )
    archive_name = Path(result["archive_path"]).name
    # format: weather_YYYYMMDD_HHMMSS
    assert archive_name.startswith("weather_")
    parts = archive_name.split("_")
    assert len(parts) == 3
    assert parts[1].isdigit() and len(parts[1]) == 8  # YYYYMMDD


@pytest.mark.asyncio
async def test_skill_remove_not_found(registry: ToolRegistry) -> None:
    result = await registry.get_handler("skill_remove")(  # type: ignore[misc]
        person="alice", name="nonexistent", owner="household"
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_skill_remove_preserves_all_data_files(
    registry: ToolRegistry, workspaces: Path
) -> None:
    skill_dir = make_skill(workspaces, "household", "recipes")
    (skill_dir / "index.json").write_text('{"items": []}')
    (skill_dir / "cache.md").write_text("# Cache\n\n- item1\n")

    result = await registry.get_handler("skill_remove")(  # type: ignore[misc]
        person="alice", name="recipes", owner="household"
    )

    archive_path = Path(result["archive_path"])
    assert (archive_path / "skill.md").exists()
    assert (archive_path / "notes.md").exists()
    assert (archive_path / "index.json").exists()
    assert (archive_path / "cache.md").exists()


@pytest.mark.asyncio
async def test_skill_remove_without_plugin_registry(
    workspaces: Path,
) -> None:
    """Remove still archives the directory even without a plugin registry."""
    make_skill(workspaces, "household", "weather")
    reg = ToolRegistry()
    register_builtin_tools(reg, workspaces)  # no plugin_registry

    result = await reg.get_handler("skill_remove")(  # type: ignore[misc]
        person="alice", name="weather", owner="household"
    )
    assert result["status"] == "archived"
    assert result["unregistered"] is False


# ---------------------------------------------------------------------------
# skill_migrate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_migrate_household_to_private(
    registry: ToolRegistry, workspaces: Path, plugin_reg: PluginRegistry
) -> None:
    skill_dir = make_skill(workspaces, "household", "weather")
    plugin_reg.register(load_skill(skill_dir, "household"), PluginType.SKILL)

    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="weather",
        current_owner="household",
        to_scope="private",
        to_person="alice",
    )

    assert result["status"] == "migrated"
    assert result["from_owner"] == "household"
    assert result["to_owner"] == "alice"
    assert result["loaded"] is True

    # Old location gone, new location exists with data
    assert not (workspaces / "household" / "skills" / "weather").exists()
    new_dir = workspaces / "alice" / "skills" / "weather"
    assert new_dir.exists()
    assert (new_dir / "skill.md").exists()
    assert (new_dir / "notes.md").exists()

    # Re-registered with new scope
    plugin = plugin_reg.get("weather")
    assert plugin is not None
    assert plugin.scope == "alice"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_skill_migrate_private_to_household(
    registry: ToolRegistry, workspaces: Path, plugin_reg: PluginRegistry
) -> None:
    skill_dir = make_skill(workspaces, "alice", "my_skill")
    plugin_reg.register(load_skill(skill_dir, "alice"), PluginType.SKILL)

    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="my_skill",
        current_owner="alice",
        to_scope="household",
    )

    assert result["status"] == "migrated"
    assert result["to_owner"] == "household"
    assert (workspaces / "household" / "skills" / "my_skill").exists()
    assert not (workspaces / "alice" / "skills" / "my_skill").exists()

    plugin = plugin_reg.get("my_skill")
    assert plugin is not None
    assert plugin.scope == "household"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_skill_migrate_private_to_private(
    registry: ToolRegistry, workspaces: Path, plugin_reg: PluginRegistry
) -> None:
    """Transfer a private skill from one person to another."""
    skill_dir = make_skill(workspaces, "alice", "shared_recipe")
    plugin_reg.register(load_skill(skill_dir, "alice"), PluginType.SKILL)

    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="shared_recipe",
        current_owner="alice",
        to_scope="private",
        to_person="bob",
    )

    assert result["to_owner"] == "bob"
    assert (workspaces / "bob" / "skills" / "shared_recipe").exists()
    assert not (workspaces / "alice" / "skills" / "shared_recipe").exists()


@pytest.mark.asyncio
async def test_skill_migrate_not_found(registry: ToolRegistry) -> None:
    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="nonexistent",
        current_owner="household",
        to_scope="private",
        to_person="alice",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_skill_migrate_destination_exists_error(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "household", "weather")
    make_skill(workspaces, "alice", "weather")  # already exists at destination

    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="weather",
        current_owner="household",
        to_scope="private",
        to_person="alice",
    )
    assert "error" in result
    assert "already exists" in result["error"]


@pytest.mark.asyncio
async def test_skill_migrate_invalid_scope(registry: ToolRegistry, workspaces: Path) -> None:
    make_skill(workspaces, "household", "weather")
    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="weather",
        current_owner="household",
        to_scope="shared",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_skill_migrate_private_scope_requires_to_person(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "household", "weather")
    result = await registry.get_handler("skill_migrate")(  # type: ignore[misc]
        person="alice",
        name="weather",
        current_owner="household",
        to_scope="private",
        # to_person omitted
    )
    assert "error" in result
    assert "to_person" in result["error"]
