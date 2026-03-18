"""Settings API routes — system configuration and feature flags."""

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from homeclaw.api.deps import AuthDep, get_config
from homeclaw.memory.status import get_semantic_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", dependencies=[AuthDep])
async def get_settings() -> dict[str, Any]:
    config = get_config()
    status = get_semantic_status(config.enhanced_memory, config.workspaces.resolve())
    return {
        "enhanced_memory": config.enhanced_memory,
        "semantic_status": status,
    }


class UpdateSettingsBody(BaseModel):
    enhanced_memory: bool | None = None


@router.put("", dependencies=[AuthDep])
async def update_settings(body: UpdateSettingsBody) -> dict[str, Any]:
    config = get_config()
    if body.enhanced_memory is not None:
        config.enhanced_memory = body.enhanced_memory
    await config.save_async()
    status = get_semantic_status(config.enhanced_memory, config.workspaces.resolve())
    return {
        "enhanced_memory": config.enhanced_memory,
        "semantic_status": status,
    }
