"""Pydantic models for contacts, interactions, and reminders."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, computed_field, model_validator

InteractionType = Literal["call", "message", "meetup", "other"]


class Interaction(BaseModel):
    date: datetime
    type: InteractionType
    notes: str


class ContactReminder(BaseModel):
    interval_days: int | None = None  # recurring: check in every N days
    next_date: date | None = None  # one-shot: remind on this date
    note: str = ""

    @model_validator(mode="after")
    def _require_at_least_one(self) -> "ContactReminder":
        if self.interval_days is None and self.next_date is None:
            raise ValueError("ContactReminder must have interval_days or next_date")
        return self


class Contact(BaseModel):
    id: str
    name: str
    nicknames: list[str] = []
    relationship: str
    birthday: date | None = None
    facts: list[str] = []
    interactions: list[Interaction] = []
    reminders: list[ContactReminder] = []
    member: str | None = None  # workspace name if this contact is also a household member

    @computed_field  # type: ignore[prop-decorator]
    @property
    def last_contact(self) -> datetime | None:
        """Derived from the most recent interaction — no longer stored separately."""
        if not self.interactions:
            return None
        return max(ix.date for ix in self.interactions)
