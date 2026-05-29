"""Skills API routes — active skill browsing, file editing, and archive management."""

from __future__ import annotations

import mimetypes
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from homeclaw.api.deps import AdminDep, AuthDep, get_config, list_member_workspaces

router = APIRouter(prefix="/api/skills", tags=["skills"])


def _load_env(skill_dir: Path) -> dict[str, str]:
    """Load .env from skill dir for dep checking."""
    from homeclaw.plugins.skills.loader import _load_skill_env

    return _load_skill_env(skill_dir)


def _check_deps(
    metadata: dict[str, Any],
    skill_env: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    """Check skill deps, return result only if something is missing."""
    from homeclaw.plugins.skills.deps import check_skill_deps

    deps = check_skill_deps(metadata, skill_env=skill_env)
    if deps["satisfied"]:
        return None
    return deps


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_env(env_file: Path) -> list[tuple[str, str]]:
    """Parse a .env file into (key, value) pairs."""
    entries: list[tuple[str, str]] = []
    if env_file.is_file():
        for line in env_file.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            entries.append((key.strip(), value.strip()))
    return entries


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
            ui_app: dict[str, Any] | None = None
            try:
                defn = skill_md_to_definition(skill_md.read_text())
                description = defn.description
                allowed_domains = defn.allowed_domains
                ui_app = defn.ui_app.model_dump() if defn.ui_app else None
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
                "ui_app": ui_app,
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

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
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
    install_all: bool = False


@router.get("/list-remote", dependencies=[AuthDep])
async def list_remote_skills(url: str) -> dict[str, Any]:
    """Discover skills available at a GitHub repo URL."""
    from homeclaw.plugins.skills.github import list_repo_skills, parse_github_url

    if parse_github_url(url.strip()) is None:
        raise HTTPException(status_code=400, detail="Not a recognised GitHub URL")

    skills = await list_repo_skills(url.strip())
    return {"url": url.strip(), "skills": skills}


async def _install_single_skill(
    url: str,
    scope: str,
    workspaces: Path,
) -> dict[str, Any]:
    """Install a single skill from a URL that points at one SKILL.md."""
    import httpx

    from homeclaw.plugins.skills.github import (
        download_skill_repo,
        normalize_gist_url,
        raw_skill_md_url,
    )
    from homeclaw.plugins.skills.loader import load_skill, skill_md_to_definition

    original_url = url
    skill_md_url = raw_skill_md_url(original_url)
    is_github_repo = skill_md_url is not None
    if skill_md_url is None:
        skill_md_url = normalize_gist_url(original_url) or original_url

    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(skill_md_url)
            resp.raise_for_status()
            content = resp.text
    except httpx.HTTPStatusError as e:
        return {"error": f"Failed to fetch: HTTP {e.response.status_code}"}
    except httpx.RequestError as e:
        return {"error": f"Failed to fetch: {e}"}

    try:
        defn = skill_md_to_definition(content)
    except ValueError as e:
        return {"error": f"Invalid SKILL.md: {e}"}

    from homeclaw.pathutil import safe_slug

    slug = safe_slug(defn.name)
    owner = "household" if scope == "household" else scope
    skill_dir = workspaces / owner / "skills" / slug

    if skill_dir.exists():
        return {"error": f"Skill '{slug}' already exists", "name": slug}

    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)

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
        "scope": scope,
        "loaded": loaded,
    }
    if not deps["satisfied"]:
        result["deps"] = deps
    return result


@router.post("/install", dependencies=[AdminDep])
async def install_skill_from_url(body: SkillInstallRequest) -> dict[str, Any]:
    """Install skill(s) from a GitHub repo, gist, or direct SKILL.md URL.

    For multi-skill repos (no root SKILL.md), returns the list of available
    skills unless ``install_all`` is true.
    """
    import httpx

    from homeclaw.plugins.skills.github import (
        list_repo_skills,
        parse_github_url,
        raw_skill_md_url,
        skill_subpath_url,
    )

    workspaces = get_config().workspaces.resolve()
    original_url = body.url.strip()
    is_github_repo = parse_github_url(original_url) is not None

    # Try fetching SKILL.md at the target path first
    skill_md_url = raw_skill_md_url(original_url) if is_github_repo else None
    has_root_skill = False
    if skill_md_url is not None:
        try:
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(timeout=30, transport=transport) as client:
                resp = await client.get(skill_md_url)
                has_root_skill = resp.status_code == 200
        except httpx.RequestError:
            pass

    # Single-skill case: SKILL.md found at target, or not a GitHub repo
    if has_root_skill or not is_github_repo:
        result = await _install_single_skill(original_url, body.scope, workspaces)
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        return result

    # Multi-skill case: no root SKILL.md, discover subdirectories
    available = await list_repo_skills(original_url)
    if not available:
        raise HTTPException(
            status_code=404,
            detail="No SKILL.md files found in this repository",
        )

    if not body.install_all:
        return {
            "status": "multiple_skills",
            "url": original_url,
            "skills": available,
            "hint": "Set install_all=true to install all, or use a more specific URL",
        }

    # Install all discovered skills
    results: list[dict[str, Any]] = []
    for skill_info in available:
        sub_url = skill_subpath_url(original_url, skill_info["path"])
        result = await _install_single_skill(sub_url, body.scope, workspaces)
        results.append(result)

    installed = [r for r in results if r.get("status") == "installed"]
    errors = [r for r in results if "error" in r]
    return {
        "status": "installed_multiple",
        "installed": installed,
        "errors": errors,
        "total": len(results),
    }


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
        "ui_app": defn.ui_app.model_dump() if defn.ui_app else None,
    }


class DbQuery(BaseModel):
    sql: str
    params: list[Any] | None = None


@router.post("/{owner}/{name}/db/query", dependencies=[AuthDep])
async def skill_db_query(owner: str, name: str, body: DbQuery) -> dict[str, Any]:
    """Run a read-only SELECT query against a skill's SQLite database.

    Intended for Arrow.js web UIs that need to display skill data without
    loading the full dataset.
    """
    import sqlite3

    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    db_path = skill_dir / "data" / f"{name}.db"
    if not db_path.is_file():
        raise HTTPException(status_code=404, detail="No database found for this skill")

    sql_upper = body.sql.strip().upper()
    if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
        raise HTTPException(
            status_code=400,
            detail="Only SELECT queries are allowed from the API",
        )

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(body.sql, body.params or [])
            rows = [dict(row) for row in cur.fetchall()]
            return {"rows": rows, "count": len(rows)}
        finally:
            conn.close()
    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


def read_db_schema(db_path: Path) -> list[dict[str, Any]]:
    """Return ``[{name, columns: [{name, type, notnull, pk}]}]`` for a sqlite db.

    Shared by the HTTP endpoint and the ``skill_db_schema`` agent tool so both
    report identical structure. Raises ``sqlite3.Error`` on a bad database.
    """
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        tables: list[dict[str, Any]] = []
        cur = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        for row in cur.fetchall():
            table = row["name"]
            # PRAGMA does not accept bound params; the name comes from
            # sqlite_master (not user input), so quote it defensively.
            info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            columns = [
                {
                    "name": col["name"],
                    "type": col["type"],
                    "notnull": bool(col["notnull"]),
                    "pk": bool(col["pk"]),
                }
                for col in info
            ]
            tables.append({"name": table, "columns": columns})
        return tables
    finally:
        conn.close()


@router.get("/{owner}/{name}/db/schema", dependencies=[AuthDep])
async def skill_db_schema(owner: str, name: str) -> dict[str, Any]:
    """Return the skill database's tables and columns.

    Mini-apps (and the agent authoring them) should call this first so the UI is
    built against real column names instead of guessed ones — querying a column
    that does not exist is a common reason a mini-app silently renders nothing.
    """
    import sqlite3

    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)
    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    db_path = skill_dir / "data" / f"{name}.db"
    if not db_path.is_file():
        raise HTTPException(status_code=404, detail="No database found for this skill")

    try:
        tables = read_db_schema(db_path)
    except sqlite3.Error as e:
        raise HTTPException(status_code=400, detail=str(e)) from None
    return {"tables": tables, "count": len(tables)}


@router.get("/{owner}/{name}/files/{file_path:path}", dependencies=[AuthDep])
async def read_skill_file(owner: str, name: str, file_path: str) -> dict[str, Any]:
    """Read the content of a file inside a skill directory.

    For ``.env`` files, values are masked — only key names and whether
    each key has a value set are returned.
    """
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    path = _safe_relative(skill_dir, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # .env files: return structured key/is_set data, never raw secrets
    if file_path == ".env":
        entries = _parse_env(path)
        return {
            "path": file_path,
            "is_env": True,
            "entries": [{"key": k, "is_set": bool(v)} for k, v in entries],
            "size": path.stat().st_size,
        }

    try:
        content = path.read_text()
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="File is not a text file") from exc

    return {
        "path": file_path,
        "content": content,
        "size": path.stat().st_size,
    }


class FileUpdate(BaseModel):
    content: str | None = None
    entries: list[dict[str, Any]] | None = None


@router.put("/{owner}/{name}/files/{file_path:path}", dependencies=[AuthDep])
async def write_skill_file(
    owner: str,
    name: str,
    file_path: str,
    body: FileUpdate,
) -> dict[str, Any]:
    """Write or update a file inside a skill directory.

    For ``.env`` files, accepts ``entries`` (list of ``{key, value}`` dicts)
    instead of raw ``content``.  Values set to ``null`` preserve the existing
    secret.  Keys are validated and values are sanitized.
    """
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    path = _safe_relative(skill_dir, file_path)

    # .env files: structured write with validation and merge
    if file_path == ".env" and body.entries is not None:
        for entry in body.entries:
            key = entry.get("key", "").strip()
            if key and not _ENV_KEY_RE.match(key):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid key: {key!r}. Keys must be alphanumeric with underscores.",
                )

        existing = dict(_parse_env(path)) if path.is_file() else {}

        lines: list[str] = []
        for entry in body.entries:
            key = entry.get("key", "").strip()
            if not key:
                continue
            value = entry.get("value")
            if value is None:
                value = existing.get(key, "")
            else:
                value = re.sub(r"[\x00-\x1f\x7f]", "", value)
            lines.append(f"{key}={value}")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + ("\n" if lines else ""))

        return {"path": file_path, "size": path.stat().st_size, "status": "written"}

    # Block raw content writes to .env (must use entries)
    if file_path == ".env" and body.content is not None:
        raise HTTPException(
            status_code=400,
            detail="Use the entries field to update .env files",
        )

    if body.content is None:
        raise HTTPException(status_code=400, detail="content is required")

    # Validate SKILL.md before saving
    if file_path == "SKILL.md":
        from homeclaw.plugins.skills.loader import skill_md_to_definition

        try:
            skill_md_to_definition(body.content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid SKILL.md: {exc}") from exc

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
        raise HTTPException(
            status_code=400,
            detail="Cannot delete SKILL.md — use skill_remove instead",
        )

    path = _safe_relative(skill_dir, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    path.unlink()
    return {"status": "deleted", "path": file_path}


# ---------------------------------------------------------------------------
# Skill asset serving — for embedded mini-apps (Arrow.js etc.)
# ---------------------------------------------------------------------------

# Client-side error boundary auto-injected into every served HTML mini-app. A
# subtly-wrong Arrow app throws at mount and renders a *blank* page with the
# error buried in the console — so the agent (and user) get no signal. This
# script (a) renders any uncaught error or rejection as a visible banner so the
# app is never silently blank, and (b) POSTs it once to the skill's render-log
# so the agent can read what actually went wrong via ``skill_render_status``.
# It is a classic <script> injected into <head>, so it installs its handlers
# before the deferred ES-module mini-app runs and throws.
_RENDER_BOUNDARY_MARKER = "__homeclaw_render_boundary__"
_RENDER_BOUNDARY_JS = (
    "<script>/* " + _RENDER_BOUNDARY_MARKER + " */\n"
    "(function(){\n"
    "  function skill(){var m=location.pathname.match("
    "/\\/api\\/skills\\/([^/]+)\\/([^/]+)\\//);return m?{owner:m[1],name:m[2]}:null;}\n"
    "  function token(){try{var t=localStorage.getItem('homeclaw_token');"
    "if(t)return t;}catch(e){}"
    "return new URLSearchParams(location.search).get('token')||'';}\n"
    "  var reported=false;\n"
    "  function banner(msg){try{var id='__homeclaw_error_banner__';"
    "var el=document.getElementById(id);"
    "if(!el){el=document.createElement('div');el.id=id;"
    "el.style.cssText='position:fixed;top:0;left:0;right:0;z-index:2147483647;"
    "background:#7f1d1d;color:#fff;font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;"
    "padding:10px 14px;white-space:pre-wrap;box-shadow:0 2px 10px rgba(0,0,0,.35)';"
    "(document.body||document.documentElement).appendChild(el);}"
    "el.textContent='\\u26a0 Mini-app error: '+msg;}catch(e){}}\n"
    "  function report(msg,stack){banner(msg);if(reported)return;reported=true;"
    "var s=skill();if(!s)return;try{fetch('/api/skills/'+s.owner+'/'+s.name+'/_render_log',"
    "{method:'POST',headers:{'Content-Type':'application/json',"
    "'Authorization':'Bearer '+token()},"
    "body:JSON.stringify({message:String(msg),stack:String(stack||''),url:location.href})"
    "}).catch(function(){});}catch(e){}}\n"
    "  window.addEventListener('error',function(e){"
    "report((e&&e.message)||(e&&e.error&&e.error.message)||'Uncaught error',"
    "e&&e.error&&e.error.stack);});\n"
    "  window.addEventListener('unhandledrejection',function(e){var r=(e&&e.reason)||{};"
    "report(r.message||String(r),r.stack);});\n"
    "  window.__homeclawReportError=report;\n"
    "})();</script>\n"
)

_HEAD_OPEN_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
_BODY_OPEN_RE = re.compile(r"<body\b[^>]*>", re.IGNORECASE)


def _inject_render_boundary(html: str) -> str:
    """Insert the error-boundary <script> so it runs before the mini-app module.

    Idempotent: a page that already carries the marker is returned unchanged.
    Inserts just after ``<head>`` (or before ``<body>``, or at the top) so the
    classic boundary script executes ahead of the deferred ES module.
    """
    if _RENDER_BOUNDARY_MARKER in html:
        return html
    m = _HEAD_OPEN_RE.search(html)
    if m:
        return html[: m.end()] + "\n" + _RENDER_BOUNDARY_JS + html[m.end() :]
    m = _BODY_OPEN_RE.search(html)
    if m:
        return html[: m.start()] + _RENDER_BOUNDARY_JS + html[m.start() :]
    return _RENDER_BOUNDARY_JS + html


# Last-seen runtime render errors per (owner, name), reported by the boundary.
# In-memory and ephemeral: it exists so the agent can read what broke right
# after a user opens a freshly-written mini-app, not as a durable log.
_RENDER_LOG: dict[tuple[str, str], list[dict[str, Any]]] = {}
_RENDER_LOG_MAX = 10


def get_render_log(owner: str, name: str) -> list[dict[str, Any]]:
    """Return recent runtime render errors for a skill (newest last)."""
    return list(_RENDER_LOG.get((owner, name), []))


class RenderLogEntry(BaseModel):
    message: str
    stack: str | None = None
    url: str | None = None


@router.get(
    "/{owner}/{name}/assets/{file_path:path}",
    dependencies=[AuthDep],
    response_model=None,
)
async def serve_skill_asset(owner: str, name: str, file_path: str) -> FileResponse | HTMLResponse:
    """Serve a file from the skill's assets/ directory as a browser document.

    This endpoint is used to load embedded mini-apps (e.g. Arrow.js apps)
    declared via the ``ui-app`` SKILL.md frontmatter key. The browser
    navigates to this URL inside an iframe, so auth is accepted via the
    ``?token=`` query parameter in addition to the ``Authorization`` header.

    HTML documents get the error boundary injected so a mini-app that throws at
    mount shows the error instead of a blank page. Other files are served
    verbatim with correct MIME types. Path traversal is rejected.
    """
    workspaces = get_config().workspaces.resolve()
    skill_dir = _safe_relative(workspaces / owner / "skills", name)

    if not skill_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill not found")

    assets_dir = skill_dir / "assets"
    if not assets_dir.is_dir():
        raise HTTPException(status_code=404, detail="Skill has no assets directory")

    path = _safe_relative(assets_dir, file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Asset not found: {file_path}")

    media_type, _ = mimetypes.guess_type(str(path))
    if (media_type or "").startswith("text/html"):
        return HTMLResponse(_inject_render_boundary(path.read_text()))
    return FileResponse(path, media_type=media_type or "application/octet-stream")


@router.post("/{owner}/{name}/_render_log", dependencies=[AuthDep])
async def post_render_log(owner: str, name: str, body: RenderLogEntry) -> dict[str, str]:
    """Record a runtime error reported by a mini-app's error boundary."""
    key = (owner, name)
    entries = _RENDER_LOG.setdefault(key, [])
    entries.append(
        {
            "message": body.message,
            "stack": body.stack,
            "url": body.url,
            "logged_at": datetime.now(UTC).isoformat(),
        }
    )
    del entries[:-_RENDER_LOG_MAX]
    return {"status": "logged"}


@router.get("/{owner}/{name}/_render_log", dependencies=[AuthDep])
async def read_render_log(owner: str, name: str) -> dict[str, Any]:
    """Return recent runtime render errors for a skill's mini-app."""
    events = get_render_log(owner, name)
    return {"events": events, "count": len(events)}


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
        archived_at = datetime.strptime(ts_str, "%Y%m%d_%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None

    files = sorted(str(p.relative_to(archive_dir)) for p in archive_dir.rglob("*") if p.is_file())

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
