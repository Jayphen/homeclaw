"""Dashboard API route — today's overview for the whole household."""

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter

from homeclaw.api.deps import MemberDep, get_config, visible_members_with_household
from homeclaw.contacts.store import list_contacts
from homeclaw.reminders.store import load_reminders

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _today_notes(workspaces_path: str, members: list[str], today: str) -> list[dict[str, Any]]:
    """Get today's notes for all members."""
    from pathlib import Path

    ws = Path(workspaces_path)
    notes: list[dict[str, Any]] = []
    for person in members:
        path = ws / person / "notes" / f"{today}.md"
        if path.exists():
            mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            notes.append({"person": person, "content": path.read_text().strip(), "updated_at": mtime})
    return notes


def _upcoming_reminders(
    workspaces: Path, members: list[str], days: int = 7,
) -> list[dict[str, Any]]:
    """Get reminders due within the next N days from the JSON reminder store."""
    today = date.today()
    end = today + timedelta(days=days)
    reminders: list[dict[str, Any]] = []

    for person in members:
        for r in load_reminders(workspaces, person):
            due = r.next_due
            if due and today <= due <= end:
                reminders.append({
                    "date": due.isoformat(),
                    "person": person,
                    "note": r.note,
                })

    reminders.sort(key=lambda r: r["date"])
    return reminders


def _upcoming_birthdays(workspaces_path: str, days: int = 30) -> list[dict[str, Any]]:
    """Get contact birthdays within the next N days."""
    from pathlib import Path

    today = date.today()
    end = today + timedelta(days=days)
    contacts = list_contacts(Path(workspaces_path))
    birthdays: list[dict[str, Any]] = []

    for c in contacts:
        if c.birthday is None:
            continue
        bday = c.birthday.replace(year=today.year)
        # Handle birthdays that already passed this year
        if bday < today:
            bday = bday.replace(year=today.year + 1)
        if today <= bday <= end:
            birthdays.append({
                "date": bday.isoformat(),
                "name": c.name,
                "relationship": c.relationship,
            })

    birthdays.sort(key=lambda b: b["date"])
    return birthdays


def _recent_interactions(workspaces_path: str, days: int = 7) -> list[dict[str, Any]]:
    """Get recent contact interactions."""
    from pathlib import Path

    cutoff = datetime.now().date() - timedelta(days=days)
    contacts = list_contacts(Path(workspaces_path))
    interactions: list[dict[str, Any]] = []

    for c in contacts:
        for ix in c.interactions:
            if ix.date.date() >= cutoff:
                interactions.append({
                    "date": ix.date.isoformat(),
                    "contact": c.name,
                    "type": ix.type,
                    "notes": ix.notes[:200],
                })

    interactions.sort(key=lambda i: i["date"], reverse=True)
    return interactions


def _overdue_checkins(workspaces_path: str) -> list[dict[str, Any]]:
    """Find contacts with overdue recurring check-ins."""
    from pathlib import Path

    today = date.today()
    contacts = list_contacts(Path(workspaces_path))
    overdue: list[dict[str, Any]] = []

    for c in contacts:
        for r in c.reminders:
            if r.interval_days and r.next_date and r.next_date < today:
                overdue.append({
                    "contact": c.name,
                    "relationship": c.relationship,
                    "note": r.note,
                    "due_date": r.next_date.isoformat(),
                    "days_overdue": (today - r.next_date).days,
                })

    overdue.sort(key=lambda o: o["days_overdue"], reverse=True)
    return overdue


@router.get("")
async def dashboard(
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    ws_str = str(workspaces)
    members = visible_members_with_household(workspaces, member)
    today = date.today().isoformat()

    return {
        "date": today,
        "members": members,
        "today_notes": _today_notes(ws_str, members, today),
        "upcoming_reminders": _upcoming_reminders(workspaces, members),
        "upcoming_birthdays": _upcoming_birthdays(ws_str),
        "recent_interactions": _recent_interactions(ws_str),
        "overdue_checkins": _overdue_checkins(ws_str),
    }
