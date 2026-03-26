"""Parse and manage ROUTINES.md — structured routine definitions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_ROUTINES_FILE = "household/ROUTINES.md"
ROUTINES_FILE = _ROUTINES_FILE  # public alias for tools

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
    title: str  # human-readable heading, used in user-facing messages
    description: str  # full detail including actions, used as LLM prompt
    trigger_type: str  # "cron" or "interval"
    trigger_kwargs: dict[str, int | str]
    target: str | None = None  # None/"household" = group, "each_member" = all, name = DM


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
      - "Every 3 days" / "Every N hours"
      - "Every other day at 7:30am"
      - "Every other Tuesday at 9:00am"
      - "Every N weeks on Wednesday at 10:00am"
      - "Monthly on the 15th at 9:00am"
      - "1st/2nd/3rd/4th Monday of the month at 10:00am"
      - "Last Friday of the month at 3:00pm"
      - Standard 5-field cron expressions (e.g. "30 7 * * 1-5")
    """
    text = text.strip()

    # --- Direct cron expression: "30 7 * * 1-5" ---
    m = re.match(r"^([\d*/,-]+)\s+([\d*/,-]+)\s+([\d*/,-]+)\s+([\d*/,-]+)\s+([\d*/,a-zA-Z-]+)$", text)
    if m:
        return "cron", {
            "minute": m.group(1),
            "hour": m.group(2),
            "day": m.group(3),
            "month": m.group(4),
            "day_of_week": m.group(5),
        }

    # --- "Every N days/hours/minutes/weeks" ---
    m = re.match(r"every\s+(\d+)\s+(day|hour|minute|week)s?", text, re.IGNORECASE)
    if m:
        amount = int(m.group(1))
        unit = m.group(2).lower() + "s"
        return "interval", {unit: amount}

    # --- "Every other day at TIME" ---
    m = re.match(r"every\s+other\s+day\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        hour, minute = _parse_time(m.group(1))
        return "interval", {"days": 2, "hours": hour, "minutes": minute}

    # --- "Every other <dayname> at TIME" ---
    m = re.match(r"every\s+other\s+(\w+)\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        day_word = m.group(1).lower()
        day_code = _DAYS.get(day_word)
        if day_code:
            hour, minute = _parse_time(m.group(2))
            return "interval", {"weeks": 2, "days": _day_offset(day_code), "hours": hour, "minutes": minute}

    # --- "Every N weeks on <dayname> at TIME" ---
    m = re.match(r"every\s+(\d+)\s+weeks?\s+on\s+(\w+)\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        n_weeks = int(m.group(1))
        day_word = m.group(2).lower()
        day_code = _DAYS.get(day_word)
        if day_code:
            hour, minute = _parse_time(m.group(3))
            return "interval", {"weeks": n_weeks, "days": _day_offset(day_code), "hours": hour, "minutes": minute}

    # --- Ordinal weekday of month: "1st Monday of the month at TIME" ---
    m = re.match(
        r"(1st|2nd|3rd|4th|first|second|third|fourth|last)\s+(\w+)\s+of\s+(?:the\s+)?month\s+at\s+(.+)",
        text, re.IGNORECASE,
    )
    if m:
        ordinal_str = m.group(1).lower()
        day_word = m.group(2).lower()
        day_code = _DAYS.get(day_word)
        if day_code:
            hour, minute = _parse_time(m.group(3))
            day_range = _ordinal_day_range(ordinal_str)
            return "cron", {"day_of_week": day_code, "day": day_range, "hour": hour, "minute": minute}

    # --- "Monthly on the Nth at TIME" ---
    m = re.match(r"monthly\s+on\s+the\s+(\d+)(?:st|nd|rd|th)?\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        day_of_month = int(m.group(1))
        hour, minute = _parse_time(m.group(2))
        return "cron", {"day": day_of_month, "hour": hour, "minute": minute}

    # --- "Every weekday at TIME" ---
    m = re.match(r"every\s+weekday\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        hour, minute = _parse_time(m.group(1))
        return "cron", {"day_of_week": "mon-fri", "hour": hour, "minute": minute}

    # --- "Every <dayname> at TIME" / "Every day at TIME" ---
    m = re.match(r"every\s+(\w+)\s+at\s+(.+)", text, re.IGNORECASE)
    if m:
        day_word = m.group(1).lower()
        hour, minute = _parse_time(m.group(2))
        if day_word == "day":
            return "cron", {"hour": hour, "minute": minute}
        day_code = _DAYS.get(day_word)
        if day_code:
            return "cron", {"day_of_week": day_code, "hour": hour, "minute": minute}

    raise ValueError(
        f"Cannot parse schedule: {text!r}. Use natural language "
        f"(e.g. 'Every Monday at 9am', 'Monthly on the 1st at 10am') "
        f"or a 5-field cron expression (e.g. '0 9 * * 1')."
    )


# Weekday offsets from Monday (for interval-based scheduling)
_DAY_OFFSETS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def _day_offset(day_code: str) -> int:
    """Return the offset (0-6) for a day code, for use with interval triggers."""
    return _DAY_OFFSETS.get(day_code, 0)


def _ordinal_day_range(ordinal: str) -> str:
    """Convert an ordinal like '1st'/'first'/'last' to a cron day-of-month range.

    Uses the trick of constraining both day_of_week and day to get
    'Nth weekday of the month' behavior with APScheduler's CronTrigger.
    """
    mapping = {
        "1st": "1-7", "first": "1-7",
        "2nd": "8-14", "second": "8-14",
        "3rd": "15-21", "third": "15-21",
        "4th": "22-28", "fourth": "22-28",
        "last": "25-31",
    }
    return mapping.get(ordinal, "1-7")


def _extract_schedule_and_actions(
    lines: list[str],
) -> tuple[str | None, list[str], str | None]:
    """Extract schedule, action lines, and target from a routine's body.

    Supports two formats:
      1. Structured: lines with **Schedule**: ... and **Action**: ...
      2. Plain: all bullet points are action descriptions (schedule is in heading)

    Returns (schedule, actions, target).
    """
    schedule: str | None = None
    target: str | None = None
    actions: list[str] = []

    for line in lines:
        stripped = line.strip().lstrip("- ").strip()
        # Check for **Schedule**: ...
        m = re.match(r"\*\*Schedule\*\*:\s*(.+)", stripped)
        if m:
            schedule = m.group(1).strip()
            continue
        # Check for **Target**: ...
        m = re.match(r"\*\*Target\*\*:\s*(.+)", stripped)
        if m:
            target = m.group(1).strip().lower()
            continue
        # Check for **Action**: ...
        m = re.match(r"\*\*Action\*\*:\s*(.+)", stripped)
        if m:
            actions.append(m.group(1).strip())
            continue
        # Plain bullet point
        if stripped:
            actions.append(stripped)

    return schedule, actions, target


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

        schedule_text, actions, target = _extract_schedule_and_actions(body_lines)

        # If no explicit **Schedule** field, try parsing the heading as the schedule
        if schedule_text is None:
            schedule_text = heading

        try:
            trigger_type, trigger_kwargs = _parse_schedule(schedule_text)
        except ValueError:
            # Skip routines we can't parse
            continue

        # Normalise target: "household"/"group" → None (group chat default)
        if target in ("household", "group"):
            target = None

        # Build description from heading + actions
        description = f"{heading}: {'; '.join(actions)}" if actions else heading

        routines.append(
            ParsedRoutine(
                name=re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_"),
                title=heading,
                description=description,
                trigger_type=trigger_type,
                trigger_kwargs=trigger_kwargs,
                target=target,
            )
        )

    return routines


def _routines_path(workspaces: Path) -> Path:
    return workspaces / _ROUTINES_FILE


def add_routine(
    workspaces: Path,
    title: str,
    schedule: str,
    action: str,
    target: str | None = None,
) -> None:
    """Append a routine section to ROUTINES.md.

    Validates the schedule string before writing.
    """
    _parse_schedule(schedule)  # raises ValueError if invalid
    path = _routines_path(workspaces)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("# Household Routines\n")
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"
    target_line = f"\n- **Target**: {target}" if target else ""
    text += f"\n## {title}\n- **Schedule**: {schedule}{target_line}\n- **Action**: {action}\n"
    path.write_text(text, encoding="utf-8")


def update_routine(
    workspaces: Path,
    name: str,
    *,
    schedule: str | None = None,
    action: str | None = None,
    title: str | None = None,
    target: str | None = ...,  # type: ignore[assignment]  # sentinel: ... = unchanged
) -> bool:
    """Update an existing routine's schedule, action, target, or title by slug name.

    Returns True if found and updated.  Pass ``target=None`` to explicitly
    clear the target (revert to household group).  Omit ``target`` (or pass
    the ``...`` sentinel) to leave it unchanged.
    """
    if schedule is not None:
        _parse_schedule(schedule)  # validate before modifying file

    path = _routines_path(workspaces)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(^## .+)", text, flags=re.MULTILINE)
    # sections: [preamble, "## heading1", body1, "## heading2", body2, ...]
    found = False
    i = 0
    while i < len(sections):
        part = sections[i]
        if part.startswith("## "):
            heading = part[3:].strip()
            slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
            if slug == name:
                found = True
                # Parse existing body to get current values
                body = sections[i + 1] if i + 1 < len(sections) else ""
                cur_schedule, cur_actions, cur_target = _extract_schedule_and_actions(
                    body.strip().splitlines()
                )
                new_title = title or heading
                new_schedule = schedule or cur_schedule or ""
                new_action = action or ("; ".join(cur_actions) if cur_actions else "")
                new_target = cur_target if target is ... else target

                sections[i] = f"## {new_title}"
                target_line = f"\n- **Target**: {new_target}" if new_target else ""
                sections[i + 1] = (
                    f"\n- **Schedule**: {new_schedule}"
                    f"{target_line}"
                    f"\n- **Action**: {new_action}\n"
                )
                break
        i += 1
    if found:
        path.write_text("".join(sections).rstrip() + "\n", encoding="utf-8")
    return found


def remove_routine(workspaces: Path, name: str) -> bool:
    """Remove a routine by slug name. Returns True if found and removed."""
    path = _routines_path(workspaces)
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8")
    sections = re.split(r"(^## .+)", text, flags=re.MULTILINE)
    # sections: [preamble, "## heading1", body1, "## heading2", body2, ...]
    new_parts: list[str] = []
    found = False
    i = 0
    while i < len(sections):
        part = sections[i]
        if part.startswith("## "):
            heading = part[3:].strip()
            slug = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_")
            if slug == name:
                found = True
                i += 2  # skip heading + body
                continue
        new_parts.append(part)
        i += 1
    if found:
        path.write_text("".join(new_parts).rstrip() + "\n", encoding="utf-8")
    return found
