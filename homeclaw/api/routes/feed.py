"""Activity feed API — unified timeline of what homeclaw has been doing.

Merges events from multiple sources into a single chronological stream:
- Memory saves (new knowledge learned)
- Routine executions (scheduled tasks completed)
- Contact interactions (logged by the agent)
- Notes written (daily note updates)
- Reminders fired (upcoming/completed)
- Messages sent (outbound via channel dispatcher)

Each event has: timestamp, type, summary, person (if applicable), and
optional detail payload.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query

from homeclaw.api.deps import MemberDep, get_config, list_member_workspaces, visible_members
from homeclaw.contacts.store import list_contacts

router = APIRouter(prefix="/api/feed", tags=["feed"])

EventType = Literal[
    "memory_save",
    "routine_run",
    "interaction",
    "note_update",
    "cost_spike",
    "tool_use",
]


def _memory_events(
    workspaces: Path, members: list[str], since: datetime,
) -> list[dict[str, Any]]:
    """Scan memory files for entries added since the cutoff.

    Memory entries are formatted as: - [YYYY-MM-DD HH:MM] content
    We parse the timestamps to filter recent entries.
    """
    events: list[dict[str, Any]] = []
    for person in members:
        memory_dir = workspaces / person / "memory"
        if not memory_dir.is_dir():
            continue
        for f in memory_dir.iterdir():
            if f.suffix != ".md":
                continue
            topic = f.stem
            for line in f.read_text().splitlines():
                line = line.strip()
                if not line.startswith("- ["):
                    continue
                # Parse: - [2026-03-22 14:30] content here
                bracket_end = line.find("]", 3)
                if bracket_end == -1:
                    continue
                ts_str = line[3:bracket_end]
                try:
                    ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M").replace(
                        tzinfo=UTC,
                    )
                except ValueError:
                    continue
                if ts < since:
                    continue
                content = line[bracket_end + 1 :].strip()
                events.append({
                    "ts": ts.isoformat(),
                    "type": "memory_save",
                    "summary": f"Learned about {topic}",
                    "detail": content[:200],
                    "person": person,
                    "meta": {"topic": topic},
                })
    return events


def _routine_events(
    workspaces: Path, since: datetime,
) -> list[dict[str, Any]]:
    """Read routine last-run timestamps to find recent executions."""
    last_run_path = workspaces / "household" / ".routine_last_run.json"
    if not last_run_path.exists():
        return []
    try:
        data: dict[str, str] = json.loads(last_run_path.read_text())
    except (json.JSONDecodeError, OSError):
        return []

    events: list[dict[str, Any]] = []
    for job_id, ts_str in data.items():
        try:
            ts = datetime.fromisoformat(ts_str)
        except ValueError:
            continue
        if ts < since:
            continue
        # Clean up job_id for display: "routine:morning-check" -> "Morning check"
        name = job_id.split(":", 1)[-1].replace("-", " ").replace("_", " ").capitalize()
        events.append({
            "ts": ts.isoformat(),
            "type": "routine_run",
            "summary": f"Ran routine: {name}",
            "detail": None,
            "person": None,
            "meta": {"job_id": job_id},
        })
    return events


def _interaction_events(
    workspaces: Path, since: datetime,
) -> list[dict[str, Any]]:
    """Pull recent contact interactions."""
    contacts = list_contacts(workspaces)
    events: list[dict[str, Any]] = []
    for c in contacts:
        for ix in c.interactions:
            if ix.date < since:
                continue
            events.append({
                "ts": ix.date.isoformat(),
                "type": "interaction",
                "summary": f"{ix.type.capitalize()} with {c.name}",
                "detail": ix.notes[:200] if ix.notes else None,
                "person": None,
                "meta": {"contact": c.name, "interaction_type": ix.type},
            })
    return events


def _note_events(
    workspaces: Path, members: list[str], since: datetime,
) -> list[dict[str, Any]]:
    """Find notes updated since the cutoff."""
    events: list[dict[str, Any]] = []
    for person in members:
        notes_dir = workspaces / person / "notes"
        if not notes_dir.is_dir():
            continue
        for f in notes_dir.iterdir():
            if f.suffix != ".md" or f.name == "reminders.md":
                continue
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=UTC)
            if mtime < since:
                continue
            # Read first non-empty line as preview
            content = f.read_text().strip()
            preview = ""
            for line in content.splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    preview = line[:120]
                    break
            events.append({
                "ts": mtime.isoformat(),
                "type": "note_update",
                "summary": f"{person}'s note for {f.stem}",
                "detail": preview or None,
                "person": person,
                "meta": {"date": f.stem},
            })
    return events


def _tool_use_events(
    workspaces: Path, since: datetime,
) -> list[dict[str, Any]]:
    """Read tool use events from the JSONL log."""
    log_path = workspaces / "household" / "logs" / "tool_use.jsonl"
    if not log_path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        for line in log_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_str = entry.get("ts", "")
            try:
                ts = datetime.fromisoformat(ts_str)
            except (ValueError, TypeError):
                continue
            if ts < since:
                continue
            events.append({
                "ts": ts.isoformat(),
                "type": "tool_use",
                "summary": entry.get("summary", f"Used {entry.get('tool', '?')}"),
                "detail": None,
                "person": entry.get("person"),
                "meta": {"tool": entry.get("tool", "")},
            })
    except OSError:
        pass
    return events


@router.get("")
async def activity_feed(
    member: Annotated[str | None, MemberDep],
    days: int = Query(default=3, ge=1, le=30, description="Lookback window in days"),
    limit: int = Query(default=30, ge=1, le=100, description="Max events to return"),
) -> dict[str, Any]:
    """Unified activity feed — most recent household events."""
    config = get_config()
    workspaces = config.workspaces.resolve()
    all_members = list_member_workspaces(workspaces)
    members = visible_members(member, all_members)
    since = datetime.now(UTC) - timedelta(days=days)

    # Gather events from all sources
    events: list[dict[str, Any]] = []
    events.extend(_memory_events(workspaces, members, since))
    events.extend(_routine_events(workspaces, since))
    events.extend(_interaction_events(workspaces, since))
    events.extend(_note_events(workspaces, members, since))
    events.extend(_tool_use_events(workspaces, since))

    # Sort by timestamp descending (most recent first)
    events.sort(key=lambda e: e["ts"], reverse=True)

    # Count by type for summary stats
    type_counts: dict[str, int] = {}
    for e in events:
        type_counts[e["type"]] = type_counts.get(e["type"], 0) + 1

    return {
        "events": events[:limit],
        "total": len(events),
        "type_counts": type_counts,
        "since": since.isoformat(),
    }
