"""Pydantic models for household member reminders."""

from datetime import date, datetime

from pydantic import BaseModel


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
