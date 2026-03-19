"""Calendar API route — unified monthly view."""

from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query

from homeclaw.api.deps import MemberDep, get_config, list_member_workspaces, visible_members
from homeclaw.contacts.store import list_contacts

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _parse_month(month_str: str) -> tuple[date, date]:
    """Parse YYYY-MM and return (first_day, last_day) of the month."""
    parts = month_str.split("-")
    year, month = int(parts[0]), int(parts[1])
    first = date(year, month, 1)
    # Last day: go to next month, subtract 1 day
    if month == 12:
        last = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    return first, last


def _collect_notes(
    workspaces_path: str, members: list[str], start: date, end: date,
) -> list[dict[str, Any]]:
    """Collect notes from all members within date range."""
    from pathlib import Path

    events: list[dict[str, Any]] = []
    ws = Path(workspaces_path)
    current = start
    while current <= end:
        date_str = current.isoformat()
        for person in members:
            path = ws / person / "notes" / f"{date_str}.md"
            if path.exists():
                events.append({
                    "date": date_str,
                    "type": "note",
                    "person": person,
                    "summary": path.read_text().strip()[:200],
                })
        current += timedelta(days=1)
    return events


def _collect_reminders(
    workspaces_path: str, members: list[str], start: date, end: date,
) -> list[dict[str, Any]]:
    """Collect reminders from all members within date range."""
    from pathlib import Path

    events: list[dict[str, Any]] = []
    ws = Path(workspaces_path)
    for person in members:
        path = ws / person / "notes" / "reminders.md"
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line.startswith("- ["):
                continue
            # Parse "- [ ] YYYY-MM-DD: text" or "- [x] YYYY-MM-DD: text"
            done = line.startswith("- [x]")
            rest = line[6:].strip()  # after "- [ ] " or "- [x] "
            if ":" not in rest:
                continue
            date_part, note = rest.split(":", 1)
            try:
                reminder_date = date.fromisoformat(date_part.strip())
            except ValueError:
                continue
            if start <= reminder_date <= end:
                events.append({
                    "date": reminder_date.isoformat(),
                    "type": "reminder",
                    "person": person,
                    "summary": note.strip(),
                    "done": done,
                })
    return events


def _collect_birthdays(workspaces_path: str, start: date, end: date) -> list[dict[str, Any]]:
    """Collect contact birthdays within date range."""
    from pathlib import Path

    events: list[dict[str, Any]] = []
    contacts = list_contacts(Path(workspaces_path))
    for c in contacts:
        if c.birthday is None:
            continue
        # Check if birthday falls within range (use current year)
        bday = c.birthday.replace(year=start.year)
        if start <= bday <= end:
            events.append({
                "date": bday.isoformat(),
                "type": "birthday",
                "person": c.name,
                "summary": f"{c.name}'s birthday",
            })
    return events


def _collect_interactions(workspaces_path: str, start: date, end: date) -> list[dict[str, Any]]:
    """Collect contact interactions within date range."""
    from pathlib import Path

    events: list[dict[str, Any]] = []
    contacts = list_contacts(Path(workspaces_path))
    for c in contacts:
        for ix in c.interactions:
            ix_date = ix.date.date()
            if start <= ix_date <= end:
                events.append({
                    "date": ix_date.isoformat(),
                    "type": "interaction",
                    "person": c.name,
                    "summary": f"{ix.type}: {ix.notes}"[:200],
                })
    return events


@router.get("")
async def calendar_month(
    member: Annotated[str | None, MemberDep],
    month: str = Query(
        default=None,
        description="Month in YYYY-MM format (defaults to current month)",
    ),
) -> dict[str, Any]:
    workspaces = get_config().workspaces.resolve()
    ws_str = str(workspaces)

    if month is None:
        month = datetime.now().strftime("%Y-%m")

    start, end = _parse_month(month)
    all_members = list_member_workspaces(workspaces)
    members = visible_members(member, all_members)

    events: list[dict[str, Any]] = []
    events.extend(_collect_notes(ws_str, members, start, end))
    events.extend(_collect_reminders(ws_str, members, start, end))
    events.extend(_collect_birthdays(ws_str, start, end))
    events.extend(_collect_interactions(ws_str, start, end))

    events.sort(key=lambda e: e["date"])

    return {
        "month": month,
        "event_count": len(events),
        "events": events,
    }
