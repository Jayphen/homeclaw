"""Integration tests for the agent loop.

These tests use mock providers for now. When recorded LLM responses are
available, swap ``mock_provider`` for ``llm_recorder`` — see inline comments.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeclaw.agent.loop import AgentLoop
from homeclaw.agent.providers.base import LLMResponse, ToolCall
from homeclaw.agent.tools import ToolRegistry, register_builtin_tools


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_loop(
    provider: AsyncMock,
    workspaces: Path,
    on_tool_call: MagicMock | None = None,
) -> AgentLoop:
    registry = ToolRegistry()
    register_builtin_tools(registry, workspaces)
    return AgentLoop(
        provider=provider,
        registry=registry,
        workspaces=workspaces,
        on_tool_call=on_tool_call,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_response(mock_provider: AsyncMock, dev_workspaces: Path) -> None:
    """Send a plain message and get a string response back."""
    # To use recorded responses later:
    #   loop = _make_loop(llm_recorder.wrap(real_provider), dev_workspaces)
    loop = _make_loop(mock_provider, dev_workspaces)

    result = await loop.run("Hello, what's for dinner?", person="alice")

    assert isinstance(result, str)
    assert result == "I've noted that."
    mock_provider.complete.assert_awaited_once()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tool_call_response(mock_provider: AsyncMock, dev_workspaces: Path) -> None:
    """Verify the loop dispatches a tool call and makes a follow-up LLM call."""
    # First call: LLM requests the contact_list tool
    # Second call: LLM returns a final text response
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="tc1", name="contact_list", arguments={})],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Here are your contacts.",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    loop = _make_loop(mock_provider, dev_workspaces)
    result = await loop.run("Who's in my contacts?", person="alice")

    assert result == "Here are your contacts."
    assert mock_provider.complete.await_count == 2


@pytest.mark.integration
@pytest.mark.asyncio
async def test_on_tool_call_callback(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """Verify the on_tool_call callback fires with the correct name and args."""
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[ToolCall(id="tc1", name="contact_list", arguments={})],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Done.",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    callback = MagicMock()
    loop = _make_loop(mock_provider, dev_workspaces, on_tool_call=callback)

    await loop.run("List contacts", person="alice")

    callback.assert_called_once_with("contact_list", {})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_history_persisted(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """After run(), history.jsonl should contain user and assistant turns only."""
    loop = _make_loop(mock_provider, dev_workspaces)

    await loop.run("Remember to buy milk", person="alice")

    history_path = dev_workspaces / "alice" / "history.jsonl"
    assert history_path.exists(), "history.jsonl was not written"

    lines = [
        line for line in history_path.read_text().strip().splitlines() if line
    ]
    # First line is metadata, rest are messages
    assert len(lines) >= 3  # metadata + at least one user + one assistant

    metadata = json.loads(lines[0])
    assert metadata.get("_type") == "metadata"

    msg_lines = lines[1:]
    for line in msg_lines:
        msg = json.loads(line)
        assert msg["role"] in ("user", "assistant"), (
            f"Only user/assistant messages should be persisted, got {msg['role']}"
        )

    # Verify the content is what we expect
    user_msg = json.loads(msg_lines[-2])
    assistant_msg = json.loads(msg_lines[-1])
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "Remember to buy milk"
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == "I've noted that."


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dm_enforces_person_on_note_save(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """In a DM (no channel), note_save should force person to the authenticated caller."""
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="note_save",
                    # LLM tries to write to "bob" but caller is "alice"
                    arguments={"person": "bob", "content": "Test note"},
                ),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Noted!",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    loop = _make_loop(mock_provider, dev_workspaces)
    await loop.run("Save a note", person="alice")

    # Note should be saved under alice, not bob
    alice_notes = dev_workspaces / "alice" / "notes"
    bob_notes = dev_workspaces / "bob" / "notes"
    assert any(alice_notes.glob("*.md")), "Note should be saved under alice"
    assert not any(bob_notes.glob("*.md")), "Note should NOT be saved under bob"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_group_chat_allows_cross_person_notes(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """In a group chat (channel set), note_save should allow writing to any person."""
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="note_save",
                    arguments={"person": "bob", "content": "Group note for bob"},
                ),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Done!",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    loop = _make_loop(mock_provider, dev_workspaces)
    await loop.run("[alice] Save a note for bob", person="alice", channel="group-123")

    # In group chat, bob's workspace should get the note
    bob_notes = dev_workspaces / "bob" / "notes"
    assert any(bob_notes.glob("*.md")), "Group chat should allow writing to bob"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dm_enforces_person_on_memory_read(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """In a DM, memory_read should force person to the authenticated caller."""
    # Seed bob's memory so there's something to read
    bob_mem = dev_workspaces / "bob" / "memory"
    bob_mem.mkdir(parents=True, exist_ok=True)
    (bob_mem / "secrets.md").write_text("# secrets\n\n- Bob's secret info\n")

    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="memory_read",
                    # LLM tries to read bob's memory but caller is alice
                    arguments={"person": "bob", "topic": "secrets"},
                ),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Nothing found.",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    callback = MagicMock()
    loop = _make_loop(mock_provider, dev_workspaces, on_tool_call=callback)
    await loop.run("Read bob's secrets", person="alice")

    # The tool should have been called with person="alice", not "bob"
    callback.assert_called_once_with("memory_read", {"person": "alice", "topic": "secrets"})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dm_enforces_person_on_note_get(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """In a DM, note_get should force person to the authenticated caller."""
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="note_get",
                    arguments={"person": "bob"},
                ),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="No notes.",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    callback = MagicMock()
    loop = _make_loop(mock_provider, dev_workspaces, on_tool_call=callback)
    await loop.run("Show me bob's notes", person="alice")

    callback.assert_called_once_with("note_get", {"person": "alice"})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_dm_allows_household_memory_read(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """In a DM, memory_read for 'household' should be allowed through."""
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="memory_read",
                    arguments={"person": "household"},
                ),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Household topics listed.",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    callback = MagicMock()
    loop = _make_loop(mock_provider, dev_workspaces, on_tool_call=callback)
    await loop.run("What does the household know?", person="alice")

    # "household" should pass through, not be overridden to "alice"
    callback.assert_called_once_with("memory_read", {"person": "household"})


@pytest.mark.integration
@pytest.mark.asyncio
async def test_group_chat_allows_cross_person_reads(
    mock_provider: AsyncMock, dev_workspaces: Path
) -> None:
    """In a group chat, read tools should allow reading any person."""
    mock_provider.complete.side_effect = [
        LLMResponse(
            content="",
            tool_calls=[
                ToolCall(
                    id="tc1",
                    name="memory_read",
                    arguments={"person": "bob"},
                ),
            ],
            stop_reason="tool_use",
        ),
        LLMResponse(
            content="Bob's memory.",
            tool_calls=[],
            stop_reason="end_turn",
        ),
    ]

    callback = MagicMock()
    loop = _make_loop(mock_provider, dev_workspaces, on_tool_call=callback)
    await loop.run("[alice] What does bob remember?", person="alice", channel="group-123")

    # In group chat, cross-person reads should be allowed
    callback.assert_called_once_with("memory_read", {"person": "bob"})
