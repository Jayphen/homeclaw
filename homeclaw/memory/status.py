"""Canonical semantic memory status — single source of truth."""

from pathlib import Path
from typing import Literal

from homeclaw import SEMANTIC_INDEX_PATH

SemanticStatus = Literal["disabled", "missing_memsearch", "indexing", "ready"]


def get_semantic_status(enhanced_memory: bool, workspaces: Path) -> SemanticStatus:
    """Return the current semantic memory status.

    This is the single canonical check used by both the agent tools
    and the API routes.
    """
    if not enhanced_memory:
        return "disabled"
    try:
        import memsearch  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return "missing_memsearch"
    if not (workspaces / SEMANTIC_INDEX_PATH).exists():
        return "indexing"
    return "ready"
