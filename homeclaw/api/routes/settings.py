"""Settings API routes — system configuration."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

from homeclaw.api.deps import AdminDep, get_config
from homeclaw.api.logbuffer import get_log_buffer, get_log_entries_from_file
from homeclaw.memory.status import get_semantic_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", dependencies=[AdminDep])
async def get_settings() -> dict[str, Any]:
    config = get_config()
    return {
        "semantic_status": get_semantic_status(config.workspaces.resolve()),
    }


@router.get("/logs", dependencies=[AdminDep])
async def get_logs(
    limit: int = 200,
    level: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    """Return log entries. Uses file when date range given, buffer otherwise."""
    if after or before:
        entries = get_log_entries_from_file(
            after=after, before=before, level=level,
            search=search, limit=min(limit, 5000),
        )
        return {"entries": entries, "source": "file"}
    buf = get_log_buffer()
    if buf is None:
        return {"entries": [], "note": "Log buffer not initialized"}
    return {"entries": buf.get_entries(limit=min(limit, 500), level=level)}


@router.get("/logs/download", dependencies=[AdminDep])
async def download_logs(
    level: str | None = None,
    after: datetime | None = None,
    before: datetime | None = None,
    search: str | None = None,
    limit: int = 5000,
) -> PlainTextResponse:
    """Download filtered log entries as a text file."""
    entries = get_log_entries_from_file(
        after=after, before=before, level=level,
        search=search, limit=min(limit, 10000),
    )
    lines = [
        f"{e['ts']}  {e['level']:<7}  {e['logger']}  {e['message']}"
        for e in entries
    ]
    content = "\n".join(lines) + "\n" if lines else "No log entries.\n"
    return PlainTextResponse(
        content,
        headers={
            "Content-Disposition": 'attachment; filename="homeclaw-logs.txt"',
        },
    )


def _read_tool_log(
    log_path: Path,
    days: int = 7,
    tool: str | None = None,
    person: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Read raw tool_use.jsonl entries with full args."""
    if not log_path.exists():
        return []
    since = datetime.now(UTC) - timedelta(days=days)
    entries: list[dict[str, Any]] = []
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
            if tool and entry.get("tool") != tool:
                continue
            if person and entry.get("person") != person:
                continue
            entries.append(entry)
    except OSError:
        return []
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    return entries[:limit]


@router.get("/tool-log", dependencies=[AdminDep])
async def get_tool_log(
    days: int = Query(default=7, ge=1, le=90, description="Lookback window in days"),
    tool: str | None = Query(default=None, description="Filter by tool name"),
    person: str | None = Query(default=None, description="Filter by person"),
    limit: int = Query(default=200, ge=1, le=1000, description="Max entries"),
) -> dict[str, Any]:
    """Admin tool call log — raw entries from tool_use.jsonl with full args."""
    config = get_config()
    log_path = config.workspaces.resolve() / "household" / "logs" / "tool_use.jsonl"
    entries = _read_tool_log(log_path, days=days, tool=tool, person=person, limit=limit)
    # Collect unique tool names for filter dropdown
    tools_seen: set[str] = set()
    persons_seen: set[str] = set()
    for e in entries:
        if t := e.get("tool"):
            tools_seen.add(t)
        if p := e.get("person"):
            persons_seen.add(p)
    return {
        "entries": entries,
        "total": len(entries),
        "tools": sorted(tools_seen),
        "persons": sorted(persons_seen),
    }
