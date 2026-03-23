"""Notes API routes — per-person, per-date markdown notes."""

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.api.deps import (
    MemberDep,
    get_config,
    list_member_workspaces,
    require_person_access,
    validate_person,
    visible_members,
)

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("")
async def notes_index(
    member: Annotated[str | None, MemberDep],
) -> list[dict[str, Any]]:
    """List all notes across visible members, newest first."""
    workspaces = get_config().workspaces.resolve()
    all_members = list_member_workspaces(workspaces)
    members = visible_members(member, all_members)
    # Always include household — it's visible to all members
    if HOUSEHOLD_WORKSPACE not in members:
        members = [*members, HOUSEHOLD_WORKSPACE]
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


@router.get("/{person}")
async def notes_by_person(
    person: str,
    member: Annotated[str | None, MemberDep],
) -> list[dict[str, Any]]:
    """List all notes for a specific person, newest first."""
    workspaces = get_config().workspaces.resolve()
    validate_person(person, workspaces)
    require_person_access(member, person)
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


@router.get("/{person}/{note_date}")
async def note_detail(
    person: str,
    note_date: str,
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    """Get the full content of a specific note."""
    workspaces = get_config().workspaces.resolve()
    validate_person(person, workspaces)
    require_person_access(member, person)
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


class NoteUpdate(BaseModel):
    content: str


@router.put("/{person}/{note_date}")
async def note_save(
    person: str,
    note_date: str,
    body: NoteUpdate,
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    """Create or update a note's content."""
    workspaces = get_config().workspaces.resolve()
    validate_person(person, workspaces)
    require_person_access(member, person)
    try:
        date.fromisoformat(note_date)
    except ValueError as err:
        raise HTTPException(
            status_code=400, detail="Invalid date format, expected YYYY-MM-DD"
        ) from err

    notes_dir = workspaces / person / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    path = notes_dir / f"{note_date}.md"
    path.write_text(body.content)

    mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
    return {
        "person": person,
        "date": note_date,
        "content": body.content,
        "updated_at": mtime,
    }
