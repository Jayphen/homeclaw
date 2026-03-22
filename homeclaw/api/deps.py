"""Shared API dependencies — auth, config access, setup token."""

import logging
import secrets
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request

from homeclaw import HOUSEHOLD_WORKSPACE, PLUGINS_DIR
from homeclaw.config import HomeclawConfig

logger = logging.getLogger(__name__)

# Session tokens expire after 7 days.
_SESSION_TOKEN_TTL = timedelta(days=7)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plaintext password against a bcrypt hash.

    Also accepts legacy plaintext passwords (no ``$2`` prefix) so that
    existing config.json files keep working until the password is re-set.
    """
    if hashed.startswith("$2"):
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    # Legacy plaintext comparison — constant-time to avoid timing attacks.
    return secrets.compare_digest(plain, hashed)


# ---------------------------------------------------------------------------
# JWT session tokens
# ---------------------------------------------------------------------------

def _ensure_jwt_secret(config: HomeclawConfig) -> str:
    """Return the JWT signing secret, generating and persisting one if needed."""
    if config.jwt_secret:
        return config.jwt_secret
    config.jwt_secret = secrets.token_urlsafe(32)
    config.save()
    return config.jwt_secret


def create_session_token(
    member: str, *, is_admin: bool,
) -> dict[str, Any]:
    """Create a signed JWT session token.

    Returns ``{"token": "...", "expires_at": "...", "member": ..., "is_admin": ...}``.
    """
    config = get_config()
    secret = _ensure_jwt_secret(config)
    now = datetime.now(UTC)
    exp = now + _SESSION_TOKEN_TTL
    payload = {
        "sub": member,
        "adm": is_admin,
        "iat": now,
        "exp": exp,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {
        "token": token,
        "member": member,
        "is_admin": is_admin,
        "expires_at": exp.isoformat(),
    }


def _parse_jwt(token: str) -> tuple[str | None, bool] | None:
    """Validate a JWT and return (member, is_admin), or None if invalid."""
    config = get_config()
    if not config.jwt_secret:
        return None
    try:
        payload = jwt.decode(token, config.jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    sub = payload.get("sub")
    if not sub or sub == "__admin__":
        # Legacy admin-only token — treat as admin if no member specified.
        # New tokens always have a real member name.
        return None, True
    is_admin = sub in config.admin_members
    return sub, is_admin

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


_agent_loop: Any = None  # AgentLoop — set by serve entry points


def set_agent_loop(loop: Any) -> None:
    global _agent_loop
    _agent_loop = loop


def get_agent_loop() -> Any:
    return _agent_loop


_plugin_registry: Any = None  # PluginRegistry — avoided to prevent circular import


def set_plugin_registry(registry: Any) -> None:
    global _plugin_registry
    _plugin_registry = registry


def get_plugin_registry() -> Any:
    return _plugin_registry


_scheduler: Any = None  # Scheduler instance — set by main entry point


def set_scheduler(scheduler: Any) -> None:
    global _scheduler
    _scheduler = scheduler


def get_scheduler() -> Any:
    return _scheduler


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
        if d.is_dir()
        and d.name not in skip
        and not d.name.startswith(".")
        and not d.name.startswith("group-")
    )


def _parse_auth(request: Request) -> tuple[str | None, bool]:
    """Parse the Authorization header and return (member_name, is_admin).

    Token formats (tried in order):
    - ``Bearer <jwt>``              → decoded from signed session token
    - ``Bearer <web_password>``     → legacy admin (migration compat)
    - ``Bearer <member>:<password>``→ specific member (legacy / CLI)

    Returns (None, False) if auth is invalid.
    """
    config = get_config()
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None, False

    token = auth.removeprefix("Bearer ")

    # Try JWT first (tokens always start with "eyJ")
    if token.startswith("eyJ"):
        result = _parse_jwt(token)
        if result is not None:
            return result

    # Legacy admin auth: matches web_password — return first admin member
    if config.web_password and verify_password(token, config.web_password):
        first_admin = config.admin_members[0] if config.admin_members else None
        return first_admin, True

    # Member auth: "member:password"
    if ":" in token:
        member, password = token.split(":", 1)
        member = member.lower()
        expected = config.member_passwords.get(member)
        if expected is not None and verify_password(password, expected):
            return member, member in config.admin_members

    return None, False


async def require_auth(request: Request) -> None:
    config = get_config()
    # No passwords configured → open access
    if not config.web_password and not config.member_passwords:
        return
    member, _is_admin = _parse_auth(request)
    if member is None:
        raise HTTPException(status_code=401, detail="Unauthorized")


async def get_current_member(request: Request) -> str | None:
    """Return the authenticated member name, or None for open access.

    All authenticated users (including admins) get their member name.
    Admin privileges only grant access to settings, not other members' data.
    Raises 401 if passwords are configured but auth is invalid.
    """
    config = get_config()
    if not config.web_password and not config.member_passwords:
        return None
    member, _is_admin = _parse_auth(request)
    if member is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return member


async def require_admin(request: Request) -> None:
    """Require admin authentication (web_password). Members are rejected."""
    config = get_config()
    if not config.web_password and not config.member_passwords:
        return  # Open access
    _, is_admin = _parse_auth(request)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")


def validate_person(person: str, workspaces: Path) -> None:
    """Validate that *person* is a known member workspace.

    Prevents path traversal via crafted ``person`` URL parameters.
    """
    members = list_member_workspaces(workspaces)
    if person not in members:
        raise HTTPException(status_code=404, detail=f"Unknown member: {person}")


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
AdminDep = Depends(require_admin)
MemberDep = Depends(get_current_member)
