"""Health check endpoint — unauthenticated, suitable for Docker HEALTHCHECK."""

import platform
import resource
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from homeclaw import SEMANTIC_INDEX_PATH
from homeclaw.api.deps import get_agent_loop, get_config, get_whatsapp_connected

router = APIRouter(prefix="/api", tags=["health"])

_start_time = time.monotonic()


@router.get("/health")
async def health() -> dict[str, Any]:
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # ru_maxrss is bytes on macOS, kilobytes on Linux
    divisor = 1024 * 1024 if platform.system() == "Darwin" else 1024
    rss_mb = round(usage.ru_maxrss / divisor, 1)

    # Semantic memory status + index size
    semantic: dict[str, Any] = {"enabled": False}
    loop = get_agent_loop()
    if loop is not None and hasattr(loop, "_semantic_memory"):
        sm = loop._semantic_memory
        if sm is not None:
            semantic["enabled"] = sm.enabled
    try:
        config = get_config()
        index_path = Path(str(config.workspaces)) / SEMANTIC_INDEX_PATH
        if index_path.exists():
            semantic["index_size_mb"] = round(
                index_path.stat().st_size / (1024 * 1024), 2
            )
    except RuntimeError:
        pass

    # Channel connectivity
    channels: dict[str, bool] = {}
    try:
        config = get_config()
        channels["telegram"] = config.telegram_token is not None
        channels["whatsapp"] = get_whatsapp_connected()
    except RuntimeError:
        pass

    return {
        "status": "ok",
        "uptime_seconds": round(time.monotonic() - _start_time),
        "process": {
            "rss_mb": rss_mb,
        },
        "semantic_memory": semantic,
        "channels": channels,
    }
