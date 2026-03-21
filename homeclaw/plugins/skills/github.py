"""GitHub skill repository downloader."""

from __future__ import annotations

import logging
from pathlib import Path
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

# Known subdirectories to recurse into per the AgentSkills spec
_KNOWN_DIRS = {"scripts", "references", "assets", "data"}


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

    return user, repo, "main", ""


def raw_skill_md_url(url: str) -> str | None:
    """Convert a GitHub URL to a raw SKILL.md download URL."""
    info = parse_github_url(url)
    if info is None:
        return None
    user, repo, branch, subpath = info
    base = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}"
    if subpath:
        base += f"/{subpath}"
    return f"{base}/SKILL.md"


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
