"""Pydantic models for contacts, interactions, and reminders."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

InteractionType = Literal["call", "message", "meetup", "other"]


class Interaction(BaseModel):
    date: datetime
    type: InteractionType
    notes: str


class Reminder(BaseModel):
    interval_days: int | None = None  # recurring: check in every N days
    next_date: date | None = None  # one-shot: remind on this date
    note: str = ""


class Contact(BaseModel):
    id: str
    name: str
    nicknames: list[str] = []
    relationship: str
    birthday: date | None = None
    facts: list[str] = []
    interactions: list[Interaction] = []
    reminders: list[Reminder] = []
    last_contact: datetime | None = None
    member: str | None = None  # workspace name if this contact is also a household member
