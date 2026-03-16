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
    assert len(lines) >= 2  # at least one user + one assistant

    for line in lines:
        msg = json.loads(line)
        assert msg["role"] in ("user", "assistant"), (
            f"Only user/assistant messages should be persisted, got {msg['role']}"
        )

    # Verify the content is what we expect
    user_msg = json.loads(lines[-2])
    assistant_msg = json.loads(lines[-1])
    assert user_msg["role"] == "user"
    assert user_msg["content"] == "Remember to buy milk"
    assert assistant_msg["role"] == "assistant"
    assert assistant_msg["content"] == "I've noted that."
