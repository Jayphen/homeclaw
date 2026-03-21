"""Tests for the skill plugin loader."""

from __future__ import annotations

from pathlib import Path

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
    parse_skill_md,
    render_skill_md,
    skill_md_to_definition,
)

# ---------------------------------------------------------------------------
# Sample SKILL.md content
# ---------------------------------------------------------------------------

WEATHER_SKILL = """\
---
name: weather
description: Get current weather and forecasts
allowed-domains:
  - api.openweathermap.org
metadata:
  api_key_env: OPENWEATHER_API_KEY
---
When the user asks about weather, use the weather__http_call tool.
For forecasts, call the API with /forecast endpoint.
"""

MINIMAL_SKILL = """\
---
name: minimal
description: A minimal skill
---
"""

BUDGET_SKILL = """\
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


def make_skill_dir(parent: Path, name: str, content: str) -> Path:
    """Create a skill directory with a SKILL.md file."""
    skill_dir = parent / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)
    return skill_dir


# ---------------------------------------------------------------------------
# parse_skill_md
# ---------------------------------------------------------------------------


def test_parse_skill_md_basic() -> None:
    fm, body = parse_skill_md(WEATHER_SKILL)
    assert fm.name == "weather"
    assert fm.description == "Get current weather and forecasts"
    assert fm.allowed_domains == ["api.openweathermap.org"]
    assert fm.metadata == {"api_key_env": "OPENWEATHER_API_KEY"}
    assert "http_call" in body


def test_parse_skill_md_minimal() -> None:
    fm, body = parse_skill_md(MINIMAL_SKILL)
    assert fm.name == "minimal"
    assert fm.description == "A minimal skill"
    assert fm.allowed_domains == []
    assert body == ""


def test_parse_skill_md_all_fields() -> None:
    fm, body = parse_skill_md(BUDGET_SKILL)
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
    defn = skill_md_to_definition(BUDGET_SKILL)
    assert defn.name == "budget-tracker"
    assert defn.description == "Track household spending and budgets"
    assert defn.license == "MIT"
    assert defn.allowed_tools == ["data_read", "data_write"]
    assert "## Usage" in defn.instructions


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
    defn = skill_md_to_definition(WEATHER_SKILL)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert isinstance(plugin, Plugin)


def test_skill_plugin_name_and_description(tmp_path: Path) -> None:
    defn = skill_md_to_definition(WEATHER_SKILL)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.name == "weather"
    assert plugin.description == "Get current weather and forecasts"


def test_skill_plugin_data_dir_and_scope(tmp_path: Path) -> None:
    defn = skill_md_to_definition(WEATHER_SKILL)
    skill_dir = tmp_path / "weather"
    plugin = SkillPlugin(defn, skill_dir, "alice")
    assert plugin.data_dir == skill_dir / "data"
    assert plugin.data_dir.is_dir()
    assert plugin.scope == "alice"


def test_skill_plugin_tools_returns_http_call(tmp_path: Path) -> None:
    defn = skill_md_to_definition(WEATHER_SKILL)
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


def test_skill_plugin_no_http_call_without_domains(tmp_path: Path) -> None:
    defn = skill_md_to_definition(MINIMAL_SKILL)
    plugin = SkillPlugin(defn, tmp_path, "household")
    tool_names = [t.name for t in plugin.tools()]
    assert "http_call" not in tool_names


def test_skill_plugin_routines_empty(tmp_path: Path) -> None:
    defn = skill_md_to_definition(WEATHER_SKILL)
    plugin = SkillPlugin(defn, tmp_path, "household")
    assert plugin.routines() == []


@pytest.mark.asyncio
async def test_skill_plugin_handle_tool_unknown(tmp_path: Path) -> None:
    defn = skill_md_to_definition(WEATHER_SKILL)
    plugin = SkillPlugin(defn, tmp_path, "household")
    result = await plugin.handle_tool("unknown_tool", {})
    assert "error" in result


# ---------------------------------------------------------------------------
# discover_skills
# ---------------------------------------------------------------------------


def test_discover_skills_finds_household_and_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    make_skill_dir(
        tmp_path / "alice" / "skills", "notes",
        MINIMAL_SKILL.replace("minimal", "notes"),
    )

    locations = discover_skills(tmp_path, "alice", include_builtin=False)

    assert len(locations) == 2
    by_name = {loc.name: loc for loc in locations}
    assert by_name["weather"].scope == "household"
    assert by_name["notes"].scope == "alice"


def test_discover_skills_household_only(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    locations = discover_skills(tmp_path, "bob", include_builtin=False)
    assert len(locations) == 1
    assert locations[0].scope == "household"


def test_discover_skills_skips_archive_dir(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    archived = tmp_path / "household" / "skills" / ".archive" / "old_skill"
    archived.mkdir(parents=True)
    (archived / "SKILL.md").write_text(MINIMAL_SKILL)

    locations = discover_skills(tmp_path, "alice", include_builtin=False)
    assert len(locations) == 1
    assert locations[0].name == "weather"


def test_discover_skills_skips_dirs_without_skill_md(tmp_path: Path) -> None:
    skills_dir = tmp_path / "household" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "notaskill").mkdir()
    (skills_dir / "notaskill" / "README.md").write_text("not a skill")
    make_skill_dir(skills_dir, "weather", WEATHER_SKILL)

    locations = discover_skills(tmp_path, "alice", include_builtin=False)
    assert len(locations) == 1


def test_discover_skills_empty(tmp_path: Path) -> None:
    assert discover_skills(tmp_path, "alice", include_builtin=False) == []


def test_discover_skills_household_before_personal(tmp_path: Path) -> None:
    make_skill_dir(
        tmp_path / "alice" / "skills", "aaa",
        MINIMAL_SKILL.replace("minimal", "aaa"),
    )
    make_skill_dir(
        tmp_path / "household" / "skills", "zzz",
        MINIMAL_SKILL.replace("minimal", "zzz"),
    )

    locations = discover_skills(tmp_path, "alice", include_builtin=False)
    assert locations[0].scope == "household"
    assert locations[1].scope == "alice"


# ---------------------------------------------------------------------------
# load_skill
# ---------------------------------------------------------------------------


def test_load_skill_reads_skill_md(tmp_path: Path) -> None:
    skill_dir = make_skill_dir(tmp_path, "weather", WEATHER_SKILL)
    plugin = load_skill(skill_dir, "household")
    assert plugin.name == "weather"
    assert plugin.scope == "household"
    assert plugin.data_dir == skill_dir / "data"


def test_load_skill_migrates_data_files(tmp_path: Path) -> None:
    """Skills with data files alongside SKILL.md get auto-migrated."""
    skill_dir = make_skill_dir(tmp_path, "budget", MINIMAL_SKILL)
    (skill_dir / "spending.md").write_text("# Spending\n- coffee $5\n")
    (skill_dir / "categories.json").write_text('["food","transport"]')

    plugin = load_skill(skill_dir, "household")

    assert not (skill_dir / "spending.md").exists()
    assert not (skill_dir / "categories.json").exists()
    assert (skill_dir / "data" / "spending.md").exists()
    assert (skill_dir / "data" / "categories.json").exists()
    assert (skill_dir / "SKILL.md").exists()
    assert plugin.data_dir == skill_dir / "data"


def test_load_skill_no_migration_when_data_dir_exists(tmp_path: Path) -> None:
    skill_dir = make_skill_dir(tmp_path, "budget", MINIMAL_SKILL)
    data_dir = skill_dir / "data"
    data_dir.mkdir()
    (data_dir / "spending.md").write_text("# Spending\n")
    (skill_dir / "old.md").write_text("stale")

    load_skill(skill_dir, "household")

    assert (skill_dir / "old.md").exists()
    assert (data_dir / "spending.md").exists()


def test_load_skill_missing_skill_md(tmp_path: Path) -> None:
    skill_dir = tmp_path / "empty"
    skill_dir.mkdir()
    with pytest.raises(FileNotFoundError):
        load_skill(skill_dir, "household")


# ---------------------------------------------------------------------------
# load_all_skills
# ---------------------------------------------------------------------------


def test_load_all_skills_registers_with_registry(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)

    assert len(entries) == 1
    assert entries[0].name == "weather"
    assert entries[0].plugin_type == PluginType.SKILL
    assert tool_reg.has_tool("weather__http_call")


def test_load_all_skills_loads_household_and_private(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    make_skill_dir(tmp_path / "alice" / "skills", "minimal", MINIMAL_SKILL)

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)

    assert len(entries) == 2
    names = {e.name for e in entries}
    assert names == {"weather", "minimal"}


def test_load_all_skills_other_person_cannot_see_private(tmp_path: Path) -> None:
    make_skill_dir(
        tmp_path / "alice" / "skills", "secret",
        MINIMAL_SKILL.replace("minimal", "secret"),
    )

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "bob", plugin_reg, include_builtin=False)
    assert len(entries) == 0


def test_load_all_skills_skips_bad_files(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    bad_dir = tmp_path / "household" / "skills" / "broken"
    bad_dir.mkdir()
    (bad_dir / "SKILL.md").write_text("This is not valid YAML frontmatter.")

    tool_reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=tool_reg)

    entries = load_all_skills(tmp_path, "alice", plugin_reg, include_builtin=False)
    assert len(entries) == 1
    assert entries[0].name == "weather"


# ---------------------------------------------------------------------------
# build_skill_catalog
# ---------------------------------------------------------------------------


def test_build_skill_catalog_basic(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    (tmp_path / "household" / "skills" / "weather" / "scripts").mkdir()

    catalog = build_skill_catalog(tmp_path, "alice", include_builtin=False)
    assert len(catalog) == 1
    assert catalog[0].name == "weather"
    assert catalog[0].scope == "household"
    assert catalog[0].has_scripts is True
    assert catalog[0].has_http is True


def test_build_skill_catalog_empty(tmp_path: Path) -> None:
    assert build_skill_catalog(tmp_path, "alice", include_builtin=False) == []


def test_build_skill_catalog_mixed_scopes(tmp_path: Path) -> None:
    make_skill_dir(tmp_path / "household" / "skills", "weather", WEATHER_SKILL)
    make_skill_dir(
        tmp_path / "alice" / "skills", "budget",
        MINIMAL_SKILL.replace("minimal", "budget"),
    )

    catalog = build_skill_catalog(tmp_path, "alice", include_builtin=False)
    assert len(catalog) == 2
    names = {c.name for c in catalog}
    assert "weather" in names
    assert "budget" in names
