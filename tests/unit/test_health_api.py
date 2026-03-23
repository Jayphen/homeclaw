"""Tests for the health check endpoint."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from homeclaw.api.app import app
from homeclaw.api.deps import set_agent_loop, set_config
from homeclaw.config import HomeclawConfig


@pytest.fixture()
def workspaces(tmp_path: Path) -> Path:
    ws = tmp_path / "workspaces"
    (ws / "household").mkdir(parents=True)
    return ws


@pytest.fixture()
def _open_access(workspaces: Path) -> None:
    config = HomeclawConfig(workspaces_path=str(workspaces), web_password="")
    set_config(config)
    yield  # type: ignore[misc]
    set_agent_loop(None)


@pytest.fixture()
def client(_open_access: None) -> TestClient:
    return TestClient(app)


class TestHealthEndpoint:
    def test_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "uptime_seconds" in data
        assert "process" in data
        assert "rss_mb" in data["process"]

    def test_no_auth_required(self, workspaces: Path) -> None:
        """Health endpoint works even with passwords configured."""
        config = HomeclawConfig(
            workspaces_path=str(workspaces), web_password="secret"
        )
        set_config(config)
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_semantic_memory_disabled_by_default(self, client: TestClient) -> None:
        data = client.get("/api/health").json()
        assert data["semantic_memory"]["enabled"] is False

    def test_index_size_when_present(
        self, client: TestClient, workspaces: Path,
    ) -> None:
        index_dir = workspaces / ".index"
        index_dir.mkdir()
        db_file = index_dir / "milvus.db"
        db_file.write_bytes(b"\x00" * 2048)

        data = client.get("/api/health").json()
        assert "index_size_mb" in data["semantic_memory"]
        assert data["semantic_memory"]["index_size_mb"] >= 0
