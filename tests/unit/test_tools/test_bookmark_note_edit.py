"""Tests for bookmark_note_edit tool."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools
from homeclaw.bookmarks.models import Bookmark
from homeclaw.bookmarks.store import save_bookmark
from homeclaw.plugins.registry import PluginRegistry


@pytest.fixture
def workspaces(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def registry(workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    plugin_reg = PluginRegistry(tool_registry=ToolRegistry())
    register_builtin_tools(reg, workspaces, plugin_registry=plugin_reg)
    return reg


def _save_test_bookmark(workspaces: Path, bookmark_id: str = "bk1") -> Bookmark:
    b = Bookmark(
        id=bookmark_id,
        title="Test Cafe",
        category="place",
        tags=["coffee"],
        saved_at=datetime.now(timezone.utc),
    )
    save_bookmark(workspaces, b)
    return b


def _notes_path(workspaces: Path, bookmark_id: str = "bk1") -> Path:
    return workspaces / "household" / "bookmarks" / "notes" / f"{bookmark_id}.md"


def _write_notes(workspaces: Path, bookmark_id: str = "bk1") -> Path:
    """Create a notes file with two entries."""
    path = _notes_path(workspaces, bookmark_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Test Cafe\n"
        "\n"
        "- [2026-01-01 10:00] Great espresso\n"
        "- [2026-01-02 14:00] Closed on Mondays\n"
    )
    return path


@pytest.mark.asyncio
async def test_edit_first_note(workspaces: Path, registry: ToolRegistry) -> None:
    _save_test_bookmark(workspaces)
    _write_notes(workspaces)

    handler = registry.get_handler("bookmark_note_edit")
    result = await handler(bookmark_id="bk1", note_index=1, content="Decent espresso")

    assert result["status"] == "updated"
    lines = _notes_path(workspaces).read_text().splitlines()
    assert lines[2] == "- [2026-01-01 10:00] Decent espresso"
    # Second note unchanged
    assert lines[3] == "- [2026-01-02 14:00] Closed on Mondays"


@pytest.mark.asyncio
async def test_edit_second_note(workspaces: Path, registry: ToolRegistry) -> None:
    _save_test_bookmark(workspaces)
    _write_notes(workspaces)

    handler = registry.get_handler("bookmark_note_edit")
    result = await handler(bookmark_id="bk1", note_index=2, content="Open every day now")

    assert result["status"] == "updated"
    lines = _notes_path(workspaces).read_text().splitlines()
    assert lines[2] == "- [2026-01-01 10:00] Great espresso"
    assert lines[3] == "- [2026-01-02 14:00] Open every day now"


@pytest.mark.asyncio
async def test_edit_invalid_index(workspaces: Path, registry: ToolRegistry) -> None:
    _save_test_bookmark(workspaces)
    _write_notes(workspaces)

    handler = registry.get_handler("bookmark_note_edit")
    result = await handler(bookmark_id="bk1", note_index=3, content="nope")
    assert "error" in result

    result = await handler(bookmark_id="bk1", note_index=0, content="nope")
    assert "error" in result


@pytest.mark.asyncio
async def test_edit_no_notes_file(workspaces: Path, registry: ToolRegistry) -> None:
    _save_test_bookmark(workspaces)

    handler = registry.get_handler("bookmark_note_edit")
    result = await handler(bookmark_id="bk1", note_index=1, content="nope")
    assert "error" in result


@pytest.mark.asyncio
async def test_edit_nonexistent_bookmark(workspaces: Path, registry: ToolRegistry) -> None:
    handler = registry.get_handler("bookmark_note_edit")
    result = await handler(bookmark_id="nope", note_index=1, content="nope")
    assert "error" in result
