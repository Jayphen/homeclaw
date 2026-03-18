"""Pydantic models for household member reminders."""

from datetime import date, datetime

from pydantic import BaseModel, model_validator


class Reminder(BaseModel):
    id: str
    person: str
    note: str
    # One-shot: fires on this date then done
    due_date: date | None = None
    # Recurring: fires every N days
    interval_days: int | None = None
    # Tracking
    last_completed: date | None = None
    created_at: datetime | None = None
    done: bool = False

    @model_validator(mode="after")
    def _validate_reminder_type(self) -> "Reminder":
        if self.due_date is None and self.interval_days is None:
            raise ValueError("Reminder must have due_date or interval_days")
        if self.done and self.interval_days is not None:
            # Recurring reminders are never permanently done — reset the flag.
            self.done = False
        return self

    @property
    def next_due(self) -> date | None:
        """Calculate when this reminder is next due."""
        if self.done:
            return None
        if self.due_date and not self.interval_days:
            return self.due_date
        if self.interval_days:
            base = self.last_completed or (self.due_date or date.today())
            from datetime import timedelta

            return base + timedelta(days=self.interval_days)
        return self.due_date
