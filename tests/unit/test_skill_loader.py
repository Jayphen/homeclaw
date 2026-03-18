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
    SkillLocation,
    SkillPlugin,
    discover_skills,
    load_all_skills,
    load_skill,
    parse_skill_markdown,
)

# ---------------------------------------------------------------------------
# Sample markdown
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
# Helpers
# ---------------------------------------------------------------------------


def make_skill_dir(parent: Path, name: str, content: str) -> Path:
    """Create a skill directory with a skill.md file."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "skill.md").write_text(content)
    return skill_dir


# ---------------------------------------------------------------------------
# parse_skill_markdown — valid input
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


# ---------------------------------------------------------------------------
# parse_skill_markdown — missing / malformed sections
# ---------------------------------------------------------------------------


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
    assert plugin.data_dir == skill_dir
    assert plugin.scope == "alice"


def test_skill_plugin_household_scope(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.scope == "household"


def test_skill_plugin_tools_returns_http_call(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path, "household")
    tools = plugin.tools()

    assert len(tools) == 1
    assert tools[0].name == "http_call"
    assert "url" in tools[0].parameters["properties"]
    assert "method" in tools[0].parameters["properties"]


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


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


def test_discover_skills_finds_household_and_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    make_skill_dir(tmp_path / "alice" / "skills", "notes", MINIMAL_SKILL_MD.replace("minimal", "notes"))

    locations = discover_skills(tmp_path, "alice")

    assert len(locations) == 2
    by_name = {loc.name: loc for loc in locations}

    assert by_name["weather"].scope == "household"
    assert by_name["weather"].skill_dir == tmp_path / "household" / "skills" / "weather"

    assert by_name["notes"].scope == "alice"
    assert by_name["notes"].skill_dir == tmp_path / "alice" / "skills" / "notes"


def test_discover_skills_household_only(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)

    locations = discover_skills(tmp_path, "bob")

    assert len(locations) == 1
    assert locations[0].name == "weather"
    assert locations[0].scope == "household"


def test_discover_skills_private_only(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "alice" / "skills", "myskill", MINIMAL_SKILL_MD.replace("minimal", "myskill"))

    locations = discover_skills(tmp_path, "alice")

    assert len(locations) == 1
    assert locations[0].scope == "alice"


def test_discover_skills_skips_archive_dir(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    # An archived skill — should be ignored
    archived = tmp_path / "household" / "skills" / ".archive" / "old_skill"
    archived.mkdir(parents=True)
    (archived / "skill.md").write_text(MINIMAL_SKILL_MD)

    locations = discover_skills(tmp_path, "alice")

    assert len(locations) == 1
    assert locations[0].name == "weather"


def test_discover_skills_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    skills_dir = tmp_path / "household" / "skills"
    skills_dir.mkdir(parents=True)
    # A directory without skill.md — not a skill
    (skills_dir / "notaskill").mkdir()
    (skills_dir / "notaskill" / "README.md").write_text("not a skill")
    make_skill_dir(skills_dir, "weather", WEATHER_SKILL_MD)

    locations = discover_skills(tmp_path, "alice")

    assert len(locations) == 1
    assert locations[0].name == "weather"


def test_discover_skills_empty(tmp_path: Path) -> None:
    assert discover_skills(tmp_path, "alice") == []


def test_discover_skills_missing_dirs(tmp_path: Path) -> None:
    assert discover_skills(tmp_path / "nonexistent", "alice") == []


def test_discover_skills_household_before_personal(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "alice" / "skills", "aaa", MINIMAL_SKILL_MD.replace("minimal", "aaa"))
    make_skill_dir(tmp_path / "household" / "skills", "zzz", MINIMAL_SKILL_MD.replace("minimal", "zzz"))

    locations = discover_skills(tmp_path, "alice")

    # Household comes first regardless of name sort
    assert locations[0].scope == "household"
    assert locations[1].scope == "alice"


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------


def test_load_skill_reads_skill_md(tmp_path: Path) -> None:
    skill_dir = make_skill_dir(tmp_path, "weather", WEATHER_SKILL_MD)
    plugin = load_skill(skill_dir, "household")

    assert plugin.name == "weather"
    assert plugin.scope == "household"
    assert plugin.data_dir == skill_dir


# ---------------------------------------------------------------------------
# load_all_skills
# ---------------------------------------------------------------------------


def test_load_all_skills_registers_with_registry(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg)

    assert len(entries) == 1
    assert entries[0].name == "weather"
    assert entries[0].plugin_type == PluginType.SKILL
    assert tool_reg.has_tool("weather.http_call")


def test_load_all_skills_loads_household_and_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    make_skill_dir(tmp_path / "alice" / "skills", "minimal", MINIMAL_SKILL_MD)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg)

    assert len(entries) == 2
    names = {e.name for e in entries}
    assert names == {"weather", "minimal"}
    assert plugin_reg.plugin_count == 2


def test_load_all_skills_other_person_cannot_see_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "alice" / "skills", "secret", MINIMAL_SKILL_MD.replace("minimal", "secret"))

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "bob", plugin_reg)

    assert len(entries) == 0


def test_load_all_skills_skips_bad_files(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL_MD)
    bad_dir = tmp_path / "household" / "skills" / "broken"
    bad_dir.mkdir()
    (bad_dir / "skill.md").write_text("This is not a valid skill file.")

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg)

    assert len(entries) == 1
    assert entries[0].name == "weather"
