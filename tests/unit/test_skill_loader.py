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
    plugin = SkillPlugin(defn, tmp_path)
    assert isinstance(plugin, Plugin)


def test_skill_plugin_name_and_description(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path)
    assert plugin.name == "weather"
    assert plugin.description == "Get current weather and forecasts"


def test_skill_plugin_tools_returns_http_call(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path)
    tools = plugin.tools()

    assert len(tools) == 1
    assert tools[0].name == "http_call"
    assert "url" in tools[0].parameters["properties"]
    assert "method" in tools[0].parameters["properties"]


def test_skill_plugin_routines_empty(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path)
    assert plugin.routines() == []


@pytest.mark.asyncio
async def test_skill_plugin_handle_tool_unknown(tmp_path: Path) -> None:
    defn = parse_skill_markdown(WEATHER_SKILL_MD)
    plugin = SkillPlugin(defn, tmp_path)
    result = await plugin.handle_tool("unknown_tool", {})
    assert "error" in result


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


def test_discover_skills_finds_md_files(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "weather.md").write_text(WEATHER_SKILL_MD)
    (skills_dir / "news.md").write_text(MINIMAL_SKILL_MD.replace("minimal", "news"))
    (skills_dir / "notes.txt").write_text("not a skill")

    names = discover_skills(skills_dir)
    assert sorted(names) == ["news", "weather"]


def test_discover_skills_empty_dir(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    assert discover_skills(skills_dir) == []


def test_discover_skills_missing_dir(tmp_path: Path) -> None:
    assert discover_skills(tmp_path / "nonexistent") == []


# ---------------------------------------------------------------------------
# load_all_skills
# ---------------------------------------------------------------------------


def test_load_all_skills_registers_with_registry(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "weather.md").write_text(WEATHER_SKILL_MD)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(skills_dir, tmp_path, plugin_reg)

    assert len(entries) == 1
    assert entries[0].name == "weather"
    assert entries[0].plugin_type == PluginType.SKILL

    # The tool should be namespaced as weather.http_call
    assert tool_reg.has_tool("weather.http_call")


def test_load_all_skills_multiple(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "weather.md").write_text(WEATHER_SKILL_MD)
    (skills_dir / "minimal.md").write_text(MINIMAL_SKILL_MD)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(skills_dir, tmp_path, plugin_reg)

    assert len(entries) == 2
    names = {e.name for e in entries}
    assert names == {"weather", "minimal"}
    assert plugin_reg.plugin_count == 2


def test_load_all_skills_skips_bad_files(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "weather.md").write_text(WEATHER_SKILL_MD)
    (skills_dir / "broken.md").write_text("This is not a valid skill file.")

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(skills_dir, tmp_path, plugin_reg)

    # Only the valid skill should be loaded
    assert len(entries) == 1
    assert entries[0].name == "weather"
