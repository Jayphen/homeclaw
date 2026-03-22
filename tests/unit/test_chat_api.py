"""Tests for the chat API endpoint."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from homeclaw.api.app import app
from homeclaw.api.deps import set_agent_loop, set_config
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


class TestChatHistory:
    def test_empty_history(self, client: TestClient):
        resp = client.get("/api/chat/history")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_user_and_assistant_messages(
        self, client: TestClient, workspaces: Path,
    ):
        person_dir = workspaces / "user"
        person_dir.mkdir(parents=True)
        lines = [
            json.dumps({"role": "user", "content": "hello"}),
            json.dumps({"role": "assistant", "content": "hi there!"}),
            json.dumps({"role": "tool", "content": '{"ok": true}',
                         "tool_call_id": "t1"}),
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
        self, client: TestClient, workspaces: Path,
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
