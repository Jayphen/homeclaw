"""Shared API dependencies — auth, config access, setup token."""

import logging
import secrets

from fastapi import Depends, HTTPException, Request

from homeclaw.config import HomeclawConfig

logger = logging.getLogger(__name__)

_config: HomeclawConfig | None = None
_setup_token: str | None = None


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


async def require_auth(request: Request) -> None:
    config = get_config()
    if not config.web_password:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.web_password}":
        raise HTTPException(status_code=401, detail="Unauthorized")


AuthDep = Depends(require_auth)
