"""Skills API routes — archived skill management."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from homeclaw.api.deps import AuthDep, get_config, list_member_workspaces

router = APIRouter(prefix="/api/skills", tags=["skills"])

# The timestamp suffix appended by skill_remove: _YYYYMMDD_HHMMSS (16 chars)
_TIMESTAMP_SUFFIX_LEN = 16


def _parse_archive_dir(owner: str, archive_dir: Path) -> dict[str, Any] | None:
    """Parse an archive directory into a metadata dict. Returns None if invalid."""
    name_ts = archive_dir.name
    if len(name_ts) <= _TIMESTAMP_SUFFIX_LEN:
        return None

    skill_name = name_ts[:-_TIMESTAMP_SUFFIX_LEN]
    ts_str = name_ts[-15:]  # YYYYMMDD_HHMMSS

    try:
        archived_at = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    files = sorted(
        str(p.relative_to(archive_dir))
        for p in archive_dir.rglob("*")
        if p.is_file()
    )

    return {
        "id": name_ts,
        "name": skill_name,
        "owner": owner,
        "archived_at": archived_at.isoformat(),
        "file_count": len(files),
        "files": files,
    }


def _scan_archives(workspaces: Path) -> list[dict[str, Any]]:
    """Scan all owner workspaces for archived skill directories."""
    owners = ["household"] + list_member_workspaces(workspaces)
    archives: list[dict[str, Any]] = []

    for owner in owners:
        archive_root = workspaces / owner / "skills" / ".archive"
        if not archive_root.is_dir():
            continue
        for child in sorted(archive_root.iterdir()):
            if child.is_dir():
                entry = _parse_archive_dir(owner, child)
                if entry:
                    archives.append(entry)

    archives.sort(key=lambda a: a["archived_at"], reverse=True)
    return archives


@router.get("/archives", dependencies=[AuthDep])
async def list_archives() -> dict[str, Any]:
    """List all archived skills across all owners."""
    workspaces = get_config().workspaces.resolve()
    return {"archives": _scan_archives(workspaces)}


@router.delete("/archives/{owner}/{archive_id}", dependencies=[AuthDep])
async def delete_archive(owner: str, archive_id: str) -> dict[str, str]:
    """Permanently delete an archived skill. This cannot be undone."""
    workspaces = get_config().workspaces.resolve()
    archive_dir = workspaces / owner / "skills" / ".archive" / archive_id

    if not archive_dir.exists() or not archive_dir.is_dir():
        raise HTTPException(status_code=404, detail="Archive not found")

    # Safety: ensure the resolved path is still inside the expected archive root
    expected_root = (workspaces / owner / "skills" / ".archive").resolve()
    if not archive_dir.resolve().is_relative_to(expected_root):
        raise HTTPException(status_code=400, detail="Invalid archive path")

    shutil.rmtree(archive_dir)
    return {"status": "deleted", "id": archive_id}


@router.post("/archives/{owner}/{archive_id}/restore", dependencies=[AuthDep])
async def restore_archive(owner: str, archive_id: str) -> dict[str, Any]:
    """Restore an archived skill back to its active location.

    The skill will be available after the next server restart (hot-loading
    is not yet supported via the API).
    """
    workspaces = get_config().workspaces.resolve()
    archive_dir = workspaces / owner / "skills" / ".archive" / archive_id

    if not archive_dir.exists() or not archive_dir.is_dir():
        raise HTTPException(status_code=404, detail="Archive not found")

    expected_root = (workspaces / owner / "skills" / ".archive").resolve()
    if not archive_dir.resolve().is_relative_to(expected_root):
        raise HTTPException(status_code=400, detail="Invalid archive path")

    if len(archive_id) <= _TIMESTAMP_SUFFIX_LEN:
        raise HTTPException(status_code=400, detail="Invalid archive ID")

    skill_name = archive_id[:-_TIMESTAMP_SUFFIX_LEN]
    restore_dir = workspaces / owner / "skills" / skill_name

    if restore_dir.exists():
        raise HTTPException(
            status_code=409,
            detail=f"A skill named '{skill_name}' already exists under '{owner}'. Remove it first.",
        )

    restore_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(archive_dir), str(restore_dir))

    return {
        "status": "restored",
        "name": skill_name,
        "owner": owner,
        "skill_dir": str(restore_dir),
        "note": "Skill restored to disk. It will be active after the next server restart.",
    }
