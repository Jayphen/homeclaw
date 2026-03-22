"""Knowledge stats API — how much does homeclaw know about your household?

Surfaces memory growth, topic distribution, and per-member knowledge depth.
Designed to make the dashboard feel alive by showing the system's understanding
of your household expanding over time.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter

from homeclaw.api.deps import MemberDep, get_config, list_member_workspaces, visible_members
from homeclaw.contacts.store import list_contacts
from homeclaw.memory.status import get_semantic_status

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

# Matches memory entry lines: - [2026-03-22 14:30] content
_ENTRY_RE = re.compile(r"^- \[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]")


def _analyze_person_memory(
    workspaces: Path, person: str,
) -> dict[str, Any]:
    """Analyze one person's memory directory."""
    memory_dir = workspaces / person / "memory"
    topics: list[dict[str, Any]] = []
    total_entries = 0
    earliest_entry: datetime | None = None
    latest_entry: datetime | None = None

    if not memory_dir.is_dir():
        return {
            "person": person,
            "topic_count": 0,
            "total_entries": 0,
            "topics": [],
            "earliest_entry": None,
            "latest_entry": None,
        }

    for f in sorted(memory_dir.iterdir()):
        if f.suffix != ".md":
            continue
        topic = f.stem
        content = f.read_text()
        lines = content.splitlines()

        entry_count = 0
        topic_earliest: datetime | None = None
        topic_latest: datetime | None = None

        for line in lines:
            m = _ENTRY_RE.match(line.strip())
            if not m:
                continue
            entry_count += 1
            try:
                ts = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(
                    tzinfo=UTC,
                )
            except ValueError:
                continue
            if topic_earliest is None or ts < topic_earliest:
                topic_earliest = ts
            if topic_latest is None or ts > topic_latest:
                topic_latest = ts

        total_entries += entry_count

        if topic_earliest and (earliest_entry is None or topic_earliest < earliest_entry):
            earliest_entry = topic_earliest
        if topic_latest and (latest_entry is None or topic_latest > latest_entry):
            latest_entry = topic_latest

        topics.append({
            "name": topic,
            "entries": entry_count,
            "last_updated": topic_latest.isoformat() if topic_latest else None,
            "size_bytes": f.stat().st_size,
        })

    # Sort topics by entry count descending — most active first
    topics.sort(key=lambda t: t["entries"], reverse=True)

    return {
        "person": person,
        "topic_count": len(topics),
        "total_entries": total_entries,
        "topics": topics,
        "earliest_entry": earliest_entry.isoformat() if earliest_entry else None,
        "latest_entry": latest_entry.isoformat() if latest_entry else None,
    }


def _household_stats(workspaces: Path) -> dict[str, Any]:
    """Aggregate household-level knowledge stats."""
    contacts = list_contacts(workspaces)
    total_interactions = sum(len(c.interactions) for c in contacts)
    contacts_with_birthday = sum(1 for c in contacts if c.birthday)
    contacts_with_reminders = sum(1 for c in contacts if c.reminders)

    # Count notes across all members
    total_notes = 0
    members = [
        d.name for d in workspaces.iterdir()
        if d.is_dir() and d.name != "household" and not d.name.startswith(".")
    ]
    for person in members:
        notes_dir = workspaces / person / "notes"
        if notes_dir.is_dir():
            total_notes += sum(
                1 for f in notes_dir.iterdir()
                if f.suffix == ".md" and f.name != "reminders.md"
            )

    # Count bookmarks
    bookmarks_path = workspaces / "household" / "bookmarks" / "bookmarks.json"
    bookmark_count = 0
    if bookmarks_path.exists():
        try:
            data = json.loads(bookmarks_path.read_text())
            bookmark_count = len(data) if isinstance(data, list) else 0
        except (json.JSONDecodeError, OSError):
            pass

    return {
        "contacts": len(contacts),
        "contacts_with_birthday": contacts_with_birthday,
        "contacts_with_reminders": contacts_with_reminders,
        "total_interactions": total_interactions,
        "total_notes": total_notes,
        "total_bookmarks": bookmark_count,
    }


@router.get("")
async def knowledge_stats(
    member: Annotated[str | None, MemberDep],
) -> dict[str, Any]:
    """Knowledge overview — how much does homeclaw know?"""
    config = get_config()
    workspaces = config.workspaces.resolve()
    all_members = list_member_workspaces(workspaces)
    members = visible_members(member, all_members)

    # Per-member memory analysis
    member_knowledge = [_analyze_person_memory(workspaces, m) for m in members]

    # Household memory (shared knowledge)
    household_knowledge = _analyze_person_memory(workspaces, "household")

    # Aggregate totals
    member_topics = sum(m["topic_count"] for m in member_knowledge)
    total_topics = member_topics + household_knowledge["topic_count"]
    member_entries = sum(m["total_entries"] for m in member_knowledge)
    total_entries = member_entries + household_knowledge["total_entries"]

    # Semantic memory status
    semantic_status = get_semantic_status(workspaces)

    # Household-level stats (contacts, notes, bookmarks)
    household = _household_stats(workspaces)

    return {
        "summary": {
            "total_topics": total_topics,
            "total_entries": total_entries,
            "total_contacts": household["contacts"],
            "total_notes": household["total_notes"],
            "total_bookmarks": household["total_bookmarks"],
            "total_interactions": household["total_interactions"],
            "semantic_status": semantic_status,
        },
        "members": member_knowledge,
        "household": household_knowledge,
        "contacts": {
            "total": household["contacts"],
            "with_birthday": household["contacts_with_birthday"],
            "with_reminders": household["contacts_with_reminders"],
        },
    }
