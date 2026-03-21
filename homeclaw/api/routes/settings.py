"""Settings API routes — system configuration."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter
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
