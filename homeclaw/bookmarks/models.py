"""Pydantic models for saved bookmarks (places, recipes, links)."""

from datetime import datetime

from pydantic import BaseModel


class Bookmark(BaseModel):
    id: str
    url: str | None = None
    title: str
    category: str = "other"
    tags: list[str] = []
    saved_by: str = ""
    saved_at: datetime | None = None
    neighborhood: str = ""
    city: str = ""
