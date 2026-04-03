"""Tests for deterministic skill verification."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry
from homeclaw.plugins.registry import PluginRegistry, PluginType
from homeclaw.plugins.skills.loader import load_skill
from homeclaw.plugins.skills.verification import verify_skill


WEATHER_SKILL_MD = """\
---
name: weather
description: Get current weather and forecasts
allowed-domains:
  - api.openweathermap.org
---
Use weather__http_call when asked about current conditions.
"""


@pytest.fixture
def workspaces(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture(autouse=True)
def _no_builtin_skills(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "homeclaw.plugins.skills.loader._builtin_skills_dir",
        lambda: tmp_path / "_no_builtin_skills",
    )


def _make_skill(workspaces: Path, owner: str, name: str, md: str) -> Path:
    skill_dir = workspaces / owner / "skills" / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(md)
    return skill_dir


def test_verify_skill_passes_for_registered_skill(workspaces: Path) -> None:
    tool_registry = ToolRegistry()
    plugin_registry = PluginRegistry(tool_registry=tool_registry)
    skill_dir = _make_skill(workspaces, "household", "weather", WEATHER_SKILL_MD)
    plugin = load_skill(skill_dir, "household")
    plugin_registry.register(plugin, PluginType.SKILL)

    report = verify_skill(
        skill_dir,
        owner="household",
        scope="household",
        source="test",
        plugin_registry=plugin_registry,
        expect_registered=True,
    )

    assert report.status == "verified"
    assert not report.missing_tools
    assert "weather__http_call" in report.expected_tools


def test_verify_skill_warns_on_missing_dependencies(workspaces: Path) -> None:
    skill_dir = _make_skill(
        workspaces,
        "household",
        "needs_env",
        """\
---
name: needs_env
description: Needs an API key
metadata:
  openclaw:
    requires:
      env:
        - SECRET_TOKEN
---
Use the secret token.
""",
    )

    report = verify_skill(
        skill_dir,
        owner="household",
        scope="household",
        source="test",
    )

    assert report.status == "warning"
    assert "Missing env var 'SECRET_TOKEN'" in report.dependency_warnings


def test_verify_skill_fails_on_name_mismatch(workspaces: Path) -> None:
    skill_dir = _make_skill(
        workspaces,
        "household",
        "dir_name",
        """\
---
name: different-name
description: mismatch
---
Mismatch.
""",
    )

    report = verify_skill(
        skill_dir,
        owner="household",
        scope="household",
        source="test",
    )

    assert report.status == "failed"
    assert any(
        check.name == "skill_name_matches_directory" and check.status == "failed"
        for check in report.checks
    )
