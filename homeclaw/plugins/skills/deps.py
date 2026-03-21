"""Skill dependency checker — verifies required bins and env vars."""

from __future__ import annotations

import os
import shutil
from typing import Any


def check_skill_deps(metadata: dict[str, Any]) -> dict[str, Any]:
    """Check skill dependencies from metadata.openclaw.requires.

    Returns a dict with:
    - missing_bins: list of required binaries not found on PATH
    - missing_env: list of required env vars not set
    - satisfied: True if all deps are met
    """
    openclaw = metadata.get("openclaw", {})
    if not isinstance(openclaw, dict):
        return {"missing_bins": [], "missing_env": [], "satisfied": True}

    requires = openclaw.get("requires", {})
    if not isinstance(requires, dict):
        return {"missing_bins": [], "missing_env": [], "satisfied": True}

    required_bins: list[str] = requires.get("bins", [])
    required_env: list[str] = requires.get("env", [])

    missing_bins = [b for b in required_bins if shutil.which(b) is None]
    missing_env = [e for e in required_env if not os.environ.get(e)]

    return {
        "missing_bins": missing_bins,
        "missing_env": missing_env,
        "satisfied": not missing_bins and not missing_env,
    }
