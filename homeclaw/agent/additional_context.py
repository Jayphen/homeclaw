"""Per-turn additional context envelope for user messages."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel

_ADDITIONAL_CONTEXT_RE = re.compile(
    r"\s*<additional_context>[\s\S]*?</additional_context>",
    re.MULTILINE,
)

_FIELD_TAGS: tuple[tuple[str, str], ...] = (
    ("current_time", "current_time"),
    ("current_time_zone", "current_time_zone"),
    ("channel", "channel"),
    ("sender", "sender"),
    ("household_members", "household_members"),
    ("active_reminders", "active_reminders"),
    ("skills_available", "skills_available"),
    ("memory_facts", "memory_facts"),
    ("recent_routines", "recent_routines"),
)

_MAX_TABLE_ROWS = 20


class AdditionalContext(BaseModel):
    """Structured context appended to a single user turn."""

    current_time: str = ""
    current_time_zone: str = ""
    channel: str = ""
    sender: str = ""
    household_members: str = ""
    active_reminders: str = ""
    skills_available: str = ""
    memory_facts: str = ""
    recent_routines: str = ""

    def render(self) -> str:
        """Render non-empty fields as an XML-tagged envelope."""
        parts: list[str] = []
        for field_name, tag in _FIELD_TAGS:
            value = getattr(self, field_name)
            if not value:
                continue
            parts.append(f"<{tag}>\n{escape(value.strip(), quote=False)}\n</{tag}>")
        if not parts:
            return ""
        body = "\n".join(parts)
        return f"<additional_context>\n{body}\n</additional_context>"


def strip_additional_context(text: str) -> str:
    """Remove appended additional_context envelopes from visible text."""
    return _ADDITIONAL_CONTEXT_RE.sub("", text).strip()


def append_additional_context_to_text(text: str, context: AdditionalContext) -> str:
    """Append rendered additional context after the user-visible text."""
    rendered = context.render()
    if not rendered:
        return text
    return f"{text.strip()}\n\n{rendered}" if text.strip() else rendered


def build_additional_context(
    *,
    workspaces: Path,
    person: str,
    channel_label: str | None,
    include_sender: bool,
    now: datetime | None = None,
) -> AdditionalContext:
    """Build the non-duplicative per-turn context envelope."""
    current_time, time_zone = _current_time_fields(workspaces, now)
    return AdditionalContext(
        current_time=current_time,
        current_time_zone=time_zone,
        channel=channel_label or "",
        sender=person.lower() if include_sender else "",
        recent_routines=_recent_routines(workspaces, now or datetime.now().astimezone()),
    )


def _current_time_fields(workspaces: Path, now: datetime | None) -> tuple[str, str]:
    configured_zone = _configured_timezone(workspaces)
    tz: ZoneInfo | None = None
    if configured_zone:
        try:
            tz = ZoneInfo(configured_zone)
        except ZoneInfoNotFoundError:
            tz = None

    if tz is not None:
        local_now = (now or datetime.now(tz)).astimezone(tz)
        return local_now.strftime("%Y-%m-%d %H:%M %Z"), configured_zone or ""

    local_now = now or datetime.now().astimezone()
    env_tz = os.environ.get("TZ", "")
    iana_zone = env_tz if "/" in env_tz else ""
    return local_now.strftime("%Y-%m-%d %H:%M %Z"), iana_zone


def _configured_timezone(workspaces: Path) -> str:
    path = workspaces / "config.json"
    if not path.is_file():
        return ""
    try:
        value = json.loads(path.read_text()).get("timezone", "")
    except (json.JSONDecodeError, OSError):
        return ""
    return value if isinstance(value, str) else ""


def _recent_routines(workspaces: Path, now: datetime) -> str:
    if now.tzinfo is None:
        now = now.astimezone()

    path = workspaces / "household" / ".routine_last_run.json"
    if not path.is_file():
        return ""
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return ""
    if not isinstance(data, dict):
        return ""

    since = now - timedelta(hours=6)
    rows: list[tuple[datetime, str]] = []
    for job_id, ts_value in data.items():
        if not isinstance(job_id, str) or not isinstance(ts_value, str):
            continue
        try:
            fired_at = datetime.fromisoformat(ts_value)
        except ValueError:
            continue
        if fired_at.tzinfo is None:
            fired_at = fired_at.astimezone()
        if fired_at < since:
            continue
        rows.append((fired_at, _routine_label(job_id)))

    rows.sort(key=lambda row: row[0], reverse=True)
    if not rows:
        return ""

    table_rows = [
        (
            name,
            fired_at.astimezone(now.tzinfo).strftime("%Y-%m-%d %H:%M %Z"),
        )
        for fired_at, name in rows
    ]
    return _markdown_table(("routine", "fired"), table_rows)


def _routine_label(job_id: str) -> str:
    label = job_id.split(":", 1)[-1]
    return label.replace("-", " ").replace("_", " ").capitalize()


def _markdown_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    visible_rows = rows[:_MAX_TABLE_ROWS]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in visible_rows:
        lines.append("| " + " | ".join(_table_cell(cell) for cell in row) + " |")
    hidden = len(rows) - len(visible_rows)
    if hidden > 0:
        filler = [""] * (len(headers) - 1)
        lines.append("| " + " | ".join([f"+{hidden} more", *filler]) + " |")
    return "\n".join(lines)


def _table_cell(value: str) -> str:
    return value.replace("\n", " ").replace("|", "\\|").strip()
