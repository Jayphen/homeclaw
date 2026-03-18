"""Bookmark JSON store — shared across the household."""

from difflib import SequenceMatcher
from pathlib import Path

from homeclaw.bookmarks.models import Bookmark

_FUZZY_THRESHOLD = 0.4


def _bookmarks_path(workspaces: Path) -> Path:
    d = workspaces / "household" / "bookmarks"
    d.mkdir(parents=True, exist_ok=True)
    return d / "bookmarks.json"


def _load_all(workspaces: Path) -> list[Bookmark]:
    path = _bookmarks_path(workspaces)
    if not path.exists():
        return []
    import json

    raw = json.loads(path.read_text())
    return [Bookmark.model_validate(item) for item in raw]


def _save_all(workspaces: Path, bookmarks: list[Bookmark]) -> None:
    path = _bookmarks_path(workspaces)
    import json

    path.write_text(json.dumps([b.model_dump(mode="json") for b in bookmarks], indent=2))


def save_bookmark(workspaces: Path, bookmark: Bookmark) -> Bookmark:
    bookmarks = _load_all(workspaces)
    # Deduplicate by URL if present
    if bookmark.url:
        for existing in bookmarks:
            if existing.url == bookmark.url:
                existing.title = bookmark.title or existing.title
                existing.category = bookmark.category
                existing.tags = bookmark.tags or existing.tags
                _save_all(workspaces, bookmarks)
                return existing
    bookmarks.append(bookmark)
    _save_all(workspaces, bookmarks)
    return bookmark


def list_bookmarks(
    workspaces: Path,
    category: str | None = None,
    tag: str | None = None,
) -> list[Bookmark]:
    bookmarks = _load_all(workspaces)
    if category:
        bookmarks = [b for b in bookmarks if b.category == category]
    if tag:
        tag_lower = tag.lower()
        bookmarks = [b for b in bookmarks if any(tag_lower in t.lower() for t in b.tags)]
    return bookmarks


def search_bookmarks(workspaces: Path, query: str) -> list[Bookmark]:
    """Search bookmarks by fuzzy matching against title, tags, notes, neighborhood, city."""
    query_lower = query.lower().strip()
    bookmarks = _load_all(workspaces)
    scored: list[tuple[Bookmark, float]] = []

    for b in bookmarks:
        candidates = [b.title.lower()]
        candidates.extend(t.lower() for t in b.tags)
        if b.category:
            candidates.append(b.category.lower())

        best = 0.0
        for candidate in candidates:
            if query_lower in candidate:
                best = max(best, 0.9)
            ratio = SequenceMatcher(None, query_lower, candidate).ratio()
            best = max(best, ratio)

        if best >= _FUZZY_THRESHOLD:
            scored.append((b, best))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [b for b, _ in scored]


def get_categories(workspaces: Path) -> list[str]:
    """Return all distinct categories currently in use, sorted alphabetically."""
    bookmarks = _load_all(workspaces)
    return sorted({b.category for b in bookmarks if b.category})


def update_bookmark(
    workspaces: Path,
    bookmark_id: str,
    url: str | None = None,
    title: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
) -> Bookmark | None:
    """Update fields on an existing bookmark. Returns updated bookmark or None if not found."""
    bookmarks = _load_all(workspaces)
    for b in bookmarks:
        if b.id == bookmark_id:
            if url is not None:
                b.url = url
            if title is not None:
                b.title = title
            if category is not None:
                b.category = category
            if tags is not None:
                b.tags = tags
            _save_all(workspaces, bookmarks)
            return b
    return None


def delete_bookmark(workspaces: Path, bookmark_id: str) -> bool:
    bookmarks = _load_all(workspaces)
    original_len = len(bookmarks)
    bookmarks = [b for b in bookmarks if b.id != bookmark_id]
    if len(bookmarks) == original_len:
        return False
    _save_all(workspaces, bookmarks)
    return True
