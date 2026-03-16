"""Integration tests for the REPL channel.

Tests mock builtins.input and the AgentLoop to verify REPL behaviour
without requiring a real LLM provider.
"""

from unittest.mock import AsyncMock, patch

import pytest

from homeclaw.channel.repl import run_repl


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repl_exit() -> None:
    """Typing 'exit' should cause run_repl to return without error."""
    mock_loop = AsyncMock()

    with patch("builtins.input", side_effect=["exit"]):
        await run_repl(person="alice", loop=mock_loop)

    # The loop's run() should never have been called — the user exited immediately
    mock_loop.run.assert_not_awaited()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repl_processes_message() -> None:
    """A message followed by 'exit' should invoke loop.run() with the message."""
    mock_loop = AsyncMock()
    mock_loop.run.return_value = "Got it."

    with patch("builtins.input", side_effect=["hello there", "exit"]):
        await run_repl(person="alice", loop=mock_loop)

    mock_loop.run.assert_awaited_once_with("hello there", "alice")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_repl_multiline() -> None:
    r"""Lines ending with '\\' should be joined as multiline input."""
    mock_loop = AsyncMock()
    mock_loop.run.return_value = "Noted."

    # "hello \" triggers continuation; "world" completes it; "exit" quits.
    with patch("builtins.input", side_effect=["hello\\", "world", "exit"]):
        await run_repl(person="alice", loop=mock_loop)

    mock_loop.run.assert_awaited_once_with("hello\nworld", "alice")
