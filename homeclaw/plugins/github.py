"""GitHub plugin repository downloader.

Downloads Python plugins from GitHub repos, reusing URL parsing from the
skills module.  Unlike skills (which only recurse known subdirectories),
plugins download all files recursively.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import httpx

from homeclaw.plugins.skills.github import parse_github_url

logger = logging.getLogger(__name__)

_SKIP_DIRS = {"__pycache__", ".git", ".github", "node_modules"}
_SKIP_PREFIXES = (".",)


def _should_skip(rel_path: str) -> bool:
    """Return True if a path should be excluded from download."""
    parts = rel_path.split("/")
    for p in parts:
        if p in _SKIP_DIRS:
            return True
        if any(p.startswith(pfx) for pfx in _SKIP_PREFIXES):
            return True
    return False


async def list_repo_plugins(url: str) -> list[dict[str, str]]:
    """Discover directories containing ``plugin.py`` in a GitHub repo.

    Uses the Git tree API (recursive) to find every ``plugin.py``.  Returns
    ``[{"path": "<dir>"}]`` — one per plugin found.  A root-level ``plugin.py``
    has ``path`` = ``""``.
    """
    info = parse_github_url(url)
    if info is None:
        return []

    user, repo, branch, subpath = info
    api_url = (
        f"https://api.github.com/repos/{user}/{repo}"
        f"/git/trees/{branch}?recursive=1"
    )

    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                logger.debug(
                    "GitHub tree API returned %d for %s", resp.status_code, api_url
                )
                return []
            tree = resp.json().get("tree", [])
    except Exception:
        logger.debug("Failed to list repo plugins for %s", url, exc_info=True)
        return []

    prefix = f"{subpath}/" if subpath else ""
    plugins: list[dict[str, str]] = []
    for item in tree:
        path: str = item.get("path", "")
        if item.get("type") != "blob":
            continue
        if not path.endswith("/plugin.py") and path != "plugin.py":
            continue
        if prefix and not path.startswith(prefix):
            continue
        rel = path[len(prefix) :]
        plugin_dir = rel.rsplit("/", 1)[0] if "/" in rel else ""
        plugins.append({"path": plugin_dir})

    return plugins


async def download_plugin_repo(url: str, plugin_dir: Path) -> list[str]:
    """Download all files from a GitHub plugin directory into *plugin_dir*.

    Unlike the skill downloader, this recurses into all subdirectories
    (not just known ones).  Uses the tree API for discovery and raw
    downloads for individual files.
    """
    info = parse_github_url(url)
    if info is None:
        return []

    user, repo, branch, subpath = info
    api_url = (
        f"https://api.github.com/repos/{user}/{repo}"
        f"/git/trees/{branch}?recursive=1"
    )

    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=60, transport=transport) as client:
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                logger.debug(
                    "GitHub tree API returned %d for %s", resp.status_code, api_url
                )
                return []

            tree = resp.json().get("tree", [])
            prefix = f"{subpath}/" if subpath else ""
            fetched: list[str] = []

            for item in tree:
                path: str = item.get("path", "")
                if item.get("type") != "blob":
                    continue
                if prefix and not path.startswith(prefix):
                    continue
                if not prefix and subpath == "" and path == path:
                    pass  # root — keep everything

                rel = path[len(prefix) :]
                if not rel or _should_skip(rel):
                    continue

                raw_url = (
                    f"https://raw.githubusercontent.com/"
                    f"{user}/{repo}/{branch}/{path}"
                )
                try:
                    file_resp = await client.get(raw_url)
                    if file_resp.status_code != 200:
                        continue
                except httpx.RequestError:
                    logger.debug("Failed to download %s", raw_url)
                    continue

                dest = plugin_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(file_resp.content)
                fetched.append(rel)

    except Exception:
        logger.debug("Failed to download plugin repo for %s", url, exc_info=True)
        return []

    return fetched


_ENV_PATTERN = re.compile(
    r"""os\.environ(?:\.get)?\s*\(\s*["']([A-Z][A-Z0-9_]+)["']"""
    r"""|os\.getenv\s*\(\s*["']([A-Z][A-Z0-9_]+)["']"""
    r"""|os\.environ\s*\[\s*["']([A-Z][A-Z0-9_]+)["']""",
)


def extract_env_hints(plugin_dir: Path) -> list[str]:
    """Scan Python files in *plugin_dir* for environment variable references.

    Returns a deduplicated list of variable names found via common patterns
    like ``os.environ.get("FOO")``, ``os.getenv("FOO")``, etc.
    """
    found: set[str] = set()
    for py_file in plugin_dir.glob("**/*.py"):
        try:
            text = py_file.read_text(errors="replace")
        except OSError:
            continue
        for match in _ENV_PATTERN.finditer(text):
            name = match.group(1) or match.group(2) or match.group(3)
            if name:
                found.add(name)
    return sorted(found)
