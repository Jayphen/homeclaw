"""Tests for skill mini-app reliability: reset, error boundary, render-log, db schema."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from homeclaw.agent.history import (
    history_path,
    load_history,
    read_history_file,
    reset_history,
)
from homeclaw.api.app import app
from homeclaw.api.deps import set_agent_loop, set_config
from homeclaw.api.routes.skills import (
    _RENDER_LOG,
    read_db_schema,
)
from homeclaw.config import HomeclawConfig

# ---------------------------------------------------------------------------
# reset_history (loop)
# ---------------------------------------------------------------------------


def _write_history(path: Path, last_consolidated: int, n_messages: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"_type": "metadata", "last_consolidated": last_consolidated})]
    for i in range(n_messages):
        role = "user" if i % 2 == 0 else "assistant"
        lines.append(json.dumps({"role": role, "content": f"m{i}"}))
    path.write_text("\n".join(lines) + "\n")


class TestResetHistory:
    def test_clears_live_window_and_preserves_file(self, tmp_path: Path) -> None:
        path = history_path(tmp_path, "alice")
        _write_history(path, last_consolidated=0, n_messages=4)

        cleared = reset_history(tmp_path, "alice")

        assert cleared == 4
        last, msgs = read_history_file(path)
        assert last == 4  # pointer advanced to the end
        assert len(msgs) == 4  # raw messages still on disk (append-only audit)
        assert load_history(tmp_path, "alice") == []  # live context empty

    def test_counts_only_unconsolidated(self, tmp_path: Path) -> None:
        path = history_path(tmp_path, "bob")
        _write_history(path, last_consolidated=2, n_messages=5)
        assert reset_history(tmp_path, "bob") == 3  # 5 - 2 already-consolidated

    def test_idempotent_when_already_fresh(self, tmp_path: Path) -> None:
        path = history_path(tmp_path, "cara")
        _write_history(path, last_consolidated=0, n_messages=2)
        assert reset_history(tmp_path, "cara") == 2
        assert reset_history(tmp_path, "cara") == 0

    def test_no_history_file(self, tmp_path: Path) -> None:
        assert reset_history(tmp_path, "nobody") == 0


# ---------------------------------------------------------------------------
# read_db_schema
# ---------------------------------------------------------------------------


class TestReadDbSchema:
    def test_lists_tables_and_columns(self, tmp_path: Path) -> None:
        db = tmp_path / "s.db"
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT NOT NULL, done INT)")
        conn.commit()
        conn.close()

        tables = read_db_schema(db)

        assert len(tables) == 1
        assert tables[0]["name"] == "items"
        cols = {c["name"]: c for c in tables[0]["columns"]}
        assert set(cols) == {"id", "name", "done"}
        assert cols["id"]["pk"] is True
        assert cols["name"]["notnull"] is True
        assert cols["done"]["pk"] is False

    def test_skips_sqlite_internal_tables(self, tmp_path: Path) -> None:
        db = tmp_path / "s.db"
        conn = sqlite3.connect(db)
        # AUTOINCREMENT makes sqlite create the internal sqlite_sequence table.
        conn.execute("CREATE TABLE a (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        conn.commit()
        conn.close()
        names = {t["name"] for t in read_db_schema(db)}
        assert "a" in names
        assert not any(n.startswith("sqlite_") for n in names)


# ---------------------------------------------------------------------------
# HTTP endpoints (asset injection, render-log, db schema) — open access
# ---------------------------------------------------------------------------


@pytest.fixture()
def skill_ws(tmp_path: Path) -> Path:
    ws = tmp_path / "workspaces"
    skill = ws / "household" / "skills" / "tracker"
    (skill / "assets").mkdir(parents=True)
    (skill / "data").mkdir(parents=True)
    (skill / "assets" / "index.html").write_text(
        "<!doctype html><html><head><title>t</title></head><body><div id='app'></div></body></html>"
    )
    (skill / "assets" / "data.json").write_text('{"ok": true}')
    conn = sqlite3.connect(skill / "data" / "tracker.db")
    conn.execute("CREATE TABLE rows (id INTEGER PRIMARY KEY, label TEXT)")
    conn.commit()
    conn.close()
    return ws


@pytest.fixture()
def client(skill_ws: Path) -> Iterator[TestClient]:
    set_config(HomeclawConfig(workspaces_path=str(skill_ws), web_password=""))
    _RENDER_LOG.clear()
    yield TestClient(app)
    _RENDER_LOG.clear()
    set_agent_loop(None)


class TestRenderLog:
    def test_post_then_read(self, client: TestClient) -> None:
        post = client.post(
            "/api/skills/household/tracker/_render_log",
            json={"message": "Invalid HTML position", "stack": "at mount", "url": "u"},
        )
        assert post.status_code == 200
        got = client.get("/api/skills/household/tracker/_render_log")
        assert got.status_code == 200
        body = got.json()
        assert body["count"] == 1
        assert body["events"][0]["message"] == "Invalid HTML position"
        assert "logged_at" in body["events"][0]

    def test_empty_when_nothing_reported(self, client: TestClient) -> None:
        got = client.get("/api/skills/household/tracker/_render_log")
        assert got.json() == {"events": [], "count": 0}


class TestDbSchemaEndpoint:
    def test_returns_schema(self, client: TestClient) -> None:
        resp = client.get("/api/skills/household/tracker/db/schema")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert body["tables"][0]["name"] == "rows"
        assert {c["name"] for c in body["tables"][0]["columns"]} == {"id", "label"}

    def test_404_when_no_db(self, client: TestClient, skill_ws: Path) -> None:
        (skill_ws / "household" / "skills" / "nodb" / "assets").mkdir(parents=True)
        resp = client.get("/api/skills/household/nodb/db/schema")
        assert resp.status_code == 404


def _make_sandbox_skill(ws: Path, name: str = "jobs", *, with_css: bool = True) -> Path:
    """Create a skill that declares a sandbox (@arrow-js/sandbox) mini-app."""
    skill = ws / "household" / "skills" / name
    (skill / "app").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: jobs\n"
        "ui-app:\n  entry: app/main.ts\n  title: Jobs\n---\nBody.\n"
    )
    (skill / "app" / "main.ts").write_text("export default html`<div>jobs</div>`")
    if with_css:
        (skill / "app" / "main.css").write_text("div { color: red }")
    return skill


class TestAppSourceEndpoint:
    def test_returns_source_map(self, client: TestClient, skill_ws: Path) -> None:
        _make_sandbox_skill(skill_ws)
        resp = client.get("/api/skills/household/jobs/app-source")
        assert resp.status_code == 200
        body = resp.json()
        assert body["title"] == "Jobs"
        assert body["source"]["main.ts"] == "export default html`<div>jobs</div>`"
        assert body["source"]["main.css"] == "div { color: red }"

    def test_omits_css_when_absent(self, client: TestClient, skill_ws: Path) -> None:
        _make_sandbox_skill(skill_ws, name="nocss", with_css=False)
        resp = client.get("/api/skills/household/nocss/app-source")
        assert resp.status_code == 200
        assert set(resp.json()["source"]) == {"main.ts"}

    def test_404_for_iframe_skill(self, client: TestClient) -> None:
        # The fixture's "tracker" skill is a legacy iframe app, not a sandbox one.
        resp = client.get("/api/skills/household/tracker/app-source")
        assert resp.status_code == 404

    def test_404_when_entry_file_missing(self, client: TestClient, skill_ws: Path) -> None:
        skill = _make_sandbox_skill(skill_ws, name="broken")
        (skill / "app" / "main.ts").unlink()
        resp = client.get("/api/skills/household/broken/app-source")
        assert resp.status_code == 404
