"""Tests for data export/import round-trip."""

import io
import json
import zipfile
from pathlib import Path

import pytest

from homeclaw.api.routes.data import _build_zip, _restore_zip


@pytest.fixture
def workspaces(tmp_path: Path) -> Path:
    ws = tmp_path / "workspaces"
    ws.mkdir()
    return ws


def _seed_workspace(ws: Path) -> None:
    """Create a realistic workspace with all data types."""
    # Household shared data
    household = ws / "household"
    (household / "contacts").mkdir(parents=True)
    (household / "bookmarks").mkdir(parents=True)

    (household / "memory.json").write_text(
        json.dumps({"facts": ["We have a cat named Mochi"], "preferences": {}})
    )
    (household / "contacts" / "james-ko.json").write_text(
        json.dumps({"id": "james-ko", "name": "James Ko", "relationship": "friend"})
    )
    (household / "bookmarks" / "bookmarks.json").write_text(
        json.dumps([{"id": "b1", "title": "Pizza Place", "category": "place"}])
    )
    (household / "ROUTINES.md").write_text("## Morning brief\n**Schedule**: Every day at 7:30am\n")
    (household / "telegram_users.json").write_text(json.dumps({"12345": "alice"}))

    # Per-person data
    alice = ws / "alice"
    (alice / "notes").mkdir(parents=True)
    (alice / "memory.json").write_text(
        json.dumps({"facts": ["Works at the agency"], "preferences": {"tone": "casual"}})
    )
    (alice / "reminders.json").write_text(
        json.dumps([{"id": "r1", "person": "alice", "note": "Buy cat food", "done": False}])
    )
    (alice / "notes" / "2026-03-15.md").write_text("# Saturday\nWent to the park.")
    (alice / "notes" / "reminders.md").write_text("- [ ] 2026-03-21: Buy cat food\n")
    (alice / "history.jsonl").write_text(
        '{"role":"user","content":"hello"}\n{"role":"assistant","content":"hi"}\n'
    )

    # Things that should NOT be exported
    (ws / "config.json").write_text(json.dumps({"openai_api_key": "sk-secret"}))
    (ws / "cost_log.jsonl").write_text('{"ts":"2026-03-15"}\n')
    index_dir = ws / ".index"
    index_dir.mkdir()
    (index_dir / "milvus.db").write_text("binary-data")


def test_export_contains_expected_files(workspaces: Path) -> None:
    _seed_workspace(workspaces)
    buf = _build_zip(workspaces)
    with zipfile.ZipFile(buf) as zf:
        names = set(zf.namelist())

    assert "metadata.json" in names
    assert "household/memory.json" in names
    assert "household/contacts/james-ko.json" in names
    assert "household/bookmarks/bookmarks.json" in names
    assert "household/ROUTINES.md" in names
    assert "household/telegram_users.json" in names
    assert "alice/memory.json" in names
    assert "alice/reminders.json" in names
    assert "alice/notes/2026-03-15.md" in names
    assert "alice/notes/reminders.md" in names
    assert "alice/history.jsonl" in names


def test_export_excludes_secrets_and_derived(workspaces: Path) -> None:
    _seed_workspace(workspaces)
    buf = _build_zip(workspaces)
    with zipfile.ZipFile(buf) as zf:
        names = set(zf.namelist())

    assert "config.json" not in names
    assert "cost_log.jsonl" not in names
    assert ".index/milvus.db" not in names


def test_export_metadata(workspaces: Path) -> None:
    _seed_workspace(workspaces)
    buf = _build_zip(workspaces)
    with zipfile.ZipFile(buf) as zf:
        meta = json.loads(zf.read("metadata.json"))

    assert meta["version"] == "1"
    assert "exported_at" in meta
    assert "alice" in meta["members"]


def test_import_round_trip(workspaces: Path) -> None:
    """Export from one workspace, import into a fresh one, verify contents match."""
    _seed_workspace(workspaces)
    buf = _build_zip(workspaces)

    # Import into a fresh workspace
    fresh = workspaces.parent / "fresh"
    fresh.mkdir()

    with zipfile.ZipFile(buf) as zf:
        result = _restore_zip(fresh, zf)

    assert result["files_written"] > 0
    assert "alice" in result["members_imported"]

    # Verify key files round-tripped
    alice_mem = json.loads((fresh / "alice" / "memory.json").read_text())
    assert "Works at the agency" in alice_mem["facts"]

    contact = json.loads((fresh / "household" / "contacts" / "james-ko.json").read_text())
    assert contact["name"] == "James Ko"

    note = (fresh / "alice" / "notes" / "2026-03-15.md").read_text()
    assert "park" in note

    routines = (fresh / "household" / "ROUTINES.md").read_text()
    assert "Morning brief" in routines


def test_import_rejects_path_traversal(workspaces: Path) -> None:
    """Paths with .. should be skipped."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"version": "1"}))
        zf.writestr("../escape.txt", "pwned")

    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        result = _restore_zip(workspaces, zf)

    assert result["files_skipped"] >= 1
    assert not (workspaces.parent / "escape.txt").exists()
