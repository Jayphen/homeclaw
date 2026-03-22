"""Skills API routes — active skill browsing, file editing, and archive management."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from homeclaw.api.deps import AdminDep, AuthDep, MemberDep, get_config, list_member_workspaces

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _load_env(skill_dir: Path) -> dict[str, str]:
    """Load .env from skill dir for dep checking."""
    from homeclaw.plugins.skills.loader import _load_skill_env
    return _load_skill_env(skill_dir)


def _check_deps(
    metadata: dict[str, Any], skill_env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Check skill deps, return result only if something is missing."""
    from homeclaw.plugins.skills.deps import check_skill_deps

    deps = check_skill_deps(metadata, skill_env=skill_env)
    if deps["satisfied"]:
        return None
    return deps

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

            parse_error: str | None = None
            try:
                defn = skill_md_to_definition(skill_md.read_text())
                description = defn.description
                allowed_domains = defn.allowed_domains
            except Exception as exc:
                description = ""
                allowed_domains = []
                parse_error = str(exc)

            # Collect all files in the skill directory
            files: list[dict[str, str]] = []
            for f in sorted(child.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(child))
                    files.append({"path": rel, "size": str(f.stat().st_size)})

            entry: dict[str, Any] = {
                "name": child.name,
                "owner": owner,
                "description": description,
                "allowed_domains": allowed_domains,
                "file_count": len(files),
                "files": files,
            }
            if parse_error:
                entry["parse_error"] = parse_error
            skills.append(entry)

    return skills


# ---------------------------------------------------------------------------
# Skill settings
# ---------------------------------------------------------------------------


@router.get("/settings", dependencies=[AuthDep])
async def get_skill_settings() -> dict[str, Any]:
    config = get_config()
    return {
        "skill_approval_required": config.skill_approval_required,
        "skill_allow_local_network": config.skill_allow_local_network,
    }


class SkillSettingsUpdate(BaseModel):
    skill_approval_required: bool | None = None
    skill_allow_local_network: bool | None = None


@router.put("/settings", dependencies=[AdminDep])
async def update_skill_settings(body: SkillSettingsUpdate) -> dict[str, Any]:
    config = get_config()
    if body.skill_approval_required is not None:
        config.skill_approval_required = body.skill_approval_required
    if body.skill_allow_local_network is not None:
        config.skill_allow_local_network = body.skill_allow_local_network
    await config.save_async()
    return {
        "skill_approval_required": config.skill_approval_required,
        "skill_allow_local_network": config.skill_allow_local_network,
    }



# ---------------------------------------------------------------------------
# Delete (archive) a skill
# ---------------------------------------------------------------------------


@router.delete("/{owner}/{name}", dependencies=[AdminDep])
async def delete_skill(owner: str, name: str) -> dict[str, Any]:
    """Archive (soft-delete) an active skill."""
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    archive_root = workspaces / owner / "skills" / ".archive"
    archive_root.mkdir(parents=True, exist_ok=True)
    archive_dir = archive_root / f"{name}_{timestamp}"

    shutil.move(str(skill_dir), str(archive_dir))

    # Unregister from plugin registry
    from homeclaw.api.deps import get_plugin_registry

    registry = get_plugin_registry()
    if registry is not None:
        registry.unregister(name)

    return {
        "status": "archived",
        "name": name,
        "owner": owner,
        "archive_path": str(archive_dir),
    }


# ---------------------------------------------------------------------------
# Install skill from URL
# ---------------------------------------------------------------------------


class SkillInstallRequest(BaseModel):
    url: str
    scope: str = "household"


@router.post("/install", dependencies=[AdminDep])
async def install_skill_from_url(body: SkillInstallRequest) -> dict[str, Any]:
    """Install a skill from a GitHub repo, gist, or direct SKILL.md URL."""
    import httpx

    from homeclaw.plugins.skills.github import (
        download_skill_repo,
        normalize_gist_url,
        raw_skill_md_url,
    )
    from homeclaw.plugins.skills.loader import load_skill, skill_md_to_definition

    workspaces = get_config().workspaces.resolve()

    # Normalize URL to a fetchable SKILL.md
    original_url = body.url.strip()
    skill_md_url = raw_skill_md_url(original_url)
    is_github_repo = skill_md_url is not None
    if skill_md_url is None:
        skill_md_url = normalize_gist_url(original_url) or original_url
    url = skill_md_url

    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content = resp.text
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch: HTTP {e.response.status_code}")
    except httpx.RequestError as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch: {e}")

    try:
        defn = skill_md_to_definition(content)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid SKILL.md: {e}")

    from homeclaw.pathutil import safe_slug

    slug = safe_slug(defn.name)
    owner = "household" if body.scope == "household" else body.scope
    skill_dir = workspaces / owner / "skills" / slug

    if skill_dir.exists():
        raise HTTPException(status_code=409, detail=f"Skill '{slug}' already exists")

    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)

    # Download additional files from GitHub repos (scripts, references, etc.)
    if is_github_repo:
        await download_skill_repo(original_url, skill_dir)

    # Hot-load
    from homeclaw.api.deps import get_plugin_registry
    from homeclaw.plugins.registry import PluginType

    registry = get_plugin_registry()
    loaded = False
    if registry is not None:
        try:
            allow_local = get_config().skill_allow_local_network
            plugin = load_skill(skill_dir, owner, allow_local_network=allow_local)
            registry.register(plugin, PluginType.SKILL)
            loaded = True
        except Exception:
            pass

    from homeclaw.plugins.skills.deps import check_skill_deps

    deps = check_skill_deps(defn.metadata)
    result: dict[str, Any] = {
        "status": "installed",
        "name": slug,
        "description": defn.description,
        "scope": body.scope,
        "loaded": loaded,
    }
    if not deps["satisfied"]:
        result["deps"] = deps
    return result


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

    files: list[dict[str, str]] = []
    for f in sorted(skill_dir.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(skill_dir))
            files.append({"path": rel, "size": str(f.stat().st_size)})

    if not skill_md.is_file():
        return {
            "name": name,
            "owner": owner,
            "description": "",
            "allowed_domains": [],
            "instructions": "",
            "metadata": {},
            "compatibility": None,
            "files": files,
            "deps": None,
            "parse_error": "Skill has no SKILL.md",
        }

    try:
        defn = skill_md_to_definition(skill_md.read_text())
    except ValueError as exc:
        return {
            "name": name,
            "owner": owner,
            "description": "",
            "allowed_domains": [],
            "instructions": "",
            "metadata": {},
            "compatibility": None,
            "files": files,
            "deps": None,
            "parse_error": str(exc),
        }

    return {
        "name": name,
        "owner": owner,
        "description": defn.description,
        "allowed_domains": defn.allowed_domains,
        "instructions": defn.instructions,
        "metadata": defn.metadata,
        "compatibility": defn.compatibility,
        "files": files,
        "deps": _check_deps(defn.metadata, _load_env(skill_dir)),
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

    # Validate SKILL.md before saving
    validation_error: str | None = None
    if file_path == "SKILL.md":
        from homeclaw.plugins.skills.loader import skill_md_to_definition

        try:
            skill_md_to_definition(body.content)
        except ValueError as exc:
            validation_error = str(exc)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body.content)

    result: dict[str, Any] = {
        "path": file_path,
        "size": len(body.content),
        "status": "written",
    }
    if validation_error:
        result["validation_error"] = validation_error
    return result


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
