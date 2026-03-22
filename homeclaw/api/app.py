"""FastAPI application — serves REST API and static web UI."""

import os
from importlib.metadata import version as _pkg_version
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from homeclaw.api.deps import AuthDep as AuthDep  # noqa: F401
from homeclaw.api.deps import get_config as get_config  # noqa: F401
from homeclaw.api.deps import set_config as set_config  # noqa: F401
from homeclaw.api.routes.auth import router as auth_router
from homeclaw.api.routes.bookmarks import router as bookmarks_router
from homeclaw.api.routes.calendar import router as calendar_router
from homeclaw.api.routes.chat import router as chat_router
from homeclaw.api.routes.contacts import router as contacts_router
from homeclaw.api.routes.cost import router as cost_router
from homeclaw.api.routes.dashboard import router as dashboard_router
from homeclaw.api.routes.data import router as data_router
from homeclaw.api.routes.feed import router as feed_router
from homeclaw.api.routes.knowledge import router as knowledge_router
from homeclaw.api.routes.memory import router as memory_router
from homeclaw.api.routes.notes import router as notes_router
from homeclaw.api.routes.plugins import router as plugins_router
from homeclaw.api.routes.routines import router as routines_router
from homeclaw.api.routes.settings import router as settings_router
from homeclaw.api.routes.setup import router as setup_router
from homeclaw.api.routes.skills import router as skills_router

try:
    _version = _pkg_version("homeclaw")
except Exception:
    _version = "dev"

app = FastAPI(title="homeclaw", version=_version)
app.include_router(auth_router)
app.include_router(bookmarks_router)
app.include_router(chat_router)
app.include_router(plugins_router)
app.include_router(skills_router)
app.include_router(calendar_router)
app.include_router(contacts_router)
app.include_router(cost_router)
app.include_router(data_router)
app.include_router(feed_router)
app.include_router(knowledge_router)
app.include_router(dashboard_router)
app.include_router(memory_router)
app.include_router(notes_router)
app.include_router(routines_router)
app.include_router(settings_router)
app.include_router(setup_router)

# CORS: Set HOMECLAW_CORS_ORIGINS (comma-separated) to your domain(s).
# Defaults to same-origin only (no cross-origin requests allowed) for security.
# Set to "*" explicitly if you need open access (e.g. development).
_cors_origins_env = os.environ.get("HOMECLAW_CORS_ORIGINS", "")
_cors_origins = [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=_cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Mount static files for web UI if dist/ exists.
# In Docker the package is installed to site-packages, so __file__-relative
# resolution won't find ui/dist. HOMECLAW_UI_DIST overrides the path.
_ui_dist_env = os.environ.get("HOMECLAW_UI_DIST")
_ui_dist = Path(_ui_dist_env) if _ui_dist_env else Path(__file__).parent.parent.parent / "ui" / "dist"
if _ui_dist.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ui_dist / "assets")), name="assets")

    @app.get("/")
    async def serve_index() -> FileResponse:
        return FileResponse(str(_ui_dist / "index.html"))
