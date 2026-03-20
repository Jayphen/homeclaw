"""Tests for the skill plugin loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from homeclaw.agent.providers.base import ToolDefinition
from homeclaw.agent.tools import ToolRegistry
from homeclaw.plugins.interface import Plugin
from homeclaw.plugins.registry import PluginEntry, PluginRegistry, PluginType
from homeclaw.plugins.skills.loader import (
    SkillCatalogEntry,
    SkillLocation,
    SkillPlugin,
    build_skill_catalog,
    discover_skills,
    load_all_skills,
    load_skill,
    migrate_legacy_skill,
    parse_skill_file,
    parse_skill_markdown,
    parse_skill_md,
    render_skill_md,
    skill_md_to_definition,
)

# ---------------------------------------------------------------------------
# Sample markdown — legacy format
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

### get_forecast
Description: Get 5-day forecast
Parameters:
- location (string, required): City name
- days (integer, optional): Number of days (default 5)

## Instructions
When the user asks about weather, use the get_weather tool.
For forecasts, use get_forecast.
"""

MINIMAL_SKILL_MD = """\
# Skill: minimal

Description: A minimal skill

## Allowed Domains
- example.com

## Tools

## Instructions
"""

# ---------------------------------------------------------------------------
# Sample SKILL.md — new YAML frontmatter format
# ---------------------------------------------------------------------------

WEATHER_SKILL_NEW = """\
---
name: weather
description: Get current weather and forecasts
allowed-domains:
  - api.openweathermap.org
metadata:
  api_key_env: OPENWEATHER_API_KEY
---
When the user asks about weather, use the get_weather tool.
For forecasts, use get_forecast.
"""

MINIMAL_SKILL_NEW = """\
---
name: minimal
description: A minimal skill
---
"""

BUDGET_SKILL_NEW = """\
---
name: budget-tracker
description: Track household spending and budgets
license: MIT
metadata:
  currency: AUD
allowed-tools: data_read data_write
---
## Usage
When the user mentions spending, bills, or budget:
1. Load the current month's data file
2. Append the new entry
3. Show a running total
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_skill_dir(parent: Path, name: str, content: str, filename: str = "skill.md") -> Path:
    """Create a skill directory with a skill definition file."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / filename).write_text(content)
    return skill_dir


# ---------------------------------------------------------------------------
# parse_skill_md — new YAML frontmatter format
# ---------------------------------------------------------------------------


def test_parse_skill_md_basic() -> None:
    fm, body = parse_skill_md(WEATHER_SKILL_NEW)
    assert fm.name == "weather"
    assert fm.description == "Get current weather and forecasts"
    assert fm.allowed_domains == ["api.openweathermap.org"]
    assert fm.metadata == {"api_key_env": "OPENWEATHER_API_KEY"}
    assert "get_weather" in body


def test_parse_skill_md_minimal() -> None:
    fm, body = parse_skill_md(MINIMAL_SKILL_NEW)
    assert fm.name == "minimal"
    assert fm.description == "A minimal skill"
    assert fm.allowed_domains == []
    assert body == ""


def test_parse_skill_md_all_fields() -> None:
    fm, body = parse_skill_md(BUDGET_SKILL_NEW)
    assert fm.name == "budget-tracker"
    assert fm.license == "MIT"
    assert fm.metadata == {"currency": "AUD"}
    assert fm.allowed_tools == ["data_read", "data_write"]
    assert "## Usage" in body


def test_parse_skill_md_missing_frontmatter() -> None:
    with pytest.raises(ValueError, match="missing YAML frontmatter"):
        parse_skill_md("# Just a markdown file\nNo frontmatter here.")


def test_parse_skill_md_missing_name() -> None:
    content = "---\ndescription: no name\n---\nBody here.\n"
    with pytest.raises(ValueError, match="missing required 'name'"):
        parse_skill_md(content)


def test_parse_skill_md_invalid_yaml() -> None:
    content = "---\n: invalid yaml [[\n---\nBody.\n"
    with pytest.raises(ValueError, match="Invalid YAML"):
        parse_skill_md(content)


def test_skill_md_to_definition() -> None:
    defn = skill_md_to_definition(BUDGET_SKILL_NEW)
    assert defn.name == "budget-tracker"
    assert defn.description == "Track household spending and budgets"
    assert defn.license == "MIT"
    assert defn.allowed_tools == ["data_read", "data_write"]
    assert "## Usage" in defn.instructions


# ---------------------------------------------------------------------------
# parse_skill_markdown — legacy format
# ---------------------------------------------------------------------------


def test_parse_valid_skill() -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)

    assert defn.name == "weather"
    assert defn.description == "Get current weather and forecasts"
    assert defn.allowed_domains == ["api.openweathermap.org"]
    assert len(defn.tools) == 2

    tool0 = defn.tools[0]
    assert tool0.name == "get_weather"
    assert tool0.description == "Get current weather for a location"
    assert len(tool0.parameters) == 1
    assert tool0.parameters[0].name == "location"
    assert tool0.parameters[0].type == "string"
    assert tool0.parameters[0].required is True

    tool1 = defn.tools[1]
    assert tool1.name == "get_forecast"
    assert len(tool1.parameters) == 2
    assert tool1.parameters[1].name == "days"
    assert tool1.parameters[1].required is False

    assert "get_weather" in defn.instructions


def test_parse_minimal_skill() -> None:
    defn = parse_skill_markdown(MINIMAL_SKILL_MD)

    assert defn.name == "minimal"
    assert defn.description == "A minimal skill"
    assert defn.allowed_domains == ["example.com"]
    assert defn.tools == []
    assert defn.instructions == ""


def test_parse_missing_name_raises() -> None:
    bad_md = """\
Description: no header

## Allowed Domains
- example.com

## Tools

## Instructions
"""
    with pytest.raises(ValueError, match="missing"):
        parse_skill_markdown(bad_md)


def test_parse_missing_description_gives_empty() -> None:
    md = """\
# Skill: nodesc

## Allowed Domains
- example.com

## Tools

## Instructions
"""
    defn = parse_skill_markdown(md)
    assert defn.name == "nodesc"
    assert defn.description == ""


def test_parse_missing_sections_gives_defaults() -> None:
    md = """\
# Skill: bare

Description: just a name
"""
    defn = parse_skill_markdown(md)
    assert defn.name == "bare"
    assert defn.allowed_domains == []
    assert defn.tools == []
    assert defn.instructions == ""


# ---------------------------------------------------------------------------
# parse_skill_file — auto-detect format
# ---------------------------------------------------------------------------


def test_parse_skill_file_detects_new_format() -> None:
    defn = parse_skill_file(WEATHER_SKILL_NEW)
    assert defn.name == "weather"
    assert defn.description == "Get current weather and forecasts"


def test_parse_skill_file_detects_legacy_format() -> None:
    defn = parse_skill_file(WEATHER_SKILL_MD)
    assert defn.name == "weather"
    assert len(defn.tools) == 2


# ---------------------------------------------------------------------------
# render_skill_md
# ---------------------------------------------------------------------------


def test_render_skill_md_roundtrip() -> None:
    rendered = render_skill_md(
        name="test-skill",
        description="A test skill",
        allowed_domains=["api.example.com"],
        instructions="Do the thing.",
    )
    defn = skill_md_to_definition(rendered)
    assert defn.name == "test-skill"
    assert defn.description == "A test skill"
    assert defn.allowed_domains == ["api.example.com"]
    assert defn.instructions == "Do the thing."


def test_render_skill_md_no_domains() -> None:
    rendered = render_skill_md(name="simple", description="Simple skill")
    defn = skill_md_to_definition(rendered)
    assert defn.name == "simple"
    assert defn.allowed_domains == []


def test_render_skill_md_with_metadata() -> None:
    rendered = render_skill_md(
        name="meta",
        description="With metadata",
        metadata={"key": "value"},
    )
    defn = skill_md_to_definition(rendered)
    assert defn.metadata == {"key": "value"}


# ---------------------------------------------------------------------------
# SkillPlugin satisfies Protocol
# ---------------------------------------------------------------------------


def test_skill_plugin_satisfies_protocol(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert isinstance(plugin, Plugin)


def test_skill_plugin_name_and_description(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.name == "weather"
    assert plugin.description == "Get current weather and forecasts"


def test_skill_plugin_data_dir_and_scope(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    skill_dir = tmp_path / "weather"
    plugin = SkillPlugin(defn, skill_dir, "alice")
    assert plugin.data_dir == skill_dir / "data"
    assert plugin.data_dir.is_dir()
    assert plugin.scope == "alice"


def test_skill_plugin_household_scope(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.scope == "household"


def test_skill_plugin_tools_returns_http_call(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    tools = plugin.tools()

    tool_names = [t.name for t in tools]
    assert "data_list" in tool_names
    assert "data_read" in tool_names
    assert "data_write" in tool_names
    assert "data_delete" in tool_names
    assert "http_call" in tool_names
    http_tool = next(t for t in tools if t.name == "http_call")
    assert "url" in http_tool.parameters["properties"]
    assert "method" in http_tool.parameters["properties"]


def test_skill_plugin_log_dir_inside_skill_dir(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    skill_dir = tmp_path / "weather"
    plugin = SkillPlugin(defn, skill_dir, "household")
    assert plugin._config.log_dir == skill_dir / "logs"


def test_skill_plugin_routines_empty(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.routines() == []


@pytest.mark.asyncio
async def test_skill_plugin_handle_tool_unknown(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    result = await plugin.handle_tool("unknown_tool", {})
    assert "error" in result


def test_skill_plugin_from_new_format(tmp_path: Path) -> None:
    defn = skill_md_to_definition(WEATHER_SKILL_NEW)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.name == "weather"
    tools = plugin.tools()
    assert any(t.name == "http_call" for t in tools)


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


def test_discover_skills_finds_household_and_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    make_skill_dir(tmp_path / "alice" / "skills", "notes", MINIMAL_SKILL_MD.replace("minimal", "notes"))

    locations = discover_skills(tmp_path, "alice", include_builtin=False)

    assert len(locations) == 2
    by_name = {loc.name: loc for loc in locations}

    assert by_name["weather"].scope == "household"
    assert by_name["weather"].skill_dir == tmp_path / "household" / "skills" / "weather"

    assert by_name["notes"].scope == "alice"
    assert by_name["notes"].skill_dir == tmp_path / "alice" / "skills" / "notes"


def test_discover_skills_finds_new_format(tmp_path: Path) -> None:
    make_skill_dir(
        tmp_path / "household" / "skills", "weather",
        WEATHER_SKILL_NEW, filename="SKILL.md",
    )
    locations = discover_skills(tmp_path, "alice", include_builtin=False)
    assert len(locations) == 1
    assert locations[0].skill_file == "SKILL.md"


def test_discover_skills_prefers_skill_md_over_legacy(tmp_path: Path) -> None:
    """If both SKILL.md and skill.md exist, SKILL.md wins.

    On case-insensitive filesystems (macOS, Windows), both files can't
    coexist, so this test only runs on case-sensitive FS.
    """
    skill_dir = tmp_path / "household" / "skills" / "weather"
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.md").write_text(WEATHER_SKILL_MD)
    (skill_dir / "SKILL.md").write_text(WEATHER_SKILL_NEW)

    # Check if FS is case-sensitive
    actual_files = {f.name for f in skill_dir.iterdir()}
    if "SKILL.md" not in actual_files or "skill.md" not in actual_files:
        pytest.skip("Case-insensitive filesystem — can't have both files")

    locations = discover_skills(tmp_path, "alice", include_builtin=False)
    assert len(locations) == 1
    assert locations[0].skill_file == "SKILL.md"


def test_discover_skills_household_only(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)

    locations = discover_skills(tmp_path, "bob", include_builtin=False)

    assert len(locations) == 1
    assert locations[0].name == "weather"
    assert locations[0].scope == "household"


def test_discover_skills_private_only(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "alice" / "skills", "myskill", MINIMAL_SKILL_MD.replace("minimal", "myskill"))

    locations = discover_skills(tmp_path, "alice", include_builtin=False)

    assert len(locations) == 1
    assert locations[0].scope == "alice"


def test_discover_skills_skips_archive_dir(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    # An archived skill — should be ignored
    archived = tmp_path / "household" / "skills" / ".archive" / "old_skill"
    archived.mkdir(parents=True)
    (archived / "skill.md").write_text(MINIMAL_SKILL_MD)

    locations = discover_skills(tmp_path, "alice", include_builtin=False)

    assert len(locations) == 1
    assert locations[0].name == "weather"


def test_discover_skills_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    skills_dir = tmp_path / "household" / "skills"
    skills_dir.mkdir(parents=True)
    # A directory without skill.md — not a skill
    (skills_dir / "notaskill").mkdir()
    (skills_dir / "notaskill" / "README.md").write_text("not a skill")
    make_skill_dir(skills_dir, "weather", WEATHER_SKILL_MD)

    locations = discover_skills(tmp_path, "alice", include_builtin=False)

    assert len(locations) == 1
    assert locations[0].name == "weather"


def test_discover_skills_empty(tmp_path: Path) -> None:
    assert discover_skills(tmp_path, "alice", include_builtin=False) == []


def test_discover_skills_missing_dirs(tmp_path: Path) -> None:
    assert discover_skills(tmp_path / "nonexistent", "alice", include_builtin=False) == []


def test_discover_skills_household_before_personal(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "alice" / "skills", "aaa", MINIMAL_SKILL_MD.replace("minimal", "aaa"))
    make_skill_dir(tmp_path / "household" / "skills", "zzz", MINIMAL_SKILL_MD.replace("minimal", "zzz"))

    locations = discover_skills(tmp_path, "alice", include_builtin=False)

    # Household comes first regardless of name sort
    assert locations[0].scope == "household"
    assert locations[1].scope == "alice"


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------


def test_load_skill_reads_legacy_skill_md(tmp_path: Path) -> None:
    skill_dir = make_skill_dir(tmp_path, "weather", WEATHER_SKILL_MD)
    plugin = load_skill(skill_dir, "household")

    assert plugin.name == "weather"
    assert plugin.scope == "household"
    assert plugin.data_dir == skill_dir / "data"


def test_load_skill_reads_new_skill_md(tmp_path: Path) -> None:
    skill_dir = make_skill_dir(tmp_path, "weather", WEATHER_SKILL_NEW, filename="SKILL.md")
    plugin = load_skill(skill_dir, "household")

    assert plugin.name == "weather"
    assert plugin.scope == "household"


def test_load_skill_auto_migrates_legacy(tmp_path: Path) -> None:
    """Loading a legacy skill.md creates SKILL.md alongside it."""
    skill_dir = make_skill_dir(tmp_path, "weather", WEATHER_SKILL_MD)
    load_skill(skill_dir, "household")

    assert (skill_dir / "SKILL.md").is_file()
    assert (skill_dir / "skill.md").is_file()  # kept as backup


def test_load_skill_migrates_legacy_data_files(tmp_path: Path) -> None:
    """Legacy skills with data files alongside skill.md get auto-migrated."""
    skill_dir = make_skill_dir(tmp_path, "budget", MINIMAL_SKILL_MD)
    # Simulate legacy layout: data files at skill root
    (skill_dir / "spending.md").write_text("# Spending\n- coffee $5\n")
    (skill_dir / "categories.json").write_text('["food","transport"]')

    plugin = load_skill(skill_dir, "household")

    # Data files moved into data/
    assert not (skill_dir / "spending.md").exists()
    assert not (skill_dir / "categories.json").exists()
    assert (skill_dir / "data" / "spending.md").exists()
    assert (skill_dir / "data" / "categories.json").exists()
    # skill.md stays at root
    assert (skill_dir / "skill.md").exists()
    assert plugin.data_dir == skill_dir / "data"


def test_load_skill_no_migration_when_data_dir_exists(tmp_path: Path) -> None:
    """If data/ already exists with files, migration is skipped."""
    skill_dir = make_skill_dir(tmp_path, "budget", MINIMAL_SKILL_MD)
    data_dir = skill_dir / "data"
    data_dir.mkdir()
    (data_dir / "spending.md").write_text("# Spending\n")
    # Stale file at root (shouldn't be moved since data/ has content)
    (skill_dir / "old.md").write_text("stale")

    load_skill(skill_dir, "household")

    # old.md stays where it is — migration skipped
    assert (skill_dir / "old.md").exists()
    assert (data_dir / "spending.md").exists()


# ---------------------------------------------------------------------------
# migrate_legacy_skill
# ---------------------------------------------------------------------------


def test_migrate_legacy_skill_creates_skill_md(tmp_path: Path) -> None:
    skill_dir = make_skill_dir(tmp_path, "weather", WEATHER_SKILL_MD)
    assert migrate_legacy_skill(skill_dir) is True
    assert (skill_dir / "SKILL.md").is_file()

    # Verify the new file parses correctly
    defn = skill_md_to_definition((skill_dir / "SKILL.md").read_text())
    assert defn.name == "weather"
    assert defn.description == "Get current weather and forecasts"


def test_migrate_legacy_skill_skips_if_already_new_format(tmp_path: Path) -> None:
    """If the skill already has SKILL.md (new format), migration is skipped."""
    skill_dir = tmp_path / "weather"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(WEATHER_SKILL_NEW)
    assert migrate_legacy_skill(skill_dir) is False


def test_migrate_legacy_skill_skips_if_no_legacy(tmp_path: Path) -> None:
    skill_dir = tmp_path / "weather"
    skill_dir.mkdir()
    assert migrate_legacy_skill(skill_dir) is False


# ---------------------------------------------------------------------------
# load_all_skills
# ---------------------------------------------------------------------------


def test_load_all_skills_registers_with_registry(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)

    assert len(entries) == 1
    assert entries[0].name == "weather"
    assert entries[0].plugin_type == PluginType.SKILL
    # PluginRegistry namespaces tools as name__tool_name
    assert tool_reg.has_tool("weather__http_call")


def test_load_all_skills_loads_household_and_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    make_skill_dir(tmp_path / "alice" / "skills", "minimal", MINIMAL_SKILL_MD)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)

    assert len(entries) == 2
    names = {e.name for e in entries}
    assert names == {"weather", "minimal"}
    assert plugin_reg.plugin_count == 2


def test_load_all_skills_other_person_cannot_see_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "alice" / "skills", "secret", MINIMAL_SKILL_MD.replace("minimal", "secret"))

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "bob", plugin_reg, include_builtin=False)

    assert len(entries) == 0


def test_load_all_skills_skips_bad_files(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    bad_dir = tmp_path / "household" / "skills" / "broken"
    bad_dir.mkdir()
    (bad_dir / "skill.md").write_text("This is not a valid skill file.")

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)

    assert len(entries) == 1
    assert entries[0].name == "weather"


def test_load_all_skills_with_new_format(tmp_path: Path) -> None:
    make_skill_dir(
        tmp_path / "household" / "skills", "weather",
        WEATHER_SKILL_NEW, filename="SKILL.md",
    )

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)

    assert len(entries) == 1
    assert entries[0].name == "weather"
    assert tool_reg.has_tool("weather__http_call")


# ---------------------------------------------------------------------------
# build_skill_catalog
# ---------------------------------------------------------------------------


def test_build_skill_catalog_basic(tmp_path: Path) -> None:
    make_skill_dir(
        tmp_path / "household" / "skills", "weather",
        WEATHER_SKILL_NEW, filename="SKILL.md",
    )
    # Add scripts/ dir
    (tmp_path / "household" / "skills" / "weather" / "scripts").mkdir()

    catalog = build_skill_catalog(tmp_path, "alice", include_builtin=False)
    assert len(catalog) == 1
    assert catalog[0].name == "weather"
    assert catalog[0].scope == "household"
    assert catalog[0].has_scripts is True


def test_build_skill_catalog_empty(tmp_path: Path) -> None:
    assert build_skill_catalog(tmp_path, "alice", include_builtin=False) == []


def test_build_skill_catalog_mixed_formats(tmp_path: Path) -> None:
    make_skill_dir(
        tmp_path / "household" / "skills", "weather",
        WEATHER_SKILL_NEW, filename="SKILL.md",
    )
    make_skill_dir(
        tmp_path / "alice" / "skills", "budget",
        MINIMAL_SKILL_MD.replace("minimal", "budget"),
    )

    catalog = build_skill_catalog(tmp_path, "alice", include_builtin=False)
    assert len(catalog) == 2
    names = {c.name for c in catalog}
    assert "weather" in names
    assert "budget" in names
