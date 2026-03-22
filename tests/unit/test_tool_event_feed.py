"""Tests for tool use event logging and feed reader."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from homeclaw.agent.loop import _FEED_WORTHY_TOOLS, _log_tool_event
from homeclaw.agent.providers.base import LLMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_provider(summary: str) -> AsyncMock:
    provider = AsyncMock()
    provider.complete.return_value = LLMResponse(
        content=summary,
        tool_calls=[],
        stop_reason="end_turn",
    )
    return provider


def _read_events(workspaces: Path) -> list[dict]:
    path = workspaces / "household" / "logs" / "tool_use.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# _log_tool_event
# ---------------------------------------------------------------------------


class TestLogToolEvent:
    """Tests for the async tool event logger."""

    @pytest.mark.asyncio
    async def test_writes_event_with_llm_summary(self, tmp_path: Path) -> None:
        provider = _mock_provider("Saved a food memory for Alice")
        await _log_tool_event(
            tmp_path, "memory_save",
            {"topic": "food", "person": "alice", "content": "likes pasta"},
            "alice", provider,
        )
        events = _read_events(tmp_path)
        assert len(events) == 1
        assert events[0]["summary"] == "Saved a food memory for Alice"
        assert events[0]["tool"] == "memory_save"
        assert events[0]["person"] == "alice"
        provider.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fallback_when_provider_is_none(self, tmp_path: Path) -> None:
        await _log_tool_event(
            tmp_path, "memory_save",
            {"topic": "food", "person": "alice"},
            "alice", None,
        )
        events = _read_events(tmp_path)
        assert len(events) == 1
        assert "memory save" in events[0]["summary"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_llm_error(self, tmp_path: Path) -> None:
        provider = AsyncMock()
        provider.complete.side_effect = RuntimeError("API down")
        await _log_tool_event(
            tmp_path, "bookmark_save",
            {"title": "Cool site", "url": "https://example.com"},
            "bob", provider,
        )
        events = _read_events(tmp_path)
        assert len(events) == 1
        assert "bob" in events[0]["summary"].lower()

    @pytest.mark.asyncio
    async def test_fallback_on_short_llm_response(self, tmp_path: Path) -> None:
        """LLM returns too-short text → fallback used."""
        provider = _mock_provider("OK")
        await _log_tool_event(
            tmp_path, "note_save", {"person": "carol", "date": "today"},
            "carol", provider,
        )
        events = _read_events(tmp_path)
        assert len(events) == 1
        # "OK" is < 5 chars, so fallback kicks in
        assert "carol" in events[0]["summary"].lower()

    @pytest.mark.asyncio
    async def test_skips_non_feed_worthy_tools(self, tmp_path: Path) -> None:
        provider = _mock_provider("Listed contacts")
        await _log_tool_event(
            tmp_path, "contact_list", {}, "alice", provider,
        )
        events = _read_events(tmp_path)
        assert len(events) == 0
        provider.complete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_args_truncated(self, tmp_path: Path) -> None:
        provider = _mock_provider("Saved a memory for Alice")
        long_content = "x" * 500
        await _log_tool_event(
            tmp_path, "memory_save",
            {"topic": "food", "content": long_content, "person": "alice"},
            "alice", provider,
        )
        events = _read_events(tmp_path)
        assert len(events) == 1
        assert len(events[0]["args"]["content"]) <= 100

    @pytest.mark.asyncio
    async def test_multiple_events_append(self, tmp_path: Path) -> None:
        provider = _mock_provider("Did something")
        await _log_tool_event(
            tmp_path, "memory_save", {"topic": "a"}, "alice", provider,
        )
        await _log_tool_event(
            tmp_path, "note_save", {"person": "bob", "date": "today"}, "bob", provider,
        )
        events = _read_events(tmp_path)
        assert len(events) == 2

    def test_feed_worthy_set_has_only_write_tools(self) -> None:
        """Sanity check: no read-only tools in the set."""
        read_tools = {
            "contact_list", "contact_get", "memory_read", "note_get",
            "reminder_list", "bookmark_list", "bookmark_search",
            "bookmark_categories", "routine_list", "settings_get",
            "log_read", "channel_preference_get", "skill_list",
        }
        assert _FEED_WORTHY_TOOLS.isdisjoint(read_tools)


# ---------------------------------------------------------------------------
# _tool_use_events (feed reader)
# ---------------------------------------------------------------------------


class TestToolUseEvents:
    """Tests for the feed API's tool_use event reader."""

    def _write_events(self, workspaces: Path, entries: list[dict]) -> None:
        log_dir = workspaces / "household" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "tool_use.jsonl", "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")

    def test_reads_recent_events(self, tmp_path: Path) -> None:
        from homeclaw.api.routes.feed import _tool_use_events

        now = datetime.now(UTC)
        self._write_events(tmp_path, [
            {"ts": now.isoformat(), "tool": "memory_save", "summary": "Saved food memory", "person": "alice"},
            {"ts": (now - timedelta(hours=1)).isoformat(), "tool": "note_save", "summary": "Updated note", "person": "bob"},
        ])
        events = _tool_use_events(tmp_path, now - timedelta(hours=2))
        assert len(events) == 2
        assert all(e["type"] == "tool_use" for e in events)
        assert events[0]["summary"] == "Saved food memory"

    def test_filters_old_events(self, tmp_path: Path) -> None:
        from homeclaw.api.routes.feed import _tool_use_events

        now = datetime.now(UTC)
        self._write_events(tmp_path, [
            {"ts": now.isoformat(), "tool": "memory_save", "summary": "Recent", "person": "alice"},
            {"ts": (now - timedelta(days=10)).isoformat(), "tool": "note_save", "summary": "Old", "person": "bob"},
        ])
        events = _tool_use_events(tmp_path, now - timedelta(days=3))
        assert len(events) == 1
        assert events[0]["summary"] == "Recent"

    def test_returns_empty_when_no_file(self, tmp_path: Path) -> None:
        from homeclaw.api.routes.feed import _tool_use_events

        events = _tool_use_events(tmp_path, datetime.now(UTC) - timedelta(days=1))
        assert events == []

    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        from homeclaw.api.routes.feed import _tool_use_events

        log_dir = tmp_path / "household" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(UTC)
        with open(log_dir / "tool_use.jsonl", "w") as f:
            f.write("not json\n")
            f.write(json.dumps({"ts": now.isoformat(), "tool": "memory_save", "summary": "OK", "person": "a"}) + "\n")
            f.write("\n")

        events = _tool_use_events(tmp_path, now - timedelta(hours=1))
        assert len(events) == 1
