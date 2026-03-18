"""Tests for bookmarks store and models."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from homeclaw.bookmarks.models import Bookmark
from homeclaw.bookmarks.store import (
    delete_bookmark,
    get_categories,
    list_bookmarks,
    save_bookmark,
    search_bookmarks,
)


@pytest.fixture
def workspaces(tmp_path: Path) -> Path:
    return tmp_path


def _make_bookmark(**kwargs: object) -> Bookmark:
    defaults: dict[str, object] = {
        "id": "abc123",
        "title": "Test Place",
        "category": "place",
        "url": "https://example.com",
        "tags": ["italian"],
        "saved_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return Bookmark.model_validate(defaults)


def test_save_and_list(workspaces: Path) -> None:
    b = _make_bookmark()
    save_bookmark(workspaces, b)
    results = list_bookmarks(workspaces)
    assert len(results) == 1
    assert results[0].title == "Test Place"


def test_dedup_by_url(workspaces: Path) -> None:
    b1 = _make_bookmark(id="aaa", title="Old Name")
    save_bookmark(workspaces, b1)
    b2 = _make_bookmark(id="bbb", title="New Name", url="https://example.com")
    save_bookmark(workspaces, b2)
    results = list_bookmarks(workspaces)
    assert len(results) == 1
    assert results[0].title == "New Name"


def test_filter_by_category(workspaces: Path) -> None:
    save_bookmark(workspaces, _make_bookmark(id="a", category="place", url=None))
    save_bookmark(workspaces, _make_bookmark(id="b", category="recipe", url=None, title="Pasta"))
    assert len(list_bookmarks(workspaces, category="recipe")) == 1
    assert len(list_bookmarks(workspaces, category="place")) == 1


def test_filter_by_tag(workspaces: Path) -> None:
    save_bookmark(workspaces, _make_bookmark(id="a", tags=["brunch", "outdoor"], url=None))
    save_bookmark(workspaces, _make_bookmark(id="b", tags=["dinner"], url=None))
    assert len(list_bookmarks(workspaces, tag="brunch")) == 1


def test_search(workspaces: Path) -> None:
    save_bookmark(workspaces, _make_bookmark(id="a", title="Klunkerkranich", tags=["rooftop", "bar"], url=None))
    save_bookmark(workspaces, _make_bookmark(id="b", title="Pasta Carbonara", category="recipe", url=None))
    results = search_bookmarks(workspaces, "rooftop")
    assert len(results) >= 1
    assert results[0].title == "Klunkerkranich"

    results = search_bookmarks(workspaces, "pasta")
    assert len(results) >= 1
    assert results[0].title == "Pasta Carbonara"


def test_delete(workspaces: Path) -> None:
    save_bookmark(workspaces, _make_bookmark(id="del1", url=None))
    assert delete_bookmark(workspaces, "del1")
    assert len(list_bookmarks(workspaces)) == 0
    assert not delete_bookmark(workspaces, "nonexistent")


def test_get_categories(workspaces: Path) -> None:
    save_bookmark(workspaces, _make_bookmark(id="a", category="place", url=None))
    save_bookmark(workspaces, _make_bookmark(id="b", category="recipe", url=None))
    save_bookmark(workspaces, _make_bookmark(id="c", category="place", url=None))
    cats = get_categories(workspaces)
    assert cats == ["place", "recipe"]


def test_dynamic_category(workspaces: Path) -> None:
    save_bookmark(workspaces, _make_bookmark(id="a", category="book", url=None, title="Dune"))
    cats = get_categories(workspaces)
    assert "book" in cats
