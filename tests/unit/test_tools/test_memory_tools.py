"""Tests for built-in memory tools (memory_save, memory_read)."""

from __future__ import annotations

from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools


@pytest.fixture
def registry(dev_workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, dev_workspaces)
    return reg


# ── memory_save ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_save_creates_topic(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("memory_save")
    assert handler is not None
    result = await handler(person="alice", topic="food", content="Likes manchego")
    assert result["status"] == "saved"
    assert result["topic"] == "food"

    # Verify file was created
    path = dev_workspaces / "alice" / "memory" / "food.md"
    assert path.exists()
    text = path.read_text()
    assert "# food" in text
    assert "Likes manchego" in text


@pytest.mark.asyncio
async def test_memory_save_appends(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("memory_save")
    assert handler is not None
    await handler(person="alice", topic="health", content="Allergic to shellfish")
    await handler(person="alice", topic="health", content="Runs 3x per week")

    path = dev_workspaces / "alice" / "memory" / "health.md"
    text = path.read_text()
    assert "Allergic to shellfish" in text
    assert "Runs 3x per week" in text


# ── memory_read ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_memory_read_lists_topics(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    save = registry.get_handler("memory_save")
    read = registry.get_handler("memory_read")
    assert save is not None and read is not None

    await save(person="bob", topic="work", content="Works remotely")
    await save(person="bob", topic="hobbies", content="Likes cooking")

    result = await read(person="bob")
    assert "hobbies" in result["topics"]
    assert "work" in result["topics"]


@pytest.mark.asyncio
async def test_memory_read_specific_topic(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    save = registry.get_handler("memory_save")
    read = registry.get_handler("memory_read")
    assert save is not None and read is not None

    await save(person="alice", topic="pets", content="Cat named Mochi")
    result = await read(person="alice", topic="pets")
    assert result["content"] is not None
    assert "Cat named Mochi" in result["content"]


@pytest.mark.asyncio
async def test_memory_read_nonexistent_topic(registry: ToolRegistry) -> None:
    read = registry.get_handler("memory_read")
    assert read is not None
    result = await read(person="alice", topic="nonexistent")
    assert result["content"] is None


@pytest.mark.asyncio
async def test_memory_read_nonexistent_person(registry: ToolRegistry) -> None:
    read = registry.get_handler("memory_read")
    assert read is not None
    result = await read(person="nobody")
    assert result["topics"] == []


# ── memory_save with person="household" ─────────────────────────────────


@pytest.mark.asyncio
async def test_memory_save_household_writes_to_household(
    registry: ToolRegistry, dev_workspaces: Path,
) -> None:
    handler = registry.get_handler("memory_save")
    assert handler is not None
    result = await handler(person="household", topic="pets", content="We adopted a cat named Miso")
    assert result["status"] == "saved"

    path = dev_workspaces / "household" / "memory" / "pets.md"
    assert path.exists()
    assert "We adopted a cat named Miso" in path.read_text()


@pytest.mark.asyncio
async def test_memory_save_household_does_not_touch_personal(
    registry: ToolRegistry, dev_workspaces: Path,
) -> None:
    handler = registry.get_handler("memory_save")
    assert handler is not None
    await handler(person="household", topic="house-rules", content="No shoes indoors")

    # Alice should not have this in her personal memory
    alice_memory = dev_workspaces / "alice" / "memory" / "house-rules.md"
    assert not alice_memory.exists()
