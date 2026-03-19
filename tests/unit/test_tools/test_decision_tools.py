"""Tests for built-in decision tools (decision_log, decision_list)."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools


@pytest.fixture
def registry(dev_workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, dev_workspaces)
    return reg


# ── decision_log ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_log_creates_household_file(
    registry: ToolRegistry, dev_workspaces: Path,
) -> None:
    handler = registry.get_handler("decision_log")
    assert handler is not None
    result = await handler(person="alice", decision="Piano lessons on Tuesdays")
    assert result["status"] == "logged"
    assert result["scope"] == "household"
    path = dev_workspaces / "household" / "decisions.md"
    assert path.exists()
    content = path.read_text()
    assert "Piano lessons on Tuesdays" in content
    assert "— alice" in content


@pytest.mark.asyncio
async def test_decision_log_appends(
    registry: ToolRegistry, dev_workspaces: Path,
) -> None:
    handler = registry.get_handler("decision_log")
    assert handler is not None
    await handler(person="alice", decision="Oat milk only")
    await handler(person="bob", decision="No screens after 8pm")
    path = dev_workspaces / "household" / "decisions.md"
    content = path.read_text()
    assert "Oat milk only" in content
    assert "No screens after 8pm" in content


@pytest.mark.asyncio
async def test_decision_log_personal_scope(
    registry: ToolRegistry, dev_workspaces: Path,
) -> None:
    handler = registry.get_handler("decision_log")
    assert handler is not None
    result = await handler(
        person="alice", decision="Morning yoga at 6am", scope="personal",
    )
    assert result["scope"] == "personal"
    path = dev_workspaces / "alice" / "decisions.md"
    assert path.exists()
    assert "Morning yoga at 6am" in path.read_text()


@pytest.mark.asyncio
async def test_decision_log_invalid_scope(registry: ToolRegistry) -> None:
    handler = registry.get_handler("decision_log")
    assert handler is not None
    result = await handler(person="alice", decision="test", scope="invalid")
    assert "error" in result


# ── decision_list ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_decision_list_empty(registry: ToolRegistry) -> None:
    handler = registry.get_handler("decision_list")
    assert handler is not None
    result = await handler()
    assert result["decisions"] == []


@pytest.mark.asyncio
async def test_decision_list_after_logging(
    registry: ToolRegistry,
) -> None:
    log_handler = registry.get_handler("decision_log")
    list_handler = registry.get_handler("decision_list")
    assert log_handler is not None
    assert list_handler is not None

    await log_handler(person="alice", decision="Taco Tuesday every week")
    result = await list_handler()
    assert result["count"] == 1
    assert "Taco Tuesday every week" in result["decisions"][0]


@pytest.mark.asyncio
async def test_decision_list_personal_scope(
    registry: ToolRegistry,
) -> None:
    log_handler = registry.get_handler("decision_log")
    list_handler = registry.get_handler("decision_list")
    assert log_handler is not None
    assert list_handler is not None

    await log_handler(person="alice", decision="Read before bed", scope="personal")
    result = await list_handler(scope="personal", person="alice")
    assert result["count"] == 1
    assert "Read before bed" in result["decisions"][0]
