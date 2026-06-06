"""Tests for the chat API endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from homeclaw.agent.runtime_state import (
    ConsolidationEvent,
    InMemoryRuntimeObservability,
    now_utc,
)
from homeclaw.api.app import app
from homeclaw.api.deps import set_agent_loop, set_config
from homeclaw.api.routes.chat import _latest_consolidation_debug
from homeclaw.config import HomeclawConfig


@pytest.fixture()
def workspaces(tmp_path) -> Path:
    ws = tmp_path / "workspaces"
    (ws / "household").mkdir(parents=True)
    return ws


@pytest.fixture()
def _open_access(workspaces):
    """Set up open-access config (no passwords)."""
    config = HomeclawConfig(workspaces_path=str(workspaces), web_password="")
    set_config(config)
    yield
    set_agent_loop(None)


@pytest.fixture()
def client(_open_access: Any) -> TestClient:
    return TestClient(app)


class TestChatEndpoint:
    def test_no_agent_loop_returns_503(self, client: TestClient):
        set_agent_loop(None)
        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        assert resp.status_code == 503

    def test_no_user_message_returns_400(self, client: TestClient):
        set_agent_loop(object())
        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "assistant", "content": "hi"}]},
        )
        assert resp.status_code == 400

    def test_empty_message_returns_400(self, client: TestClient):
        set_agent_loop(object())
        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": ""}]},
        )
        assert resp.status_code == 400

    def test_streams_response(self, client: TestClient):
        mock_loop = AsyncMock()
        mock_loop.run.return_value = "Hello from homeclaw!"
        set_agent_loop(mock_loop)

        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200
        assert "Hello from homeclaw!" in resp.text
        mock_loop.run.assert_called_once()
        assert mock_loop.run.call_args[0][0] == "hi"
        assert mock_loop.run.call_args[0][1] == "user"

    def test_extracts_text_from_parts(self, client: TestClient):
        mock_loop = AsyncMock()
        mock_loop.run.return_value = "Got it!"
        set_agent_loop(mock_loop)

        resp = client.post(
            "/api/chat",
            json={
                "messages": [
                    {
                        "role": "user",
                        "parts": [{"type": "text", "text": "hello parts"}],
                    },
                ],
            },
        )
        assert resp.status_code == 200
        assert "Got it!" in resp.text
        assert mock_loop.run.call_args[0][0] == "hello parts"

    def test_handles_agent_error(self, client: TestClient):
        mock_loop = AsyncMock()
        mock_loop.run.side_effect = RuntimeError("LLM failed")
        set_agent_loop(mock_loop)

        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert resp.status_code == 200
        assert "something went wrong" in resp.text.lower()

    def test_new_command_resets_without_calling_llm(self, client: TestClient):
        mock_loop = AsyncMock()
        mock_loop.reset_conversation.return_value = 12
        set_agent_loop(mock_loop)

        resp = client.post(
            "/api/chat",
            json={"messages": [{"role": "user", "content": "/new"}]},
        )

        assert resp.status_code == 200
        assert "Chat cleared" in resp.text
        mock_loop.reset_conversation.assert_awaited_once_with("user", channel=None)
        mock_loop.run.assert_not_called()

    def test_new_command_resets_household_channel(self, client: TestClient):
        mock_loop = AsyncMock()
        mock_loop.reset_conversation.return_value = 3
        set_agent_loop(mock_loop)

        resp = client.post(
            "/api/chat",
            json={
                "channel": "web-household",
                "messages": [{"role": "user", "content": "/new"}],
            },
        )

        assert resp.status_code == 200
        mock_loop.reset_conversation.assert_awaited_once_with(
            "user",
            channel="web-household",
        )
        mock_loop.run.assert_not_called()

    def test_reset_endpoint_resets_without_llm(self, client: TestClient):
        mock_loop = AsyncMock()
        mock_loop.reset_conversation.return_value = 5
        set_agent_loop(mock_loop)

        resp = client.post("/api/chat/reset", json={})

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "cleared": 5}
        mock_loop.reset_conversation.assert_awaited_once_with("user", channel=None)
        mock_loop.run.assert_not_called()

    def test_reset_endpoint_rejects_invalid_channel(self, client: TestClient):
        mock_loop = AsyncMock()
        set_agent_loop(mock_loop)

        resp = client.post("/api/chat/reset", json={"channel": "../alice"})

        assert resp.status_code == 400
        mock_loop.reset_conversation.assert_not_called()


def test_latest_consolidation_debug_filters_to_history_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = InMemoryRuntimeObservability()
    runtime.record_consolidation(
        ConsolidationEvent(
            history_key="other",
            person="alice",
            status="succeeded",
            reason="ok",
            history_tokens=100,
            recorded_at=now_utc(),
        )
    )
    runtime.record_consolidation(
        ConsolidationEvent(
            history_key="web-household",
            person="alice",
            status="succeeded",
            reason="summary_only",
            unconsolidated_messages=12,
            history_tokens=2400,
            chunk_size=20,
            saved_entries=0,
            model="test-model",
            recorded_at=now_utc(),
        )
    )
    monkeypatch.setattr(
        "homeclaw.api.routes.chat.get_runtime_observability",
        lambda: runtime,
    )

    debug = _latest_consolidation_debug("web-household")

    assert debug is not None
    assert debug["reason"] == "summary_only"
    assert debug["history_tokens"] == 2400
    assert debug["unconsolidated_messages"] == 12
    assert debug["model"] == "test-model"


class TestChatHistory:
    def test_empty_history(self, client: TestClient):
        resp = client.get("/api/chat/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_user_and_assistant_messages(
        self,
        client: TestClient,
        workspaces: Path,
    ):
        person_dir = workspaces / "user"
        person_dir.mkdir(parents=True)
        lines = [
            json.dumps({"role": "user", "content": "hello"}),
            json.dumps({"role": "assistant", "content": "hi there!"}),
            json.dumps({"role": "tool", "content": '{"ok": true}', "tool_call_id": "t1"}),
            json.dumps({"role": "user", "content": "bye"}),
            json.dumps({"role": "assistant", "content": "see ya"}),
        ]
        (person_dir / "history.jsonl").write_text("\n".join(lines))

        resp = client.get("/api/chat/history")
        data = resp.json()
        assert len(data) == 4
        assert data[0] == {"role": "user", "content": "hello"}
        assert data[1] == {"role": "assistant", "content": "hi there!"}
        assert data[2] == {"role": "user", "content": "bye"}
        assert data[3] == {"role": "assistant", "content": "see ya"}

    def test_skips_metadata_lines(
        self,
        client: TestClient,
        workspaces: Path,
    ):
        person_dir = workspaces / "user"
        person_dir.mkdir(parents=True)
        lines = [
            json.dumps({"_type": "metadata", "last_consolidated": 0}),
            json.dumps({"role": "user", "content": "test"}),
            json.dumps({"role": "assistant", "content": "reply"}),
        ]
        (person_dir / "history.jsonl").write_text("\n".join(lines))

        resp = client.get("/api/chat/history")
        data = resp.json()
        assert len(data) == 2

    def test_strips_additional_context_from_visible_history(
        self,
        client: TestClient,
        workspaces: Path,
    ):
        person_dir = workspaces / "user"
        person_dir.mkdir(parents=True)
        content = "hello\n\n<additional_context>\n<channel>\nweb\n</channel>\n</additional_context>"
        (person_dir / "history.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"role": "user", "content": content}),
                    json.dumps({"role": "assistant", "content": "hi"}),
                ]
            )
        )

        resp = client.get("/api/chat/history")
        data = resp.json()
        assert data[0] == {"role": "user", "content": "hello"}
