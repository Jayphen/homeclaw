"""Tests for built-in note tools (note_get, note_save)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from homeclaw.agent.tools import ToolRegistry, register_builtin_tools


@pytest.fixture
def registry(dev_workspaces: Path) -> ToolRegistry:
    reg = ToolRegistry()
    register_builtin_tools(reg, dev_workspaces)
    return reg


# ── note_get ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_note_get_specific_date(registry: ToolRegistry) -> None:
    handler = registry.get_handler("note_get")
    assert handler is not None
    result = await handler(person="alice", date="2026-03-12")
    assert result["date"] == "2026-03-12"
    assert "call Mum about Easter" in result["content"]


@pytest.mark.asyncio
async def test_note_get_nonexistent_date(registry: ToolRegistry) -> None:
    handler = registry.get_handler("note_get")
    assert handler is not None
    result = await handler(person="alice", date="1999-01-01")
    assert result["content"] == ""
    assert result["date"] == "1999-01-01"


@pytest.mark.asyncio
async def test_note_get_defaults_to_today(registry: ToolRegistry) -> None:
    handler = registry.get_handler("note_get")
    assert handler is not None
    # Patch datetime.now so we control "today"
    fake_now = datetime(2026, 3, 12, 12, 0, 0, tzinfo=timezone.utc)
    with patch("homeclaw.agent.tools.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await handler(person="alice")
    assert result["date"] == "2026-03-12"
    assert "call Mum about Easter" in result["content"]


# ── note_save ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_note_save_creates_new_file(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("note_save")
    assert handler is not None
    fake_now = datetime(2026, 4, 1, 10, 0, 0, tzinfo=timezone.utc)
    with patch("homeclaw.agent.tools.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await handler(person="alice", content="Buy groceries")
    assert result["status"] == "saved"
    # Verify file was created
    path = dev_workspaces / "alice" / "notes" / "2026-04-01.md"
    assert path.exists()
    assert path.read_text() == "Buy groceries"


@pytest.mark.asyncio
async def test_note_save_appends_to_existing(
    registry: ToolRegistry, dev_workspaces: Path
) -> None:
    handler = registry.get_handler("note_save")
    assert handler is not None
    # note_save uses today's date; patch it to 2026-03-12 so it hits the existing file
    fake_now = datetime(2026, 3, 12, 14, 0, 0, tzinfo=timezone.utc)
    with patch("homeclaw.agent.tools.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = await handler(person="alice", content="Also book flights")
    assert result["status"] == "saved"
    path = dev_workspaces / "alice" / "notes" / "2026-03-12.md"
    content = path.read_text()
    # Original content should still be there
    assert "call Mum about Easter" in content
    # New content appended after double newline
    assert "Also book flights" in content
