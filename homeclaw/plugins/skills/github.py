"""GitHub skill repository downloader."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Known subdirectories to recurse into per the AgentSkills spec
_KNOWN_DIRS = {"scripts", "references", "assets", "data"}

# GitHub URL path segments that are actions, not repo subpaths
_GITHUB_ACTIONS = {
    "tree", "blob", "raw", "commit", "commits", "releases", "issues",
    "pull", "pulls", "actions", "settings", "wiki", "discussions",
    "projects", "security", "network", "compare", "tags", "archive",
}


def parse_github_url(url: str) -> tuple[str, str, str, str] | None:
    """Parse a GitHub URL into (user, repo, branch, subpath).

    Accepts:
    - https://github.com/user/repo
    - https://github.com/user/repo/tree/branch
    - https://raw.githubusercontent.com/user/repo/branch[/path]
    - https://raw.githubusercontent.com/user/repo/refs/heads/branch[/path]

    Returns None if not a recognized GitHub URL.
    """
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]

    if parsed.hostname == "raw.githubusercontent.com":
        if len(parts) < 3:
            return None
        user, repo = parts[0], parts[1]
        rest = "/".join(parts[2:])
        # Strip SKILL.md from the end
        for suffix in ("/SKILL.md", "/skill.md"):
            if rest.endswith(suffix):
                rest = rest[: -len(suffix)]
                break
        if rest.startswith("refs/heads/"):
            branch = rest.removeprefix("refs/heads/")
            return user, repo, branch, ""
        # Assume parts[2] is the branch
        return user, repo, parts[2], "/".join(parts[3:]) if len(parts) > 3 else ""

    if parsed.hostname not in ("github.com", "www.github.com"):
        return None

    if len(parts) < 2:
        return None

    user, repo = parts[0], parts[1]
    if len(parts) >= 4 and parts[2] == "tree":
        branch = parts[3]
        subpath = "/".join(parts[4:]) if len(parts) > 4 else ""
        return user, repo, branch, subpath

    # Extra path segments that aren't a known GitHub action → treat as subpath
    if len(parts) > 2 and parts[2] not in _GITHUB_ACTIONS:
        subpath = "/".join(parts[2:])
        return user, repo, "main", subpath

    return user, repo, "main", ""


def raw_skill_md_url(url: str) -> str | None:
    """Convert a GitHub repo URL to a raw SKILL.md download URL.

    Returns None for non-GitHub-repo URLs (gists, arbitrary URLs).
    Those should be fetched directly.
    """
    info = parse_github_url(url)
    if info is None:
        return None
    user, repo, branch, subpath = info
    base = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}"
    if subpath:
        base += f"/{subpath}"
    return f"{base}/SKILL.md"


def normalize_gist_url(url: str) -> str | None:
    """Convert a gist.github.com URL to a raw download URL.

    Returns None if not a gist URL.
    """
    parsed = urlparse(url)

    # Already raw
    if parsed.hostname == "gist.githubusercontent.com":
        return url

    if parsed.hostname != "gist.github.com":
        return None

    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) < 2:
        return None

    # gist.github.com/user/hash[/raw] → fetch raw via API-style URL
    user, gist_id = parts[0], parts[1]
    return f"https://gist.githubusercontent.com/{user}/{gist_id}/raw"


def skill_subpath_url(url: str, subpath: str) -> str:
    """Build a GitHub URL pointing at a specific subpath within a repo.

    Given ``https://github.com/user/repo`` and subpath ``cooking``, returns
    ``https://github.com/user/repo/tree/main/cooking``.  Works with any
    URL form that :func:`parse_github_url` understands.
    """
    info = parse_github_url(url)
    if info is None:
        raise ValueError(f"Not a recognised GitHub URL: {url}")
    user, repo, branch, base = info
    parts = [p for p in (base, subpath) if p]
    full_subpath = "/".join(parts)
    return f"https://github.com/{user}/{repo}/tree/{branch}/{full_subpath}"


async def list_repo_skills(url: str) -> list[dict[str, str]]:
    """Discover all SKILL.md files in a GitHub repo or subpath.

    Uses the Git tree API (recursive) to find every ``SKILL.md`` under the
    target path.  Returns a list of ``{"path": "<dir>", "name": "<from frontmatter>"}``
    dicts — one per skill found.  The root-level SKILL.md (if any) has
    ``path`` = ``""``.

    Returns an empty list for non-GitHub URLs or on API failure.
    """
    info = parse_github_url(url)
    if info is None:
        return []

    user, repo, branch, subpath = info

    # Use the recursive tree API — single request, no pagination needed
    api_url = f"https://api.github.com/repos/{user}/{repo}/git/trees/{branch}?recursive=1"
    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                api_url,
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                logger.debug("GitHub tree API returned %d for %s", resp.status_code, api_url)
                return []

            tree = resp.json().get("tree", [])
    except Exception:
        logger.debug("Failed to list repo skills for %s", url, exc_info=True)
        return []

    prefix = f"{subpath}/" if subpath else ""
    skills: list[dict[str, str]] = []
    for item in tree:
        path: str = item.get("path", "")
        if item.get("type") != "blob":
            continue
        if not path.endswith("/SKILL.md") and path != "SKILL.md":
            continue
        # Must be under the subpath prefix
        if prefix and not path.startswith(prefix):
            continue
        # Strip prefix to get the relative path
        rel = path[len(prefix):]
        # The skill dir is the parent of SKILL.md
        skill_subdir = rel.rsplit("/", 1)[0] if "/" in rel else ""
        skills.append({"path": skill_subdir})

    return skills


async def download_skill_repo(url: str, skill_dir: Path) -> list[str]:
    """Download all files from a GitHub skill repo into *skill_dir*.

    Assumes SKILL.md has already been written to skill_dir.
    Returns a list of additional files that were downloaded.
    """
    info = parse_github_url(url)
    if info is None:
        return []

    user, repo, branch, subpath = info
    contents_path = subpath if subpath else ""
    api_url = f"https://api.github.com/repos/{user}/{repo}/contents/{contents_path}"

    fetched: list[str] = []
    try:
        transport = httpx.AsyncHTTPTransport(retries=2)
        async with httpx.AsyncClient(timeout=30, transport=transport) as client:
            resp = await client.get(
                api_url,
                params={"ref": branch},
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                logger.debug("GitHub API returned %d for %s", resp.status_code, api_url)
                return fetched

            items = resp.json()
            if not isinstance(items, list):
                return fetched

            for item in items:
                name = item.get("name", "")
                item_type = item.get("type", "")
                download_url = item.get("download_url")

                if name in ("SKILL.md", "skill.md") or name.startswith("."):
                    continue

                if item_type == "file" and download_url:
                    file_resp = await client.get(download_url)
                    if file_resp.status_code == 200:
                        dest = skill_dir / name
                        dest.write_bytes(file_resp.content)
                        fetched.append(name)

                elif item_type == "dir" and name in _KNOWN_DIRS:
                    sub_api = item.get("url", "")
                    if not sub_api:
                        continue
                    sub_resp = await client.get(
                        sub_api,
                        params={"ref": branch},
                        headers={"Accept": "application/vnd.github.v3+json"},
                    )
                    if sub_resp.status_code != 200:
                        continue
                    sub_dir = skill_dir / name
                    sub_dir.mkdir(exist_ok=True)
                    for sub_item in sub_resp.json():
                        sub_name = sub_item.get("name", "")
                        sub_dl = sub_item.get("download_url")
                        if sub_item.get("type") == "file" and sub_dl:
                            sub_file_resp = await client.get(sub_dl)
                            if sub_file_resp.status_code == 200:
                                (sub_dir / sub_name).write_bytes(sub_file_resp.content)
                                fetched.append(f"{name}/{sub_name}")

    except Exception:
        logger.debug("Failed to download GitHub tree for %s", url, exc_info=True)

    return fetched
