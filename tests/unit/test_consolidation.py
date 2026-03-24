"""Tests for homeclaw/agent/consolidation.py — context consolidation."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from homeclaw.agent.consolidation import consolidate_chunk, save_consolidated_memories
from homeclaw.agent.providers.base import LLMResponse, Message


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_messages(pairs: list[tuple[str, str]]) -> list[Message]:
    """Create alternating user/assistant message pairs."""
    messages: list[Message] = []
    for user_text, assistant_text in pairs:
        messages.append(Message(role="user", content=user_text))
        messages.append(Message(role="assistant", content=assistant_text))
    return messages


def _mock_provider(response_content: str) -> AsyncMock:
    """Create a mock LLM provider that returns the given content."""
    provider = AsyncMock()
    provider.complete.return_value = LLMResponse(
        content=response_content,
        tool_calls=[],
        stop_reason="end_turn",
    )
    return provider


# ---------------------------------------------------------------------------
# consolidate_chunk
# ---------------------------------------------------------------------------


class TestConsolidateChunk:
    """Tests for consolidate_chunk."""

    @pytest.mark.asyncio
    async def test_valid_json_response(self) -> None:
        """Mock LLM returns valid JSON → parsed correctly."""
        response_json = json.dumps({
            "memory_entries": [
                {"topic": "food", "content": "Alice likes pasta"},
                {"topic": "health", "content": "Bob has a peanut allergy"},
            ],
            "summary": "Discussed food preferences and allergies.",
        })
        provider = _mock_provider(response_json)

        messages = _make_messages([
            ("I love pasta", "Noted! Pasta fan."),
            ("Bob can't eat peanuts", "Good to know about the allergy."),
        ])

        result = await consolidate_chunk(messages, "alice", provider)

        assert "memory_entries" in result
        assert len(result["memory_entries"]) == 2
        assert result["memory_entries"][0]["topic"] == "food"
        assert result["summary"] == "Discussed food preferences and allergies."

        # Verify the provider was called
        provider.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self) -> None:
        """Mock LLM returns invalid JSON → error dict returned for retry."""
        provider = _mock_provider("This is not valid JSON at all")

        messages = _make_messages([("hello", "hi there")])

        result = await consolidate_chunk(messages, "alice", provider)

        assert "error" in result
        assert "Invalid JSON" in result["error"]

    @pytest.mark.asyncio
    async def test_llm_raises_exception(self) -> None:
        """Mock LLM raises an exception → error dict returned."""
        provider = AsyncMock()
        provider.complete.side_effect = RuntimeError("API timeout")

        messages = _make_messages([("hello", "hi")])

        result = await consolidate_chunk(messages, "alice", provider)

        assert "error" in result
        assert "API timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_non_dict_json_returns_error(self) -> None:
        """Mock LLM returns valid JSON but not a dict → error for retry."""
        provider = _mock_provider(json.dumps(["not", "a", "dict"]))

        messages = _make_messages([("test", "response")])

        result = await consolidate_chunk(messages, "alice", provider)

        assert "error" in result

    @pytest.mark.asyncio
    async def test_empty_messages_list(self) -> None:
        """Empty message list still calls the provider."""
        response_json = json.dumps({
            "memory_entries": [],
            "summary": "No conversation to summarize.",
        })
        provider = _mock_provider(response_json)

        result = await consolidate_chunk([], "alice", provider)

        assert result["memory_entries"] == []
        assert result["summary"] == "No conversation to summarize."
        provider.complete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_provider_called_with_correct_args(self) -> None:
        """Verify the provider receives the formatted conversation."""
        response_json = json.dumps({"memory_entries": [], "summary": "ok"})
        provider = _mock_provider(response_json)

        messages = [
            Message(role="user", content="What's for dinner?"),
            Message(role="assistant", content="How about tacos?"),
        ]

        await consolidate_chunk(messages, "alice", provider)

        call_args = provider.complete.call_args
        sent_messages = call_args.kwargs["messages"]
        assert len(sent_messages) == 1
        assert sent_messages[0].role == "user"
        assert "What's for dinner?" in sent_messages[0].content
        assert "tacos" in sent_messages[0].content
        assert call_args.kwargs["system"]  # system prompt is non-empty


# ---------------------------------------------------------------------------
# save_consolidated_memories
# ---------------------------------------------------------------------------


class TestSaveConsolidatedMemories:
    """Tests for save_consolidated_memories."""

    @pytest.mark.asyncio
    async def test_saves_entries_to_memory_topics(self, tmp_path: Path) -> None:
        """Entries are written to the correct memory topic files."""
        entries = [
            {"topic": "food", "content": "Alice likes pasta"},
            {"topic": "health", "content": "Bob has a peanut allergy"},
        ]

        saved = await save_consolidated_memories(entries, "alice", tmp_path)

        assert saved == 2

        # Check files were created
        food_path = tmp_path / "alice" / "memory" / "food.md"
        assert food_path.is_file()
        assert "Alice likes pasta" in food_path.read_text()

        health_path = tmp_path / "alice" / "memory" / "health.md"
        assert health_path.is_file()
        assert "Bob has a peanut allergy" in health_path.read_text()

    @pytest.mark.asyncio
    async def test_skips_empty_content(self, tmp_path: Path) -> None:
        """Entries with empty content are skipped."""
        entries = [
            {"topic": "food", "content": ""},
            {"topic": "health", "content": "Valid entry"},
        ]

        saved = await save_consolidated_memories(entries, "alice", tmp_path)

        assert saved == 1
        # Only health.md should exist
        health_path = tmp_path / "alice" / "memory" / "health.md"
        assert health_path.is_file()

    @pytest.mark.asyncio
    async def test_empty_entries_list(self, tmp_path: Path) -> None:
        """Empty list of entries → 0 saved."""
        saved = await save_consolidated_memories([], "alice", tmp_path)
        assert saved == 0

    @pytest.mark.asyncio
    async def test_default_topic(self, tmp_path: Path) -> None:
        """Entry with missing topic key uses 'general' as default."""
        entries = [{"content": "Some useful fact"}]

        saved = await save_consolidated_memories(entries, "alice", tmp_path)

        assert saved == 1
        general_path = tmp_path / "alice" / "memory" / "general.md"
        assert general_path.is_file()
        assert "Some useful fact" in general_path.read_text()

    @pytest.mark.asyncio
    async def test_appends_to_existing_topic(self, tmp_path: Path) -> None:
        """Multiple entries for the same topic append to the same file."""
        entries = [
            {"topic": "food", "content": "Likes pasta"},
            {"topic": "food", "content": "Hates broccoli"},
        ]

        saved = await save_consolidated_memories(entries, "alice", tmp_path)

        assert saved == 2
        food_path = tmp_path / "alice" / "memory" / "food.md"
        content = food_path.read_text()
        assert "Likes pasta" in content
        assert "Hates broccoli" in content
