"""Skills API routes — active skill browsing, file editing, and archive management."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw.api.deps import AuthDep, MemberDep, get_config, list_member_workspaces

router = APIRouter(prefix="/api/skills", tags=["skills"])

# The timestamp suffix appended by skill_remove: _YYYYMMDD_HHMMSS (16 chars)
_TIMESTAMP_SUFFIX_LEN = 16


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_relative(base: Path, relative: str) -> Path:
    """Resolve *relative* inside *base*, rejecting path traversal."""
    resolved = (base / relative).resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    return resolved


def _scan_active_skills(workspaces: Path) -> list[dict[str, Any]]:
    """Scan all owner workspaces for active (non-archived) skill directories."""
    from homeclaw.plugins.skills.loader import skill_md_to_definition

    owners = ["household"] + list_member_workspaces(workspaces)
    skills: list[dict[str, Any]] = []

    for owner in owners:
        skills_dir = workspaces / owner / "skills"
        if not skills_dir.is_dir():
            continue
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            skill_md = child / "SKILL.md"
            if not skill_md.is_file():
                continue

            try:
                defn = skill_md_to_definition(skill_md.read_text())
                description = defn.description
                allowed_domains = defn.allowed_domains
            except Exception:
                description = ""
                allowed_domains = []

            # Collect all files in the skill directory
            files: list[dict[str, str]] = []
            for f in sorted(child.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(child))
                    files.append({"path": rel, "size": str(f.stat().st_size)})

            skills.append({
                "name": child.name,
                "owner": owner,
                "description": description,
                "allowed_domains": allowed_domains,
                "file_count": len(files),
                "files": files,
            })

    return skills


# ---------------------------------------------------------------------------
# Active skills — browse and edit
# ---------------------------------------------------------------------------


@router.get("", dependencies=[AuthDep])
async def list_skills() -> dict[str, Any]:
    """List all active skills across all owners."""
    workspaces = get_config().workspaces.resolve()
    return {"skills": _scan_active_skills(workspaces)}


@router.get("/{owner}/{name}", dependencies=[AuthDep])
async def get_skill(owner: str, name: str) -> dict[str, Any]:
    """Get skill metadata and file listing."""
    from homeclaw.plugins.skills.loader import skill_md_to_definition

    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        raise HTTPException(status_code=404, detail="Skill has no SKILL.md")

    defn = skill_md_to_definition(skill_md.read_text())

    files: list[dict[str, str]] = []
    for f in sorted(skill_dir.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(skill_dir))
            files.append({"path": rel, "size": str(f.stat().st_size)})

    return {
        "name": name,
        "owner": owner,
        "description": defn.description,
        "allowed_domains": defn.allowed_domains,
        "instructions": defn.instructions,
        "metadata": defn.metadata,
        "files": files,
    }


@router.get("/{owner}/{name}/files/{file_path:path}", dependencies=[AuthDep])
async def read_skill_file(owner: str, name: str, file_path: str) -> dict[str, Any]:
    """Read the content of a file inside a skill directory."""
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    path = _safe_relative(skill_dir, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = path.read_text()
    except UnicodeDecodeError:
        raise HTTPException(status_code=422, detail="File is not a text file")

    return {
        "path": file_path,
        "content": content,
        "size": path.stat().st_size,
    }


class FileUpdate(BaseModel):
    content: str


@router.put("/{owner}/{name}/files/{file_path:path}", dependencies=[AuthDep])
async def write_skill_file(
    owner: str, name: str, file_path: str, body: FileUpdate,
) -> dict[str, Any]:
    """Write or update a file inside a skill directory."""
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    path = _safe_relative(skill_dir, file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content)

    return {
        "path": file_path,
        "size": len(body.content),
        "status": "written",
    }


@router.delete("/{owner}/{name}/files/{file_path:path}", dependencies=[AuthDep])
async def delete_skill_file(owner: str, name: str, file_path: str) -> dict[str, str]:
    """Delete a file inside a skill directory. Cannot delete SKILL.md."""
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    if file_path == "SKILL.md":
        raise HTTPException(status_code=400, detail="Cannot delete SKILL.md — use skill_remove instead")

    path = _safe_relative(skill_dir, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    path.unlink()
    return {"status": "deleted", "path": file_path}


# ---------------------------------------------------------------------------
# Archives — existing functionality
# ---------------------------------------------------------------------------


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
