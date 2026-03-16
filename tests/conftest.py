"""Shared test fixtures for homeclaw test suite."""

import shutil
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from homeclaw.agent.providers.base import LLMResponse


@pytest.fixture
def dev_workspaces(tmp_path: Path) -> Path:
    """Copy workspaces-dev/ to a temp dir so tests don't mutate fixtures."""
    src = Path(__file__).parent.parent / "workspaces-dev"
    dest = tmp_path / "workspaces"
    shutil.copytree(src, dest)
    return dest


@pytest.fixture
def mock_provider() -> AsyncMock:
    """Mock LLM provider that returns a simple response with no tool calls."""
    provider = AsyncMock()
    provider.complete.return_value = LLMResponse(
        content="I've noted that.",
        tool_calls=[],
        stop_reason="end_turn",
    )
    return provider
