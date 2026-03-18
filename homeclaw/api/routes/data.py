"""Data export/import API routes — full household backup and restore."""

import io
import json
import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from homeclaw import HOUSEHOLD_WORKSPACE
from homeclaw.api.deps import SKIP_EXPORT_NAMES, AuthDep, get_config, list_member_workspaces

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/data", tags=["data"])

# Re-use the shared skip set from deps for consistency.
_SKIP_NAMES = SKIP_EXPORT_NAMES

# Maximum upload size: 100 MB.
_MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _build_zip(workspaces: Path) -> io.BytesIO:
    """Walk the workspaces directory and pack exportable files into a ZIP."""
    buf = io.BytesIO()
    members = list_member_workspaces(workspaces)

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Metadata
        meta: dict[str, Any] = {
            "exported_at": datetime.now(UTC).isoformat(),
            "version": "1",
            "members": members,
        }
        zf.writestr("metadata.json", json.dumps(meta, indent=2))

        # Walk the workspaces tree
        for path in sorted(workspaces.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(workspaces)
            # Skip excluded names at any level
            if any(part in _SKIP_NAMES for part in rel.parts):
                continue
            # Skip hidden directories
            if any(part.startswith(".") for part in rel.parts):
                continue
            # Skip plugin directories (code, not data)
            if rel.parts[0] == "plugins":
                continue
            arcname = str(rel)
            zf.write(path, arcname)

    buf.seek(0)
    return buf


def _restore_zip(workspaces: Path, zf: zipfile.ZipFile) -> dict[str, Any]:
    """Extract a ZIP archive into the workspaces directory.

    Returns summary statistics about what was imported.
    """
    stats: dict[str, int] = {
        "files_written": 0,
        "files_skipped": 0,
    }
    members_seen: set[str] = set()

    for info in zf.infolist():
        # Skip directories and metadata
        if info.is_dir() or info.filename == "metadata.json":
            continue

        # Safety: reject paths that escape workspaces
        cleaned = Path(info.filename)
        if cleaned.is_absolute() or ".." in cleaned.parts:
            stats["files_skipped"] += 1
            logger.warning("Skipping unsafe path in archive: %s", info.filename)
            continue

        # Skip hidden/excluded
        if any(part in _SKIP_NAMES for part in cleaned.parts):
            stats["files_skipped"] += 1
            continue
        if any(part.startswith(".") for part in cleaned.parts):
            stats["files_skipped"] += 1
            continue

        dest = workspaces / cleaned
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(zf.read(info.filename))
        stats["files_written"] += 1

        # Track members
        if len(cleaned.parts) >= 1 and cleaned.parts[0] != HOUSEHOLD_WORKSPACE:
            members_seen.add(cleaned.parts[0])

    return {
        **stats,
        "members_imported": sorted(members_seen),
    }


@router.get("/export", dependencies=[AuthDep])
async def export_data() -> StreamingResponse:
    """Export all household data as a ZIP archive."""
    workspaces = get_config().workspaces.resolve()
    if not workspaces.is_dir():
        raise HTTPException(status_code=404, detail="No workspace data found")

    buf = _build_zip(workspaces)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    filename = f"homeclaw-export-{timestamp}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", dependencies=[AuthDep])
async def import_data(file: UploadFile) -> dict[str, Any]:
    """Import household data from a previously exported ZIP archive.

    Overwrites existing files if they conflict with the archive contents.
    """
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Upload must be a .zip file")

    content = await file.read()
    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds maximum size of {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="Invalid ZIP file") from exc

    # Validate: must contain metadata.json
    if "metadata.json" not in zf.namelist():
        raise HTTPException(
            status_code=400,
            detail="Not a valid homeclaw export (missing metadata.json)",
        )

    workspaces = get_config().workspaces.resolve()
    workspaces.mkdir(parents=True, exist_ok=True)

    result = _restore_zip(workspaces, zf)
    logger.info("Data import complete: %s", result)
    return {"status": "ok", **result}
