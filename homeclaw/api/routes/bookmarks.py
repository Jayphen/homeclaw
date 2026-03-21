"""Bookmarks API routes — household-shared saved links and places."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from homeclaw.api.deps import AuthDep, get_config
from homeclaw.bookmarks.models import Bookmark
from homeclaw.bookmarks.store import (
    delete_bookmark_safe,
    get_categories,
    list_bookmarks,
    search_bookmarks,
)

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


def _notes_for(workspaces: Path, bookmark: Bookmark) -> str | None:
    """Read the markdown notes file for a bookmark, if it exists."""
    path = workspaces / "household" / "bookmarks" / "notes" / f"{bookmark.id}.md"
    if not path.is_file():
        return None
    text = path.read_text()
    # Strip legacy "# Title" header — the UI already shows the bookmark title
    lines = text.splitlines()
    if lines and lines[0].startswith("# "):
        lines = [l for l in lines[1:] if l.strip()]
        text = "\n".join(lines) + "\n" if lines else ""
    return text or None


@router.get("", dependencies=[AuthDep])
async def bookmarks_index(
    category: str | None = None,
    tag: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """List or search bookmarks. Use ?q= for search, ?category= or ?tag= to filter."""
    workspaces = get_config().workspaces.resolve()
    if q:
        results = search_bookmarks(workspaces, q)
    else:
        results = list_bookmarks(workspaces, category=category, tag=tag)
    items: list[dict[str, Any]] = []
    for b in results:
        item = b.model_dump(mode="json")
        item["notes_md"] = _notes_for(workspaces, b)
        items.append(item)
    return {
        "bookmarks": items,
        "categories": get_categories(workspaces),
    }


@router.delete("/{bookmark_id}", dependencies=[AuthDep])
async def bookmark_remove(bookmark_id: str) -> dict[str, str]:
    """Delete a bookmark by ID."""
    workspaces = get_config().workspaces.resolve()
    if not await delete_bookmark_safe(workspaces, bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"status": "deleted"}
