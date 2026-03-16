"""Parse ROUTINES.md into structured routine definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ROUTINES_FILE = "household/ROUTINES.md"

# Day name → APScheduler day_of_week value
_DAYS = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}


@dataclass
class ParsedRoutine:
    """A routine parsed from ROUTINES.md."""

    name: str
    description: str
    trigger_type: str  # "cron" or "interval"
    trigger_kwargs: dict[str, int | str]


def _parse_time(time_str: str) -> tuple[int, int]:
    """Parse '7:30am', '6:00 PM', '10:00am' etc. into (hour, minute)."""
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)?", time_str.strip(), re.IGNORECASE)
    if not m:
        raise ValueError(f"Cannot parse time: {time_str!r}")
    hour, minute = int(m.group(1)), int(m.group(2))
    ampm = (m.group(3) or "").lower()
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def _parse_schedule(text: str) -> tuple[str, dict[str, int | str]]:
    """Parse a natural-language schedule string into (trigger_type, kwargs).

    Supported forms:
      - "Every day at 7:30am"
      - "Every weekday at 7:30am"
      - "Every Sunday at 10:00am"
      - "Every Monday at 9:00am"
      - "Every 3 days"
      - "Every N hours"
    """
    text = text.strip()

    # "Every N days/hours/minutes"
    m = re.match(r"every\s+(\d+)\s+(day|hour|minute)s?", text, re.IGNORECASE)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower() + "s"
        return "interval", {unit: amount}

    # "Every weekday at TIME"
    m = re.match(r"every\s+weekday\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        hour, minute = _parse_time(m.group(1))
        return "cron", {"day_of_week": "mon-fri", "hour": hour, "minute": minute}

    # "Every <dayname> at TIME"
    m = re.match(r"every\s+(\w+)\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        day_word = m.group(1).lower()
        hour, minute = _parse_time(m.group(2))
        if day_word == "day":
            return "cron", {"hour": hour, "minute": minute}
        day_code = _DAYS.get(day_word)
        if day_code:
            return "cron", {"day_of_week": day_code, "hour": hour, "minute": minute}

    raise ValueError(f"Cannot parse schedule: {text!r}")


def _extract_schedule_and_actions(lines: list[str]) -> tuple[str | None, list[str]]:
    """Extract schedule and action lines from a routine's body.

    Supports two formats:
      1. Structured: lines with **Schedule**: ... and **Action**: ...
      2. Plain: all bullet points are action descriptions (schedule is in heading)
    """
    schedule: str | None = None
    actions: list[str] = []

    for line in lines:
        stripped = line.strip().lstrip("- ").strip()
        # Check for **Schedule**: ...
        m = re.match(r"\*\*Schedule\*\*:\s*(.+)", stripped)
        if m:
            schedule = m.group(1).strip()
            continue
        # Check for **Action**: ...
        m = re.match(r"\*\*Action\*\*:\s*(.+)", stripped)
        if m:
            actions.append(m.group(1).strip())
            continue
        # Plain bullet point
        if stripped:
            actions.append(stripped)

    return schedule, actions


def parse_routines_md(workspaces: Path) -> list[ParsedRoutine]:
    """Parse workspaces/household/ROUTINES.md into a list of routines."""
    path = workspaces / _ROUTINES_FILE
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    routines: list[ParsedRoutine] = []

    # Split by ## headings
    sections = re.split(r"^##\s+", text, flags=re.MULTILINE)

    for section in sections[1:]:  # skip preamble before first ##
        lines = section.strip().splitlines()
        if not lines:
            continue

        heading = lines[0].strip()
        body_lines = lines[1:]

        schedule_text, actions = _extract_schedule_and_actions(body_lines)

        # If no explicit **Schedule** field, try parsing the heading as the schedule
        if schedule_text is None:
            schedule_text = heading

        try:
            trigger_type, trigger_kwargs = _parse_schedule(schedule_text)
        except ValueError:
            # Skip routines we can't parse
            continue

        # Build description from heading + actions
        description = f"{heading}: {'; '.join(actions)}" if actions else heading

        routines.append(
            ParsedRoutine(
                name=re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_"),
                description=description,
                trigger_type=trigger_type,
                trigger_kwargs=trigger_kwargs,
            )
        )

    return routines
