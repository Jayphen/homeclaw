"""Bookmarks API routes — household-shared saved links and places."""

from typing import Any

from fastapi import APIRouter, HTTPException

from homeclaw.api.deps import AuthDep, get_config
from homeclaw.bookmarks.store import (
    delete_bookmark,
    get_categories,
    list_bookmarks,
    search_bookmarks,
)

router = APIRouter(prefix="/api/bookmarks", tags=["bookmarks"])


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
    return {
        "bookmarks": [b.model_dump(mode="json") for b in results],
        "categories": get_categories(workspaces),
    }


@router.delete("/{bookmark_id}", dependencies=[AuthDep])
async def bookmark_remove(bookmark_id: str) -> dict[str, str]:
    """Delete a bookmark by ID."""
    workspaces = get_config().workspaces.resolve()
    if not delete_bookmark(workspaces, bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"status": "deleted"}
