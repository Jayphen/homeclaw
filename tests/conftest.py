"""Shared test fixtures for homeclaw test suite."""

import hashlib
import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from homeclaw.agent.providers.base import LLMResponse

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "llm_responses"


# ---------------------------------------------------------------------------
# Pytest plugin: --record flag for integration tests
# ---------------------------------------------------------------------------


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--record",
        action="store_true",
        default=False,
        help="Record LLM API responses for replay in integration tests",
    )


@pytest.fixture
def record_mode(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--record"))


@pytest.fixture
def llm_recorder(record_mode: bool) -> "LLMRecorder":
    """Provides an LLM response recorder/replayer for integration tests.

    In record mode (--record): calls the real provider, saves responses.
    In replay mode (default): loads saved responses, no API call.
    """
    return LLMRecorder(fixtures_dir=FIXTURES_DIR, record=record_mode)


class LLMRecorder:
    """Records and replays LLM responses keyed by a hash of the request."""

    def __init__(self, fixtures_dir: Path, record: bool) -> None:
        self._dir = fixtures_dir
        self._record = record
        self._dir.mkdir(parents=True, exist_ok=True)

    def _request_key(self, messages_summary: str, system: str) -> str:
        content = f"{system}|{messages_summary}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _fixture_path(self, name: str, key: str) -> Path:
        return self._dir / f"{name}_{key}.json"

    async def complete(
        self,
        provider: object,
        messages: list,
        tools: list,
        system: str,
        fixture_name: str = "response",
    ) -> LLMResponse:
        """Call provider.complete() with recording/replay.

        In record mode: calls the real provider, saves the response to disk.
        In replay mode: loads the saved response, no API call made.
        """
        msg_summary = "|".join(
            f"{m.role}:{m.content[:100] if isinstance(m.content, str) else 'list'}"
            for m in messages
        )
        key = self._request_key(msg_summary, system)
        path = self._fixture_path(fixture_name, key)

        if not self._record:
            if not path.exists():
                raise FileNotFoundError(
                    f"No recorded response at {path}. "
                    f"Run with --record to capture it first."
                )
            data = json.loads(path.read_text())
            return LLMResponse.model_validate(data["response"])

        # Record mode — call the real provider
        complete_fn = getattr(provider, "complete")
        response: LLMResponse = await complete_fn(
            messages=messages, tools=tools, system=system
        )

        data = {
            "fixture_name": fixture_name,
            "request": {
                "system_preview": system[:200],
                "message_count": len(messages),
                "tool_count": len(tools),
            },
            "response": response.model_dump(mode="json"),
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        return response


# ---------------------------------------------------------------------------
# Standard fixtures
# ---------------------------------------------------------------------------


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
