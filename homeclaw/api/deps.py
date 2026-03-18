"""Shared API dependencies — auth, config access, setup token."""

import logging
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import Depends, HTTPException, Request

from homeclaw import HOUSEHOLD_WORKSPACE, PLUGINS_DIR
from homeclaw.config import HomeclawConfig

logger = logging.getLogger(__name__)

_config: HomeclawConfig | None = None
_setup_token: str | None = None
_on_telegram_configured: Callable[[str], Awaitable[None]] | None = None


def set_config(config: HomeclawConfig) -> None:
    global _config
    _config = config


def get_config() -> HomeclawConfig:
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


def generate_setup_token() -> str:
    """Generate and store a one-time setup token. Printed to logs on first boot."""
    global _setup_token
    _setup_token = secrets.token_urlsafe(32)
    logger.info(
        "\n"
        "╔══════════════════════════════════════════════════════╗\n"
        "║  homeclaw setup token (paste this in the web UI):   ║\n"
        "║                                                     ║\n"
        "║  %s  ║\n"
        "║                                                     ║\n"
        "╚══════════════════════════════════════════════════════╝",
        _setup_token[:43],
    )
    return _setup_token


def get_setup_token() -> str | None:
    return _setup_token


def clear_setup_token() -> None:
    """Invalidate the setup token after a password has been set."""
    global _setup_token
    _setup_token = None


def verify_setup_token(token: str) -> bool:
    return _setup_token is not None and secrets.compare_digest(token, _setup_token)


def set_on_telegram_configured(cb: Callable[[str], Awaitable[None]]) -> None:
    """Register a callback to start Telegram when a token is configured via setup."""
    global _on_telegram_configured
    _on_telegram_configured = cb


def get_on_telegram_configured() -> Callable[[str], Awaitable[None]] | None:
    return _on_telegram_configured


# Names to skip at any level during export/import (derived data, caches).
SKIP_EXPORT_NAMES = frozenset({
    ".index", "__pycache__", "config.json", "cost_log.jsonl",
})

# Additional top-level dirs that are not member workspaces.
_NON_MEMBER_DIRS = frozenset({HOUSEHOLD_WORKSPACE, PLUGINS_DIR})


def list_member_workspaces(workspaces: Path) -> list[str]:
    """List household member workspace directories.

    This is the single source of truth for enumerating members.
    """
    ws = workspaces if isinstance(workspaces, Path) else Path(workspaces)
    skip = SKIP_EXPORT_NAMES | _NON_MEMBER_DIRS
    if not ws.is_dir():
        return []
    return sorted(
        d.name
        for d in ws.iterdir()
        if d.is_dir() and d.name not in skip and not d.name.startswith(".")
    )


async def require_auth(request: Request) -> None:
    config = get_config()
    if not config.web_password:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.web_password}":
        raise HTTPException(status_code=401, detail="Unauthorized")


AuthDep = Depends(require_auth)
