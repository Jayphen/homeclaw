"""Pydantic models for contacts, interactions, and reminders."""

from datetime import date, datetime

from pydantic import BaseModel


class Interaction(BaseModel):
    date: datetime
    type: str  # "call" | "message" | "meetup" | "other"
    notes: str


class Reminder(BaseModel):
    interval_days: int | None = None  # recurring: check in every N days
    next_date: date | None = None  # one-shot: remind on this date
    note: str = ""


class Contact(BaseModel):
    id: str
    name: str
    relationship: str  # "friend" | "family" | "colleague" | "other"
    birthday: date | None = None
    facts: list[str] = []
    interactions: list[Interaction] = []
    reminders: list[Reminder] = []
    last_contact: datetime | None = None
