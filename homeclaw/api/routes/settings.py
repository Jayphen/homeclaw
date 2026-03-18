"""Settings API routes — system configuration."""

from typing import Any

from fastapi import APIRouter

from homeclaw.api.deps import AuthDep, get_config
from homeclaw.memory.status import get_semantic_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", dependencies=[AuthDep])
async def get_settings() -> dict[str, Any]:
    config = get_config()
    return {
        "semantic_status": get_semantic_status(config.workspaces.resolve()),
    }
