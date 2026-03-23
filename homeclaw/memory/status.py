"""Canonical semantic memory status — single source of truth."""

from pathlib import Path
from typing import Literal

from homeclaw import SEMANTIC_INDEX_PATH

SemanticStatus = Literal["missing_memsearch", "indexing", "ready", "stale"]


def get_semantic_status(
    workspaces: Path,
    *,
    stale_seconds: float = 600,
) -> SemanticStatus:
    """Return the current semantic memory status.

    Checks whether the index exists and whether any workspace markdown
    files have been modified more recently than the index — if so, the
    index may be stale (the file watcher should catch up, but this
    surfaces the gap).
    """
    try:
        import memsearch  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return "missing_memsearch"
    index_path = workspaces / SEMANTIC_INDEX_PATH
    if not index_path.exists():
        return "indexing"
    # Check freshness: compare index mtime against newest workspace file.
    try:
        index_mtime = index_path.stat().st_mtime
        newest_md = max(
            (f.stat().st_mtime for f in workspaces.rglob("*.md") if not f.name.startswith(".")),
            default=0.0,
        )
        if newest_md > index_mtime + stale_seconds:
            return "stale"
    except OSError:
        pass
    return "ready"
