"""FastAPI application — serves REST API and static web UI."""

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from homeclaw.api.deps import AuthDep as AuthDep  # noqa: F401
from homeclaw.api.deps import get_config as get_config  # noqa: F401
from homeclaw.api.deps import set_config as set_config  # noqa: F401
from homeclaw.api.routes.calendar import router as calendar_router
from homeclaw.api.routes.contacts import router as contacts_router
from homeclaw.api.routes.cost import router as cost_router
from homeclaw.api.routes.dashboard import router as dashboard_router
from homeclaw.api.routes.memory import router as memory_router
from homeclaw.api.routes.notes import router as notes_router
from homeclaw.api.routes.settings import router as settings_router

app = FastAPI(title="homeclaw", version="0.1.0")
app.include_router(calendar_router)
app.include_router(contacts_router)
app.include_router(cost_router)
app.include_router(dashboard_router)
app.include_router(memory_router)
app.include_router(notes_router)
app.include_router(settings_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
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
