"""Canonical semantic memory status — single source of truth."""

from pathlib import Path
from typing import Literal

from homeclaw import SEMANTIC_INDEX_PATH

SemanticStatus = Literal["missing_memsearch", "indexing", "ready"]


def get_semantic_status(workspaces: Path) -> SemanticStatus:
    """Return the current semantic memory status."""
    try:
        import memsearch  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return "missing_memsearch"
    if not (workspaces / SEMANTIC_INDEX_PATH).exists():
        return "indexing"
    return "ready"
