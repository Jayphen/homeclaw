"""Tests for skill_list and skill_create built-in tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
from homeclaw.plugins.registry import PluginRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

WEATHER_SKILL_MD = """\
# Skill: weather

Description: Get current weather and forecasts

## Allowed Domains
- api.openweathermap.org

## Tools

### get_weather
Description: Get current weather for a location
Parameters:
- location (string, required): City name or coordinates

## Instructions
Use get_weather when asked about current conditions.
"""


def make_skill(workspaces: Path, owner: str, name: str, md: str) -> Path:
    skill_dir = workspaces / owner / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill.md").write_text(md)
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
# skill_list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_list_empty(registry: ToolRegistry) -> None:
    handler = registry.get_handler("skill_list")
    assert handler is not None
    result = await handler(person="alice")
    assert result["count"] == 0
    assert result["skills"] == []


@pytest.mark.asyncio
async def test_skill_list_household_skill(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "household", "weather", WEATHER_SKILL_MD)
    result = await registry.get_handler("skill_list")(person="alice")  # type: ignore[misc]
    assert result["count"] == 1
    assert result["skills"][0]["name"] == "weather"
    assert result["skills"][0]["scope"] == "household"
    assert result["skills"][0]["description"] == "Get current weather and forecasts"
    assert result["skills"][0]["tool_count"] == 1


@pytest.mark.asyncio
async def test_skill_list_private_skill(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "alice", "myskill", WEATHER_SKILL_MD.replace("weather", "myskill"))
    result = await registry.get_handler("skill_list")(person="alice")  # type: ignore[misc]
    assert result["count"] == 1
    assert result["skills"][0]["scope"] == "alice"


@pytest.mark.asyncio
async def test_skill_list_isolates_private_skills(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "alice", "secret", WEATHER_SKILL_MD)
    # bob cannot see alice's private skill
    result = await registry.get_handler("skill_list")(person="bob")  # type: ignore[misc]
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_skill_list_household_and_private(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "household", "weather", WEATHER_SKILL_MD)
    make_skill(workspaces, "alice", "personal", WEATHER_SKILL_MD.replace("weather", "personal"))
    result = await registry.get_handler("skill_list")(person="alice")  # type: ignore[misc]
    assert result["count"] == 2
    scopes = {s["name"]: s["scope"] for s in result["skills"]}
    assert scopes["weather"] == "household"
    assert scopes["personal"] == "alice"


# ---------------------------------------------------------------------------
# skill_create — basic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_create_household(
    registry: ToolRegistry, workspaces: Path, plugin_reg: PluginRegistry
) -> None:
    handler = registry.get_handler("skill_create")
    assert handler is not None
    result = await handler(
        person="alice",
        name="weather",
        description="Get weather info",
        scope="household",
        allowed_domains=["api.openweathermap.org"],
        instructions="Use this to answer weather questions.",
        tools=[{"name": "get_weather", "description": "Get weather", "params": [
            {"name": "location", "type": "string", "required": True, "description": "City name"}
        ]}],
    )
    assert result["status"] == "created"
    assert result["name"] == "weather"
    assert result["scope"] == "household"
    assert result["loaded"] is True

    # skill.md created in correct location
    skill_dir = workspaces / "household" / "skills" / "weather"
    assert (skill_dir / "skill.md").exists()
    assert "# Skill: weather" in (skill_dir / "skill.md").read_text()

    # registered in plugin registry
    assert plugin_reg.get("weather") is not None


@pytest.mark.asyncio
async def test_skill_create_private(
    registry: ToolRegistry, workspaces: Path, plugin_reg: PluginRegistry
) -> None:
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="my_budget",
        description="Track my budget",
        scope="private",
        allowed_domains=[],
        instructions="Use this skill to track personal expenses.",
    )
    assert result["status"] == "created"
    assert result["scope"] == "private"
    assert (workspaces / "alice" / "skills" / "my_budget" / "skill.md").exists()


@pytest.mark.asyncio
async def test_skill_create_slugifies_name(
    registry: ToolRegistry, workspaces: Path
) -> None:
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="My Weather Tool",
        description="desc",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
    )
    assert result["name"] == "my_weather_tool"
    assert (workspaces / "household" / "skills" / "my_weather_tool").exists()


@pytest.mark.asyncio
async def test_skill_create_invalid_name_error(registry: ToolRegistry) -> None:
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="!!!",
        description="desc",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_skill_create_invalid_scope_error(registry: ToolRegistry) -> None:
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="myskill",
        description="desc",
        scope="shared",
        allowed_domains=[],
        instructions="instructions",
    )
    assert "error" in result


@pytest.mark.asyncio
async def test_skill_create_duplicate_error(
    registry: ToolRegistry, workspaces: Path
) -> None:
    make_skill(workspaces, "household", "weather", WEATHER_SKILL_MD)
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="weather",
        description="desc",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
    )
    assert "error" in result
    assert "already exists" in result["error"]


# ---------------------------------------------------------------------------
# skill_create — initial_files
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_create_with_initial_files(
    registry: ToolRegistry, workspaces: Path
) -> None:
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="recipes",
        description="Recipe manager",
        scope="private",
        allowed_domains=["api.recipes.com"],
        instructions="Use this to manage recipes.",
        initial_files=[
            {"filename": "notes.md", "content": "# My Recipes\n\n- Pasta\n- Pizza\n"},
            {"filename": "config.json", "content": '{"api_key": "placeholder"}'},
        ],
    )
    assert result["status"] == "created"
    data_dir = workspaces / "alice" / "skills" / "recipes" / "data"
    assert (data_dir / "notes.md").exists()
    assert "Pasta" in (data_dir / "notes.md").read_text()
    assert (data_dir / "config.json").exists()
    assert "seeded_files" in result
    assert "notes.md" in result["seeded_files"]


@pytest.mark.asyncio
async def test_skill_create_initial_files_strips_path(
    registry: ToolRegistry, workspaces: Path
) -> None:
    """Path components in filename are stripped for safety."""
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="safe_test",
        description="desc",
        scope="private",
        allowed_domains=[],
        instructions="instructions",
        initial_files=[{"filename": "../../../etc/evil.txt", "content": "evil"}],
    )
    assert result["status"] == "created"
    data_dir = workspaces / "alice" / "skills" / "safe_test" / "data"
    # File is created with just the basename, not the full path
    assert (data_dir / "evil.txt").exists()
    # Parent directories were not escaped
    assert not (workspaces / "etc" / "evil.txt").exists()


# ---------------------------------------------------------------------------
# skill_create — source_notes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_create_with_source_notes(
    registry: ToolRegistry, workspaces: Path
) -> None:
    # Seed person's memory
    memory_dir = workspaces / "alice" / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "recipes.md").write_text("# recipes\n\n- [2026-01-01] Pasta carbonara\n")

    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="food_skill",
        description="Food assistant",
        scope="private",
        allowed_domains=[],
        instructions="instructions",
        source_notes=["recipes"],
    )
    assert result["status"] == "created"
    data_dir = workspaces / "alice" / "skills" / "food_skill" / "data"
    assert (data_dir / "recipes.md").exists()
    assert "Pasta carbonara" in (data_dir / "recipes.md").read_text()
    assert "recipes.md" in result["seeded_files"]


@pytest.mark.asyncio
async def test_skill_create_source_notes_falls_back_to_household(
    registry: ToolRegistry, workspaces: Path
) -> None:
    # Seed only household memory (not person's)
    household_memory = workspaces / "household" / "memory"
    household_memory.mkdir(parents=True)
    (household_memory / "house-rules.md").write_text("# house-rules\n\n- No shoes inside\n")

    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="rules_skill",
        description="desc",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
        source_notes=["house-rules"],
    )
    assert result["status"] == "created"
    data_dir = workspaces / "household" / "skills" / "rules_skill" / "data"
    assert (data_dir / "house-rules.md").exists()


@pytest.mark.asyncio
async def test_skill_create_source_notes_missing_topic_skipped(
    registry: ToolRegistry, workspaces: Path
) -> None:
    """Missing topics are skipped without failing the whole create."""
    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="myskill",
        description="desc",
        scope="private",
        allowed_domains=[],
        instructions="instructions",
        source_notes=["nonexistent_topic"],
    )
    assert result["status"] == "created"
    assert "nonexistent_topic.md" not in result["seeded_files"]


# ---------------------------------------------------------------------------
# skill_create — source_bookmarks
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_create_with_source_bookmarks(
    registry: ToolRegistry, workspaces: Path
) -> None:
    from homeclaw.bookmarks.models import Bookmark
    from homeclaw.bookmarks.store import save_bookmark
    from datetime import datetime, timezone

    bm = Bookmark(
        id="abc123",
        title="French Laundry",
        category="place",
        url="https://example.com/french-laundry",
        tags=["fine-dining", "michelin"],
        saved_by="alice",
        saved_at=datetime.now(timezone.utc),
    )
    save_bookmark(workspaces, bm)

    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="dining_skill",
        description="Restaurant assistant",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
        source_bookmarks={"category": "place"},
    )
    assert result["status"] == "created"
    data_dir = workspaces / "household" / "skills" / "dining_skill" / "data"
    assert (data_dir / "bookmarks.md").exists()
    content = (data_dir / "bookmarks.md").read_text()
    assert "French Laundry" in content
    assert "fine-dining" in content
    assert "bookmarks.md" in result["seeded_files"]


@pytest.mark.asyncio
async def test_skill_create_source_bookmarks_by_ids(
    registry: ToolRegistry, workspaces: Path
) -> None:
    from homeclaw.bookmarks.models import Bookmark
    from homeclaw.bookmarks.store import save_bookmark
    from datetime import datetime, timezone

    save_bookmark(workspaces, Bookmark(id="keep1", title="Keep This", category="place", saved_at=datetime.now(timezone.utc)))
    save_bookmark(workspaces, Bookmark(id="skip2", title="Skip This", category="place", saved_at=datetime.now(timezone.utc)))

    result = await registry.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="selected_skill",
        description="desc",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
        source_bookmarks={"ids": ["keep1"]},
    )
    assert result["status"] == "created"
    data_dir = workspaces / "household" / "skills" / "selected_skill" / "data"
    content = (data_dir / "bookmarks.md").read_text()
    assert "Keep This" in content
    assert "Skip This" not in content


# ---------------------------------------------------------------------------
# skill_create — no plugin_registry (graceful degradation)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_create_without_plugin_registry(
    workspaces: Path,
) -> None:
    """skill_create without plugin_registry still creates files, just not hot-loaded."""
    reg = ToolRegistry()
    register_builtin_tools(reg, workspaces)  # no plugin_registry
    result = await reg.get_handler("skill_create")(  # type: ignore[misc]
        person="alice",
        name="cold_skill",
        description="desc",
        scope="household",
        allowed_domains=[],
        instructions="instructions",
    )
    assert result["status"] == "created"
    assert result["loaded"] is False
    assert "note" in result
    assert (workspaces / "household" / "skills" / "cold_skill" / "skill.md").exists()
