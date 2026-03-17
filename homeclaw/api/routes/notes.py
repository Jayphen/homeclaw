"""Notes API routes — per-person, per-date markdown notes."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from homeclaw.api.deps import AuthDep, get_config, list_member_workspaces

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", dependencies=[AuthDep])
async def notes_index() -> list[dict[str, Any]]:
    """List all notes across all members, newest first."""
    workspaces = get_config().workspaces.resolve()
    members = list_member_workspaces(workspaces)
    notes: list[dict[str, Any]] = []

    for person in members:
        notes_dir = workspaces / person / "notes"
        if not notes_dir.is_dir():
            continue
        for f in notes_dir.iterdir():
            if not f.name.endswith(".md") or f.name == "reminders.md":
                continue
            date_str = f.stem
            try:
                date.fromisoformat(date_str)
            except ValueError:
                continue
            content = f.read_text().strip()
            mtime = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            notes.append({
                "person": person,
                "date": date_str,
                "preview": content[:200],
                "updated_at": mtime,
            })

    notes.sort(key=lambda n: n["date"], reverse=True)
    return notes


@router.get("/{person}", dependencies=[AuthDep])
async def notes_by_person(person: str) -> list[dict[str, Any]]:
    """List all notes for a specific person, newest first."""
    workspaces = get_config().workspaces.resolve()
    notes_dir = workspaces / person / "notes"
    if not notes_dir.is_dir():
        return []

    notes: list[dict[str, Any]] = []
    for f in notes_dir.iterdir():
        if not f.name.endswith(".md") or f.name == "reminders.md":
            continue
        date_str = f.stem
        try:
            date.fromisoformat(date_str)
        except ValueError:
            continue
        content = f.read_text().strip()
        mtime = datetime.fromtimestamp(f.stat().st_mtime).isoformat()
        notes.append({
            "date": date_str,
            "preview": content[:200],
            "updated_at": mtime,
        })

    notes.sort(key=lambda n: n["date"], reverse=True)
    return notes


@router.get("/{person}/{note_date}", dependencies=[AuthDep])
async def note_detail(person: str, note_date: str) -> dict[str, Any]:
    """Get the full content of a specific note."""
    workspaces = get_config().workspaces.resolve()
    try:
        date.fromisoformat(note_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    path = workspaces / person / "notes" / f"{note_date}.md"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Note not found")

    mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    return {
        "person": person,
        "date": note_date,
        "content": path.read_text().strip(),
        "updated_at": mtime,
    }
