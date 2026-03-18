"""Reminder JSON store — one file per person at workspaces/{person}/reminders.json."""

from pathlib import Path

from homeclaw.locking import LockPool
from homeclaw.reminders.models import Reminder

_lock_pool = LockPool()


def _reminders_path(workspaces: Path, person: str) -> Path:
    d = workspaces / person
    d.mkdir(parents=True, exist_ok=True)
    return d / "reminders.json"


def load_reminders(workspaces: Path, person: str) -> list[Reminder]:
    path = _reminders_path(workspaces, person)
    if not path.exists():
        return []
    import json

    data = json.loads(path.read_text())
    return [Reminder.model_validate(r) for r in data]


def save_reminders(workspaces: Path, person: str, reminders: list[Reminder]) -> None:
    path = _reminders_path(workspaces, person)
    import json

    path.write_text(json.dumps([r.model_dump(mode="json") for r in reminders], indent=2))


def add_reminder(workspaces: Path, reminder: Reminder) -> Reminder:
    reminders = load_reminders(workspaces, reminder.person)
    reminders.append(reminder)
    save_reminders(workspaces, reminder.person, reminders)
    return reminder


async def add_reminder_safe(workspaces: Path, reminder: Reminder) -> Reminder:
    """Add a reminder with per-person locking to prevent concurrent races."""
    async with _lock_pool.lock_for(reminder.person):
        return add_reminder(workspaces, reminder)


def get_reminder(workspaces: Path, person: str, reminder_id: str) -> Reminder | None:
    for r in load_reminders(workspaces, person):
        if r.id == reminder_id:
            return r
    return None


def complete_reminder(workspaces: Path, person: str, reminder_id: str) -> Reminder | None:
    """Mark a reminder as completed. For recurring, advances last_completed."""
    from datetime import date as date_type

    reminders = load_reminders(workspaces, person)
    for r in reminders:
        if r.id != reminder_id:
            continue
        if r.interval_days:
            r.last_completed = date_type.today()
        else:
            r.done = True
        save_reminders(workspaces, person, reminders)
        return r
    return None


async def complete_reminder_safe(workspaces: Path, person: str, reminder_id: str) -> Reminder | None:
    """Complete a reminder with per-person locking."""
    async with _lock_pool.lock_for(person):
        return complete_reminder(workspaces, person, reminder_id)


def delete_reminder(workspaces: Path, person: str, reminder_id: str) -> bool:
    reminders = load_reminders(workspaces, person)
    filtered = [r for r in reminders if r.id != reminder_id]
    if len(filtered) == len(reminders):
        return False
    save_reminders(workspaces, person, filtered)
    return True


async def delete_reminder_safe(workspaces: Path, person: str, reminder_id: str) -> bool:
    """Delete a reminder with per-person locking."""
    async with _lock_pool.lock_for(person):
        return delete_reminder(workspaces, person, reminder_id)
