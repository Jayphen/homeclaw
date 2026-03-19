"""Shared API dependencies — auth, config access, setup token."""

import logging
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import Depends, HTTPException, Request

from homeclaw import HOUSEHOLD_WORKSPACE, PLUGINS_DIR
from homeclaw.config import HomeclawConfig

logger = logging.getLogger(__name__)

_config: HomeclawConfig | None = None
_setup_token: str | None = None
_on_telegram_configured: Callable[[str], Awaitable[None]] | None = None
_whatsapp_connected_fn: Callable[[], bool] | None = None


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


def set_whatsapp_connected_fn(fn: Callable[[], bool]) -> None:
    """Register a callback that returns whether WhatsApp is connected."""
    global _whatsapp_connected_fn
    _whatsapp_connected_fn = fn


def get_whatsapp_connected() -> bool:
    if _whatsapp_connected_fn is None:
        return False
    return _whatsapp_connected_fn()


_plugin_registry: Any = None  # PluginRegistry — avoided to prevent circular import


def set_plugin_registry(registry: Any) -> None:
    global _plugin_registry
    _plugin_registry = registry


def get_plugin_registry() -> Any:
    return _plugin_registry


_whatsapp_qr_fn: Callable[[], bytes | None] | None = None


def set_whatsapp_qr_fn(fn: Callable[[], bytes | None]) -> None:
    """Register a callback that returns pending QR data (or None)."""
    global _whatsapp_qr_fn
    _whatsapp_qr_fn = fn


def get_whatsapp_qr() -> bytes | None:
    if _whatsapp_qr_fn is None:
        return None
    return _whatsapp_qr_fn()


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


def _parse_auth(request: Request) -> tuple[str | None, bool]:
    """Parse the Authorization header and return (member_name, is_admin).

    Token formats:
    - ``Bearer <web_password>`` → admin (sees all data)
    - ``Bearer <member>:<password>`` → specific member

    Returns (None, False) if auth is invalid.
    """
    config = get_config()
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, False

    token = auth.removeprefix("Bearer ")

    # Admin auth: matches web_password directly
    if config.web_password and secrets.compare_digest(token, config.web_password):
        return None, True

    # Member auth: "member:password"
    if ":" in token:
        member, password = token.split(":", 1)
        expected = config.member_passwords.get(member)
        if expected is not None and secrets.compare_digest(password, expected):
            return member, False

    return None, False


async def require_auth(request: Request) -> None:
    config = get_config()
    # No password and no member passwords → open access
    if not config.web_password and not config.member_passwords:
        return
    member, is_admin = _parse_auth(request)
    if not is_admin and member is None:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def get_current_member(request: Request) -> str | None:
    """Return the authenticated member name, or None for admin/open access.

    Admin users get None — callers should treat this as "all members visible".
    Raises 401 if passwords are configured but auth is invalid.
    """
    config = get_config()
    if not config.web_password and not config.member_passwords:
        return None
    member, is_admin = _parse_auth(request)
    if not is_admin and member is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if is_admin:
        return None  # Admin sees everything
    return member


def require_person_access(member: str | None, person: str) -> None:
    """Raise 403 if *member* cannot access *person*'s data.

    Admins (member=None) can access everything.
    Members can only access their own workspace.
    """
    if member is not None and member != person:
        raise HTTPException(
            status_code=403,
            detail=f"Access denied to {person}'s data",
        )


def visible_members(member: str | None, all_members: list[str]) -> list[str]:
    """Return the members visible to the current user."""
    if member is None:
        return all_members
    return [member] if member in all_members else []


AuthDep = Depends(require_auth)
MemberDep = Depends(get_current_member)
