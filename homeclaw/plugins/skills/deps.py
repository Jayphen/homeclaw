"""Skill dependency checker — verifies required bins and env vars."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


def _is_docker() -> bool:
    """Detect if we're running inside a Docker container."""
    return (
        Path("/.dockerenv").exists()
        or os.environ.get("container") == "docker"
        or (
            Path("/proc/1/cgroup").exists()
            and "docker" in Path("/proc/1/cgroup").read_text(errors="ignore")
        )
    )


def _install_hint(binary: str, in_docker: bool) -> str:
    """Return a human-readable install hint for a missing binary."""
    if in_docker:
        return (
            f"Add '{binary}' to workspaces/household/packages.txt and restart "
            f"the container — it will be installed automatically on startup"
        )
    if shutil.which("brew"):
        return f"Run: brew install {binary}"
    return f"Install '{binary}' with your system package manager"


def check_skill_deps(
    metadata: dict[str, Any],
    skill_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Check skill dependencies from metadata.openclaw.requires.

    Args:
        metadata: The skill's metadata dict.
        skill_env: Env vars from the skill's .env file (checked alongside os.environ).

    Returns a dict with:
    - missing_bins: list of {name, hint} for required binaries not found on PATH
    - missing_env: list of required env vars not set
    - satisfied: True if all deps are met
    - runtime: "docker" or "host"
    """
    openclaw = metadata.get("openclaw", {})
    if not isinstance(openclaw, dict):
        return {"missing_bins": [], "missing_env": [], "satisfied": True, "runtime": "host"}

    requires = openclaw.get("requires", {})
    if not isinstance(requires, dict):
        return {"missing_bins": [], "missing_env": [], "satisfied": True, "runtime": "host"}

    required_bins: list[str] = requires.get("bins", [])
    required_env: list[str] = requires.get("env", [])
    env_lookup = skill_env or {}

    in_docker = _is_docker()
    runtime = "docker" if in_docker else "host"

    missing_bins = [
        {"name": b, "hint": _install_hint(b, in_docker)}
        for b in required_bins
        if shutil.which(b) is None
    ]
    missing_env = [e for e in required_env if not env_lookup.get(e) and not os.environ.get(e)]

    return {
        "missing_bins": missing_bins,
        "missing_env": missing_env,
        "satisfied": not missing_bins and not missing_env,
        "runtime": runtime,
    }
