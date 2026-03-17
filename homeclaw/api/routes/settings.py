"""Settings API routes — system configuration and feature flags."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from homeclaw.api.deps import AuthDep, get_config

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _check_memsearch_available() -> bool:
    """Check if the memsearch package is importable."""
    try:
        import memsearch  # type: ignore[import-not-found]  # noqa: F401

        return True
    except ImportError:
        return False


@router.get("", dependencies=[AuthDep])
async def get_settings() -> dict[str, Any]:
    config = get_config()
    memsearch_installed = _check_memsearch_available()
    return {
        "enhanced_memory": config.enhanced_memory,
        "memsearch_installed": memsearch_installed,
        "semantic_ready": config.enhanced_memory and memsearch_installed,
    }


class UpdateSettingsBody(BaseModel):
    enhanced_memory: bool | None = None


@router.put("", dependencies=[AuthDep])
async def update_settings(body: UpdateSettingsBody) -> dict[str, Any]:
    config = get_config()
    if body.enhanced_memory is not None:
        config.enhanced_memory = body.enhanced_memory
    memsearch_installed = _check_memsearch_available()
    return {
        "enhanced_memory": config.enhanced_memory,
        "memsearch_installed": memsearch_installed,
        "semantic_ready": config.enhanced_memory and memsearch_installed,
    }
