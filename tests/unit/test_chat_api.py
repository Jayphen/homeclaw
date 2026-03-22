"""Tests for the chat API endpoint."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from homeclaw.api.app import app
from homeclaw.api.deps import set_agent_loop, set_config
from homeclaw.config import HomeclawConfig


@pytest.fixture()
def _open_access(tmp_path):
    """Set up open-access config (no passwords)."""
    ws = tmp_path / "workspaces"
    (ws / "household").mkdir(parents=True)
    config = HomeclawConfig(workspaces_path=str(ws), web_password="")
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
