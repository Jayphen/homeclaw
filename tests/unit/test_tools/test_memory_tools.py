"""Tests for built-in memory tools (memory_read, memory_update)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools


@pytest.fixture
def registry(dev_workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, dev_workspaces)
    return reg


# ── memory_read ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_read_alice(registry: ToolRegistry) -> None:
    handler = registry.get_handler("memory_read")
    assert handler is not None
    result = await handler(person="alice")
    assert len(result["facts"]) == 4
    assert "Vegetarian" in result["facts"]
    prefs = result["preferences"]
    assert prefs["reminder_time"] == "7:30am"
    assert prefs["communication_style"] == "brief and friendly"
    assert prefs["dietary"] == "vegetarian"
    assert result["last_updated"] is not None


@pytest.mark.asyncio
async def test_memory_read_nonexistent_person(registry: ToolRegistry) -> None:
    handler = registry.get_handler("memory_read")
    assert handler is not None
    result = await handler(person="nobody")
    assert result["facts"] == []
    assert result["preferences"] == {}


# ── memory_update ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_update_replaces_facts(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("memory_update")
    assert handler is not None
    new_facts = ["Likes running", "Works from home"]
    result = await handler(person="alice", facts=new_facts)
    assert result["status"] == "updated"
    assert result["person"] == "alice"

    # Verify via read
    read_handler = registry.get_handler("memory_read")
    assert read_handler is not None
    mem = await read_handler(person="alice")
    assert mem["facts"] == new_facts


@pytest.mark.asyncio
async def test_memory_update_replaces_preferences(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("memory_update")
    assert handler is not None
    new_prefs = {"theme": "dark", "language": "en"}
    result = await handler(person="bob", preferences=new_prefs)
    assert result["status"] == "updated"

    read_handler = registry.get_handler("memory_read")
    assert read_handler is not None
    mem = await read_handler(person="bob")
    assert mem["preferences"] == new_prefs


@pytest.mark.asyncio
async def test_memory_update_persists_to_disk(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("memory_update")
    assert handler is not None
    await handler(person="alice", facts=["Only fact"])

    # Read directly from disk, not through the tool
    path = dev_workspaces / "alice" / "memory.json"
    data = json.loads(path.read_text())
    assert data["facts"] == ["Only fact"]
    assert data["last_updated"] is not None
