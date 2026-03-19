"""Settings API routes — system configuration."""

from typing import Any

from fastapi import APIRouter

from homeclaw.api.deps import AdminDep, get_config
from homeclaw.api.logbuffer import get_log_buffer
from homeclaw.memory.status import get_semantic_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", dependencies=[AdminDep])
async def get_settings() -> dict[str, Any]:
    config = get_config()
    return {
        "semantic_status": get_semantic_status(config.workspaces.resolve()),
    }


@router.get("/logs", dependencies=[AdminDep])
async def get_logs(limit: int = 200, level: str | None = None) -> dict[str, Any]:
    """Return recent application log entries from the in-memory buffer."""
    buf = get_log_buffer()
    if buf is None:
        return {"entries": [], "note": "Log buffer not initialized"}
    return {"entries": buf.get_entries(limit=min(limit, 500), level=level)}
