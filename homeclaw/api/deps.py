"""Shared API dependencies — auth, config access."""

from fastapi import Depends, HTTPException, Request

from homeclaw.config import HomeclawConfig

_config: HomeclawConfig | None = None


def set_config(config: HomeclawConfig) -> None:
    global _config
    _config = config


def get_config() -> HomeclawConfig:
    if _config is None:
        raise RuntimeError("Config not initialized")
    return _config


async def require_auth(request: Request) -> None:
    config = get_config()
    if not config.web_password:
        return
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {config.web_password}":
        raise HTTPException(status_code=401, detail="Unauthorized")


AuthDep = Depends(require_auth)
